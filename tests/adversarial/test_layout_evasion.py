import pytest
from models.schemas import DocumentBlock
from detection.pii_engine import detect_pii_in_document_blocks
from detection.multimodal.schemas import MultimodalCandidateItem
from detection.multimodal.detector import LightweightMultimodalDetector
from redaction.validator import validate_sanitized_blocks


def test_split_pii_across_adjacent_shapes():
    """Attack: Label in shape 1 ('SSN:'), value in shape 2 ('219-45-6789')."""
    block_label = DocumentBlock(
        document_id="doc_pptx_split",
        file_name="deck.pptx",
        file_type="pptx",
        location="slide_1_shape_1",
        block_type="shape",
        text="Employee Social Security Number:",
        order=0,
        bbox=[0.1, 0.1, 0.3, 0.2]
    )
    block_val = DocumentBlock(
        document_id="doc_pptx_split",
        file_name="deck.pptx",
        file_type="pptx",
        location="slide_1_shape_2",
        block_type="shape",
        text="219-45-6789",
        order=1,
        bbox=[0.35, 0.1, 0.6, 0.2]
    )

    findings = detect_pii_in_document_blocks([block_label, block_val])
    assert len(findings) >= 1
    assert any(f.pii_type == "SSN" for f in findings)


def test_split_table_cell_identifier_context():
    """Attack: Table header specifies 'Tax Identifier', data cell contains value."""
    detector = LightweightMultimodalDetector()
    detector.load()
    item = MultimodalCandidateItem(
        sample_id="adv_table_01",
        block_id="cell_val",
        text="219-45-6789",
        source="table_cell",
        bbox=[0.4, 0.4, 0.6, 0.5],
        metadata={
            "table_context": {"header": "Tax Identifier", "row": 2, "col": 1},
            "neighbor_texts": ["Tax Identifier", "Annual Compensation"]
        }
    )

    pred = detector.predict(item)
    assert pred is not None
    assert pred.pii_type == "SSN"
    assert pred.score >= 0.70


def test_unresolvable_fragmented_layout_routes_to_human_review():
    """
    Attack: Fragmented text across malformed layout blocks where extraction
    confidence is degraded. Gate must not release as SAFE.
    """
    block = DocumentBlock(
        document_id="doc_frag",
        file_name="corrupt_layout.pdf",
        file_type="pdf",
        location="page_1",
        block_type="OCR_UNAVAILABLE",
        text="[IMAGE_OCR_UNAVAILABLE]",
        order=0,
        metadata={"is_uncertain": True, "fragmented": True}
    )

    val = validate_sanitized_blocks("doc_frag", [block])
    assert val.is_safe is False
    assert val.requires_human_review is True
    assert val.security_decision in ["HUMAN_REVIEW", "BLOCKED"]
