from typing import List
from models.schemas import DocumentBlock, ValidationResult
from detection.pii_engine import detect_pii_in_block


def is_block_uncertain(block: DocumentBlock) -> bool:
    """
    Check if an extraction block has uncertain, unavailable, or failed extraction.
    Covers metadata is_uncertain, OCR_UNAVAILABLE, OCR_FAILED, OCR_LOW_CONFIDENCE,
    and IMAGE_OCR_UNAVAILABLE.
    """
    if block.metadata and block.metadata.get("is_uncertain", False):
        return True
    bt = (block.block_type or "").upper()
    if bt.startswith("OCR_") or "UNAVAILABLE" in bt or "FAILED" in bt or "LOW_CONFIDENCE" in bt:
        return True
    return False


def validate_sanitized_blocks(document_id: str, blocks: List[DocumentBlock]) -> ValidationResult:
    """
    Fail-closed security gate for sanitized document blocks:
    1. Checks for extraction uncertainty (failed OCR, unavailable OCR, uninspected screenshots).
       If content was not verified by extraction, the document CANNOT be declared safe.
    2. Re-runs PII detection across all blocks to ensure no residual high-risk PII remains.
    3. Status Decision:
       - Residual high-risk PII -> is_safe=False, requires_human_review=False (BLOCKED)
       - Extraction uncertainty -> is_safe=False, requires_human_review=True (HUMAN_REVIEW)
       - Verified clean extraction & zero residual PII -> is_safe=True (SANITIZED)
    """
    remaining_findings = []
    uncertain_blocks = []

    for block in blocks:
        # Check extraction uncertainty
        if is_block_uncertain(block):
            uncertain_blocks.append(block)

        # Re-run detection on the sanitized block
        findings = detect_pii_in_block(block)
        remaining_findings.extend(findings)

    # Check for high/critical severity or high confidence findings
    high_risk_remaining = [
        f for f in remaining_findings
        if f.severity in ["CRITICAL", "HIGH"] or f.confidence >= 0.85
    ]

    if high_risk_remaining:
        is_safe = False
        requires_human_review = False
        message = f"Residual PII detected ({len(high_risk_remaining)} high-risk findings). Document is blocked."
    elif uncertain_blocks:
        is_safe = False
        requires_human_review = True
        message = (
            f"Extraction uncertainty detected ({len(uncertain_blocks)} uninspected/failed blocks). "
            f"Fail-closed policy requires HUMAN REVIEW."
        )
    else:
        is_safe = True
        requires_human_review = False
        message = "No high-confidence PII remains. Document is safe."

    return ValidationResult(
        document_id=document_id,
        is_safe=is_safe,
        remaining_findings=remaining_findings,
        message=message,
        requires_human_review=requires_human_review,
        uncertain_blocks_count=len(uncertain_blocks)
    )
