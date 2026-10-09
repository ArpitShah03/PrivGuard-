import re
from typing import List, Dict, Any, Optional
from detection.multimodal.schemas import MultimodalCandidateItem

# Semantic PII keyword anchors for label -> value pattern recognition
ANCHOR_KEYWORDS = {
    "name": ["name:", "full name:", "employee name:", "candidate:", "author:", "director:"],
    "email": ["email:", "e-mail:", "email address:", "contact email:", "account email:"],
    "phone": ["phone:", "tel:", "mobile:", "contact:", "phone no:", "call:"],
    "empid": ["employee id:", "emp id:", "emp-", "badge:", "staff id:", "worker id:"],
    "ssn": ["ssn:", "social security:", "social sec:", "ssn no:"],
    "pan": ["pan:", "pan id:", "pan no:", "permanent account number:"],
    "din": ["din:", "director identification number:", "din no:"],
    "vendid": ["vendor id:", "supplier id:", "vendid:", "contractor id:"],
    "bank": ["account:", "acct #:", "account no:", "checking acct:", "ifsc:", "bank:"],
    "secret": ["api_key:", "vault key:", "secret:", "access token:", "bearer token:", "token:"]
}


def detect_label_value_cues(text: str, preceding_text: str) -> Dict[str, float]:
    """Check if preceding or current text exhibits strong label -> value anchor patterns."""
    combined = f"{preceding_text} {text}".lower()

    features = {}
    for anchor_type, patterns in ANCHOR_KEYWORDS.items():
        matched = 1.0 if any(pat in combined for pat in patterns) else 0.0
        features[f"anchor_{anchor_type}"] = matched

    return features


def extract_table_context_features(item: MultimodalCandidateItem) -> Dict[str, float]:
    """Capture tabular structure cues from cell position and header context."""
    is_table = 1.0 if item.source == "table" or item.modality == "TABLE" or item.metadata.get("is_table_cell") else 0.0
    row_idx = float(item.metadata.get("row_idx", item.metadata.get("row", 0)))
    col_idx = float(item.metadata.get("col_idx", item.metadata.get("col", 0)))
    header_text = str(item.metadata.get("header_text", "")).lower()

    header_has_name = 1.0 if any(k in header_text for k in ["name", "employee", "candidate"]) else 0.0
    header_has_email = 1.0 if "email" in header_text else 0.0
    header_has_phone = 1.0 if "phone" in header_text or "tel" in header_text else 0.0
    header_has_id = 1.0 if any(k in header_text for k in ["id", "empid", "din", "pan"]) else 0.0
    header_has_bank = 1.0 if any(k in header_text for k in ["bank", "ifsc", "account"]) else 0.0

    return {
        "is_table_cell": is_table,
        "table_row_idx": row_idx,
        "table_col_idx": col_idx,
        "header_has_name": header_has_name,
        "header_has_email": header_has_email,
        "header_has_phone": header_has_phone,
        "header_has_id": header_has_id,
        "header_has_bank": header_has_bank,
    }


def extract_relationship_context_features(item: MultimodalCandidateItem) -> Dict[str, float]:
    """Capture structural relationship graph cues (org-charts, hierarchy, same-entity)."""
    rels = item.relationships or []
    rel_count = float(len(rels))

    has_manages = 0.0
    has_reports_to = 0.0
    has_same_entity = 0.0
    has_belongs_to = 0.0
    has_associated_with = 0.0

    for r in rels:
        r_type = r.get("relationship_type", "").upper() if isinstance(r, dict) else getattr(r, "relationship_type", "").upper()
        if r_type == "MANAGES":
            has_manages = 1.0
        elif r_type == "REPORTS_TO":
            has_reports_to = 1.0
        elif r_type == "SAME_ENTITY":
            has_same_entity = 1.0
        elif r_type == "BELONGS_TO":
            has_belongs_to = 1.0
        elif r_type == "ASSOCIATED_WITH":
            has_associated_with = 1.0

    return {
        "relationship_count": min(10.0, rel_count),
        "rel_manages": has_manages,
        "rel_reports_to": has_reports_to,
        "rel_same_entity": has_same_entity,
        "rel_belongs_to": has_belongs_to,
        "rel_associated_with": has_associated_with,
        "is_org_chart_node": 1.0 if (has_manages or has_reports_to) else 0.0,
    }


def extract_context_features(
    target_item: MultimodalCandidateItem,
    all_items: Optional[List[MultimodalCandidateItem]] = None,
    window_size: int = 2
) -> Dict[str, float]:
    """Aggregate bounded neighboring text context, table headers, and relationship graph features."""
    features = {}

    preceding_text = ""
    succeeding_text = ""

    if all_items:
        # Find position in sorted list by order or block_id
        sorted_items = sorted(all_items, key=lambda x: (x.page_or_slide, x.metadata.get("order", 0)))
        try:
            idx = next(i for i, it in enumerate(sorted_items) if it.block_id == target_item.block_id)
            start_w = max(0, idx - window_size)
            end_w = min(len(sorted_items), idx + window_size + 1)

            prec_blocks = sorted_items[start_w:idx]
            succ_blocks = sorted_items[idx + 1:end_w]

            preceding_text = " ".join([b.text for b in prec_blocks])
            succeeding_text = " ".join([b.text for b in succ_blocks])
        except StopIteration:
            pass

    features.update(detect_label_value_cues(target_item.text, preceding_text))
    features.update(extract_table_context_features(target_item))
    features.update(extract_relationship_context_features(target_item))

    # Source & modality flags
    features["is_ocr_source"] = 1.0 if target_item.is_ocr or target_item.source == "OCR" else 0.0
    features["ocr_confidence"] = float(target_item.ocr_confidence) if target_item.is_ocr else 1.0
    features["is_shape_source"] = 1.0 if target_item.source == "shape" else 0.0
    features["is_metadata_source"] = 1.0 if target_item.source == "metadata" else 0.0

    return features
