import re
from typing import List, Dict, Any

CONTEXT_RULES = [
    {
        "regex": r'(?i)(?:employee[ \t]*(?:id|number|no\.?)|emp[ \t]*id)[ \t]*(?:[:#-][ \t]*|[ \t]+)([A-Za-z0-9-]+)',
        "pii_type": "EMPLOYEE_ID",
        "confidence": 0.90
    },
    {
        "regex": r'(?i)(?:gov(?:ernment)?[ \t]*id|ssn|social[ \t]*security|national[ \t]*id)[ \t]*(?:[:#-][ \t]*|[ \t]+)([A-Za-z0-9-]+)',
        "pii_type": "GOVERNMENT_ID",
        "confidence": 0.95
    },
    {
        "regex": r'(?i)(?:dob|date[ \t]*of[ \t]*birth|birth[ \t]*date)[ \t]*(?:[:#-][ \t]*|[ \t]+)(\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4})',
        "pii_type": "DATE_OF_BIRTH",
        "confidence": 0.90
    },
    {
        "regex": r'(?i)(?:signed[ \t]*(?:off)?[ \t]*by|reviewed[ \t]*by|approved[ \t]*by|prepared[ \t]*by|author|auditor|analyst|ciso|officer)[ \t]*(?:[:#-][ \t]*|[ \t]+)([A-Z][a-z]*\.?\s+[A-Z][a-z]+)',
        "pii_type": "PERSON",
        "confidence": 0.88
    }
]

def detect_context(text: str) -> List[Dict[str, Any]]:
    findings = []
    
    for rule in CONTEXT_RULES:
        for match in re.finditer(rule["regex"], text):
            # Extract the actual value, not the context words
            value = match.group(1)
            start = match.start(1)
            end = match.end(1)
            
            findings.append({
                "text": value,
                "start": start,
                "end": end,
                "pii_type": rule["pii_type"],
                "confidence": rule["confidence"],
                "detection_method": "CONTEXT"
            })
            
    return findings
