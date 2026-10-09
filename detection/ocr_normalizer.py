import re
from typing import List, Dict, Any
from detection.algorithmic_validators import validate_pan, validate_ssn, validate_luhn

# OCR Character confusion mapping
OCR_DIGIT_SUBSTITUTIONS = {
    'O': '0', 'o': '0',
    'I': '1', 'l': '1', '|': '1',
    'S': '5', 's': '5',
    'B': '8',
    'Z': '2', 'z': '2'
}

OCR_LETTER_SUBSTITUTIONS = {
    '0': 'O',
    '1': 'I',
    '5': 'S',
    '8': 'B'
}


def repair_ocr_digits(raw: str) -> str:
    """Repair OCR characters expected to be digits."""
    return "".join(OCR_DIGIT_SUBSTITUTIONS.get(c, c) for c in raw)


def repair_ocr_letters(raw: str) -> str:
    """Repair OCR characters expected to be uppercase letters."""
    return "".join(OCR_LETTER_SUBSTITUTIONS.get(c, c).upper() for c in raw)


def detect_ocr_repaired_pii(text: str) -> List[Dict[str, Any]]:
    """
    Generate targeted candidate repairs for OCR-corrupted PII.
    Only called when is_ocr=True.
    Validates all candidates through strict algorithmic validators.
    """
    findings = []
    if not text:
        return findings

    # --- 1. OCR-Corrupted PAN (e.g. ABCPEI234K or ABCPEO234K) ---
    # Normal PAN: 5 letters + 4 digits + 1 letter
    # If digits 6-9 contain O/I/S/B/Z, repair digits
    pan_candidate_pattern = re.compile(r'\b([A-Za-z]{5}[A-Za-z0-9]{4}[A-Za-z])\b')
    for match in pan_candidate_pattern.finditer(text):
        raw_val = match.group(1).upper()
        # If middle 4 are not already all digits:
        middle = raw_val[5:9]
        if not middle.isdigit():
            repaired_middle = repair_ocr_digits(middle)
            if repaired_middle.isdigit():
                candidate_pan = raw_val[:5] + repaired_middle + raw_val[9]
                is_valid, entity_type = validate_pan(candidate_pan)
                if is_valid:
                    findings.append({
                        "text": match.group(1),
                        "normalized_text": candidate_pan,
                        "start": match.start(1),
                        "end": match.end(1),
                        "pii_type": "PAN",
                        "confidence": 0.88,  # Minor penalty for OCR repair
                        "detection_method": "OCR_NORMALIZED_REGEX + ALGORITHMIC_VALIDATOR",
                        "severity": "CRITICAL",
                        "validation_details": {"ocr_repaired": True, "entity_type": entity_type}
                    })

    # --- 2. OCR-Corrupted SSN (e.g. 123-4S-6789 or I23-45-6789) ---
    ssn_candidate_pattern = re.compile(r'\b([A-Za-z0-9]{3}[- ][A-Za-z0-9]{2}[- ][A-Za-z0-9]{4})\b')
    for match in ssn_candidate_pattern.finditer(text):
        raw_val = match.group(1)
        repaired = repair_ocr_digits(raw_val)
        if repaired != raw_val and validate_ssn(repaired):
            # Check context
            window = text[max(0, match.start() - 30):min(len(text), match.end() + 30)]
            if re.search(r'(?i)(ssn|social|security)', window):
                findings.append({
                    "text": raw_val,
                    "normalized_text": repaired,
                    "start": match.start(1),
                    "end": match.end(1),
                    "pii_type": "SSN",
                    "confidence": 0.87,
                    "detection_method": "OCR_NORMALIZED_REGEX + ALGORITHMIC_VALIDATOR",
                    "severity": "CRITICAL",
                    "validation_details": {"ocr_repaired": True}
                })

    return findings
