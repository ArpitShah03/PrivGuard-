import os
import json
import time
from typing import List, Dict, Any, Tuple, Optional
from evaluation.multimodal_dataset.schemas import DatasetSample
from evaluation.multimodal_dataset.generator import MultimodalDatasetGenerator
from detection.multimodal.schemas import MultimodalCandidateItem
from detection.multimodal.detector import LightweightMultimodalDetector
from detection.fusion.schemas import EvidenceRecord, EvidenceSource, FusionResult
from detection.fusion.fusion_engine import EvidenceFusionEngine
from detection.fusion.calibration import compute_ece_and_brier
from evaluation.metrics import compute_prf1, normalize_pii_type
from detection.regex_detector import detect_regex
from detection.enterprise_patterns import detect_enterprise_patterns
from detection.context_rules import detect_context
from detection.masked_detector import detect_masked_pii
from detection.ner_detector import detect_ner


def sample_to_candidate_items(sample: DatasetSample) -> List[MultimodalCandidateItem]:
    """Extract candidate items from dataset sample."""
    items = []
    for ann in sample.pii_annotations:
        items.append(MultimodalCandidateItem(
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
        ))

    if sample.is_hard_negative or not sample.pii_annotations:
        for b in sample.blocks:
            items.append(MultimodalCandidateItem(
                sample_id=sample.sample_id,
                block_id=b.block_id,
                text=b.text,
                bbox=b.bbox,
                page_or_slide=b.page_or_slide,
                source="native_text",
                modality=sample.document_modality
            ))

    return items


class Phase5CEvaluator:
    """
    Evaluator executing:
    1. Validation-split-only calibration model training.
    2. Test-split benchmark comparison (Phase 4 vs Phase 5B vs Phase 5C).
    3. 4-tier ablation study (Tier A, Tier B, Tier C, Tier D).
    4. Expected Calibration Error (ECE) and Brier score analysis.
    5. Hard cases empirical verification.
    """

    def __init__(
        self,
        config_path: str = "config/fusion_config.yaml",
        model_dir: str = "models/fusion",
        multimodal_dir: str = "models/multimodal"
    ):
        self.config_path = config_path
        self.model_dir = model_dir
        self.multimodal_dir = multimodal_dir
        self.generator = MultimodalDatasetGenerator(seed=42)
        self.fusion_engine = EvidenceFusionEngine(
            config_path=config_path,
            model_dir=model_dir,
            multimodal_dir=multimodal_dir
        )

    def extract_evidence_for_item(
        self,
        item: MultimodalCandidateItem,
        context_items: Optional[List[MultimodalCandidateItem]] = None,
        tier: str = "TIER_D"
    ) -> List[EvidenceRecord]:
        """Harvest evidence records from active detector sources according to tier."""
        evidence: List[EvidenceRecord] = []
        text = item.text or ""

        # 1. Deterministic Algorithmic & Enterprise patterns
        ent_hits = detect_enterprise_patterns(text)
        for h in ent_hits:
            is_algo = "ALGORITHMIC_VALIDATOR" in h["detection_method"] or "ENTROPY" in h["detection_method"]
            source = EvidenceSource.ALGORITHMIC.value if is_algo else EvidenceSource.REGEX.value
            evidence.append(EvidenceRecord(
                detector_source=source,
                entity_type=normalize_pii_type(h["pii_type"]),
                raw_score=h["confidence"],
                normalized_score=h["confidence"],
                evidence_strength="STRONG" if is_algo else "MODERATE",
                location=item.block_id,
                safe_metadata={"span_len": len(text)}
            ))

        # 2. Regex
        reg_hits = detect_regex(text)
        for h in reg_hits:
            is_algo = "ALGORITHMIC_VALIDATOR" in h["detection_method"]
            source = EvidenceSource.ALGORITHMIC.value if is_algo else EvidenceSource.REGEX.value
            evidence.append(EvidenceRecord(
                detector_source=source,
                entity_type=normalize_pii_type(h["pii_type"]),
                raw_score=h["confidence"],
                normalized_score=h["confidence"],
                evidence_strength="STRONG" if is_algo else "MODERATE",
                location=item.block_id
            ))

        # 3. spaCy NER
        spacy_hits = detect_ner(text)
        for h in spacy_hits:
            evidence.append(EvidenceRecord(
                detector_source=EvidenceSource.SPACY.value,
                entity_type=normalize_pii_type(h["pii_type"]),
                raw_score=h["confidence"],
                normalized_score=h["confidence"],
                evidence_strength="MODERATE",
                location=item.block_id
            ))

        # If tier is Tier A, stop here
        if tier == "TIER_A":
            return evidence

        # 4. Multimodal layout detector (Tier B, C, D)
        if self.fusion_engine.multimodal_detector and self.fusion_engine.multimodal_detector.is_loaded:
            mm_pred = self.fusion_engine.multimodal_detector.predict(item, context_items)
            if mm_pred is not None and mm_pred.score > 0.30:
                evidence.append(EvidenceRecord(
                    detector_source=EvidenceSource.MULTIMODAL.value,
                    entity_type=normalize_pii_type(mm_pred.pii_type),
                    raw_score=mm_pred.score,
                    normalized_score=mm_pred.score,
                    evidence_strength="STRONG" if mm_pred.score >= 0.85 else "MODERATE",
                    location=item.block_id,
                    safe_metadata={"is_ocr": item.is_ocr}
                ))

        if tier == "TIER_B":
            return evidence

        # 5. Context rules (Tier C, D)
        ctx_hits = detect_context(text)
        for h in ctx_hits:
            evidence.append(EvidenceRecord(
                detector_source=EvidenceSource.CONTEXT.value,
                entity_type=normalize_pii_type(h["pii_type"]),
                raw_score=h["confidence"],
                normalized_score=h["confidence"],
                evidence_strength="MODERATE",
                location=item.block_id
            ))

        if tier == "TIER_C":
            return evidence

        # 6. Masked PII (Tier D)
        masked_hits = detect_masked_pii(text)
        for h in masked_hits:
            evidence.append(EvidenceRecord(
                detector_source=EvidenceSource.MASKED_PII.value,
                entity_type=normalize_pii_type(h["pii_type"]),
                raw_score=h["confidence"],
                normalized_score=h["confidence"],
                evidence_strength="MODERATE",
                location=item.block_id
            ))

        # 7. Synthetic token immunity explicit detection
        if self.fusion_engine.resolver.check_token_immunity(text):
            evidence.append(EvidenceRecord(
                detector_source=EvidenceSource.ENTITY_RESOLUTION.value,
                entity_type="NONE",
                raw_score=0.0,
                normalized_score=0.0,
                evidence_strength="STRONG",
                location=item.block_id,
                safe_metadata={"is_token": True}
            ))

        return evidence

    def train_calibrator_on_validation(self) -> Dict[str, Any]:
        """
        Fit Platt scaling exclusively on the validation split.
        Strict security invariant: never fits on test split.
        """
        all_samples = self.generator.generate_dataset()
        val_samples = [s for s in all_samples if s.split == "validation"]

        raw_scores: List[float] = []
        labels: List[int] = []

        for s in val_samples:
            items = sample_to_candidate_items(s)
            gt_anns = {a.annotation_id: a for a in s.pii_annotations}

            for item in items:
                gt = gt_anns.get(item.block_id)
                evidence = self.extract_evidence_for_item(item, items, tier="TIER_D")
                outcome = self.fusion_engine.resolver.resolve_candidate(item.text, evidence)

                # Label 1 if GT exists and matches, 0 if no GT or hard negative
                if gt is not None:
                    label = 1
                else:
                    label = 0

                raw_scores.append(float(outcome.fused_confidence))
                labels.append(label)

        # Fit calibrator on validation split
        meta = self.fusion_engine.calibrator.fit(raw_scores, labels, split_name="validation")
        self.fusion_engine.calibrator.save(self.model_dir)
        return meta

    def evaluate_test_split(self) -> Dict[str, Any]:
        """
        Run comprehensive benchmark evaluation on the untouched Phase 5A test split.
        """
        all_samples = self.generator.generate_dataset()
        test_samples = [s for s in all_samples if s.split == "test"]

        # Ensure calibrator is loaded
        if not self.fusion_engine.calibrator.is_loaded:
            try:
                self.fusion_engine.calibrator.load(self.model_dir)
            except Exception:
                self.train_calibrator_on_validation()

        tp = 0
        fp = 0
        fn = 0
        tn = 0

        type_metrics: Dict[str, Dict[str, int]] = {}
        decisions_count: Dict[str, int] = {"DETECT": 0, "HUMAN_REVIEW": 0, "SUPPRESS": 0}
        agreements_count: Dict[str, int] = {}

        uncalibrated_scores: List[float] = []
        calibrated_scores: List[float] = []
        labels: List[int] = []

        hard_negative_tested = 0
        hard_negative_fp = 0

        for s in test_samples:
            items = sample_to_candidate_items(s)
            gt_anns = {a.annotation_id: a for a in s.pii_annotations}

            if s.is_hard_negative:
                hard_negative_tested += 1
                for item in items:
                    evidence = self.extract_evidence_for_item(item, items, tier="TIER_D")
                    res = self.fusion_engine.fuse_candidate(item.text, evidence)
                    decisions_count[res.decision] = decisions_count.get(res.decision, 0) + 1
                    agreements_count[res.detector_agreement] = agreements_count.get(res.detector_agreement, 0) + 1

                    uncalibrated_scores.append(res.fused_confidence)
                    calibrated_scores.append(res.calibrated_confidence)
                    labels.append(0)

                    if res.decision in ["DETECT", "HUMAN_REVIEW"] and res.pii_type != "NONE":
                        fp += 1
                        hard_negative_fp += 1
                    else:
                        tn += 1
                continue

            for item in items:
                gt = gt_anns.get(item.block_id)
                evidence = self.extract_evidence_for_item(item, items, tier="TIER_D")
                res = self.fusion_engine.fuse_candidate(item.text, evidence)

                decisions_count[res.decision] = decisions_count.get(res.decision, 0) + 1
                agreements_count[res.detector_agreement] = agreements_count.get(res.detector_agreement, 0) + 1

                label = 1 if gt is not None else 0
                uncalibrated_scores.append(res.fused_confidence)
                calibrated_scores.append(res.calibrated_confidence)
                labels.append(label)

                if gt is not None:
                    g_type = normalize_pii_type(gt.pii_type)
                    if g_type not in type_metrics:
                        type_metrics[g_type] = {"tp": 0, "fp": 0, "fn": 0}

                    pred_type = normalize_pii_type(res.pii_type)
                    is_detected = res.decision in ["DETECT", "HUMAN_REVIEW"] and pred_type != "NONE"

                    if is_detected and pred_type == g_type:
                        tp += 1
                        type_metrics[g_type]["tp"] += 1
                    elif is_detected:
                        # Misclassification
                        fp += 1
                        fn += 1
                        type_metrics[g_type]["fn"] += 1
                    else:
                        # Missed (suppressed)
                        fn += 1
                        type_metrics[g_type]["fn"] += 1
                else:
                    pred_type = normalize_pii_type(res.pii_type)
                    if res.decision in ["DETECT", "HUMAN_REVIEW"] and pred_type != "NONE":
                        fp += 1
                    else:
                        tn += 1

        overall = compute_prf1(tp, fp, fn)
        overall["tn"] = tn
        overall["hard_negative_fp_rate"] = round(hard_negative_fp / max(1, hard_negative_tested), 4)

        # Calibration metrics on test split
        uncalib_cal = compute_ece_and_brier(uncalibrated_scores, labels, n_bins=10)
        calib_cal = compute_ece_and_brier(calibrated_scores, labels, n_bins=10)

        per_type = {}
        for t, m in sorted(type_metrics.items()):
            per_type[t] = compute_prf1(m["tp"], m["fp"], m["fn"])

        return {
            "overall": overall,
            "calibration": {
                "uncalibrated_ece": uncalib_cal["ece"],
                "uncalibrated_brier": uncalib_cal["brier_score"],
                "calibrated_ece": calib_cal["ece"],
                "calibrated_brier": calib_cal["brier_score"],
                "ece_improvement_pct": round(
                    ((uncalib_cal["ece"] - calib_cal["ece"]) / max(1e-6, uncalib_cal["ece"])) * 100, 2
                ),
                "bins": calib_cal["bins"]
            },
            "decisions": decisions_count,
            "agreements": agreements_count,
            "per_type": per_type,
            "test_sample_count": len(test_samples)
        }

    def run_ablation_study(self) -> Dict[str, Any]:
        """
        Run 4-tier ablation study comparing feature/detector increments:
        - Tier A: Deterministic + spaCy NER (Phase 4 baseline)
        - Tier B: Deterministic + spaCy + Multimodal Layout
        - Tier C: Deterministic + spaCy + Context + Multimodal
        - Tier D: Full Phase 5C System (All Detectors + Platt Calibration)
        """
        all_samples = self.generator.generate_dataset()
        test_samples = [s for s in all_samples if s.split == "test"]

        tiers = ["TIER_A", "TIER_B", "TIER_C", "TIER_D"]
        tier_names = {
            "TIER_A": "Tier A: Det + spaCy (Phase 4)",
            "TIER_B": "Tier B: Det + spaCy + Multimodal",
            "TIER_C": "Tier C: Det + spaCy + Context + Multimodal",
            "TIER_D": "Tier D: Full Fusion + Platt Calibration (Phase 5C)"
        }
        results = {}

        for tier in tiers:
            tp = 0
            fp = 0
            fn = 0
            tn = 0
            scores = []
            labels = []

            for s in test_samples:
                items = sample_to_candidate_items(s)
                gt_anns = {a.annotation_id: a for a in s.pii_annotations}

                if s.is_hard_negative:
                    for item in items:
                        evidence = self.extract_evidence_for_item(item, items, tier=tier)
                        res = self.fusion_engine.fuse_candidate(item.text, evidence)
                        scores.append(res.calibrated_confidence if tier == "TIER_D" else res.fused_confidence)
                        labels.append(0)
                        if res.decision in ["DETECT", "HUMAN_REVIEW"] and res.pii_type != "NONE":
                            fp += 1
                        else:
                            tn += 1
                    continue

                for item in items:
                    gt = gt_anns.get(item.block_id)
                    evidence = self.extract_evidence_for_item(item, items, tier=tier)
                    res = self.fusion_engine.fuse_candidate(item.text, evidence)

                    eval_score = res.calibrated_confidence if tier == "TIER_D" else res.fused_confidence
                    scores.append(eval_score)
                    label = 1 if gt is not None else 0
                    labels.append(label)

                    if gt is not None:
                        g_type = normalize_pii_type(gt.pii_type)
                        pred_type = normalize_pii_type(res.pii_type)
                        is_detected = res.decision in ["DETECT", "HUMAN_REVIEW"] and pred_type != "NONE"
                        if is_detected and pred_type == g_type:
                            tp += 1
                        elif is_detected:
                            fp += 1
                            fn += 1
                        else:
                            fn += 1
                    else:
                        pred_type = normalize_pii_type(res.pii_type)
                        if res.decision in ["DETECT", "HUMAN_REVIEW"] and pred_type != "NONE":
                            fp += 1
                        else:
                            tn += 1

            prf = compute_prf1(tp, fp, fn)
            prf["tn"] = tn
            cal_metrics = compute_ece_and_brier(scores, labels, n_bins=10)
            prf["ece"] = cal_metrics["ece"]
            prf["brier_score"] = cal_metrics["brier_score"]
            results[tier] = {
                "name": tier_names[tier],
                "metrics": prf
            }

        return results
