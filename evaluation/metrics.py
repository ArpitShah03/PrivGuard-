from typing import List, Dict, Any, Tuple, Optional


def normalize_pii_type(t: str) -> str:
    """Normalize equivalent type names for fair ground-truth evaluation."""
    u = t.upper().strip()
    if u in ["DOB", "DATE_OF_BIRTH", "BIRTH_DATE"]:
        return "DATE_OF_BIRTH"
    if u in ["SECRET", "API_KEY", "ACCESS_TOKEN", "AUTH_TOKEN"]:
        return "SECRET"
    if u in ["CC", "CREDIT_CARD"]:
        return "CREDIT_CARD"
    if u in ["EMPID", "EMPLOYEE_ID"]:
        return "EMPLOYEE_ID"
    if u in ["DIN", "DIRECTOR_ID"]:
        return "DIRECTOR_ID"
    if u in ["VENDID", "VENDOR_ID"]:
        return "VENDOR_ID"
    if u in ["CUSTID", "CUSTOMER_ID"]:
        return "CUSTOMER_ID"
    if u in ["MID", "MERCHANT_ID"]:
        return "MERCHANT_ID"
    if u in ["ACCT", "BANK_ACCOUNT", "ACCOUNT_NUMBER"]:
        return "BANK_ACCOUNT"
    return u


def compute_prf1(tp: int, fp: int, fn: int) -> Dict[str, float]:
    """Calculate Precision, Recall, and F1 with division by zero safeguards."""
    precision = (tp / (tp + fp)) if (tp + fp) > 0 else (1.0 if fn == 0 else 0.0)
    recall = (tp / (tp + fn)) if (tp + fn) > 0 else (1.0 if fp == 0 else 0.0)
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4)
    }


def match_entities(
    ground_truth: List[Dict[str, Any]],
    predictions: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Match predicted findings against ground-truth entities.
    Returns:
    - true_positives: list of matched pairs
    - false_positives: list of predictions with no ground-truth match
    - false_negatives: list of ground-truth entities that were missed
    """
    matched_gt_indices = set()
    matched_pred_indices = set()
    true_positives = []

    # 1. Greedy match by normalized type and (span overlap or exact text)
    for p_idx, pred in enumerate(predictions):
        p_type = normalize_pii_type(pred.get("pii_type") or pred.get("type", ""))
        p_text = str(pred.get("text", "")).strip().lower()
        p_start = pred.get("start", -1)
        p_end = pred.get("end", -1)

        best_gt_idx = None
        for g_idx, gt in enumerate(ground_truth):
            if g_idx in matched_gt_indices:
                continue

            g_type = normalize_pii_type(gt.get("type") or gt.get("pii_type", ""))
            if p_type != g_type:
                continue

            g_text = str(gt.get("text", "")).strip().lower()
            g_start = gt.get("start", -1)
            g_end = gt.get("end", -1)

            # Check matching condition: exact text or overlapping span
            text_match = (p_text == g_text) or (p_text in g_text) or (g_text in p_text)
            span_overlap = False
            if p_start >= 0 and p_end > p_start and g_start >= 0 and g_end > g_start:
                overlap_len = max(0, min(p_end, g_end) - max(p_start, g_start))
                span_overlap = overlap_len > 0

            if text_match or span_overlap:
                best_gt_idx = g_idx
                break

        if best_gt_idx is not None:
            matched_gt_indices.add(best_gt_idx)
            matched_pred_indices.add(p_idx)
            true_positives.append({
                "ground_truth": ground_truth[best_gt_idx],
                "prediction": pred
            })

    # Unmatched predictions are False Positives
    false_positives = [
        pred for p_idx, pred in enumerate(predictions)
        if p_idx not in matched_pred_indices
    ]

    # Unmatched ground-truth entities are False Negatives
    false_negatives = [
        gt for g_idx, gt in enumerate(ground_truth)
        if g_idx not in matched_gt_indices
    ]

    return true_positives, false_positives, false_negatives


class EvaluationMetricsAccumulator:
    """
    Accumulator for calculating overall, per-type, and per-category empirical metrics.
    """
    def __init__(self):
        self.tp_by_type: Dict[str, int] = {}
        self.fp_by_type: Dict[str, int] = {}
        self.fn_by_type: Dict[str, int] = {}
        self.tp_by_category: Dict[str, int] = {}
        self.fp_by_category: Dict[str, int] = {}
        self.fn_by_category: Dict[str, int] = {}

    def add_result(
        self,
        ground_truth: List[Dict[str, Any]],
        predictions: List[Dict[str, Any]],
        category: str = "general"
    ):
        tps, fps, fns = match_entities(ground_truth, predictions)

        # Update per-type metrics
        for tp_pair in tps:
            t = normalize_pii_type(tp_pair["ground_truth"]["type"])
            self.tp_by_type[t] = self.tp_by_type.get(t, 0) + 1
            self.tp_by_category[category] = self.tp_by_category.get(category, 0) + 1

        for fp in fps:
            t = normalize_pii_type(fp.get("pii_type") or fp.get("type", "UNKNOWN"))
            self.fp_by_type[t] = self.fp_by_type.get(t, 0) + 1
            self.fp_by_category[category] = self.fp_by_category.get(category, 0) + 1

        for fn in fns:
            t = normalize_pii_type(fn.get("type") or fn.get("pii_type", "UNKNOWN"))
            self.fn_by_type[t] = self.fn_by_type.get(t, 0) + 1
            self.fn_by_category[category] = self.fn_by_category.get(category, 0) + 1

    def compute_summary(self) -> Dict[str, Any]:
        """Compute comprehensive PRF1 metrics overall, per entity type, and per category."""
        all_types = sorted(set(list(self.tp_by_type.keys()) + list(self.fp_by_type.keys()) + list(self.fn_by_type.keys())))
        
        per_type_metrics = {}
        total_tp = sum(self.tp_by_type.values())
        total_fp = sum(self.fp_by_type.values())
        total_fn = sum(self.fn_by_type.values())

        for t in all_types:
            tp = self.tp_by_type.get(t, 0)
            fp = self.fp_by_type.get(t, 0)
            fn = self.fn_by_type.get(t, 0)
            per_type_metrics[t] = compute_prf1(tp, fp, fn)

        overall_metrics = compute_prf1(total_tp, total_fp, total_fn)

        per_category_metrics = {}
        for cat in sorted(set(list(self.tp_by_category.keys()) + list(self.fp_by_category.keys()) + list(self.fn_by_category.keys()))):
            c_tp = self.tp_by_category.get(cat, 0)
            c_fp = self.fp_by_category.get(cat, 0)
            c_fn = self.fn_by_category.get(cat, 0)
            per_category_metrics[cat] = compute_prf1(c_tp, c_fp, c_fn)

        return {
            "overall": overall_metrics,
            "per_type": per_type_metrics,
            "per_category": per_category_metrics,
            "total_ground_truth_entities": total_tp + total_fn,
            "total_predicted_findings": total_tp + total_fp
        }
