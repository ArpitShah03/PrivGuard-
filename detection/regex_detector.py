import re
from typing import List, Dict, Any

REGEX_PATTERNS = {
    "EMAIL": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    # Simple North American & International phone regex
    "PHONE": r'(?:\+?(\d{1,3}))?[-. (]*(\d{3})[-. )]*(\d{3})[-. ]*(\d{4})(?: *x(\d+))?',
    "CREDIT_CARD": r'\b(?:\d[ -]*?){13,16}\b',
    "IP_ADDRESS": r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b',
}

def luhn_checksum(digits: str) -> bool:
    """Validate numeric string using the standard Luhn algorithm."""
    checksum = 0
    for i, d in enumerate(reversed(digits)):
        val = int(d)
        if i % 2 == 1:
            val = val * 2
            checksum += (val - 9) if val > 9 else val
        else:
            checksum += val
    return checksum % 10 == 0


def detect_regex(text: str) -> List[Dict[str, Any]]:
    findings = []
    
    for pii_type, pattern in REGEX_PATTERNS.items():
        for match in re.finditer(pattern, text):
            match_text = match.group(0)
            
            # Additional validation for credit card using Luhn check
            if pii_type == "CREDIT_CARD":
                digits = re.sub(r'\D', '', match_text)
                if len(digits) < 13 or len(digits) > 16:
                    continue
                if not luhn_checksum(digits):
                    continue
                    
            if pii_type == "PHONE":
                 # very basic phone filtering
                 digits = re.sub(r'\D', '', match_text)
                 if len(digits) < 10:
                     continue

            findings.append({
                "text": match_text,
                "start": match.start(),
                "end": match.end(),
                "pii_type": pii_type,
                "confidence": 0.95,
                "detection_method": "REGEX"
            })
            
    return findings
