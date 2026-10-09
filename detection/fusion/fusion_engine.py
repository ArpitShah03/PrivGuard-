import os
import uuid
import yaml
from typing import List, Dict, Any, Optional, Tuple
from models.schemas import PIIFinding, DocumentBlock
from detection.fusion.schemas import EvidenceRecord, EvidenceSource, FusionResult
from detection.fusion.conflict_resolution import ConflictResolver, ResolutionOutcome
from detection.fusion.calibration import ConfidenceCalibrator
from detection.fusion.threshold_manager import ThresholdManager
from detection.multimodal.detector import LightweightMultimodalDetector
from detection.multimodal.schemas import MultimodalCandidateItem
from detection.multimodal.fusion import block_to_candidate_item


def check_is_block_uncertain(block: DocumentBlock) -> bool:
    """Check if block extraction was failed, unavailable, or marked uncertain."""
    if block.metadata and block.metadata.get("is_uncertain", False):
        return True
    bt = (block.block_type or "").upper()
    if bt.startswith("OCR_") or "UNAVAILABLE" in bt or "FAILED" in bt or "LOW_CONFIDENCE" in bt:
        return True
    text = (block.text or "").strip()
    if text.startswith("[OCR_UNAVAILABLE") or text.startswith("[IMAGE_OCR_UNAVAILABLE"):
        return True
    return False


def get_detector_strength(source: str, score: float, is_algo: bool = False) -> str:
    """Determine evidence strength category without revealing raw PII."""
    if is_algo or score >= 0.90:
        return "STRONG"
    elif score >= 0.65:
        return "MODERATE"
    return "WEAK"


class EvidenceFusionEngine:
    """
    Enterprise Evidence Fusion & Confidence Calibration Engine (Phase 5C).
    Combines deterministic validators, regex, spaCy NER, context rules,
    masked PII detectors, entity resolution, and multimodal layout predictions
    into a calibrated, explainable, and security-governed decision.
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
        self.config = self._load_config(config_path)

        self.resolver = ConflictResolver(self.config)
        self.calibrator = ConfidenceCalibrator(
            model_dir=model_dir,
            n_bins=self.config.get("calibration", {}).get("bins", 10),
            fail_closed=self.config.get("security_policy", {}).get("fail_closed_on_missing_model", True)
        )
        self.threshold_manager = ThresholdManager(self.config)

        # Attempt to load calibration model if exists
        try:
            self.calibrator.load(model_dir)
        except Exception:
            # Calibrator will operate in uncalibrated fail-closed fallback until trained
            pass

        # Attempt to load multimodal detector if exists
        self.multimodal_detector: Optional[LightweightMultimodalDetector] = None
        try:
            mm_detector = LightweightMultimodalDetector(model_dir=multimodal_dir)
            mm_detector.load(multimodal_dir)
            if mm_detector.is_loaded:
                self.multimodal_detector = mm_detector
        except Exception:
            self.multimodal_detector = None

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except Exception:
                pass
        return {
            "fusion": {"high_threshold": 0.70, "lower_threshold": 0.45},
            "calibration": {"method": "platt_scaling", "fit_on_split": "validation", "bins": 10},
            "weights": {
                "algorithmic": 1.00, "regex": 0.90, "multimodal": 0.85,
                "spacy": 0.75, "context": 0.80, "masked_pii": 0.80, "entity_resolution": 0.85
            },
            "security_policy": {
                "fail_closed_on_error": True,
                "fail_closed_on_missing_model": True,
                "deterministic_dominance": True,
                "extraction_uncertainty_priority": True,
                "token_immunity_enabled": True,
                "suppress_corporate_stopwords": True,
                "strict_synthetic_privacy": True
            }
        }

    def fuse_candidate(
        self,
        text: str,
        evidence_records: List[EvidenceRecord],
        is_block_uncertain: bool = False,
        uncertainty_reason: Optional[str] = None
    ) -> FusionResult:
        """
        Synthesize evidence records for a single candidate span.
        Applies:
        1. Conflict resolution and explainable weighted fusion.
        2. Platt scaling confidence calibration.
        3. Strict decision policy hierarchy.
        """
        # Step 1: Conflict Resolution & Weighted Evidence Combination
        outcome: ResolutionOutcome = self.resolver.resolve_candidate(
            text=text,
            evidence_records=evidence_records,
            is_block_uncertain=is_block_uncertain,
            uncertainty_context=uncertainty_reason
        )

        # Step 2: Confidence Calibration
        if outcome.is_deterministic_dominant:
            # Deterministic checksums carry near-certain empirical accuracy
            calibrated_conf = max(0.95, outcome.fused_confidence)
        elif outcome.is_suppressed:
            calibrated_conf = 0.0
        else:
            calibrated_conf = self.calibrator.calibrate(outcome.fused_confidence)

        # Step 3: Threshold Decision Policy Hierarchy
        effective_uncertainty = is_block_uncertain or outcome.is_uncertain
        effective_reason = outcome.uncertainty_reason or uncertainty_reason

        decision, final_uncertainty_reason = self.threshold_manager.determine_decision(
            calibrated_confidence=calibrated_conf,
            is_deterministic=outcome.is_deterministic_dominant,
            is_extraction_uncertain=effective_uncertainty,
            is_suppressed_by_rule=outcome.is_suppressed,
            uncertainty_reason=effective_reason
        )

        return FusionResult(
            finding_id=str(uuid.uuid4()),
            pii_type=outcome.pii_type,
            fused_confidence=outcome.fused_confidence,
            calibrated_confidence=calibrated_conf,
            decision=decision,
            detector_sources=outcome.detector_sources,
            detector_agreement=outcome.agreement_status,
            uncertainty_reason=final_uncertainty_reason,
            evidence_summary=outcome.evidence_summary,
            evidence_records=evidence_records,
            is_uncertain=effective_uncertainty
        )

    def fuse_document_blocks(
        self,
        blocks: List[DocumentBlock],
        existing_findings: List[PIIFinding]
    ) -> List[PIIFinding]:
        """
        Fuse multi-detector evidence across document blocks.
        Enriches findings with calibrated confidence, agreement classification,
        and fusion decision under strict security hierarchy.
        """
        if not blocks and not existing_findings:
            return []

        # Map findings by block_id / location
        block_uncertain_map = {b.location: check_is_block_uncertain(b) for b in blocks}

        # Step A: Collect multimodal predictions if detector is active
        multimodal_items = []
        if self.multimodal_detector and self.multimodal_detector.is_loaded:
            candidate_items = [block_to_candidate_item(b) for b in blocks]
            try:
                mm_preds = self.multimodal_detector.predict_batch(candidate_items)
                for p in mm_preds:
                    if p.text:
                        multimodal_items.append(p)
            except Exception:
                pass

        # Step B: Group existing findings and multimodal candidates by block & span
        # For existing findings, convert into evidence records
        enriched_findings: List[PIIFinding] = []

        for finding in existing_findings:
            is_uncertain = block_uncertain_map.get(finding.location, False)

            # Build EvidenceRecord list from detection_method and validation_details
            evidence_records: List[EvidenceRecord] = []
            methods = finding.detection_method or []

            has_algo = any("ALGO" in m.upper() or "ENTROPY" in m.upper() for m in methods)
            has_regex = any("REGEX" in m.upper() or "ENTERPRISE" in m.upper() for m in methods)
            has_ner = any("NER" in m.upper() or "SPACY" in m.upper() for m in methods)
            has_context = any("CONTEXT" in m.upper() for m in methods)
            has_masked = any("MASKED" in m.upper() for m in methods)
            has_entity_res = bool(finding.entity_id or finding.replacement_token)

            if has_algo:
                evidence_records.append(EvidenceRecord(
                    detector_source=EvidenceSource.ALGORITHMIC.value,
                    entity_type=finding.pii_type,
                    raw_score=finding.confidence,
                    normalized_score=finding.confidence,
                    evidence_strength="STRONG",
                    location=finding.location,
                    span_start=finding.start,
                    span_end=finding.end
                ))
            if has_regex:
                evidence_records.append(EvidenceRecord(
                    detector_source=EvidenceSource.REGEX.value,
                    entity_type=finding.pii_type,
                    raw_score=finding.confidence,
                    normalized_score=finding.confidence,
                    evidence_strength=get_detector_strength("REGEX", finding.confidence),
                    location=finding.location,
                    span_start=finding.start,
                    span_end=finding.end
                ))
            if has_ner:
                evidence_records.append(EvidenceRecord(
                    detector_source=EvidenceSource.SPACY.value,
                    entity_type=finding.pii_type,
                    raw_score=finding.confidence,
                    normalized_score=finding.confidence,
                    evidence_strength=get_detector_strength("SPACY", finding.confidence),
                    location=finding.location,
                    span_start=finding.start,
                    span_end=finding.end
                ))
            if has_context:
                evidence_records.append(EvidenceRecord(
                    detector_source=EvidenceSource.CONTEXT.value,
                    entity_type=finding.pii_type,
                    raw_score=finding.confidence,
                    normalized_score=finding.confidence,
                    evidence_strength=get_detector_strength("CONTEXT", finding.confidence),
                    location=finding.location,
                    span_start=finding.start,
                    span_end=finding.end
                ))
            if has_masked:
                evidence_records.append(EvidenceRecord(
                    detector_source=EvidenceSource.MASKED_PII.value,
                    entity_type=finding.pii_type,
                    raw_score=finding.confidence,
                    normalized_score=finding.confidence,
                    evidence_strength=get_detector_strength("MASKED_PII", finding.confidence),
                    location=finding.location,
                    span_start=finding.start,
                    span_end=finding.end
                ))
            if has_entity_res:
                evidence_records.append(EvidenceRecord(
                    detector_source=EvidenceSource.ENTITY_RESOLUTION.value,
                    entity_type=finding.pii_type,
                    raw_score=finding.confidence,
                    normalized_score=finding.confidence,
                    evidence_strength="STRONG" if finding.replacement_token else "MODERATE",
                    location=finding.location,
                    safe_metadata={"entity_id_present": bool(finding.entity_id)},
                    span_start=finding.start,
                    span_end=finding.end
                ))

            # Check if any multimodal prediction matches this finding
            for mm in multimodal_items:
                if (mm.text and finding.text and (mm.text in finding.text or finding.text in mm.text)):
                    evidence_records.append(EvidenceRecord(
                        detector_source=EvidenceSource.MULTIMODAL.value,
                        entity_type=mm.pii_type,
                        raw_score=mm.score,
                        normalized_score=mm.score,
                        evidence_strength=get_detector_strength("MULTIMODAL", mm.score),
                        location=finding.location,
                        span_start=finding.start,
                        span_end=finding.end
                    ))

            # Default fallback if no specific source mapped
            if not evidence_records:
                evidence_records.append(EvidenceRecord(
                    detector_source=EvidenceSource.REGEX.value,
                    entity_type=finding.pii_type,
                    raw_score=finding.confidence,
                    normalized_score=finding.confidence,
                    evidence_strength=get_detector_strength("UNKNOWN", finding.confidence),
                    location=finding.location,
                    span_start=finding.start,
                    span_end=finding.end
                ))

            # Synthesize through fusion engine
            res: FusionResult = self.fuse_candidate(
                text=finding.text,
                evidence_records=evidence_records,
                is_block_uncertain=is_uncertain,
                uncertainty_reason="Underlying block extraction was uncertain" if is_uncertain else None
            )

            # Filter out SUPPRESS decisions (unless extraction uncertainty exists)
            if res.decision == "SUPPRESS" and not is_uncertain:
                continue

            # Update finding with fused and calibrated fields
            finding.fusion_confidence = res.fused_confidence
            finding.calibrated_confidence = res.calibrated_confidence
            finding.detector_sources = res.detector_sources
            finding.detector_agreement = res.detector_agreement
            finding.fusion_decision = res.decision
            finding.uncertainty_reason = res.uncertainty_reason
            finding.evidence_summary = res.evidence_summary
            finding.confidence = res.calibrated_confidence if res.calibrated_confidence > 0 else finding.confidence

            # Ensure detection_method contains all active sources
            for s in res.detector_sources:
                if s not in finding.detection_method:
                    finding.detection_method.append(s)

            enriched_findings.append(finding)

        return enriched_findings


default_fusion_engine = EvidenceFusionEngine()
