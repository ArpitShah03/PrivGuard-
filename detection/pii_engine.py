import uuid
from typing import List, Dict, Any, Optional
from models.schemas import PIIFinding, DocumentBlock
from detection.regex_detector import detect_regex
from detection.ner_detector import detect_ner
from detection.context_rules import detect_context
from detection.enterprise_patterns import detect_enterprise_patterns
from detection.masked_detector import detect_masked_pii
from detection.ocr_normalizer import detect_ocr_repaired_pii
from detection.entity_resolver import default_entity_resolver, EntityResolver


def get_severity(pii_type: str) -> str:
    """Return risk severity based on enterprise sensitivity categorization."""
    if pii_type in ["GOVERNMENT_ID", "CREDIT_CARD", "SSN", "PAN", "PESEL", "PASSPORT", "SECRET"]:
        return "CRITICAL"
    elif pii_type in ["EMPLOYEE_ID", "DIRECTOR_ID", "VENDOR_ID", "EMAIL", "PHONE", "PERSON", "BANK_ACCOUNT", "IFSC"]:
        return "HIGH"
    elif pii_type in ["ADDRESS", "DATE_OF_BIRTH", "CUSTOMER_ID", "MERCHANT_ID"]:
        return "MEDIUM"
    return "LOW"


def get_detector_tier(method_str: str) -> int:
    """
    Tier-based precedence matrix for conflicting overlapping findings:
    Tier 1 (Highest): Algorithmic Checksums / Mathematical Validators
    Tier 2: Explicit Contextual Rules & Secrets
    Tier 3: Standard Patterns & Regex
    Tier 4: Statistical NER (probabilistic)
    Tier 5: Partially Masked Patterns
    """
    m = method_str.upper()
    if "ALGORITHMIC_VALIDATOR" in m or "ENTROPY" in m:
        return 1
    elif "CONTEXT" in m:
        return 2
    elif "REGEX" in m or "ENTERPRISE" in m:
        return 3
    elif "NER" in m:
        return 4
    elif "MASKED" in m:
        return 5
    return 6


def overlap(start1: int, end1: int, start2: int, end2: int) -> bool:
    return max(start1, start2) < min(end1, end2)


def combine_methods(m1: Any, m2: Any) -> str:
    parts1 = m1.split(" + ") if isinstance(m1, str) else list(m1)
    parts2 = m2.split(" + ") if isinstance(m2, str) else list(m2)
    return " + ".join(sorted(set(p.strip() for p in parts1 + parts2 if p.strip())))


def merge_findings(findings: List[dict]) -> List[dict]:
    """
    Arbitrate overlapping candidate findings using hierarchical precedence matrix
    and bounded Bayesian confidence combination.
    """
    if not findings:
        return []

    # Sort by start position, then by length (longest first)
    findings.sort(key=lambda x: (x["start"], -(x["end"] - x["start"])))

    merged = []
    current = findings[0]

    for next_find in findings[1:]:
        if overlap(current["start"], current["end"], next_find["start"], next_find["end"]):
            tier_curr = get_detector_tier(str(current.get("detection_method", "")))
            tier_next = get_detector_tier(str(next_find.get("detection_method", "")))

            # 1. Tier Precedence takes highest priority
            if tier_next < tier_curr:
                winner = next_find
                loser = current
            elif tier_curr < tier_next:
                winner = current
                loser = next_find
            else:
                # Same tier: pick higher confidence, or longer span if confidence is close
                if next_find["confidence"] > current["confidence"]:
                    winner = next_find
                    loser = current
                elif current["confidence"] > next_find["confidence"]:
                    winner = current
                    loser = next_find
                else:
                    winner = current if (current["end"] - current["start"]) >= (next_find["end"] - next_find["start"]) else next_find
                    loser = next_find if winner is current else current

            # Combine detection methods and compute bounded Bayesian confidence
            combined_method = combine_methods(winner["detection_method"], loser["detection_method"])
            # Bounded belief combination: C_new = 1 - (1 - C1) * (1 - 0.5 * C2), max 0.98
            c1 = winner["confidence"]
            c2 = loser["confidence"]
            boosted_conf = min(0.98, 1.0 - (1.0 - c1) * (1.0 - 0.5 * c2))

            # Preserve metadata details from winner
            current = dict(winner)
            current["detection_method"] = combined_method
            current["confidence"] = round(boosted_conf, 3)

            # Inherit details if present
            if loser.get("is_masked"):
                current["is_masked"] = True
            if loser.get("normalized_text"):
                current["normalized_text"] = loser.get("normalized_text")
        else:
            merged.append(current)
            current = next_find

    merged.append(current)
    return merged


def detect_pii_in_block(block: DocumentBlock) -> List[PIIFinding]:
    """
    Execute multi-stage PII detection on a single DocumentBlock:
    - Enterprise pattern detection (SSN, PAN, PESEL, Passport, IFSC, Accounts, Secrets)
    - Contextual extraction (Employee IDs, Vendor IDs, DIN)
    - Partially masked PII
    - Native regex & spaCy NER
    - OCR-corrupted candidate repairs (if is_ocr=True)
    """
    text = block.text
    if not text or text.startswith("[OCR_UNAVAILABLE") or text.startswith("[IMAGE_OCR_UNAVAILABLE"):
        return []

    raw_findings = []

    # 1. Enterprise national, financial, corporate, and secret patterns
    raw_findings.extend(detect_enterprise_patterns(text))

    # 2. Contextual rule detection
    raw_findings.extend(detect_context(text))

    # 3. Base regex detection (Email, Phone, CC with Luhn, IP)
    raw_findings.extend(detect_regex(text))

    # 4. Partially masked PII detection
    raw_findings.extend(detect_masked_pii(text))

    # 5. Targeted OCR character repair (only active on OCR blocks)
    if getattr(block, "is_ocr", False):
        raw_findings.extend(detect_ocr_repaired_pii(text))

    # 6. Statistical NER detection (spaCy Person, Address)
    raw_findings.extend(detect_ner(text))

    # Filter out weak generic dates that aren't boosted by context
    filtered_findings = []
    for f in raw_findings:
        if f["pii_type"] == "DATE_OF_BIRTH" and f["confidence"] < 0.70:
            continue
        filtered_findings.append(f)

    merged_raw = merge_findings(filtered_findings)

    final_findings = []
    for f in merged_raw:
        final_findings.append(PIIFinding(
            finding_id=str(uuid.uuid4()),
            document_id=block.document_id,
            file_name=block.file_name,
            location=block.location,
            start=f["start"],
            end=f["end"],
            text=f["text"],
            pii_type=f["pii_type"],
            confidence=f["confidence"],
            detection_method=[m.strip() for m in f["detection_method"].split("+") if m.strip()],
            severity=get_severity(f["pii_type"]),
            bbox=getattr(block, "bbox", None),
            is_ocr=getattr(block, "is_ocr", False),
            is_masked=f.get("is_masked", False),
            normalized_text=f.get("normalized_text"),
            validation_details=f.get("validation_details", {})
        ))

    return final_findings


def detect_pii_in_document_blocks(
    blocks: List[DocumentBlock],
    resolver: Optional[EntityResolver] = None,
    fusion_engine: Optional[Any] = None,
    enable_fusion: bool = False
) -> List[PIIFinding]:
    """
    End-to-end multi-block detection with cross-block entity resolution.
    Links entity variants (e.g. 'T. Lindqvist' and 'Tobias Lindqvist') using
    corroborating secondary evidence and assigns stable semantic replacement tokens.
    Optionally enriches findings with Phase 5C Evidence Fusion & Calibration.
    """
    res = resolver or default_entity_resolver
    all_findings = []

    for block in blocks:
        block_findings = detect_pii_in_block(block)
        all_findings.extend(block_findings)

    # Resolve entities across the entire collection of blocks
    resolved_findings = res.resolve_findings(all_findings, blocks)

    if enable_fusion:
        from detection.fusion.fusion_engine import default_fusion_engine
        f_engine = fusion_engine or default_fusion_engine
        try:
            return f_engine.fuse_document_blocks(blocks, resolved_findings)
        except Exception:
            return resolved_findings

    return resolved_findings


def detect_pii_with_fusion(
    blocks: List[DocumentBlock],
    resolver: Optional[EntityResolver] = None,
    fusion_engine: Optional[Any] = None
) -> List[PIIFinding]:
    """
    Convenience function: runs end-to-end multi-block detection with
    full Phase 5C Evidence Fusion & Confidence Calibration enabled.
    """
    return detect_pii_in_document_blocks(
        blocks=blocks,
        resolver=resolver,
        fusion_engine=fusion_engine,
        enable_fusion=True
    )
