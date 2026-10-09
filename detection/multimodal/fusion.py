import uuid
from typing import List, Dict, Any, Optional
from models.schemas import PIIFinding, DocumentBlock
from detection.multimodal.schemas import MultimodalCandidateItem, MultimodalPrediction
from detection.multimodal.detector import BaseMultimodalDetector


def block_to_candidate_item(block: DocumentBlock) -> MultimodalCandidateItem:
    """Convert DocumentBlock into standard MultimodalCandidateItem."""
    bbox_val = [0.0, 0.0, 1.0, 1.0]
    if block.bbox:
        if isinstance(block.bbox, dict):
            bbox_val = [
                float(block.bbox.get("x0", 0.0)),
                float(block.bbox.get("y0", 0.0)),
                float(block.bbox.get("x1", 1.0)),
                float(block.bbox.get("y1", 1.0))
            ]
        elif isinstance(block.bbox, (list, tuple)) and len(block.bbox) == 4:
            bbox_val = [float(v) for v in block.bbox]

    return MultimodalCandidateItem(
        sample_id=block.document_id,
        block_id=f"{block.document_id}_{block.order}",
        text=block.text,
        bbox=bbox_val,
        page_or_slide=int(block.metadata.get("page", block.metadata.get("slide", 1))),
        source=block.metadata.get("source_type", "OCR" if block.is_ocr else "native_text"),
        modality=block.file_type.upper(),
        is_ocr=block.is_ocr,
        ocr_confidence=block.ocr_confidence,
        metadata=block.metadata,
        parent_id=block.parent_id
    )


def prediction_to_piifinding(
    pred: MultimodalPrediction,
    block: DocumentBlock
) -> PIIFinding:
    """Convert MultimodalPrediction into enterprise PIIFinding schema."""
    start_pos = 0
    end_pos = len(pred.text) if pred.text else len(block.text)

    # Determine severity
    sev = "HIGH"
    if pred.pii_type in ["SSN", "PAN", "PESEL", "PASSPORT", "CREDIT_CARD", "SECRET"]:
        sev = "CRITICAL"
    elif pred.pii_type in ["ADDRESS", "DATE_OF_BIRTH", "CUSTOMER_ID"]:
        sev = "MEDIUM"

    return PIIFinding(
        finding_id=str(uuid.uuid4()),
        document_id=block.document_id,
        file_name=block.file_name,
        location=block.location,
        start=start_pos,
        end=end_pos,
        text=pred.text or block.text,
        pii_type=pred.pii_type,
        confidence=pred.score,
        detection_method=["MULTIMODAL_LAYOUT"],
        severity=sev,
        bbox=block.bbox,
        is_ocr=pred.is_ocr or block.is_ocr,
        is_masked=pred.is_masked,
        normalized_text=pred.normalized_text,
        validation_details=pred.evidence.to_dict() if pred.evidence else {},
        evidence={
            "multimodal_score": pred.score,
            "confidence_tier": pred.confidence_level,
            "uncertainty": pred.is_uncertain,
            "uncertainty_reason": pred.uncertainty_reason
        }
    )


def fuse_multimodal_findings(
    blocks: List[DocumentBlock],
    existing_findings: List[PIIFinding],
    detector: BaseMultimodalDetector
) -> List[PIIFinding]:
    """
    Fuse multimodal predictions with existing baseline findings:
    - Retains high-confidence deterministic findings (Regex, Luhn, etc.).
    - Augments with layout-detected items (tables, shapes, OCR noise).
    - Preserves fail-closed status if detector encounters uncertainty.
    """
    items = [block_to_candidate_item(b) for b in blocks]
    predictions = detector.predict_batch(items)

    fused = list(existing_findings)

    # Map predictions to corresponding blocks
    block_map = {f"{b.document_id}_{b.order}": b for b in blocks}

    for pred in predictions:
        # Match with candidate item / block
        target_block = None
        for b in blocks:
            if pred.text and pred.text in b.text:
                target_block = b
                break
        if not target_block and blocks:
            target_block = blocks[0]

        if not target_block:
            continue

        # Check if already detected by existing detectors
        already_covered = False
        for ex in existing_findings:
            if ex.document_id == target_block.document_id and ex.pii_type == pred.pii_type:
                if (ex.text in pred.text) or (pred.text in ex.text):
                    # Boost confidence of existing finding
                    ex.confidence = round(min(0.98, max(ex.confidence, pred.score)), 3)
                    if "MULTIMODAL_LAYOUT" not in ex.detection_method:
                        ex.detection_method.append("MULTIMODAL_LAYOUT")
                    already_covered = True
                    break

        if not already_covered:
            fused.append(prediction_to_piifinding(pred, target_block))

    return fused
