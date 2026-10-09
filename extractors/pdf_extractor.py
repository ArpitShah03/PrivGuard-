import fitz  # PyMuPDF
from typing import List, Optional, Dict, Any
from models.schemas import DocumentBlock
from extractors.ocr_engine import OCREngine, default_ocr_engine, OCRStatus
from extractors.metadata_extractor import extract_metadata_as_blocks


def is_page_scanned(page: fitz.Page, native_text: str) -> bool:
    """
    Detect whether a page is primarily scanned/visual.
    Criteria:
    1. Very little or no native extractable text (< 40 characters)
    2. Page contains images or non-empty vector graphics/drawings
    """
    clean_text = native_text.strip()
    if len(clean_text) >= 40:
        return False

    # Check if page has images
    images = page.get_images(full=True)
    if len(images) > 0:
        return True

    # Check page rect drawing or visual contents
    rect = page.rect
    if rect.width > 0 and rect.height > 0:
        drawings = page.get_drawings()
        if len(drawings) > 0:
            return True
        # If there's literally no text on the page, check if page has any visual object
        if len(clean_text) == 0:
            return True

    return False


def extract_pdf(
    file_path: str,
    document_id: str,
    original_file_name: str,
    ocr_engine: Optional[OCREngine] = None
) -> List[DocumentBlock]:
    """
    Enterprise-grade multimodal PDF extractor:
    - Extracts native text blocks with bounding boxes (normalized 0.0-1.0).
    - Detects scanned pages and renders them at 300 DPI for OCR.
    - Extracts embedded images on hybrid pages and runs OCR.
    - Injects PDF core metadata as first-class DocumentBlocks.
    - Explicitly marks OCR unavailable/failed states for fail-closed security.
    """
    engine = ocr_engine or default_ocr_engine
    blocks = []
    order = 0

    try:
        doc = fitz.open(file_path)

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            page_rect = page.rect
            page_w = max(1.0, float(page_rect.width))
            page_h = max(1.0, float(page_rect.height))

            full_page_text = page.get_text()
            page_is_scanned = is_page_scanned(page, full_page_text)

            if page_is_scanned:
                # 300 DPI Rendering
                dpi = 300
                zoom = dpi / 72.0
                matrix = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=matrix, alpha=False)
                img_bytes = pix.tobytes("png")

                ocr_result = engine.extract_text(img_bytes)

                if ocr_result.status == OCRStatus.SUCCESS and ocr_result.text.strip():
                    # If structured blocks are available, emit block-level DocumentBlocks
                    if ocr_result.blocks:
                        for b_idx, b_info in enumerate(ocr_result.blocks):
                            blocks.append(DocumentBlock(
                                document_id=document_id,
                                file_name=original_file_name,
                                file_type="pdf",
                                location=f"page_{page_num+1}_ocr_block_{b_idx+1}",
                                block_type="ocr_text",
                                text=b_info["text"],
                                order=order,
                                bbox=b_info.get("bbox"),
                                is_ocr=True,
                                ocr_confidence=b_info.get("confidence", ocr_result.confidence),
                                metadata={
                                    "page": page_num + 1,
                                    "source_type": "scanned_page_ocr",
                                    "ocr_engine": ocr_result.engine_used,
                                    "ocr_status": ocr_result.status,
                                    "dpi": dpi
                                }
                            ))
                            order += 1
                    else:
                        blocks.append(DocumentBlock(
                            document_id=document_id,
                            file_name=original_file_name,
                            file_type="pdf",
                            location=f"page_{page_num+1}",
                            block_type="ocr_text",
                            text=ocr_result.text,
                            order=order,
                            bbox={"x0": 0.0, "y0": 0.0, "x1": 1.0, "y1": 1.0},
                            is_ocr=True,
                            ocr_confidence=ocr_result.confidence,
                            metadata={
                                "page": page_num + 1,
                                "source_type": "scanned_page_ocr",
                                "ocr_engine": ocr_result.engine_used,
                                "ocr_status": ocr_result.status,
                                "dpi": dpi
                            }
                        ))
                        order += 1
                else:
                    # OCR was unavailable, failed, or low confidence
                    # Create explicit uncertainty block for fail-closed security
                    err_msg = ocr_result.error_message or "Scanned page could not be OCR processed."
                    status_block_type = f"OCR_{ocr_result.status}"
                    blocks.append(DocumentBlock(
                        document_id=document_id,
                        file_name=original_file_name,
                        file_type="pdf",
                        location=f"page_{page_num+1}",
                        block_type=status_block_type,
                        text=f"[{status_block_type}: {err_msg}]",
                        order=order,
                        bbox={"x0": 0.0, "y0": 0.0, "x1": 1.0, "y1": 1.0},
                        is_ocr=True,
                        ocr_confidence=ocr_result.confidence,
                        metadata={
                            "page": page_num + 1,
                            "source_type": "scanned_page_ocr",
                            "ocr_status": ocr_result.status,
                            "is_uncertain": ocr_result.is_uncertain,
                            "error": ocr_result.error_message,
                            "dpi": dpi
                        }
                    ))
                    order += 1

            else:
                # Native text extraction with bounding boxes
                # page.get_text("blocks") returns (x0, y0, x1, y1, text, block_no, block_type)
                page_blocks = page.get_text("blocks")
                for b_idx, b in enumerate(page_blocks):
                    block_text = b[4].strip()
                    block_type_int = b[6]  # 0 for text, 1 for image

                    if block_text and block_type_int == 0:
                        norm_bbox = {
                            "x0": round(float(b[0]) / page_w, 4),
                            "y0": round(float(b[1]) / page_h, 4),
                            "x1": round(float(b[2]) / page_w, 4),
                            "y1": round(float(b[3]) / page_h, 4),
                        }
                        blocks.append(DocumentBlock(
                            document_id=document_id,
                            file_name=original_file_name,
                            file_type="pdf",
                            location=f"page_{page_num+1}",
                            block_type="text",
                            text=block_text,
                            order=order,
                            bbox=norm_bbox,
                            is_ocr=False,
                            ocr_confidence=1.0,
                            metadata={
                                "page": page_num + 1,
                                "block_index": b_idx,
                                "source_type": "native_text"
                            }
                        ))
                        order += 1

                # Check for embedded raster images in mixed/hybrid pages
                try:
                    images = page.get_images(full=True)
                    for img_idx, img_info in enumerate(images):
                        xref = img_info[0]
                        base_image = doc.extract_image(xref)
                        if base_image and "image" in base_image:
                            img_data = base_image["image"]
                            # Only run OCR on images of reasonable size (skip 1x1 icons/bullets)
                            if len(img_data) > 1024:
                                img_ocr = engine.extract_text(img_data)
                                if img_ocr.status == OCRStatus.SUCCESS and img_ocr.text.strip():
                                    blocks.append(DocumentBlock(
                                        document_id=document_id,
                                        file_name=original_file_name,
                                        file_type="pdf",
                                        location=f"page_{page_num+1}_image_{img_idx+1}",
                                        block_type="image_ocr_text",
                                        text=img_ocr.text.strip(),
                                        order=order,
                                        is_ocr=True,
                                        ocr_confidence=img_ocr.confidence,
                                        metadata={
                                            "page": page_num + 1,
                                            "image_index": img_idx + 1,
                                            "source_type": "embedded_image_ocr",
                                            "ocr_status": img_ocr.status
                                        }
                                    ))
                                    order += 1
                except Exception:
                    pass

        # Extract PDF metadata as DocumentBlocks
        meta_blocks = extract_metadata_as_blocks(
            file_path=file_path,
            file_type="pdf",
            document_id=document_id,
            original_file_name=original_file_name,
            start_order=order
        )
        blocks.extend(meta_blocks)

    except Exception as e:
        raise Exception(f"Failed to read PDF file: {str(e)}")
    finally:
        if 'doc' in locals() and doc is not None:
            try:
                doc.close()
            except Exception:
                pass

    return blocks
