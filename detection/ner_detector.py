import re
import spacy
from typing import List, Dict, Any

try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    nlp = None

COMMON_NON_PERSONS = {
    "email", "phone", "address", "date", "name", "title", "author",
    "fax", "tel", "mobile", "contact", "id", "mr", "ms", "mrs", "dr",
    "section", "page", "slide", "table", "document", "confidential",
    "optiv", "tprm", "cadence", "workflow", "vendors", "vendor",
    "supplier", "client", "contractor", "policy", "framework",
    "management", "governance", "assessment", "compliance", "audit",
    "architecture", "gateway", "service", "services"
}


def detect_ner(text: str) -> List[Dict[str, Any]]:
    findings = []
    if not nlp or not text:
        return findings

    doc = nlp(text)

    for ent in doc.ents:
        if ent.label_ == "PERSON":
            ent_str = ent.text.strip()
            # Discard redaction tokens, false-positive standalone stop words, or too short strings
            if (ent_str.startswith("[") and ent_str.endswith("]")) or ent_str.lower() in COMMON_NON_PERSONS or len(ent_str) < 2:
                continue

            # Check if person entity inadvertently swallowed an attached email
            email_match = re.search(r'\s*[-–—:]?\s*[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', ent_str)
            if email_match:
                clean_name = ent_str[:email_match.start()].strip()
                if clean_name and clean_name.lower() not in COMMON_NON_PERSONS and len(clean_name) >= 2:
                    findings.append({
                        "text": clean_name,
                        "start": ent.start_char,
                        "end": ent.start_char + len(clean_name),
                        "pii_type": "PERSON",
                        "confidence": 0.85,
                        "detection_method": "NER"
                    })
                continue

            findings.append({
                "text": ent_str,
                "start": ent.start_char,
                "end": ent.end_char,
                "pii_type": "PERSON",
                "confidence": 0.85,
                "detection_method": "NER"
            })
        elif ent.label_ in ["GPE", "LOC"]:
            findings.append({
                "text": ent.text,
                "start": ent.start_char,
                "end": ent.end_char,
                "pii_type": "ADDRESS",  # mapped from GPE/LOC
                "confidence": 0.70,     # Lower confidence for generic locations
                "detection_method": "NER"
            })
        elif ent.label_ == "DATE":
            findings.append({
                "text": ent.text,
                "start": ent.start_char,
                "end": ent.end_char,
                "pii_type": "DATE_OF_BIRTH",  # context will boost this
                "confidence": 0.50,          # Low initial confidence, needs context
                "detection_method": "NER"
            })

    return findings
