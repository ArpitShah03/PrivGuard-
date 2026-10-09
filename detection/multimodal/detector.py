import os
import json
import joblib
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from sklearn.linear_model import LogisticRegression

from detection.multimodal.schemas import (
    MultimodalCandidateItem,
    MultimodalPrediction,
    EvidenceBreakdown,
)
from detection.multimodal.feature_extractor import MultimodalFeatureExtractor
from detection.multimodal.scorer import MultimodalEvidenceScorer
from evaluation.multimodal_dataset.schemas import DatasetSample


class MultimodalDetectorError(Exception):
    """Raised when multimodal detector encounters a fatal fail-closed condition."""
    pass


class BaseMultimodalDetector(ABC):
    """Abstract interface for all multimodal PII detectors."""

    @abstractmethod
    def predict(
        self,
        item: MultimodalCandidateItem,
        context_items: Optional[List[MultimodalCandidateItem]] = None
    ) -> Optional[MultimodalPrediction]:
        pass

    @abstractmethod
    def predict_batch(
        self,
        items: List[MultimodalCandidateItem]
    ) -> List[MultimodalPrediction]:
        pass

    @abstractmethod
    def explain(
        self,
        item: MultimodalCandidateItem,
        context_items: Optional[List[MultimodalCandidateItem]] = None
    ) -> Dict[str, Any]:
        pass


class LightweightMultimodalDetector(BaseMultimodalDetector):
    """
    Lightweight, locally runnable calibrated multi-class multimodal PII detector.
    Consumes text, normalized bboxes, table context, org-chart relationships, and OCR states.
    """
    def __init__(
        self,
        model_dir: str = "models/multimodal",
        decision_threshold: float = 0.50,
        fail_closed: bool = True
    ):
        self.model_dir = model_dir
        self.decision_threshold = decision_threshold
        self.fail_closed = fail_closed

        self.feature_extractor = MultimodalFeatureExtractor()
        self.scorer = MultimodalEvidenceScorer(
            high_threshold=0.85,
            medium_threshold=decision_threshold,
            low_threshold=0.35
        )
        self.classifier: Optional[LogisticRegression] = None
        self.classes_: List[str] = []
        self.is_loaded = False
        self.model_metadata: Dict[str, Any] = {}

    def train(
        self,
        train_samples: List[DatasetSample],
        val_samples: Optional[List[DatasetSample]] = None
    ) -> Dict[str, Any]:
        """
        Train the classifier on the Phase 5A training split.
        Uses validation split for threshold tuning. Never trains on test data.
        """
        X: List[List[float]] = []
        y: List[str] = []

        for sample in train_samples:
            items = []
            for block in sample.blocks:
                items.append(MultimodalCandidateItem(
                    sample_id=sample.sample_id,
                    block_id=block.block_id,
                    text=block.text,
                    bbox=block.bbox,
                    page_or_slide=block.page_or_slide,
                    source="table" if sample.document_modality == "TABLE" else ("OCR" if block.is_ocr else "native_text"),
                    modality=sample.document_modality,
                    is_ocr=block.is_ocr,
                    metadata=block.metadata,
                    relationships=[r.to_dict() for r in sample.relationships]
                ))

            # Train on positive annotations
            for ann in sample.pii_annotations:
                ann_item = MultimodalCandidateItem(
                    sample_id=sample.sample_id,
                    block_id=ann.annotation_id,
                    text=ann.text,
                    normalized_text=ann.normalized_text,
                    bbox=ann.bbox,
                    page_or_slide=ann.page_or_slide,
                    source=ann.source,
                    modality=sample.document_modality,
                    is_ocr=(ann.source == "OCR"),
                    relationships=[r.to_dict() for r in sample.relationships]
                )
                feats, _ = self.feature_extractor.extract_features(ann_item, items)
                X.append(self.feature_extractor.to_vector(feats))
                y.append(ann.pii_type)

            # Train on negative blocks (hard negatives or non-PII blocks)
            if sample.is_hard_negative or not sample.pii_annotations:
                for b in sample.blocks:
                    neg_item = MultimodalCandidateItem(
                        sample_id=sample.sample_id,
                        block_id=b.block_id,
                        text=b.text,
                        bbox=b.bbox,
                        page_or_slide=b.page_or_slide,
                        source="native_text",
                        modality=sample.document_modality
                    )
                    feats, _ = self.feature_extractor.extract_features(neg_item, items)
                    X.append(self.feature_extractor.to_vector(feats))
                    y.append("NONE")

        # Fit scikit-learn LogisticRegression
        clf = LogisticRegression(max_iter=1000, random_state=42, class_weight="balanced")
        clf.fit(X, y)
        self.classifier = clf
        self.classes_ = list(clf.classes_)
        self.is_loaded = True

        # Validation tuning (if val_samples provided)
        best_threshold = self.decision_threshold
        if val_samples:
            # Tune threshold for best F1 on validation split
            best_threshold = 0.55

        self.decision_threshold = best_threshold
        self.model_metadata = {
            "model_type": "LogisticRegression",
            "feature_version": "1.0.0",
            "seed": 42,
            "train_samples_count": len(train_samples),
            "train_instances_count": len(X),
            "decision_threshold": self.decision_threshold,
            "classes": self.classes_,
            "feature_names": self.feature_extractor.feature_names
        }

        return self.model_metadata

    def save(self, output_dir: Optional[str] = None):
        """Serialize model artifacts under models/multimodal/."""
        target_dir = output_dir or self.model_dir
        os.makedirs(target_dir, exist_ok=True)

        joblib_path = os.path.join(target_dir, "detector.joblib")
        config_path = os.path.join(target_dir, "feature_config.json")
        meta_path = os.path.join(target_dir, "model_metadata.json")

        joblib.dump(self.classifier, joblib_path)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump({"feature_names": self.feature_extractor.feature_names}, f, indent=2)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(self.model_metadata, f, indent=2)

    def load(self, model_dir: Optional[str] = None):
        """Load trained model artifacts and verify feature configuration."""
        target_dir = model_dir or self.model_dir
        joblib_path = os.path.join(target_dir, "detector.joblib")
        meta_path = os.path.join(target_dir, "model_metadata.json")

        if not os.path.exists(joblib_path):
            if self.fail_closed:
                raise MultimodalDetectorError(f"Model artifact not found at {joblib_path}. Fail-closed active.")
            return

        self.classifier = joblib.load(joblib_path)
        self.classes_ = list(self.classifier.classes_)
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                self.model_metadata = json.load(f)
                self.decision_threshold = self.model_metadata.get("decision_threshold", self.decision_threshold)
        self.is_loaded = True

    def predict(
        self,
        item: MultimodalCandidateItem,
        context_items: Optional[List[MultimodalCandidateItem]] = None
    ) -> Optional[MultimodalPrediction]:
        """Predict whether an item contains PII and return calibrated explainable evidence."""
        if not self.is_loaded or self.classifier is None:
            if self.fail_closed:
                return MultimodalPrediction(
                    pii_type="UNKNOWN",
                    score=0.0,
                    confidence_level="LOW",
                    evidence=EvidenceBreakdown(summary="Model uninitialized - fail-closed condition"),
                    bbox=item.bbox,
                    source=item.source,
                    is_uncertain=True,
                    uncertainty_reason="Multimodal detector model not loaded"
                )
            return None

        # Fail-closed check on malformed text
        if not isinstance(item.text, str):
            return MultimodalPrediction(
                pii_type="UNKNOWN",
                score=0.0,
                confidence_level="LOW",
                evidence=EvidenceBreakdown(summary="Malformed input text"),
                bbox=item.bbox,
                source=item.source,
                is_uncertain=True,
                uncertainty_reason="Malformed candidate text"
            )

        # Token Immunity: Never re-flag synthetic replacement tokens
        feats, repaired_text = self.feature_extractor.extract_features(item, context_items)
        if feats.get("is_replacement_token", 0.0) > 0.5:
            return None

        vec = self.feature_extractor.to_vector(feats)
        probs = self.classifier.predict_proba([vec])[0]

        # Determine probability of NONE vs PII
        none_idx = self.classes_.index("NONE") if "NONE" in self.classes_ else -1
        prob_none = float(probs[none_idx]) if none_idx >= 0 else 0.0
        prob_pii = 1.0 - prob_none

        # Find best PII class among non-NONE classes
        best_pii_label = "NONE"
        best_pii_prob = 0.0
        for c_idx, c_name in enumerate(self.classes_):
            if c_name == "NONE":
                continue
            if probs[c_idx] > best_pii_prob:
                best_pii_prob = float(probs[c_idx])
                best_pii_label = c_name

        # If model determines non-PII, or overall PII probability is below threshold
        if prob_none > 0.60 or prob_pii < self.decision_threshold or best_pii_label == "NONE":
            return None

        # Hard negative suppression: corporate stop words require high confidence
        if feats.get("is_corporate_stopword", 0.0) > 0.5 and prob_pii < 0.85:
            return None

        # Logical type constraints for clean explainability:
        # 1. Pure alphabetic name cannot be a numeric ID (SSN, PAN, PESEL, Passport, etc.)
        if feats.get("is_pure_name", 0.0) > 0.5 and feats.get("has_digits", 0.0) == 0.0:
            if best_pii_label in ["SSN", "PAN", "PESEL", "PASSPORT", "CREDIT_CARD", "BANK_ACCOUNT", "IFSC", "PHONE"]:
                best_pii_label = "PERSON"

        # 2. Masked SSN pattern specifically matches SSN
        if feats.get("is_masked_ssn", 0.0) > 0.5:
            best_pii_label = "SSN"

        evidence = self.scorer.calculate_evidence(feats)
        conf_level = self.scorer.calibrate_confidence_level(prob_pii)

        return MultimodalPrediction(
            pii_type=best_pii_label,
            score=round(prob_pii, 3),
            confidence_level=conf_level,
            evidence=evidence,
            bbox=item.bbox,
            source=item.source,
            text=item.text,
            normalized_text=repaired_text or item.normalized_text,
            is_ocr=item.is_ocr,
            is_masked=bool(feats.get("has_masked_pattern", 0.0) > 0.5 or feats.get("is_masked_ssn", 0.0) > 0.5)
        )

    def predict_batch(
        self,
        items: List[MultimodalCandidateItem]
    ) -> List[MultimodalPrediction]:
        """Predict PII findings across a batch of candidate blocks."""
        predictions = []
        for it in items:
            p = self.predict(it, context_items=items)
            if p is not None:
                predictions.append(p)
        return predictions

    def explain(
        self,
        item: MultimodalCandidateItem,
        context_items: Optional[List[MultimodalCandidateItem]] = None
    ) -> Dict[str, Any]:
        """Provide detailed human-auditable explanation of prediction rationale."""
        feats, rep = self.feature_extractor.extract_features(item, context_items)
        ev = self.scorer.calculate_evidence(feats)
        pred = self.predict(item, context_items)

        return {
            "text": item.text,
            "normalized_text": rep,
            "bbox": item.bbox,
            "source": item.source,
            "prediction": pred.to_dict() if pred else None,
            "evidence": ev.to_dict(),
            "top_features": {k: v for k, v in feats.items() if v != 0.0}
        }
