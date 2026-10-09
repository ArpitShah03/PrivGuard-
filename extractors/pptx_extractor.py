import pptx
from pptx.enum.shapes import MSO_SHAPE_TYPE
from typing import List, Optional, Tuple
from models.schemas import DocumentBlock
from extractors.ocr_engine import OCREngine, default_ocr_engine, OCRStatus
from extractors.metadata_extractor import extract_metadata_as_blocks


def _extract_shape_recursive(
    shape,
    slide_idx: int,
    loc_prefix: str,
    document_id: str,
    original_file_name: str,
    engine: OCREngine,
    order: int
) -> Tuple[List[DocumentBlock], int]:
    blocks = []

    # 1. Recursive handling for Grouped Shapes
    if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
        try:
            for child_idx, child_shape in enumerate(shape.shapes):
                child_loc = f"{loc_prefix}_child_{child_idx+1}"
                child_blocks, order = _extract_shape_recursive(
                    shape=child_shape,
                    slide_idx=slide_idx,
                    loc_prefix=child_loc,
                    document_id=document_id,
                    original_file_name=original_file_name,
                    engine=engine,
                    order=order
                )
                blocks.extend(child_blocks)
        except Exception:
            pass
        return blocks, order

    # 2. Table handling
    if shape.has_table:
        try:
            for r_idx, row in enumerate(shape.table.rows):
                for c_idx, cell in enumerate(row.cells):
                    cell_text = cell.text_frame.text.strip() if hasattr(cell, "text_frame") else cell.text.strip()
                    if cell_text:
                        blocks.append(DocumentBlock(
                            document_id=document_id,
                            file_name=original_file_name,
                            file_type="pptx",
                            location=f"{loc_prefix}_row_{r_idx+1}_cell_{c_idx+1}",
                            block_type="table_cell",
                            text=cell_text,
                            order=order,
                            is_ocr=False,
                            ocr_confidence=1.0,
                            metadata={
                                "slide": slide_idx + 1,
                                "row_index": r_idx + 1,
                                "col_index": c_idx + 1,
                                "source_type": "table_cell"
                            }
                        ))
                        order += 1
        except Exception:
            pass
        return blocks, order

    # 3. Picture / Embedded Image handling with OCR
    if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
        try:
            image_blob = shape.image.blob
            if len(image_blob) > 1024:  # skip tiny decorative icons
                ocr_res = engine.extract_text(image_blob)
                if ocr_res.status == OCRStatus.SUCCESS and ocr_res.text.strip():
                    blocks.append(DocumentBlock(
                        document_id=document_id,
                        file_name=original_file_name,
                        file_type="pptx",
                        location=loc_prefix,
                        block_type="image_ocr_text",
                        text=ocr_res.text.strip(),
                        order=order,
                        is_ocr=True,
                        ocr_confidence=ocr_res.confidence,
                        metadata={
                            "slide": slide_idx + 1,
                            "source_type": "slide_image_ocr",
                            "ocr_status": ocr_res.status
                        }
                    ))
                    order += 1
                elif ocr_res.is_uncertain:
                    blocks.append(DocumentBlock(
                        document_id=document_id,
                        file_name=original_file_name,
                        file_type="pptx",
                        location=loc_prefix,
                        block_type=f"IMAGE_OCR_{ocr_res.status}",
                        text=f"[IMAGE_OCR_{ocr_res.status}: {ocr_res.error_message or 'Slide image OCR failed'}]",
                        order=order,
                        is_ocr=True,
                        ocr_confidence=ocr_res.confidence,
                        metadata={
                            "slide": slide_idx + 1,
                            "source_type": "slide_image_ocr",
                            "ocr_status": ocr_res.status,
                            "is_uncertain": True,
                            "error": ocr_res.error_message
                        }
                    ))
                    order += 1
        except Exception:
            pass
        return blocks, order

    # 4. Standard Text Shapes / Frames
    if hasattr(shape, "text") and shape.text.strip():
        # Check if shape has text_frame with paragraphs to preserve paragraphs without merging
        text = shape.text.strip()
        blocks.append(DocumentBlock(
            document_id=document_id,
            file_name=original_file_name,
            file_type="pptx",
            location=loc_prefix,
            block_type="text",
            text=text,
            order=order,
            is_ocr=False,
            ocr_confidence=1.0,
            metadata={
                "slide": slide_idx + 1,
                "source_type": "shape_text"
            }
        ))
        order += 1

    return blocks, order


def extract_pptx(
    file_path: str,
    document_id: str,
    original_file_name: str,
    ocr_engine: Optional[OCREngine] = None
) -> List[DocumentBlock]:
    """
    Enterprise-grade multimodal PPTX extractor:
    - Recursively traverses shape trees (including MSO_SHAPE_TYPE.GROUP).
    - Extracts structured table cells.
    - Extracts embedded images/screenshots and runs OCR.
    - Extracts slide speaker notes.
    - Extracts presentation core metadata as DocumentBlocks.
    """
    engine = ocr_engine or default_ocr_engine
    blocks = []
    order = 0

    try:
        prs = pptx.Presentation(file_path)

        for slide_idx, slide in enumerate(prs.slides):
            # 1. Shapes on the slide
            for shape_idx, shape in enumerate(slide.shapes):
                loc_prefix = f"slide_{slide_idx+1}_shape_{shape_idx+1}"
                shape_blocks, order = _extract_shape_recursive(
                    shape=shape,
                    slide_idx=slide_idx,
                    loc_prefix=loc_prefix,
                    document_id=document_id,
                    original_file_name=original_file_name,
                    engine=engine,
                    order=order
                )
                blocks.extend(shape_blocks)

            # 2. Slide Speaker Notes
            try:
                if slide.has_notes_slide:
                    notes_slide = slide.notes_slide
                    notes_text = notes_slide.notes_text_frame.text.strip()
                    if notes_text:
                        blocks.append(DocumentBlock(
                            document_id=document_id,
                            file_name=original_file_name,
                            file_type="pptx",
                            location=f"slide_{slide_idx+1}_notes",
                            block_type="notes",
                            text=notes_text,
                            order=order,
                            is_ocr=False,
                            ocr_confidence=1.0,
                            metadata={
                                "slide": slide_idx + 1,
                                "source_type": "speaker_notes"
                            }
                        ))
                        order += 1
            except Exception:
                pass

        # 3. Presentation Core Properties Metadata
        meta_blocks = extract_metadata_as_blocks(
            file_path=file_path,
            file_type="pptx",
            document_id=document_id,
            original_file_name=original_file_name,
            start_order=order
        )
        blocks.extend(meta_blocks)

    except Exception as e:
        raise Exception(f"Failed to read PPTX file: {str(e)}")

    return blocks
