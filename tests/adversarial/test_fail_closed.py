import pytest
from models.schemas import DocumentBlock
from redaction.validator import validate_sanitized_blocks, is_block_uncertain
from detection.entity_resolver import EntityRegistry, EntityResolver
from detection.pii_engine import detect_pii_in_document_blocks
from extractors.router import route_and_extract


def test_corrupted_extension_routed_fail_closed():
    """Attack: Unsupported/executable file extension (.exe) rejected."""
    with pytest.raises(ValueError) as exc:
        route_and_extract("malicious_payload.exe", "doc_mal", "malicious_payload.exe")
    assert "Unsupported file type" in str(exc.value)


def test_extraction_uncertainty_zero_findings_never_safe():
    """
    CORE SECURITY PRINCIPLE:
    If a block had extraction failure (e.g., OCR unreadable) but produced 0 PII findings,
    the final gate decision must be HUMAN_REVIEW, NEVER SAFE.
    """
    block = DocumentBlock(
        document_id="doc_zero_pii_uncertain",
        file_name="unreadable_scan.pdf",
        file_type="pdf",
        location="page_1",
        block_type="OCR_UNAVAILABLE",
        text="[OCR_UNAVAILABLE]",
        order=0,
        is_ocr=True,
        ocr_confidence=0.0,
        metadata={"is_uncertain": True}
    )

    val = validate_sanitized_blocks("doc_zero_pii_uncertain", [block])
    assert val.is_safe is False
    assert val.security_decision in ["HUMAN_REVIEW", "BLOCKED"]


def test_conflicting_entities_anti_merge():
    """
    Attack: Conflicting identity attributes (different emails/IDs) must NOT merge
    even if the names are similar or share surnames.
    """
    registry = EntityRegistry()
    resolver = EntityResolver(registry)

    block1 = DocumentBlock(
        document_id="doc_conf",
        file_name="staff.txt",
        file_type="txt",
        location="p1",
        block_type="text",
        text="Employee David Miller (Email: dmiller_risk@cadence.com)",
        order=0
    )
    block2 = DocumentBlock(
        document_id="doc_conf",
        file_name="staff.txt",
        file_type="txt",
        location="p2",
        block_type="text",
        text="Contractor David Miller (Email: dmiller_external@vendor.org)",
        order=1
    )

    findings = detect_pii_in_document_blocks([block1, block2], resolver=resolver)
    person_findings = [f for f in findings if f.pii_type == "PERSON"]

    assert len(person_findings) == 2
    # Conflicting emails must prevent merging into same entity
    assert person_findings[0].entity_id != person_findings[1].entity_id
    assert person_findings[0].replacement_token != person_findings[1].replacement_token


def test_top_false_safe_regressions():
    """
    Regression check against the top dangerous false-safe conditions:
    1. IMAGE_OCR_UNAVAILABLE block
    2. is_uncertain metadata block
    Both must fail closed.
    """
    block1 = DocumentBlock(
        document_id="doc_reg1",
        file_name="scan.pdf",
        file_type="pdf",
        location="p1_img1",
        block_type="IMAGE_OCR_UNAVAILABLE",
        text="[IMAGE_OCR_UNAVAILABLE]",
        order=0,
        metadata={"is_uncertain": True}
    )
    assert is_block_uncertain(block1) is True

    val = validate_sanitized_blocks("doc_reg1", [block1])
    assert val.is_safe is False
    assert val.requires_human_review is True
