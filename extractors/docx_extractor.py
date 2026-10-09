import docx
from typing import List, Optional
from models.schemas import DocumentBlock
from extractors.ocr_engine import OCREngine, default_ocr_engine, OCRStatus
from extractors.metadata_extractor import extract_metadata_as_blocks


def extract_docx(
    file_path: str,
    document_id: str,
    original_file_name: str,
    ocr_engine: Optional[OCREngine] = None
) -> List[DocumentBlock]:
    """
    Enterprise-grade multimodal DOCX extractor:
    - Extracts paragraphs with order and style info.
    - Extracts structured tables preserving table, row, and column indices.
    - Extracts headers and footers across sections.
    - Extracts embedded images (screenshots, diagrams) and executes OCR.
    - Injects core document properties (author, comments, modified) as DocumentBlocks.
    """
    engine = ocr_engine or default_ocr_engine
    blocks = []
    order = 0

    try:
        doc = docx.Document(file_path)

        # 1. Headers and Footers across sections
        for s_idx, section in enumerate(doc.sections):
            # Header
            try:
                header = section.header
                if header:
                    for h_idx, h_para in enumerate(header.paragraphs):
                        text = h_para.text.strip()
                        if text:
                            blocks.append(DocumentBlock(
                                document_id=document_id,
                                file_name=original_file_name,
                                file_type="docx",
                                location=f"section_{s_idx+1}_header_{h_idx+1}",
                                block_type="header",
                                text=text,
                                order=order,
                                is_ocr=False,
                                ocr_confidence=1.0,
                                metadata={"section": s_idx + 1, "source_type": "header"}
                            ))
                            order += 1
            except Exception:
                pass

            # Footer
            try:
                footer = section.footer
                if footer:
                    for f_idx, f_para in enumerate(footer.paragraphs):
                        text = f_para.text.strip()
                        if text:
                            blocks.append(DocumentBlock(
                                document_id=document_id,
                                file_name=original_file_name,
                                file_type="docx",
                                location=f"section_{s_idx+1}_footer_{f_idx+1}",
                                block_type="footer",
                                text=text,
                                order=order,
                                is_ocr=False,
                                ocr_confidence=1.0,
                                metadata={"section": s_idx + 1, "source_type": "footer"}
                            ))
                            order += 1
            except Exception:
                pass

        # 2. Main Body Paragraphs
        for i, para in enumerate(doc.paragraphs):
            text = para.text.strip()
            if text:
                blocks.append(DocumentBlock(
                    document_id=document_id,
                    file_name=original_file_name,
                    file_type="docx",
                    location=f"paragraph_{i+1}",
                    block_type="text",
                    text=text,
                    order=order,
                    is_ocr=False,
                    ocr_confidence=1.0,
                    metadata={"paragraph_index": i + 1, "source_type": "paragraph"}
                ))
                order += 1

        # 3. Structured Tables
        for t_idx, table in enumerate(doc.tables):
            seen_cell_texts = set()
            for r_idx, row in enumerate(table.rows):
                for c_idx, cell in enumerate(row.cells):
                    text = cell.text.strip()
                    # Check for cell object or duplicate text in same row/col coordinate
                    cell_loc = f"table_{t_idx+1}_row_{r_idx+1}_cell_{c_idx+1}"
                    cell_key = (r_idx, c_idx, text)
                    if text and cell_key not in seen_cell_texts:
                        seen_cell_texts.add(cell_key)
                        blocks.append(DocumentBlock(
                            document_id=document_id,
                            file_name=original_file_name,
                            file_type="docx",
                            location=cell_loc,
                            block_type="table_cell",
                            text=text,
                            order=order,
                            is_ocr=False,
                            ocr_confidence=1.0,
                            metadata={
                                "table_index": t_idx + 1,
                                "row_index": r_idx + 1,
                                "col_index": c_idx + 1,
                                "source_type": "table_cell"
                            }
                        ))
                        order += 1

        # 4. Embedded Images & Screenshots OCR
        try:
            rel_parts = doc.part.related_parts
            img_idx = 0
            for rel_id, part in rel_parts.items():
                content_type = getattr(part, "content_type", "")
                if "image" in content_type:
                    img_idx += 1
                    img_bytes = part.blob
                    # Ignore tiny icons/bullets (< 1KB)
                    if len(img_bytes) > 1024:
                        ocr_res = engine.extract_text(img_bytes)
                        if ocr_res.status == OCRStatus.SUCCESS and ocr_res.text.strip():
                            blocks.append(DocumentBlock(
                                document_id=document_id,
                                file_name=original_file_name,
                                file_type="docx",
                                location=f"image_{rel_id}",
                                block_type="image_ocr_text",
                                text=ocr_res.text.strip(),
                                order=order,
                                is_ocr=True,
                                ocr_confidence=ocr_res.confidence,
                                metadata={
                                    "image_rel_id": rel_id,
                                    "image_index": img_idx,
                                    "content_type": content_type,
                                    "source_type": "embedded_image_ocr",
                                    "ocr_status": ocr_res.status
                                }
                            ))
                            order += 1
                        elif ocr_res.is_uncertain:
                            # Record explicit uncertainty block for fail-closed security
                            blocks.append(DocumentBlock(
                                document_id=document_id,
                                file_name=original_file_name,
                                file_type="docx",
                                location=f"image_{rel_id}",
                                block_type=f"IMAGE_OCR_{ocr_res.status}",
                                text=f"[IMAGE_OCR_{ocr_res.status}: {ocr_res.error_message or 'Embedded image OCR failed'}]",
                                order=order,
                                is_ocr=True,
                                ocr_confidence=ocr_res.confidence,
                                metadata={
                                    "image_rel_id": rel_id,
                                    "image_index": img_idx,
                                    "source_type": "embedded_image_ocr",
                                    "ocr_status": ocr_res.status,
                                    "is_uncertain": True,
                                    "error": ocr_res.error_message
                                }
                            ))
                            order += 1
        except Exception:
            pass

        # 5. Core Properties Metadata
        meta_blocks = extract_metadata_as_blocks(
            file_path=file_path,
            file_type="docx",
            document_id=document_id,
            original_file_name=original_file_name,
            start_order=order
        )
        blocks.extend(meta_blocks)

    except Exception as e:
        raise Exception(f"Failed to read DOCX file: {str(e)}")

    return blocks
