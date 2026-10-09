import re
from typing import List, Dict, Any

# Masked Patterns
MASKED_SSN_PATTERN = re.compile(
    r'(?:(?<!\S)|\b)(?:XXX|xxx|\*\*\*)[- ](?:XX|xx|\*\*)[- ](\d{4})\b'
)

MASKED_CC_PATTERN = re.compile(
    r'(?:(?<!\S)|\b)(?:\*{4}[ -]?|[Xx]{4}[ -]?){3}(\d{4})\b'
)

MASKED_ALPHA_PATTERN = re.compile(
    r'\b([A-Z]{3,5})[\*X]{3,5}(\d{2,4}[A-Z]?)\b'
)

MASKED_SUFFIX_PATTERN = re.compile(
    r'(?i)(?:ending\s*(?:in|with)|last\s*4\s*digits(?:\s*are|:)?)\s*[#*xX]*\s*(\d{4})\b'
)


def detect_masked_pii(text: str) -> List[Dict[str, Any]]:
    """
    Detect partially masked PII instances (e.g. XXX-XX-1234, **** **** **** 1234).
    Enforces strict context requirements to avoid false positives on code or formatting.
    """
    findings = []
    if not text:
        return findings

    # --- 1. Masked SSN ---
    for match in MASKED_SSN_PATTERN.finditer(text):
        val = match.group(0)
        # Context window check (40 chars)
        window = text[max(0, match.start() - 40):min(len(text), match.end() + 40)]
        has_context = bool(re.search(r'(?i)(ssn|social|security|tax|id)', window))
        if has_context or '-' in val:
            findings.append({
                "text": val,
                "start": match.start(),
                "end": match.end(),
                "pii_type": "SSN",
                "confidence": 0.88 if has_context else 0.78,
                "detection_method": "MASKED_PATTERN + CONTEXT",
                "severity": "HIGH",
                "is_masked": True,
                "validation_details": {"masked": True, "visible_digits": match.group(1)}
            })

    # --- 2. Masked Credit Card ---
    for match in MASKED_CC_PATTERN.finditer(text):
        val = match.group(0)
        window = text[max(0, match.start() - 40):min(len(text), match.end() + 40)]
        has_context = bool(re.search(r'(?i)(card|credit|debit|visa|mastercard|amex|payment|acct)', window))
        if has_context:
            findings.append({
                "text": val,
                "start": match.start(),
                "end": match.end(),
                "pii_type": "CREDIT_CARD",
                "confidence": 0.89,
                "detection_method": "MASKED_PATTERN + CONTEXT",
                "severity": "HIGH",
                "is_masked": True,
                "validation_details": {"masked": True, "visible_digits": match.group(1)}
            })

    # --- 3. Masked Alphanumeric (PAN / Corporate ID) ---
    for match in MASKED_ALPHA_PATTERN.finditer(text):
        val = match.group(0)
        window = text[max(0, match.start() - 40):min(len(text), match.end() + 40)]
        if re.search(r'(?i)(pan|tax|account|emp|id|vendor)', window):
            findings.append({
                "text": val,
                "start": match.start(),
                "end": match.end(),
                "pii_type": "GOVERNMENT_ID",
                "confidence": 0.85,
                "detection_method": "MASKED_PATTERN + CONTEXT",
                "severity": "HIGH",
                "is_masked": True,
                "validation_details": {"masked": True, "prefix": match.group(1)}
            })

    # --- 4. Masked Suffix Reference ("ending in 1234") ---
    for match in MASKED_SUFFIX_PATTERN.finditer(text):
        val = match.group(0)
        # Look behind to classify as card or account
        window = text[max(0, match.start() - 50):match.start()]
        pii_type = "CREDIT_CARD" if re.search(r'(?i)(card|visa|mastercard|amex)', window) else "BANK_ACCOUNT"
        findings.append({
            "text": val,
            "start": match.start(),
            "end": match.end(),
            "pii_type": pii_type,
            "confidence": 0.82,
            "detection_method": "MASKED_CONTEXT_PATTERN",
            "severity": "MEDIUM",
            "is_masked": True,
            "validation_details": {"suffix": match.group(1)}
        })

    return findings
