import os
import json
import joblib
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from sklearn.linear_model import LogisticRegression


class CalibrationError(Exception):
    """Raised when confidence calibration fails under fail-closed security policy."""
    pass


def compute_ece_and_brier(
    confidences: List[float],
    ground_truth: List[int],
    n_bins: int = 10
) -> Dict[str, Any]:
    """
    Calculate Expected Calibration Error (ECE), Brier Score, and reliability bin stats.
    ECE = sum(|B_m| / N * |acc(B_m) - conf(B_m)|)
    Brier = (1/N) * sum((p_i - y_i)^2)
    """
    if not confidences or not ground_truth:
        return {
            "ece": 0.0,
            "brier_score": 0.0,
            "sample_count": 0,
            "bins": []
        }

    n = len(confidences)
    confs = np.array(confidences, dtype=float)
    labels = np.array(ground_truth, dtype=int)

    # Brier Score
    brier_score = float(np.mean((confs - labels) ** 2))

    # Bins for ECE
    bin_boundaries = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    bin_stats = []

    for i in range(n_bins):
        bin_lower = bin_boundaries[i]
        bin_upper = bin_boundaries[i + 1]

        if i == n_bins - 1:
            in_bin = (confs >= bin_lower) & (confs <= bin_upper)
        else:
            in_bin = (confs >= bin_lower) & (confs < bin_upper)

        bin_count = int(np.sum(in_bin))

        if bin_count > 0:
            bin_acc = float(np.mean(labels[in_bin]))
            bin_conf = float(np.mean(confs[in_bin]))
            bin_diff = abs(bin_acc - bin_conf)
            ece += (bin_count / n) * bin_diff
            bin_stats.append({
                "bin_idx": i,
                "range": [round(bin_lower, 2), round(bin_upper, 2)],
                "count": bin_count,
                "accuracy": round(bin_acc, 4),
                "confidence": round(bin_conf, 4),
                "diff": round(bin_diff, 4)
            })
        else:
            bin_stats.append({
                "bin_idx": i,
                "range": [round(bin_lower, 2), round(bin_upper, 2)],
                "count": 0,
                "accuracy": 0.0,
                "confidence": 0.0,
                "diff": 0.0
            })

    return {
        "ece": round(float(ece), 4),
        "brier_score": round(float(brier_score), 4),
        "sample_count": n,
        "bins": bin_stats
    }


class ConfidenceCalibrator:
    """
    Platt Scaling Calibrator.
    Maps uncalibrated heuristic/model confidence scores to true empirical probabilities.
    STRICT POLICY: Fitted exclusively on validation split; never on test split.
    """

    def __init__(
        self,
        model_dir: str = "models/fusion",
        n_bins: int = 10,
        fail_closed: bool = True
    ):
        self.model_dir = model_dir
        self.n_bins = n_bins
        self.fail_closed = fail_closed
        self.calibrator: Optional[LogisticRegression] = None
        self.is_loaded = False
        self.metadata: Dict[str, Any] = {}

    def fit(
        self,
        raw_scores: List[float],
        labels: List[int],
        split_name: str = "validation"
    ) -> Dict[str, Any]:
        """
        Fit 1D Platt scaling (logistic regression) on validation pairs (raw_score, label).
        """
        if split_name != "validation":
            raise ValueError(f"Security invariant violated: Calibration must fit on validation split, not '{split_name}'.")

        if len(raw_scores) < 4:
            raise CalibrationError("Insufficient validation samples to fit calibration model.")

        X = np.array(raw_scores).reshape(-1, 1)
        y = np.array(labels, dtype=int)

        # Check class balance
        if len(np.unique(y)) < 2:
            # Degenerate case fallback
            y_augmented = np.concatenate([y, [0, 1]])
            X_augmented = np.concatenate([X, [[0.1], [0.9]]])
        else:
            X_augmented = X
            y_augmented = y

        clf = LogisticRegression(C=1.0, solver="lbfgs")
        clf.fit(X_augmented, y_augmented)
        self.calibrator = clf

        # Evaluate calibration improvements
        uncalib_metrics = compute_ece_and_brier(raw_scores, labels, self.n_bins)
        calibrated_scores = [self.calibrate(s) for s in raw_scores]
        calib_metrics = compute_ece_and_brier(calibrated_scores, labels, self.n_bins)

        coef_a = float(clf.coef_[0][0])
        intercept_b = float(clf.intercept_[0])

        self.metadata = {
            "method": "platt_scaling",
            "fit_split": split_name,
            "sample_count": len(raw_scores),
            "coef_A": round(coef_a, 4),
            "intercept_B": round(intercept_b, 4),
            "uncalibrated_ece": uncalib_metrics["ece"],
            "uncalibrated_brier": uncalib_metrics["brier_score"],
            "calibrated_ece": calib_metrics["ece"],
            "calibrated_brier": calib_metrics["brier_score"],
            "ece_reduction_pct": round(
                ((uncalib_metrics["ece"] - calib_metrics["ece"]) / max(1e-6, uncalib_metrics["ece"])) * 100, 2
            ),
            "bins": calib_metrics["bins"]
        }
        self.is_loaded = True
        return self.metadata

    def calibrate(self, raw_score: float) -> float:
        """
        Calibrate an uncalibrated score into a well-calibrated confidence probability.
        """
        if not self.is_loaded or self.calibrator is None:
            if self.fail_closed:
                # Under fail-closed security, uncalibrated score is preserved but flagged
                return round(float(raw_score), 3)
            return round(float(raw_score), 3)

        s_clamped = max(0.0, min(1.0, float(raw_score)))
        prob = self.calibrator.predict_proba([[s_clamped]])[0][1]
        return round(float(prob), 3)

    def save(self, model_dir: Optional[str] = None) -> str:
        """Persist calibrator and metadata to disk."""
        target_dir = model_dir or self.model_dir
        os.makedirs(target_dir, exist_ok=True)

        joblib_path = os.path.join(target_dir, "platt_calibrator.joblib")
        meta_path = os.path.join(target_dir, "calibration_metadata.json")

        if self.calibrator is not None:
            joblib.dump(self.calibrator, joblib_path)

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, indent=2)

        return target_dir

    def load(self, model_dir: Optional[str] = None) -> None:
        """Load calibrator artifact and metadata from disk."""
        target_dir = model_dir or self.model_dir
        joblib_path = os.path.join(target_dir, "platt_calibrator.joblib")
        meta_path = os.path.join(target_dir, "calibration_metadata.json")

        if not os.path.exists(joblib_path) or not os.path.exists(meta_path):
            if self.fail_closed:
                raise CalibrationError(f"Calibration model missing in {target_dir}. Fail-closed triggered.")
            return

        self.calibrator = joblib.load(joblib_path)
        with open(meta_path, "r", encoding="utf-8") as f:
            self.metadata = json.load(f)
        self.is_loaded = True
