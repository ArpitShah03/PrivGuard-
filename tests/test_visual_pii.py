import io
import fitz
import pytest
from PIL import Image

from detection.visual_pii import VisualPIIDetector, VisualFinding, default_visual_detector


def create_test_pdf_with_signature():
    """Create a minimal PDF containing a signature keyword and stroke lines."""
    doc = fitz.open()
    page = doc.new_page(width=600, height=800)
    
    # Add text
    page.insert_text(fitz.Point(50, 400), "Please review and approve this document.")
    page.insert_text(fitz.Point(50, 500), "Authorized Signature:")
    
    # Add vector drawings under the signature line
    shape = page.new_shape()
    shape.draw_line(fitz.Point(200, 505), fitz.Point(400, 505))
    # Draw some cursive-like strokes
    shape.draw_bezier(fitz.Point(210, 500), fitz.Point(230, 480), fitz.Point(260, 510), fitz.Point(280, 490))
    shape.finish(color=(0, 0, 0), width=1.5)
    shape.commit()
    
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def create_test_pdf_with_images():
    """Create a test PDF with an ID portrait photo and a decorative banner."""
    doc = fitz.open()
    page = doc.new_page(width=600, height=800)
    
    # 1. ID Photo (120x150, aspect ratio ~0.8)
    id_img = Image.new("RGB", (120, 150), color=(180, 120, 100))
    id_buf = io.BytesIO()
    id_img.save(id_buf, format="PNG")
    page.insert_image(fitz.Rect(50, 100, 170, 250), stream=id_buf.getvalue())
    page.insert_text(fitz.Point(50, 270), "Employee ID Badge Photo")
    
    # 2. Decorative Banner (600x30, aspect ratio 20:1)
    banner_img = Image.new("RGB", (600, 30), color=(50, 100, 200))
    b_buf = io.BytesIO()
    banner_img.save(b_buf, format="PNG")
    page.insert_image(fitz.Rect(0, 0, 600, 30), stream=b_buf.getvalue())
    
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_visual_detector_finds_signature():
    detector = default_visual_detector
    pdf_bytes = create_test_pdf_with_signature()
    
    findings = detector.detect_in_pdf(pdf_bytes)
    sig_findings = [f for f in findings if f.category == "SIGNATURE"]
    
    assert len(sig_findings) >= 1
    assert sig_findings[0].confidence >= 0.8
    assert sig_findings[0].page == 1


def test_visual_detector_id_photo_vs_banner():
    detector = default_visual_detector
    pdf_bytes = create_test_pdf_with_images()
    
    findings = detector.detect_in_pdf(pdf_bytes)
    
    # Must detect ID photo
    id_photos = [f for f in findings if f.category == "ID_PHOTO"]
    assert len(id_photos) >= 1
    assert id_photos[0].confidence > 0.7
    
    # Must NOT detect decorative banner as ID photo
    banners_as_photo = [f for f in findings if f.category == "ID_PHOTO" and f.bbox.get("y0", 0) < 30]
    assert len(banners_as_photo) == 0


def test_visual_uncertainty_handling():
    detector = default_visual_detector
    # Malformed bytes that cannot be parsed as PDF
    findings = detector.detect_in_pdf(b"Not a valid PDF file buffer")
    
    # Must flag visual uncertainty and fail closed
    assert len(findings) >= 1
    assert any(f.is_uncertain for f in findings)
    assert findings[0].uncertainty_reason is not None


def test_conversion_to_pii_findings():
    detector = default_visual_detector
    vf = VisualFinding(
        finding_id="vis_test_1",
        category="SIGNATURE",
        page=1,
        bbox={"x0": 50.0, "y0": 100.0, "x1": 200.0, "y1": 150.0},
        confidence=0.9
    )
    pii_findings = detector.to_pii_findings([vf], "doc-123", "contract.pdf")
    assert len(pii_findings) == 1
    assert pii_findings[0].pii_type == "SIGNATURE"
    assert pii_findings[0].replacement_token == "[SIGNATURE_REDACTED]"
    assert pii_findings[0].detector_sources == ["VisualPIIDetector"]
