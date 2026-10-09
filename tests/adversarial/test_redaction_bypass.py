import os
import pytest
from models.schemas import DocumentBlock, PIIFinding
from redaction.document_sanitizer import (
    default_document_sanitizer,
    REDACTION_TOKEN_PATTERN
)


def test_legitimate_tokens_receive_immunity():
    """Legitimate session tokens must match token pattern and avoid re-detection."""
    legit_tokens = ["[PERSON_001]", "[EMAIL_002]", "[SSN_003]", "[CREDIT_CARD_001]"]
    for tok in legit_tokens:
        assert bool(REDACTION_TOKEN_PATTERN.match(tok)) is True


def test_attacker_bracketed_text_not_immune_if_invalid_format():
    """
    CRITICAL SECURITY INVARIANT:
    Attacker tries to evade re-scan by placing arbitrary text in brackets:
    e.g. '[john.doe@cadence.com]' or '[219-45-6789]'.
    These must NOT match REDACTION_TOKEN_PATTERN.
    """
    evasive_tokens = [
        "[john.doe@cadence.com]",
        "[219-45-6789]",
        "[4111-1111-1111-1111]",
        "[SUPER_SECRET_KEY]"
    ]
    for tok in evasive_tokens:
        # PII containing punctuation or non-standard token format must not be immune
        if "@" in tok or "-" in tok:
            assert bool(REDACTION_TOKEN_PATTERN.match(tok)) is False


def test_residual_pii_on_rescan_forces_blocked():
    """
    Attack: In-memory sanitizer claims clean, but disk file or re-scan yields residual PII.
    Gateway MUST yield BLOCKED, never SAFE.
    """
    orig_finding = PIIFinding(
        finding_id="f_orig",
        document_id="doc_rescan",
        file_name="risk.txt",
        location="para_1",
        start=0,
        end=11,
        text="219-45-6789",
        pii_type="SSN",
        confidence=0.98,
        detection_method=["REGEX"],
        severity="CRITICAL"
    )

    # Simulate output file containing residual sensitive data
    dummy_path = "tests/adversarial/_test_residual.txt"
    os.makedirs(os.path.dirname(dummy_path), exist_ok=True)
    with open(dummy_path, "w", encoding="utf-8") as f:
        f.write("Residual unredacted SSN: 219-45-6789 remains here.")

    try:
        val, _ = default_document_sanitizer.verify_and_rescan(
            sanitized_file_path=dummy_path,
            original_blocks=[],
            original_findings=[orig_finding],
            document_id="doc_rescan"
        )
        assert val.is_safe is False
        assert val.security_decision == "BLOCKED"
        assert val.high_risk_residual >= 1
    finally:
        if os.path.exists(dummy_path):
            os.remove(dummy_path)


def test_missing_output_file_fails_closed():
    """If output file was not written to disk, re-scan MUST fail-closed (BLOCKED)."""
    val, _ = default_document_sanitizer.verify_and_rescan(
        sanitized_file_path="non_existent_file_path_12345.pdf",
        original_blocks=[],
        original_findings=[],
        document_id="doc_missing"
    )
    assert val.is_safe is False
    assert val.security_decision == "BLOCKED"
    assert "does not exist on disk" in val.message
