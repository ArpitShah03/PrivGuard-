import pytest
import os
import shutil
from models.schemas import DocumentBlock, PIIFinding
from detection.fusion.schemas import EvidenceRecord, EvidenceSource, FusionResult
from detection.fusion.conflict_resolution import ConflictResolver
from detection.fusion.calibration import ConfidenceCalibrator, compute_ece_and_brier
from detection.fusion.threshold_manager import ThresholdManager
from detection.fusion.fusion_engine import EvidenceFusionEngine
from detection.pii_engine import detect_pii_with_fusion, detect_pii_in_document_blocks


def test_extraction_uncertainty_priority_routes_to_human_review():
    """
    CRITICAL SECURITY INVARIANT:
    Extraction uncertainty must ALWAYS route to HUMAN_REVIEW.
    SUPPRESS must NEVER override extraction uncertainty even if score is 0.0.
    """
    tm = ThresholdManager({"fusion": {"high_threshold": 0.70, "lower_threshold": 0.45}})
    # Low confidence (0.10), but block has extraction uncertainty
    decision, reason = tm.determine_decision(
        calibrated_confidence=0.10,
        is_deterministic=False,
        is_extraction_uncertain=True,
        is_suppressed_by_rule=False
    )
    assert decision == "HUMAN_REVIEW"
    assert reason is not None
    assert "uncertainty" in reason.lower()


def test_deterministic_dominance_overrides_probabilistic_ml():
    """
    Deterministic dominance: Valid algorithmic checksum (Luhn, PESEL, etc.)
    strictly dominates probabilistic ML disagreement.
    """
    resolver = ConflictResolver()
    evidence = [
        EvidenceRecord(
            detector_source=EvidenceSource.ALGORITHMIC.value,
            entity_type="CREDIT_CARD",
            raw_score=0.99,
            normalized_score=0.99,
            evidence_strength="STRONG",
            location="block_1"
        ),
        EvidenceRecord(
            detector_source=EvidenceSource.MULTIMODAL.value,
            entity_type="NONE",
            raw_score=0.20,
            normalized_score=0.20,
            evidence_strength="WEAK",
            location="block_1"
        )
    ]
    outcome = resolver.resolve_candidate("4532015012345678", evidence)
    assert outcome.pii_type == "CREDIT_CARD"
    assert outcome.is_deterministic_dominant is True
    assert outcome.agreement_status == "DETERMINISTIC_OVERRIDE"
    assert outcome.fused_confidence >= 0.95


def test_explainable_weighted_fusion_and_synergy():
    """
    Multi-detector concurrence boosts confidence via explainable agreement synergy.
    """
    resolver = ConflictResolver()
    evidence = [
        EvidenceRecord(
            detector_source=EvidenceSource.SPACY.value,
            entity_type="PERSON",
            raw_score=0.80,
            normalized_score=0.80,
            evidence_strength="MODERATE",
            location="block_1"
        ),
        EvidenceRecord(
            detector_source=EvidenceSource.MULTIMODAL.value,
            entity_type="PERSON",
            raw_score=0.85,
            normalized_score=0.85,
            evidence_strength="STRONG",
            location="block_1"
        )
    ]
    outcome = resolver.resolve_candidate("Tobias Lindqvist", evidence)
    assert outcome.pii_type == "PERSON"
    assert outcome.agreement_status == "UNANIMOUS"
    # Weighted base is ~0.826, bonus of 0.04 brings score > 0.85
    assert outcome.fused_confidence > 0.85
    assert "SPACY" in outcome.detector_sources
    assert "MULTIMODAL" in outcome.detector_sources


def test_token_immunity_protection():
    """
    Synthetic replacement tokens (e.g. [PERSON_001]) must NEVER be re-flagged.
    """
    resolver = ConflictResolver()
    evidence = [
        EvidenceRecord(
            detector_source=EvidenceSource.SPACY.value,
            entity_type="PERSON",
            raw_score=0.90,
            normalized_score=0.90,
            evidence_strength="STRONG",
            location="block_1"
        )
    ]
    outcome = resolver.resolve_candidate("[PERSON_001]", evidence)
    assert outcome.is_suppressed is True
    assert "Token immunity" in outcome.suppression_reason
    assert outcome.fused_confidence == 0.0


def test_token_immunity_under_extraction_uncertainty():
    """
    If a replacement token is encountered in an extraction-uncertain block,
    the extraction uncertainty MUST still mandate HUMAN_REVIEW.
    """
    tm = ThresholdManager()
    decision, reason = tm.determine_decision(
        calibrated_confidence=0.0,
        is_deterministic=False,
        is_extraction_uncertain=True,
        is_suppressed_by_rule=True
    )
    assert decision == "HUMAN_REVIEW"


def test_corporate_stopword_suppression():
    """
    Corporate organizational terms flagged as PERSON by isolated weak NER are suppressed.
    """
    resolver = ConflictResolver()
    evidence = [
        EvidenceRecord(
            detector_source=EvidenceSource.SPACY.value,
            entity_type="PERSON",
            raw_score=0.72,
            normalized_score=0.72,
            evidence_strength="MODERATE",
            location="block_1"
        )
    ]
    outcome = resolver.resolve_candidate("Optiv Inc.", evidence)
    assert outcome.is_suppressed is True
    assert "corporate stop-word" in outcome.suppression_reason.lower()


def test_conflicting_predictions_route_to_conflict_and_human_review():
    """
    Close competing predictions across different PII types trigger CONFLICT status.
    """
    resolver = ConflictResolver()
    evidence = [
        EvidenceRecord(
            detector_source=EvidenceSource.SPACY.value,
            entity_type="PERSON",
            raw_score=0.62,
            normalized_score=0.62,
            evidence_strength="MODERATE",
            location="block_1"
        ),
        EvidenceRecord(
            detector_source=EvidenceSource.CONTEXT.value,
            entity_type="CUSTOMER_ID",
            raw_score=0.60,
            normalized_score=0.60,
            evidence_strength="MODERATE",
            location="block_1"
        )
    ]
    outcome = resolver.resolve_candidate("ID-6789", evidence)
    assert outcome.agreement_status == "CONFLICT"
    assert outcome.is_uncertain is True
    assert "Conflicting" in outcome.uncertainty_reason


def test_calibrated_confidence_tiers():
    """
    Threshold manager correctly maps calibrated scores to DETECT, HUMAN_REVIEW, SUPPRESS.
    """
    tm = ThresholdManager({"fusion": {"high_threshold": 0.70, "lower_threshold": 0.45}})

    # High -> DETECT
    d_high, _ = tm.determine_decision(calibrated_confidence=0.75)
    assert d_high == "DETECT"

    # Borderline -> HUMAN_REVIEW
    d_border, r_border = tm.determine_decision(calibrated_confidence=0.55)
    assert d_border == "HUMAN_REVIEW"
    assert r_border is not None

    # Low -> SUPPRESS
    d_low, _ = tm.determine_decision(calibrated_confidence=0.30)
    assert d_low == "SUPPRESS"


def test_ece_and_brier_calculation():
    """
    Verify calculation of Expected Calibration Error and Brier score.
    """
    # Perfect calibration test
    confs = [0.1, 0.9]
    labels = [0, 1]
    res = compute_ece_and_brier(confs, labels, n_bins=10)
    assert res["ece"] >= 0.0
    assert res["brier_score"] == pytest.approx(0.01, abs=0.01)
    assert len(res["bins"]) == 10

    # Empty edge case
    empty_res = compute_ece_and_brier([], [])
    assert empty_res["ece"] == 0.0
    assert empty_res["brier_score"] == 0.0


def test_calibration_strict_validation_guard(tmp_path):
    """
    Security invariant: Calibrator MUST reject fitting on any split other than 'validation'.
    """
    calibrator = ConfidenceCalibrator(model_dir=str(tmp_path))
    scores = [0.2, 0.4, 0.7, 0.8, 0.9]
    labels = [0, 0, 1, 1, 1]

    with pytest.raises(ValueError, match="Security invariant violated"):
        calibrator.fit(scores, labels, split_name="test")

    # Succeeds with 'validation'
    meta = calibrator.fit(scores, labels, split_name="validation")
    assert meta["method"] == "platt_scaling"
    assert meta["fit_split"] == "validation"


def test_calibration_persistence_and_reload(tmp_path):
    """
    Verify calibrator persistence and reloading without information loss.
    """
    calibrator = ConfidenceCalibrator(model_dir=str(tmp_path))
    scores = [0.1, 0.2, 0.6, 0.8, 0.9]
    labels = [0, 0, 1, 1, 1]
    calibrator.fit(scores, labels, split_name="validation")
    calibrator.save(str(tmp_path))

    reloaded = ConfidenceCalibrator(model_dir=str(tmp_path))
    reloaded.load(str(tmp_path))
    assert reloaded.is_loaded is True

    # Calibration output should match
    score = 0.65
    assert calibrator.calibrate(score) == reloaded.calibrate(score)


def test_zero_raw_pii_in_evidence_and_summary():
    """
    Strict Privacy Invariant: Evidence summaries and metadata must never leak raw sensitive text.
    """
    engine = EvidenceFusionEngine()
    secret_text = "4532-0150-1234-5678"
    evidence = [
        EvidenceRecord(
            detector_source=EvidenceSource.ALGORITHMIC.value,
            entity_type="CREDIT_CARD",
            raw_score=0.99,
            normalized_score=0.99,
            evidence_strength="STRONG",
            location="block_99"
        )
    ]
    res = engine.fuse_candidate(secret_text, evidence)
    assert secret_text not in res.evidence_summary
    assert res.decision == "DETECT"


def test_detect_pii_with_fusion_end_to_end():
    """
    End-to-end integration test of detect_pii_with_fusion on document blocks.
    """
    block1 = DocumentBlock(
        document_id="doc_fusion_1",
        file_name="fusion_test.txt",
        file_type="txt",
        location="para_1",
        block_type="text",
        text="Contact Tobias Lindqvist at tobias@example.com",
        order=0
    )
    findings = detect_pii_with_fusion([block1])
    assert len(findings) >= 2

    # Check fusion enrichment fields
    for f in findings:
        assert f.fusion_confidence is not None
        assert f.calibrated_confidence is not None
        assert f.fusion_decision in ["DETECT", "HUMAN_REVIEW"]
        assert f.detector_agreement is not None
        assert len(f.detector_sources) > 0
