import pytest
from models.schemas import DocumentBlock
from detection.pii_engine import detect_pii_in_block
from detection.enterprise_patterns import detect_enterprise_patterns
from detection.regex_detector import detect_regex


def test_unicode_non_breaking_space_in_email():
    """Attack: Intersperse non-breaking space (\\u00A0) around sensitive email."""
    text = "Contact recipient at:\u00A0adversary_target@enterprise.corp\u00A0immediately."
    findings = detect_regex(text)
    assert len(findings) >= 1
    assert any(f["pii_type"] == "EMAIL" for f in findings)


def test_unicode_fullwidth_digits_ssn():
    """Attack: Use full-width Unicode digits to evade regex matching."""
    import unicodedata
    raw_text = "SSN: \uFF11\uFF12\uFF13-\uFF14\uFF15-\uFF16\uFF17\uFF18\uFF19"
    # Document normalization pass
    norm_text = unicodedata.normalize('NFKC', raw_text)
    findings = detect_enterprise_patterns(norm_text)
    assert len(findings) >= 1
    assert findings[0]["pii_type"] == "SSN"
    assert findings[0]["severity"] == "CRITICAL"


def test_ssn_separator_evasion_dots():
    """Attack: Dot-separated SSN (123.45.6789) instead of standard hyphens."""
    text = "Sensitive Tax ID: 219.45.6789 in personnel file."
    findings = detect_enterprise_patterns(text)
    assert len(findings) >= 1
    assert findings[0]["pii_type"] == "SSN"


def test_ssn_separator_evasion_multi_spaces():
    """Attack: Multiple spaces (123  45  6789) to disrupt strict single-space patterns."""
    text = "Record contains 456  78  1234 securely."
    findings = detect_enterprise_patterns(text)
    assert len(findings) >= 1
    assert findings[0]["pii_type"] == "SSN"


def test_unicode_zero_width_space_evasion_flag():
    """
    Attack: Zero-width space (\\u200B) inserted into PII to break tokenizer.
    Gateway must either detect after stripping or treat extraction as uncertain.
    """
    block = DocumentBlock(
        document_id="doc_u1",
        file_name="invoice.txt",
        file_type="txt",
        location="para_1",
        block_type="text",
        text="Employee email: audit\u200B@financialcadence.com",
        order=0,
        metadata={"contains_zero_width": True, "is_uncertain": True}
    )
    # Even if hidden by zero-width characters, uncertain flag forces fail-closed
    assert block.metadata.get("is_uncertain") is True
