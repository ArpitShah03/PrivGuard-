import os
import pytest
from models.schemas import PIIFinding, DocumentBlock, ValidationResult
from policy.models import (
    SecurityPolicy,
    PolicyAction,
    EntityRule,
    ThresholdPolicy,
    UncertaintyPolicy,
    FilePolicy,
    VerificationGatePolicy,
)
from policy.loader import PolicyLoader
from policy.validator import PolicyValidator, PolicyValidationError
from policy.engine import PolicyEngine


def test_valid_policy_loading_and_validation():
    """Verify that default config/policy.yaml loads and validates successfully."""
    loader = PolicyLoader(default_path="config/policy.yaml")
    policy = loader.load_from_file()

    assert policy.policy_status == "ACTIVE"
    assert policy.effective_policy == "CONFIGURED"
    assert policy.policy_error is None
    assert policy.thresholds.high_threshold == 0.70
    assert policy.thresholds.lower_threshold == 0.45
    assert "CREDIT_CARD" in policy.entity_rules
    assert policy.entity_rules["CREDIT_CARD"].action == "DETECT"


def test_missing_policy_triggers_fail_closed_fallback():
    """CRITICAL: Missing policy file MUST fail closed, not silently proceed."""
    loader = PolicyLoader(default_path="config/non_existent_policy.yaml")
    policy = loader.load_from_file("config/non_existent_policy.yaml")

    assert policy.policy_status == "FALLBACK_STRICT"
    assert policy.effective_policy == "STRICT_FAIL_CLOSED"
    assert policy.policy_error is not None
    assert "not found" in policy.policy_error.lower()
    # Invariant: Uncertainty policy remains HUMAN_REVIEW
    assert policy.uncertainty_policy.on_extraction_uncertainty == "HUMAN_REVIEW"


def test_invalid_yaml_triggers_fail_closed_fallback(tmp_path):
    """CRITICAL: Malformed YAML syntax MUST trigger fail-closed state."""
    broken_yaml = tmp_path / "broken.yaml"
    broken_yaml.write_text("name: broken\nthresholds: [broken yaml: :", encoding="utf-8")

    loader = PolicyLoader(default_path=str(broken_yaml))
    policy = loader.load_from_file(str(broken_yaml))

    assert policy.policy_status == "FALLBACK_STRICT"
    assert policy.effective_policy == "STRICT_FAIL_CLOSED"
    assert policy.policy_error is not None
    assert "malformed yaml" in policy.policy_error.lower() or "syntax" in policy.policy_error.lower()


def test_invalid_thresholds_rejected_by_validator():
    """Validator must reject inverted or out-of-bound thresholds."""
    validator = PolicyValidator()
    policy = SecurityPolicy(
        thresholds=ThresholdPolicy(high_threshold=0.40, lower_threshold=0.80)  # Inverted!
    )
    res = validator.validate(policy)
    assert res.is_valid is False
    assert any("cannot exceed high_threshold" in err for err in res.errors)


def test_insecure_extraction_uncertainty_action_rejected():
    """CRITICAL SECURITY INVARIANT: on_extraction_uncertainty CANNOT be SAFE or SUPPRESS."""
    validator = PolicyValidator()
    policy = SecurityPolicy(
        uncertainty_policy=UncertaintyPolicy(on_extraction_uncertainty="SAFE")
    )
    res = validator.validate(policy)
    assert res.is_valid is False
    assert any("Security Invariant Violated" in err for err in res.errors)


def test_invalid_entity_action_rejected():
    """Entity rules with unknown actions must be flagged as invalid."""
    validator = PolicyValidator()
    policy = SecurityPolicy(
        entity_rules={"EMAIL": EntityRule(entity_type="EMAIL", action="CUSTOM_BYPASS")}
    )
    res = validator.validate(policy)
    assert res.is_valid is False
    assert any("invalid action" in err for err in res.errors)


def test_fail_closed_behavior_when_policy_in_fallback():
    """When policy is in fallback state, finding evaluation routes to HUMAN_REVIEW."""
    loader = PolicyLoader()
    fallback_policy = loader.build_strict_fallback_policy("Corrupted configuration file")
    engine = PolicyEngine(policy=fallback_policy)

    finding = PIIFinding(
        finding_id="f1",
        document_id="doc1",
        file_name="test.txt",
        location="p1",
        start=0,
        end=10,
        text="clean text",
        pii_type="PERSON",
        confidence=0.90,
        detection_method=["SPACY"],
        severity="HIGH"
    )

    _, status, reason = engine.evaluate_findings([finding], has_extraction_uncertainty=False)
    assert status == "HUMAN_REVIEW"
    assert "fail-closed fallback" in reason.lower()


def test_file_policy_allowed_and_blocked_extensions():
    """Input files with unpermitted extensions must be rejected by policy."""
    engine = PolicyEngine()
    # Allowed
    allowed_pdf, _ = engine.validate_input_file("report.pdf")
    assert allowed_pdf is True
    allowed_docx, _ = engine.validate_input_file("data.docx")
    assert allowed_docx is True

    # Blocked
    blocked_exe, reason_exe = engine.validate_input_file("malware.exe")
    assert blocked_exe is False
    assert "not permitted" in reason_exe.lower()


def test_file_policy_max_size_restriction():
    """Files exceeding policy size limits must be blocked."""
    engine = PolicyEngine()
    engine.policy.file_policy.max_file_size_mb = 10.0

    # 15 MB
    size_15mb = 15 * 1024 * 1024
    allowed, reason = engine.validate_input_file("large.pdf", file_size_bytes=size_15mb)
    assert allowed is False
    assert "exceeds maximum policy limit" in reason.lower()


def test_pii_enable_and_disable_in_policy():
    """Disabled PII types or ALLOWed types in policy are excluded from active redaction."""
    policy = SecurityPolicy(
        entity_rules={
            "CUSTOMER_ID": EntityRule(entity_type="CUSTOMER_ID", enabled=False, action="ALLOW"),
            "SSN": EntityRule(entity_type="SSN", enabled=True, action="DETECT")
        }
    )
    engine = PolicyEngine(policy=policy)

    f_cust = PIIFinding(
        finding_id="f_cust", document_id="doc1", file_name="t.txt", location="p1",
        start=0, end=8, text="CUST-123", pii_type="CUSTOMER_ID", confidence=0.85,
        detection_method=["CONTEXT"], severity="MEDIUM"
    )
    f_ssn = PIIFinding(
        finding_id="f_ssn", document_id="doc1", file_name="t.txt", location="p1",
        start=10, end=21, text="123-45-6789", pii_type="SSN", confidence=0.99,
        detection_method=["REGEX"], severity="CRITICAL"
    )

    active, status, _ = engine.evaluate_findings([f_cust, f_ssn])
    active_types = [f.pii_type for f in active]

    assert "CUSTOMER_ID" not in active_types
    assert "SSN" in active_types
    assert status == "PROCEED_TO_REDACTION"


def test_pii_block_action_triggers_immediate_document_block():
    """Entity rules configured with BLOCK must immediately halt and block document release."""
    policy = SecurityPolicy(
        entity_rules={
            "SECRET": EntityRule(entity_type="SECRET", action="BLOCK", severity="CRITICAL")
        }
    )
    engine = PolicyEngine(policy=policy)

    finding = PIIFinding(
        finding_id="f_sec", document_id="doc1", file_name="t.txt", location="p1",
        start=0, end=32, text="abc123secrettoken45678901234567", pii_type="SECRET",
        confidence=0.95, detection_method=["ENTROPY"], severity="CRITICAL"
    )

    _, status, reason = engine.evaluate_findings([finding])
    assert status == "BLOCK" or status == "BLOCKED"
    assert "prohibited" in reason.lower() or "blocked" in reason.lower()


def test_entity_allow_never_bypasses_extraction_uncertainty():
    """CRITICAL SECURITY INVARIANT: ALLOW on an entity CANNOT bypass extraction uncertainty."""
    policy = SecurityPolicy(
        entity_rules={
            "CUSTOMER_ID": EntityRule(entity_type="CUSTOMER_ID", action="ALLOW")
        }
    )
    engine = PolicyEngine(policy=policy)

    finding = PIIFinding(
        finding_id="f1", document_id="doc1", file_name="t.txt", location="p1",
        start=0, end=8, text="CUST-999", pii_type="CUSTOMER_ID", confidence=0.80,
        detection_method=["CONTEXT"], severity="MEDIUM"
    )

    _, status, reason = engine.evaluate_findings([finding], has_extraction_uncertainty=True)
    # Must remain HUMAN_REVIEW due to extraction uncertainty!
    assert status == "HUMAN_REVIEW"
    assert "coverage incomplete" in reason.lower()


def test_threshold_configuration_in_policy():
    """Verify threshold policy loading and custom per-type thresholds."""
    th = ThresholdPolicy(
        high_threshold=0.75,
        lower_threshold=0.50,
        per_type_thresholds={"DATE_OF_BIRTH": 0.85}
    )
    policy = SecurityPolicy(thresholds=th)
    validator = PolicyValidator()
    res = validator.validate(policy)
    assert res.is_valid is True
    assert policy.thresholds.per_type_thresholds["DATE_OF_BIRTH"] == 0.85


def test_rescan_gate_residual_pii_blocked():
    """Policy post-rescan gate strictly blocks documents containing residual high-risk PII."""
    engine = PolicyEngine()
    val = ValidationResult(
        document_id="doc_rescan",
        is_safe=True,  # Initially claimed safe
        remaining_findings=[PIIFinding(
            finding_id="f_res", document_id="doc_rescan", file_name="t.txt", location="p1",
            start=0, end=10, text="Residual", pii_type="CREDIT_CARD", confidence=0.95,
            detection_method=["REGEX"], severity="CRITICAL"
        )],
        message="Preliminary",
        uncertain_blocks_count=0,
        high_risk_residual=1
    )

    evaluated_val = engine.evaluate_rescan_gate(val)
    assert evaluated_val.is_safe is False
    assert evaluated_val.security_decision == "BLOCKED"
    assert "exceeds policy limit" in evaluated_val.message.lower()


def test_rescan_gate_uncertainty_mandates_human_review():
    """Zero residual PII with extraction uncertainty MUST be routed to HUMAN_REVIEW, never SAFE."""
    engine = PolicyEngine()
    val = ValidationResult(
        document_id="doc_rescan_unc",
        is_safe=True,
        remaining_findings=[],
        message="Preliminary clean",
        uncertain_blocks_count=2,
        high_risk_residual=0
    )

    evaluated_val = engine.evaluate_rescan_gate(val)
    assert evaluated_val.is_safe is False
    assert evaluated_val.requires_human_review is True
    assert evaluated_val.security_decision == "HUMAN_REVIEW"
    assert "incomplete" in evaluated_val.message.lower()


def test_zero_raw_pii_in_policy_and_decision_objects():
    """STRICT PRIVACY INVARIANT: Policy evaluations and objects must never leak raw PII."""
    engine = PolicyEngine()
    raw_secret_phone = "+1-800-555-0199"

    finding = PIIFinding(
        finding_id="f_priv",
        document_id="doc_priv",
        file_name="secret.txt",
        location="p_secret",
        start=0,
        end=len(raw_secret_phone),
        text=raw_secret_phone,
        pii_type="PHONE",
        confidence=0.90,
        detection_method=["REGEX"],
        severity="HIGH"
    )

    active, status, reason = engine.evaluate_findings([finding])
    policy_dict_str = str(engine.policy.to_dict())

    # Raw sensitive phone string must NEVER appear in policy data or status reasons
    assert raw_secret_phone not in policy_dict_str
    if reason:
        assert raw_secret_phone not in reason
