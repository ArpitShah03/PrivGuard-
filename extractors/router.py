import os
from typing import List, Dict, Any, Optional, Tuple
from models.schemas import DocumentBlock
from extractors.txt_extractor import extract_txt
from extractors.pdf_extractor import extract_pdf
from extractors.docx_extractor import extract_docx
from extractors.pptx_extractor import extract_pptx
from extractors.ocr_engine import OCREngine, default_ocr_engine

SUPPORTED_EXTENSIONS = {"txt", "pdf", "docx", "pptx"}


def route_and_extract(
    file_path: str,
    document_id: str,
    original_file_name: str,
    ocr_engine: Optional[OCREngine] = None
) -> List[DocumentBlock]:
    """
    Central format router that dispatches incoming files to the appropriate
    multimodal extractor and returns a normalized DocumentBlock sequence.
    """
    engine = ocr_engine or default_ocr_engine
    ext = original_file_name.split('.')[-1].lower()

    if ext == 'txt':
        return extract_txt(file_path, document_id, original_file_name)
    elif ext == 'pdf':
        return extract_pdf(file_path, document_id, original_file_name, ocr_engine=engine)
    elif ext == 'docx':
        return extract_docx(file_path, document_id, original_file_name, ocr_engine=engine)
    elif ext == 'pptx':
        return extract_pptx(file_path, document_id, original_file_name, ocr_engine=engine)
    else:
        raise ValueError(f"Unsupported file type: {ext}. Supported types: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")


def compute_extraction_metrics(blocks: List[DocumentBlock]) -> Dict[str, Any]:
    """
    Compute structured extraction metrics and coverage statistics
    from the normalized DocumentBlock collection.
    """
    total = len(blocks)
    native_count = 0
    ocr_count = 0
    image_count = 0
    meta_count = 0
    ocr_uncertain_count = 0
    ocr_confidences = []

    for b in blocks:
        if b.block_type == "metadata":
            meta_count += 1
        elif b.is_ocr:
            ocr_count += 1
            if "image" in b.block_type:
                image_count += 1
            if "OCR_" in b.block_type or b.metadata.get("is_uncertain", False):
                ocr_uncertain_count += 1
            if b.ocr_confidence > 0:
                ocr_confidences.append(b.ocr_confidence)
        else:
            native_count += 1

    avg_ocr_conf = (
        sum(ocr_confidences) / len(ocr_confidences)
        if ocr_confidences else (1.0 if ocr_count == 0 else 0.0)
    )

    # OCR coverage: percentage of OCR content successfully processed with acceptable confidence
    ocr_coverage = 1.0
    if ocr_count > 0:
        successful_ocr = ocr_count - ocr_uncertain_count
        ocr_coverage = round(max(0.0, successful_ocr / ocr_count), 3)

    return {
        "total_blocks": total,
        "native_blocks": native_count,
        "ocr_blocks": ocr_count,
        "image_blocks": image_count,
        "metadata_blocks": meta_count,
        "ocr_uncertain_blocks": ocr_uncertain_count,
        "avg_ocr_confidence": round(avg_ocr_conf, 3),
        "ocr_coverage": ocr_coverage
    }
