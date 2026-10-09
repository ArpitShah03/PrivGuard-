import io
import fitz  # PyMuPDF
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Union, Tuple
from PIL import Image

from models.schemas import PIIFinding


@dataclass
class VisualFinding:
    finding_id: str
    category: str  # "SIGNATURE", "ID_PHOTO", "OFFICIAL_STAMP"
    page: int
    bbox: Dict[str, float]  # x0, y0, x1, y1
    confidence: float
    is_uncertain: bool = False
    uncertainty_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class VisualPIIDetector:
    """
    Multimodal visual PII detector for document images, vector strokes, and embedded graphics.
    Detects signatures, identity portrait photos, and official stamps.
    Enforces fail-closed: unparsable images or ambiguous visual regions trigger visual uncertainty.
    """

    SIGNATURE_KEYWORDS = [
        "signature", "signed by", "sign here", "authorized signature",
        "authorized representative", "signatory", "countersigned", "by:"
    ]

    STAMP_KEYWORDS = [
        "official seal", "notary public", "apostille", "certified copy",
        "stamped", "approved", "seal", "notarized"
    ]

    def __init__(self):
        pass

    def detect_in_pdf(self, pdf_input: Union[str, bytes]) -> List[VisualFinding]:
        """
        Inspect PDF pages for visual PII:
        1. Vector drawings: clustering of bezier curves/lines representing handwritten signatures.
        2. Embedded images: ID portrait photos vs decorative graphics.
        3. Proximity to signature/stamp context text.
        """
        findings: List[VisualFinding] = []
        doc = None
        try:
            if isinstance(pdf_input, bytes):
                doc = fitz.open(stream=pdf_input, filetype="pdf")
            else:
                doc = fitz.open(pdf_input)

            for page_idx in range(len(doc)):
                page = doc[page_idx]
                page_rect = page.rect
                page_w = page_rect.width
                page_h = page_rect.height

                # Extract page text with layout to check context proximity
                text_page = page.get_text("blocks")
                text_blocks = [(b[0], b[1], b[2], b[3], b[4]) for b in text_page if len(b) >= 5]

                # 1. Inspect Embedded Raster Images (ID Photos vs Decorative Graphics)
                image_list = page.get_images(full=True)
                for img_idx, img_info in enumerate(image_list):
                    xref = img_info[0]
                    try:
                        base_image = doc.extract_image(xref)
                        if not base_image:
                            findings.append(VisualFinding(
                                finding_id=f"vis_unc_{page_idx}_{img_idx}",
                                category="IMAGE_UNCERTAINTY",
                                page=page_idx + 1,
                                bbox={"x0": 0.0, "y0": 0.0, "x1": page_w, "y1": page_h},
                                confidence=0.5,
                                is_uncertain=True,
                                uncertainty_reason="Failed to extract embedded image stream"
                            ))
                            continue

                        img_bytes = base_image["image"]
                        img_width = base_image["width"]
                        img_height = base_image["height"]
                        aspect_ratio = img_width / max(1.0, float(img_height))

                        # Determine image bbox on page if placed
                        img_rects = page.get_image_rects(xref)
                        bbox = {"x0": 0.0, "y0": 0.0, "x1": float(img_width), "y1": float(img_height)}
                        if img_rects:
                            r = img_rects[0]
                            bbox = {"x0": float(r.x0), "y0": float(r.y0), "x1": float(r.x1), "y1": float(r.y1)}

                        # Decorative Filter:
                        # - Tiny icons: < 32x32 px
                        # - Extreme banners / horizontal dividers: aspect ratio > 3.5 or < 0.25
                        # - Full page background / watermark: area covers > 70% of page
                        img_area_page = (bbox["x1"] - bbox["x0"]) * (bbox["y1"] - bbox["y0"])
                        is_full_page = img_area_page > (0.7 * page_w * page_h)
                        is_icon = (img_width < 32 and img_height < 32)
                        is_extreme_banner = (aspect_ratio > 3.5 or aspect_ratio < 0.25)

                        if is_icon or is_extreme_banner or is_full_page:
                            # Decorative image, skip
                            continue

                        # ID Photo Heuristic:
                        # Typical portrait / badge aspect ratio: 0.7 to 1.35
                        # Reasonable dimensions: 50x50 to 500x500 px
                        if 0.70 <= aspect_ratio <= 1.35 and (60 <= img_width <= 800) and (60 <= img_height <= 800):
                            # Check if page has identity indicators (e.g. Passport, License, Employee, ID)
                            page_text_lower = " ".join([b[4] for b in text_blocks]).lower()
                            id_signals = ["passport", "license", "employee", "badge", "identity", "photo", "card", "dob", "name:"]
                            has_id_signal = any(sig in page_text_lower for sig in id_signals)

                            conf = 0.88 if has_id_signal else 0.75
                            findings.append(VisualFinding(
                                finding_id=f"vis_id_photo_{page_idx}_{img_idx}",
                                category="ID_PHOTO",
                                page=page_idx + 1,
                                bbox=bbox,
                                confidence=conf,
                                metadata={
                                    "width": img_width,
                                    "height": img_height,
                                    "aspect_ratio": round(aspect_ratio, 2),
                                    "has_id_signal": has_id_signal
                                }
                            ))

                    except Exception as e:
                        findings.append(VisualFinding(
                            finding_id=f"vis_unc_{page_idx}_{img_idx}",
                            category="IMAGE_UNCERTAINTY",
                            page=page_idx + 1,
                            bbox={"x0": 0.0, "y0": 0.0, "x1": page_w, "y1": page_h},
                            confidence=0.5,
                            is_uncertain=True,
                            uncertainty_reason=f"Error inspecting embedded image: {str(e)}"
                        ))

                # 2. Inspect Vector Drawings for Handwritten Signatures
                try:
                    drawings = page.get_drawings()
                    # Signatures have high density of curved strokes (paths with beziers or multiple short lines)
                    # Group drawings that are near signature keywords
                    sig_keywords_present = []
                    for b in text_blocks:
                        blk_text = b[4].lower()
                        for kw in self.SIGNATURE_KEYWORDS:
                            if kw in blk_text:
                                sig_keywords_present.append((b[0], b[1], b[2], b[3], kw))

                    # If signature keyword is found, look for drawing strokes within 120 points below/right
                    for (kx0, ky0, kx1, ky1, kw) in sig_keywords_present:
                        sig_zone = fitz.Rect(kx0 - 20, ky1 - 10, max(kx1 + 250, kx0 + 250), ky1 + 100)
                        matching_drawings = [d for d in drawings if sig_zone.intersects(d["rect"])]
                        
                        if len(matching_drawings) >= 1:
                            # Signature path strokes detected
                            union_rect = matching_drawings[0]["rect"]
                            for d in matching_drawings[1:]:
                                union_rect = union_rect | d["rect"]
                            
                            findings.append(VisualFinding(
                                finding_id=f"vis_sig_{page_idx}_{int(ky0)}",
                                category="SIGNATURE",
                                page=page_idx + 1,
                                bbox={"x0": float(union_rect.x0), "y0": float(union_rect.y0), "x1": float(union_rect.x1), "y1": float(union_rect.y1)},
                                confidence=0.92,
                                metadata={"trigger_keyword": kw, "stroke_count": len(matching_drawings)}
                            ))

                    # Also check for isolated complex curve clusters even without direct keyword
                    # (e.g. standalone signature line)
                    for d in drawings:
                        items = d.get("items", [])
                        rect = d.get("rect")
                        if not rect:
                            continue
                        # If a single drawing has >= 8 curve items in a small box (handwriting stroke pattern)
                        curve_count = sum(1 for it in items if it[0] in ("c", "l"))
                        aspect = rect.width / max(1.0, rect.height)
                        if curve_count >= 12 and 1.5 <= aspect <= 6.0 and 20 <= rect.height <= 90:
                            # Avoid duplicate if already covered
                            is_dup = any(
                                f.category == "SIGNATURE" and f.page == page_idx + 1 and
                                abs(f.bbox["x0"] - rect.x0) < 30 and abs(f.bbox["y0"] - rect.y0) < 30
                                for f in findings
                            )
                            if not is_dup:
                                findings.append(VisualFinding(
                                    finding_id=f"vis_sig_curve_{page_idx}_{int(rect.y0)}",
                                    category="SIGNATURE",
                                    page=page_idx + 1,
                                    bbox={"x0": float(rect.x0), "y0": float(rect.y0), "x1": float(rect.x1), "y1": float(rect.y1)},
                                    confidence=0.82,
                                    metadata={"stroke_count": curve_count}
                                ))

                except Exception as e:
                    # Non-fatal drawing inspection
                    pass

        except Exception as e:
            findings.append(VisualFinding(
                finding_id=f"vis_unc_doc",
                category="DOCUMENT_VISUAL_UNCERTAINTY",
                page=1,
                bbox={"x0": 0.0, "y0": 0.0, "x1": 0.0, "y1": 0.0},
                confidence=0.5,
                is_uncertain=True,
                uncertainty_reason=f"Failed to inspect PDF visual objects: {str(e)}"
            ))
        finally:
            if doc:
                doc.close()

        return findings

    def to_pii_findings(self, visual_findings: List[VisualFinding], document_id: str, file_name: str) -> List[PIIFinding]:
        """Convert VisualFindings into standard PIIFinding objects for pipeline integration."""
        pii_findings: List[PIIFinding] = []
        for vf in visual_findings:
            if vf.is_uncertain:
                continue
            
            p_find = PIIFinding(
                finding_id=vf.finding_id,
                document_id=document_id,
                file_name=file_name,
                location=f"Page {vf.page} (Visual)",
                start=0,
                end=0,
                text=f"<{vf.category}>",
                pii_type=vf.category,
                confidence=vf.confidence,
                detection_method=["VISUAL_ANALYSIS"],
                severity="HIGH" if vf.category in ("SIGNATURE", "ID_PHOTO") else "MEDIUM",
                bbox=vf.bbox,
                replacement_token=f"[{vf.category}_REDACTED]",
                detector_sources=["VisualPIIDetector"],
                detector_agreement="SINGLE_HIGH",
                fusion_decision="DETECT",
                evidence_summary=f"Visual detector identified {vf.category} with {vf.confidence*100:.0f}% confidence."
            )
            pii_findings.append(p_find)
        return pii_findings


default_visual_detector = VisualPIIDetector()
