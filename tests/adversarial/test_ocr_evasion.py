import pytest
from models.schemas import DocumentBlock
from detection.ocr_normalizer import detect_ocr_repaired_pii
from detection.masked_detector import detect_masked_pii
from redaction.validator import is_block_uncertain, validate_sanitized_blocks


def test_ocr_substitution_pan_repair():
    """Attack: OCR confuses letters and numbers (O ↔ 0, I ↔ 1) in Indian PAN."""
    # PAN format: 5 letters + 4 digits + 1 letter. 'O' and 'I' substituted for digits.
    ocr_corrupted_pan = "Tax ID: ABCPEO23IK on file."
    findings = detect_ocr_repaired_pii(ocr_corrupted_pan)
    assert len(findings) >= 1
    assert findings[0]["pii_type"] == "PAN"
    assert findings[0]["normalized_text"] == "ABCPE0231K"


def test_ocr_substitution_ssn_repair():
    """Attack: S substituted for 5, I for 1 in SSN under OCR scanning."""
    ocr_corrupted_ssn = "Employee SSN: I23-4S-6789 verified."
    findings = detect_ocr_repaired_pii(ocr_corrupted_ssn)
    assert len(findings) >= 1
    assert findings[0]["pii_type"] == "SSN"
    assert findings[0]["normalized_text"] == "123-45-6789"


def test_ambiguous_ocr_forces_human_review_never_safe():
    """
    CRITICAL INVARIANT:
    If OCR failed or is uncertain on a scanned page, and 0 PII is detected,
    gateway MUST NOT declare document SAFE. It must trigger HUMAN_REVIEW.
    """
    block = DocumentBlock(
        document_id="doc_ocr_fail",
        file_name="scanned_receipt.pdf",
        file_type="pdf",
        location="page_1",
        block_type="OCR_LOW_CONFIDENCE",
        text="[OCR_LOW_CONFIDENCE: 0.32]",
        order=0,
        is_ocr=True,
        ocr_confidence=0.32,
        metadata={"is_uncertain": True}
    )
    assert is_block_uncertain(block) is True

    result = validate_sanitized_blocks("doc_ocr_fail", [block])
    assert result.is_safe is False
    assert result.security_decision in ["HUMAN_REVIEW", "BLOCKED"]


def test_partially_masked_ssn_detected():
    """Attack: Attacker uses partial masking (***-**-6789) to evade standard SSN regex."""
    text = "Account Holder SSN ending in: ***-**-6789 on the statement."
    findings = detect_masked_pii(text)
    assert len(findings) >= 1
    assert findings[0]["pii_type"] == "SSN"
    assert findings[0]["is_masked"] is True


def test_partially_masked_cc_detected():
    """Attack: Partially masked credit card (**** **** **** 1234) detected with context."""
    text = "Payment processed with credit card: **** **** **** 4242."
    findings = detect_masked_pii(text)
    assert len(findings) >= 1
    assert findings[0]["pii_type"] == "CREDIT_CARD"
