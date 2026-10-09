import os
import fitz
import pytest
from models.schemas import PIIFinding, DocumentBlock
from extractors.router import route_and_extract
from detection.pii_engine import detect_pii_in_document_blocks
from redaction.document_sanitizer import DocumentSanitizer, default_document_sanitizer
from utils.file_security import compute_file_sha256


def test_synthetic_pdf_redaction_e2e(tmp_path):
    """
    End-to-End PDF redaction and re-scan gate test:
    1. Creates small synthetic PDF with visible PII (Alice Example, alice@example.com, etc.).
    2. Verifies detection identifies PII.
    3. Verifies physical black-box redactions are applied on disk.
    4. Verifies SHA256(original) != SHA256(sanitized).
    5. Verifies extracted text from sanitized PDF contains NO raw PII.
    6. Verifies mandatory re-scan passes cleanly with SANITIZED status.
    """
    sanitizer_dir = str(tmp_path / "sanitized")
    sanitizer = DocumentSanitizer(output_dir=sanitizer_dir)

    # 1. Create Synthetic PDF with visible text
    pdf_path = str(tmp_path / "employee_sample.pdf")
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    sample_text = (
        "EMPLOYEE RECORD\n\n"
        "Employee: Alice Example\n"
        "Email: alice@example.com\n"
        "Phone: +1 212 555 0147\n"
        "Employee ID: EMP-38104\n"
        "Department: Engineering Security Operations\n"
    )
    page.insert_text((50, 72), sample_text, fontsize=12)
    doc.save(pdf_path)
    doc.close()

    assert os.path.exists(pdf_path)
    orig_sha = compute_file_sha256(pdf_path)

    # 2. Extract Document Blocks
    blocks = route_and_extract(pdf_path, "doc_synth_1", "employee_sample.pdf")
    assert len(blocks) >= 1
    extracted_text = " ".join(b.text for b in blocks)
    assert "Alice Example" in extracted_text
    assert "alice@example.com" in extracted_text

    # 3. Detect PII Findings
    findings = detect_pii_in_document_blocks(blocks)
    assert len(findings) >= 2  # At least Email and Person/Phone/ID

    # 4. Physically Sanitize PDF
    sanitized_path, applied_count = sanitizer.sanitize(
        pdf_path,
        findings,
        output_filename="employee_sample_sanitized.pdf",
        return_count=True
    )
    assert os.path.exists(sanitized_path)
    sanit_sha = compute_file_sha256(sanitized_path)

    # 5. Assert Physical & Cryptographic Changes
    assert orig_sha != sanit_sha, "Sanitized PDF must have different SHA-256 hash than original!"
    assert applied_count >= len(findings), f"Applied count ({applied_count}) must cover findings ({len(findings)})"

    # 6. Verify PyMuPDF Page & Text in Sanitized Artifact
    sanit_doc = fitz.open(sanitized_path)
    assert len(sanit_doc) == 1, "Page count must be preserved"
    sanit_text = sanit_doc[0].get_text("text")
    sanit_doc.close()

    assert "alice@example.com" not in sanit_text, "Raw email must not exist in sanitized PDF text!"
    assert "Alice Example" not in sanit_text, "Raw person name must not exist in sanitized PDF text!"
    assert "Engineering Security Operations" in sanit_text, "Non-PII context must be preserved"

    # 7. Mandatory Re-Scan Verification Gate
    val, re_blocks = sanitizer.verify_and_rescan(
        sanitized_file_path=sanitized_path,
        original_blocks=blocks,
        original_findings=findings,
        document_id="doc_synth_1",
        original_file_path=pdf_path,
        applied_redactions_count=applied_count
    )

    assert val.is_safe is True
    assert val.security_decision == "SANITIZED"
    assert val.requires_human_review is False
    assert val.pii_after == 0
    assert val.applied_redactions_count == applied_count


def test_cryptographically_identical_artifact_blocks_release(tmp_path):
    """
    If a sanitized file is an exact clone of the original file despite detected PII,
    the re-scan gate MUST fail-closed with BLOCKED.
    """
    sanitizer_dir = str(tmp_path / "sanitized")
    sanitizer = DocumentSanitizer(output_dir=sanitizer_dir)

    orig_file = str(tmp_path / "source.pdf")
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Confidential Secret: SSN 219-45-6789")
    doc.save(orig_file)
    doc.close()

    # Create fake sanitized artifact which is byte-for-byte identical to original
    sanit_file = str(tmp_path / "fake_sanitized.pdf")
    with open(orig_file, "rb") as f_in, open(sanit_file, "wb") as f_out:
        f_out.write(f_in.read())

    finding = PIIFinding(
        finding_id="f_fake_1",
        document_id="doc_fake",
        file_name="source.pdf",
        location="page_1",
        start=25,
        end=36,
        text="219-45-6789",
        pii_type="SSN",
        confidence=0.99,
        detection_method=["REGEX"],
        severity="CRITICAL",
        replacement_token="[SSN_001]"
    )

    blocks = route_and_extract(orig_file, "doc_fake", "source.pdf")

    val, _ = sanitizer.verify_and_rescan(
        sanitized_file_path=sanit_file,
        original_blocks=blocks,
        original_findings=[finding],
        document_id="doc_fake",
        original_file_path=orig_file,
        applied_redactions_count=0
    )

    assert val.is_safe is False
    assert val.security_decision == "BLOCKED"
    assert "cryptographically identical" in val.message.lower()


def test_incomplete_redaction_triggers_human_review(tmp_path):
    """
    If expected findings > applied redactions count,
    the gate MUST fail-closed to HUMAN_REVIEW.
    """
    sanitizer = DocumentSanitizer(output_dir=str(tmp_path / "sanitized"))

    orig_file = str(tmp_path / "dummy.txt")
    with open(orig_file, "w") as f:
        f.write("Clean dummy content without secrets.")

    sanit_file = str(tmp_path / "dummy_out.txt")
    with open(sanit_file, "w") as f:
        f.write("Clean dummy content without secrets modified.")

    finding1 = PIIFinding(
        finding_id="f_inc_1",
        document_id="doc_inc",
        file_name="dummy.txt",
        location="page_1",
        start=0,
        end=10,
        text="+1 555 123 4567",
        pii_type="PHONE",
        confidence=0.9,
        detection_method=["REGEX"],
        severity="HIGH"
    )
    finding2 = PIIFinding(
        finding_id="f_inc_2",
        document_id="doc_inc",
        file_name="dummy.txt",
        location="page_1",
        start=15,
        end=30,
        text="test@domain.com",
        pii_type="EMAIL",
        confidence=0.9,
        detection_method=["REGEX"],
        severity="HIGH"
    )

    val, _ = sanitizer.verify_and_rescan(
        sanitized_file_path=sanit_file,
        original_blocks=[],
        original_findings=[finding1, finding2],
        document_id="doc_inc",
        original_file_path=orig_file,
        applied_redactions_count=1  # Applied only 1 out of 2 expected
    )

    assert val.is_safe is False
    assert val.requires_human_review is True
    assert val.security_decision == "HUMAN_REVIEW"
    assert "incomplete redaction" in val.message.lower()


def test_scanned_image_uncertainty_fails_closed(tmp_path):
    """
    Scanned/image-only documents without OCR text extraction MUST have uncertainty > 0
    and fail closed to HUMAN_REVIEW, never false SANITIZED.
    """
    sanitizer = DocumentSanitizer(output_dir=str(tmp_path / "sanitized"))

    # Block representing scanned page with failed/missing OCR
    uncertain_block = DocumentBlock(
        document_id="doc_scan",
        file_name="scan.pdf",
        file_type="pdf",
        location="page_1",
        block_type="PAGE_SCAN",
        text="",
        order=0,
        metadata={"is_uncertain": True, "reason": "OCR_CONFIDENCE_BELOW_THRESHOLD", "confidence": 0.2}
    )

    txt_out = str(tmp_path / "scan_out.txt")
    with open(txt_out, "w") as f:
        f.write("Scanned uninspected text.")

    val, _ = sanitizer.verify_and_rescan(
        sanitized_file_path=txt_out,
        original_blocks=[uncertain_block],
        original_findings=[],
        document_id="doc_scan"
    )

    assert val.is_safe is False
    assert val.requires_human_review is True
    assert val.security_decision == "HUMAN_REVIEW"
    assert val.uncertain_blocks_count >= 1


def test_cadence_scanned_pdf_fail_closed(tmp_path):
    """
    Cadence PDF has 35 scanned image-only pages.
    Without OCR or with image-only pages, extraction metrics must reflect uncertainty
    and re-scan must fail closed to HUMAN_REVIEW, NEVER false SANITIZED.
    """
    cadence_path = r"C:\Users\ShahA\Downloads\Case Study 2 Supporting Material\Case Study 2 Supporting Material\Cadence_Group_Risk_Management_Policy__v6.0.pdf"
    if not os.path.exists(cadence_path):
        pytest.skip("Cadence policy PDF not present on system.")

    blocks = route_and_extract(cadence_path, "doc_cadence", "Cadence_Policy.pdf")
    sanitizer = DocumentSanitizer(output_dir=str(tmp_path / "sanitized"))

    sanitized_pdf = sanitizer.sanitize(cadence_path, [], "cadence_sanitized.pdf")
    val, _ = sanitizer.verify_and_rescan(
        sanitized_file_path=sanitized_pdf,
        original_blocks=blocks,
        original_findings=[],
        document_id="doc_cadence",
        original_file_path=cadence_path
    )

    # Scanned pages with zero extracted text or uninspected content must require human review
    assert val.is_safe is False
    assert val.requires_human_review is True
    assert val.security_decision == "HUMAN_REVIEW"


def test_viewer_defenses(monkeypatch):
    """
    Verify ui/viewer defensive assertions:
    - Path identity check prevents rendering identical original and sanitized paths.
    - Missing sanitized artifact triggers error.
    """
    from ui.viewer import _render_pdf_comparison
    from models.schemas import DocumentAnalysisResult

    errors = []
    monkeypatch.setattr("streamlit.error", lambda msg: errors.append(msg))
    monkeypatch.setattr("streamlit.warning", lambda msg: None)

    res = DocumentAnalysisResult(
        document_id="d1",
        file_name="test.pdf",
        file_type="pdf",
        status="SANITIZED",
        original_blocks=[],
        sanitized_blocks=[],
        findings=[]
    )

    # 1. Test identical paths
    _render_pdf_comparison(
        res,
        original_artifact_path="c:/test/doc.pdf",
        sanitized_artifact_path="c:/test/doc.pdf"
    )
    assert any("paths are identical" in e.lower() for e in errors)

    # 2. Test missing sanitized file
    errors.clear()
    _render_pdf_comparison(
        res,
        original_artifact_path="c:/test/orig.pdf",
        sanitized_artifact_path="c:/test/non_existent_file_9876.pdf"
    )
    assert any("does not exist on disk" in e.lower() for e in errors)

