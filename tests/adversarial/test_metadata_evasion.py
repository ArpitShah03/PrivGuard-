import pytest
from models.schemas import DocumentBlock
from detection.pii_engine import detect_pii_in_block
from redaction.validator import validate_sanitized_blocks


def test_pii_hidden_in_metadata_block_detected():
    """Attack: Sensitive author / creator PII hidden in document metadata."""
    meta_block = DocumentBlock(
        document_id="doc_meta_01",
        file_name="executive_summary.docx",
        file_type="docx",
        location="metadata_author",
        block_type="metadata",
        text="author: Tobias Lindqvist",
        order=0,
        metadata={"metadata_field": "author", "metadata_value": "Tobias Lindqvist", "source_type": "metadata"}
    )

    findings = detect_pii_in_block(meta_block)
    assert len(findings) >= 1
    assert any(f.pii_type == "PERSON" for f in findings)


def test_uninspected_corrupted_metadata_routes_to_human_review():
    """
    Attack: Metadata is corrupted/unreadable. System must record extraction
    uncertainty and prevent a silent SAFE release.
    """
    uncertain_meta_block = DocumentBlock(
        document_id="doc_meta_corrupt",
        file_name="corrupt_metadata.pdf",
        file_type="pdf",
        location="metadata_error",
        block_type="metadata_uncertain",
        text="[METADATA_UNAVAILABLE_CORRUPTED]",
        order=0,
        metadata={"is_uncertain": True, "error": "Corrupted metadata stream"}
    )

    val = validate_sanitized_blocks("doc_meta_corrupt", [uncertain_meta_block])
    assert val.is_safe is False
    assert val.requires_human_review is True
    assert val.security_decision in ["HUMAN_REVIEW", "BLOCKED"]
