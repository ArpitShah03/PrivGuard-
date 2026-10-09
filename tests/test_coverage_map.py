import pytest
from models.schemas import DocumentBlock
from reporting.coverage_map import CoverageCalculator, default_coverage_calculator


def test_coverage_calculator_fully_inspected():
    blocks = [
        DocumentBlock("doc-1", "file.pdf", "pdf", "Page 1, Para 1", "PARAGRAPH", "Text 1", 1),
        DocumentBlock("doc-1", "file.pdf", "pdf", "Page 1, Para 2", "PARAGRAPH", "Text 2", 2),
        DocumentBlock("doc-1", "file.pdf", "pdf", "Page 2, Para 1", "PARAGRAPH", "Text 3", 3),
    ]
    cov_map = default_coverage_calculator.compute_coverage("doc-1", blocks, metadata_inspected=True)
    
    assert cov_map.overall_coverage == 100.0
    assert cov_map.is_coverage_sufficient is True
    assert len(cov_map.deficit_reasons) == 0
    assert len(cov_map.pages) == 2


def test_coverage_calculator_flags_uncertain_page():
    blocks = [
        DocumentBlock("doc-2", "file.pdf", "pdf", "Page 1, Para 1", "PARAGRAPH", "Clean text", 1),
        # Page 2 has low OCR confidence / uncertain block
        DocumentBlock("doc-2", "file.pdf", "pdf", "Page 2, Para 1", "PARAGRAPH", "Blurry text", 2, is_ocr=True, ocr_confidence=0.45),
        DocumentBlock("doc-2", "file.pdf", "pdf", "Page 2, Para 2", "PARAGRAPH", "Unknown text", 3, is_ocr=True, metadata={"is_uncertain": True}),
    ]
    cov_map = default_coverage_calculator.compute_coverage("doc-2", blocks, metadata_inspected=True)
    
    assert cov_map.is_coverage_sufficient is False
    assert len(cov_map.deficit_reasons) >= 1
    assert any("Page 2" in r for r in cov_map.deficit_reasons)
    assert cov_map.pages[1].coverage_percent < 50.0


def test_coverage_calculator_uninspected_metadata():
    blocks = [
        DocumentBlock("doc-3", "file.docx", "docx", "Page 1, Para 1", "PARAGRAPH", "Clean text", 1),
    ]
    cov_map = default_coverage_calculator.compute_coverage("doc-3", blocks, metadata_inspected=False)
    
    assert cov_map.is_coverage_sufficient is False
    assert any("metadata" in r.lower() for r in cov_map.deficit_reasons)
