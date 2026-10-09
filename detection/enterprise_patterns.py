import re
from typing import List, Dict, Any
from detection.algorithmic_validators import (
    validate_ssn,
    validate_pan,
    validate_pesel,
    calculate_shannon_entropy
)

# 1. Government & National ID Patterns
SSN_PATTERN = re.compile(
    r'\b(?!(000|666|9\d{2}))(\d{3})[- .\t]+(?!(00))(\d{2})[- .\t]+(?!(0000))(\d{4})\b'
)

PAN_PATTERN = re.compile(
    r'\b([A-Z]{5}\d{4}[A-Z])\b'
)

PESEL_PATTERN = re.compile(
    r'\b(\d{11})\b'
)

PASSPORT_PATTERN = re.compile(
    r'(?i)(?:passport(?:\s*(?:no|number|#))?[:\s-]*)\b([A-Z0-9]{6,9})\b'
)

# 2. Financial Patterns
IFSC_PATTERN = re.compile(
    r'\b([A-Z]{4}0[A-Z0-9]{6})\b'
)

BANK_ACCOUNT_PATTERN = re.compile(
    r'(?i)(?:(?:bank\s*)?acc(?:oun)?t(?:\s*(?:no|number|#))?|checking\s*acc(?:oun)?t|acct\s*#)[:\s-]*\b(\d{8,18})\b'
)

# 3. Enterprise / Corporate Identifiers
DIRECTOR_ID_PATTERN = re.compile(
    r'(?i)(?:director\s*id(?:entification)?(?:\s*number)?|din)[:\s#-]*\b(\d{8})\b'
)

VENDOR_ID_PATTERN = re.compile(
    r'(?i)(?:vendor|supplier|contractor|tprm)\s*(?:id|number|code|#)[:\s-]*\b([A-Za-z0-9-_]{4,15})\b'
)

CUSTOMER_ID_PATTERN = re.compile(
    r'(?i)(?:customer|client|cust)\s*(?:id|number|#)[:\s-]*\b([A-Za-z0-9-_]{4,15})\b'
)

MERCHANT_ID_PATTERN = re.compile(
    r'(?i)(?:merchant|mid)\s*(?:id|number|#)[:\s-]*\b([A-Za-z0-9-_]{5,15})\b'
)

# 4. Secrets & Authentication Tokens
SECRET_PREFIX_PATTERN = re.compile(
    r'(?i)(?:api[_-]?key|client[_-]?secret|access[_-]?token|auth[_-]?token|bearer|private[_-]?key)[:\s=]+(["\']?)([A-Za-z0-9+/=_\-\.]{16,80})\1'
)


def detect_enterprise_patterns(text: str) -> List[Dict[str, Any]]:
    """
    Detect enterprise, national, financial, and authentication PII types
    with algorithmic checksum validation and context checks.
    """
    findings = []
    if not text:
        return findings

    # --- A. US SSN ---
    for match in SSN_PATTERN.finditer(text):
        val = match.group(0)
        if validate_ssn(val):
            # Check for surrounding context boosting
            ctx_match = re.search(r'(?i)(ssn|social\s*security)', text[max(0, match.start() - 30):min(len(text), match.end() + 30)])
            conf = 0.98 if ctx_match else 0.92
            findings.append({
                "text": val,
                "start": match.start(),
                "end": match.end(),
                "pii_type": "SSN",
                "confidence": conf,
                "detection_method": "ALGORITHMIC_VALIDATOR + REGEX",
                "severity": "CRITICAL",
                "validation_details": {"format": "US_SSN", "checksum_valid": True}
            })

    # --- B. Indian PAN ---
    for match in PAN_PATTERN.finditer(text):
        val = match.group(1)
        is_valid, entity_type = validate_pan(val)
        if is_valid:
            findings.append({
                "text": val,
                "start": match.start(1),
                "end": match.end(1),
                "pii_type": "PAN",
                "confidence": 0.96,
                "detection_method": "ALGORITHMIC_VALIDATOR + REGEX",
                "severity": "CRITICAL",
                "validation_details": {"entity_type": entity_type, "pan": val}
            })

    # --- C. Polish PESEL ---
    for match in PESEL_PATTERN.finditer(text):
        val = match.group(1)
        # PESEL requires surrounding context to distinguish from random 11-digit numbers
        surrounding = text[max(0, match.start() - 35):min(len(text), match.end() + 35)]
        has_pesel_ctx = bool(re.search(r'(?i)(pesel|national\s*id|id\s*poland|polish\s*id)', surrounding))
        if has_pesel_ctx and validate_pesel(val):
            findings.append({
                "text": val,
                "start": match.start(1),
                "end": match.end(1),
                "pii_type": "PESEL",
                "confidence": 0.98,
                "detection_method": "ALGORITHMIC_VALIDATOR + CONTEXT",
                "severity": "CRITICAL",
                "validation_details": {"checksum_valid": True}
            })

    # --- D. Passport ---
    for match in PASSPORT_PATTERN.finditer(text):
        val = match.group(1)
        findings.append({
            "text": val,
            "start": match.start(1),
            "end": match.end(1),
            "pii_type": "PASSPORT",
            "confidence": 0.90,
            "detection_method": "CONTEXT_RULE",
            "severity": "CRITICAL",
            "validation_details": {"context": "passport_prefix"}
        })

    # --- E. IFSC Code ---
    for match in IFSC_PATTERN.finditer(text):
        val = match.group(1)
        surrounding = text[max(0, match.start() - 30):min(len(text), match.end() + 30)]
        has_ifsc_ctx = bool(re.search(r'(?i)(ifsc|bank|branch|neft|rtgs|imps)', surrounding))
        conf = 0.96 if has_ifsc_ctx else 0.88
        findings.append({
            "text": val,
            "start": match.start(1),
            "end": match.end(1),
            "pii_type": "IFSC",
            "confidence": conf,
            "detection_method": "REGEX + CONTEXT" if has_ifsc_ctx else "REGEX",
            "severity": "HIGH",
            "validation_details": {"bank_code": val[:4]}
        })

    # --- F. Bank Account Number ---
    for match in BANK_ACCOUNT_PATTERN.finditer(text):
        val = match.group(1)
        findings.append({
            "text": val,
            "start": match.start(1),
            "end": match.end(1),
            "pii_type": "BANK_ACCOUNT",
            "confidence": 0.92,
            "detection_method": "CONTEXT_RULE",
            "severity": "HIGH",
            "validation_details": {"digits": len(val)}
        })

    # --- G. Director Identification Number (DIN) ---
    for match in DIRECTOR_ID_PATTERN.finditer(text):
        val = match.group(1)
        findings.append({
            "text": val,
            "start": match.start(1),
            "end": match.end(1),
            "pii_type": "DIRECTOR_ID",
            "confidence": 0.94,
            "detection_method": "CONTEXT_RULE",
            "severity": "HIGH",
            "validation_details": {"din_digits": len(val)}
        })

    # --- H. Vendor / Supplier ID ---
    for match in VENDOR_ID_PATTERN.finditer(text):
        val = match.group(1)
        findings.append({
            "text": val,
            "start": match.start(1),
            "end": match.end(1),
            "pii_type": "VENDOR_ID",
            "confidence": 0.91,
            "detection_method": "CONTEXT_RULE",
            "severity": "HIGH",
            "validation_details": {"vendor_key": val}
        })

    # --- I. Customer / Client ID ---
    for match in CUSTOMER_ID_PATTERN.finditer(text):
        val = match.group(1)
        findings.append({
            "text": val,
            "start": match.start(1),
            "end": match.end(1),
            "pii_type": "CUSTOMER_ID",
            "confidence": 0.88,
            "detection_method": "CONTEXT_RULE",
            "severity": "MEDIUM",
            "validation_details": {"customer_key": val}
        })

    # --- J. Merchant ID ---
    for match in MERCHANT_ID_PATTERN.finditer(text):
        val = match.group(1)
        findings.append({
            "text": val,
            "start": match.start(1),
            "end": match.end(1),
            "pii_type": "MERCHANT_ID",
            "confidence": 0.88,
            "detection_method": "CONTEXT_RULE",
            "severity": "MEDIUM",
            "validation_details": {"merchant_key": val}
        })

    # --- K. High-Entropy API Keys & Secrets ---
    for match in SECRET_PREFIX_PATTERN.finditer(text):
        val = match.group(2)
        # Avoid standard UUID patterns
        if re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', val, re.IGNORECASE):
            continue
        # Avoid obvious placeholders or sample/dummy secrets
        val_lower = val.lower()
        if any(p in val_lower for p in ["example", "sample", "your_token", "your_key", "placeholder", "test_key", "test_secret", "dummy", "my_secret", "xxxx", "changeme"]):
            continue
        # Require character diversity (both letters and digits) and reasonable length
        has_letter = any(c.isalpha() for c in val)
        has_digit = any(c.isdigit() for c in val)
        if not (has_letter and has_digit):
            continue

        entropy = calculate_shannon_entropy(val)
        if len(val) >= 16 and entropy >= 3.2:
            findings.append({
                "text": val,
                "start": match.start(2),
                "end": match.end(2),
                "pii_type": "SECRET",
                "confidence": 0.95,
                "detection_method": "ENTROPY_VALIDATOR + CONTEXT",
                "severity": "CRITICAL",
                "validation_details": {"entropy": round(entropy, 2), "length": len(val)}
            })

    return findings
