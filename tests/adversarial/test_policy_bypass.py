import pytest
from policy.models import (
    SecurityPolicy,
    UncertaintyPolicy,
    ThresholdPolicy,
    FilePolicy,
    VerificationGatePolicy,
    EntityRule
)
from policy.validator import PolicyValidator
from policy.engine import PolicyEngine
from models.schemas import ValidationResult, PIIFinding


def test_insecure_policy_extraction_uncertainty_safe_rejected():
    """Attack: Attacker tries to configure 'on_extraction_uncertainty: SAFE'."""
    validator = PolicyValidator()
    policy = SecurityPolicy(
        name="Malicious Policy",
        version="1.0.0",
        description="Try to force SAFE on extraction uncertainty",
        file_policy=FilePolicy(allowed_extensions=["txt"]),
        thresholds=ThresholdPolicy(high_threshold=0.70, lower_threshold=0.45),
        uncertainty_policy=UncertaintyPolicy(
            require_100_coverage=False,
            on_extraction_uncertainty="SAFE"  # Insecure!
        ),
        gate_policy=VerificationGatePolicy()
    )

    result = validator.validate(policy)
    assert result.is_valid is False
    assert any("on_extraction_uncertainty" in err or "Security Invariant Violated" in err for err in result.errors)


def test_inverted_thresholds_rejected():
    """Attack: Invert thresholds (high: 0.40 < lower: 0.70) to cause decision inversion."""
    validator = PolicyValidator()
    policy = SecurityPolicy(
        name="Inverted Thresholds Policy",
        version="1.0.0",
        description="Invalid threshold ordering",
        file_policy=FilePolicy(allowed_extensions=["txt"]),
        thresholds=ThresholdPolicy(high_threshold=0.40, lower_threshold=0.70),
        uncertainty_policy=UncertaintyPolicy(on_extraction_uncertainty="HUMAN_REVIEW"),
        gate_policy=VerificationGatePolicy()
    )

    result = validator.validate(policy)
    assert result.is_valid is False
    assert any("cannot exceed" in err for err in result.errors)


def test_fallback_strict_policy_mandates_human_review():
    """When policy is in FALLBACK_STRICT state, gate must NEVER release SAFE."""
    fallback_policy = SecurityPolicy(
        name="Fallback Strict",
        version="1.0.0",
        description="Fallback mode",
        policy_status="FALLBACK_STRICT",
        policy_error="Corrupt YAML encountered",
        file_policy=FilePolicy(allowed_extensions=["txt"]),
        thresholds=ThresholdPolicy(high_threshold=0.70, lower_threshold=0.45),
        uncertainty_policy=UncertaintyPolicy(on_extraction_uncertainty="HUMAN_REVIEW"),
        gate_policy=VerificationGatePolicy()
    )

    engine = PolicyEngine(policy=fallback_policy)
    val = ValidationResult(
        document_id="doc_fallback",
        is_safe=True,
        remaining_findings=[],
        message="Attempting safe release",
        requires_human_review=False,
        uncertain_blocks_count=0,
        pii_before=0,
        pii_after=0,
        high_risk_residual=0,
        sanitized_file_path="clean.txt",
        re_scanned_blocks_count=1,
        security_decision="SANITIZED"
    )

    res = engine.evaluate_rescan_gate(val)
    assert res.is_safe is False
    assert res.security_decision == "HUMAN_REVIEW"
    assert "fallback state" in res.message


def test_extraction_uncertainty_overrides_low_confidence():
    """
    CRITICAL:
    Even when detected PII confidence is below threshold (<0.45) or zero findings exist,
    extraction uncertainty MUST override and force HUMAN_REVIEW.
    """
    engine = PolicyEngine()
    val = ValidationResult(
        document_id="doc_low_conf",
        is_safe=True,
        remaining_findings=[],
        message="No high confidence PII detected",
        requires_human_review=False,
        uncertain_blocks_count=1,  # 1 uncertain block!
        pii_before=0,
        pii_after=0,
        high_risk_residual=0,
        sanitized_file_path="clean.txt",
        re_scanned_blocks_count=1,
        security_decision="SANITIZED"
    )

    res = engine.evaluate_rescan_gate(val)
    assert res.is_safe is False
    assert res.security_decision == "HUMAN_REVIEW"
    assert res.requires_human_review is True
