import pytest
from models.schemas import DocumentBlock, DocumentAnalysisResult
from redaction.validator import validate_sanitized_blocks, is_block_uncertain
from detection.regex_detector import detect_regex, luhn_checksum
from redaction.redactor import Redactor
from detection.pii_engine import detect_pii_in_block


def test_gate_scanned_ocr_unavailable_routes_to_human_review():
    """
    SECURITY REQUIREMENT A:
    A scanned document where OCR was unavailable MUST NOT be marked safe/sanitized.
    It must be routed to HUMAN_REVIEW.
    """
    uncertain_block = DocumentBlock(
        document_id="doc_scan_fail",
        file_name="scanned_policy.pdf",
        file_type="pdf",
        location="page_1",
        block_type="OCR_UNAVAILABLE",
        text="[OCR_UNAVAILABLE: Tesseract OCR binary not found on system]",
        order=0,
        is_ocr=True,
        ocr_confidence=0.0,
        metadata={"is_uncertain": True, "ocr_status": "UNAVAILABLE"}
    )

    validation = validate_sanitized_blocks("doc_scan_fail", [uncertain_block])
    assert validation.is_safe is False
    assert validation.requires_human_review is True
    assert validation.uncertain_blocks_count == 1
    assert "HUMAN REVIEW" in validation.message.upper()


def test_gate_image_ocr_unavailable_blocks_sanitization():
    """
    SECURITY REQUIREMENT B:
    An office document (DOCX/PPTX) with embedded images where OCR could not run
    must be flagged as uncertain and routed to HUMAN_REVIEW, never silently sanitized.
    """
    normal_block = DocumentBlock(
        document_id="doc_office",
        file_name="training.docx",
        file_type="docx",
        location="paragraph_1",
        block_type="text",
        text="General corporate training overview text.",
        order=0
    )
    image_block = DocumentBlock(
        document_id="doc_office",
        file_name="training.docx",
        file_type="docx",
        location="image_rId5",
        block_type="IMAGE_OCR_UNAVAILABLE",
        text="[IMAGE_OCR_UNAVAILABLE: Tesseract OCR failed or missing]",
        order=1,
        is_ocr=True,
        ocr_confidence=0.0,
        metadata={"is_uncertain": True}
    )

    validation = validate_sanitized_blocks("doc_office", [normal_block, image_block])
    assert validation.is_safe is False
    assert validation.requires_human_review is True
    assert validation.uncertain_blocks_count == 1


def test_gate_completely_extracted_clean_document_passes():
    """
    SECURITY REQUIREMENT C:
    A document with complete extraction, no uncertainty, and sanitized PII
    must evaluate as safe/SANITIZED.
    """
    block = DocumentBlock(
        document_id="doc_clean",
        file_name="clean.txt",
        file_type="txt",
        location="paragraph_1",
        block_type="text",
        text="Contact admin at admin@example.com",
        order=0
    )
    findings = detect_pii_in_block(block)
    assert len(findings) == 1

    redactor = Redactor()
    sanitized_block, _ = redactor.redact_block(block, findings)

    validation = validate_sanitized_blocks("doc_clean", [sanitized_block])
    assert validation.is_safe is True
    assert validation.requires_human_review is False
    assert validation.uncertain_blocks_count == 0
    assert "safe" in validation.message.lower()


def test_luhn_credit_card_timestamp_not_falsely_flagged():
    """
    SECURITY REQUIREMENT D:
    Metadata timestamps (e.g., 20260917142154) must NOT be classified as CREDIT_CARD,
    while valid credit cards must still be detected.
    """
    timestamp_text = "creationDate: D:20260917142154+05'30'"
    findings = detect_regex(timestamp_text)
    cc_findings = [f for f in findings if f["pii_type"] == "CREDIT_CARD"]
    assert len(cc_findings) == 0, "Timestamp was falsely classified as CREDIT_CARD"

    # Test valid 16-digit credit card passes Luhn check
    valid_card_text = "Card number: 4111 1111 1111 1111"
    valid_findings = detect_regex(valid_card_text)
    valid_cc = [f for f in valid_findings if f["pii_type"] == "CREDIT_CARD"]
    assert len(valid_cc) == 1
    assert valid_cc[0]["pii_type"] == "CREDIT_CARD"


def test_gate_unredacted_pii_strictly_blocked():
    """
    SECURITY REQUIREMENT E:
    Unredacted residual PII must produce is_safe=False and requires_human_review=False
    so the status evaluates strictly to BLOCKED, preserving fail-closed semantics.
    """
    leaked_block = DocumentBlock(
        document_id="doc_leak",
        file_name="leak.txt",
        file_type="txt",
        location="paragraph_1",
        block_type="text",
        text="Unredacted email remaining: secret@optiv.com",
        order=0
    )
    validation = validate_sanitized_blocks("doc_leak", [leaked_block])
    assert validation.is_safe is False
    assert validation.requires_human_review is False
    assert "BLOCKED" in validation.message.upper()
