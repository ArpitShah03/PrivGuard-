import re
from typing import List, Dict, Any, Optional, Tuple
from detection.multimodal.schemas import MultimodalCandidateItem
from detection.multimodal.layout_features import extract_layout_features
from detection.multimodal.context_features import extract_context_features
from detection.algorithmic_validators import validate_pan, validate_ssn, validate_luhn

CORPORATE_STOPWORDS = {
    "optiv", "amazon", "cadence", "department", "handbook", "policy", "project",
    "section", "overview", "standard", "procedure", "infrastructure", "operations"
}


def extract_text_surface_features(text: str) -> Dict[str, float]:
    """Calculate statistical, lexical, and structural text features."""
    t = text.strip()
    total_len = max(1, len(t))
    tokens = t.split()
    token_count = float(len(tokens))

    upper_count = sum(1 for c in t if c.isupper())
    digit_count = sum(1 for c in t if c.isdigit())
    punct_count = sum(1 for c in t if not c.isalnum() and not c.isspace())
    alnum_count = sum(1 for c in t if c.isalnum())

    has_at = 1.0 if "@" in t and "." in t else 0.0
    has_phone_sep = 1.0 if re.search(r'[\+\-\(\)]\d', t) else 0.0
    has_ssn_pattern = 1.0 if re.search(r'\b\d{3}[- ]\d{2}[- ]\d{4}\b', t) else 0.0
    has_pan_pattern = 1.0 if re.search(r'\b[A-Z]{5}\d{4}[A-Z]\b', t) else 0.0
    has_masked_pattern = 1.0 if re.search(r'(?:X{2,}|\*{2,})', t, re.IGNORECASE) else 0.0
    has_secret_shape = 1.0 if (len(t) >= 24 and re.match(r'^[a-fA-F0-9]{24,}$', t)) else 0.0

    # Token immunity check: [PERSON_001]
    is_replacement_token = 1.0 if re.match(r'^\[[A-Z_]+_\d+\]$', t) else 0.0

    # Corporate stopword check
    is_corporate_stopword = 1.0 if any(w in t.lower().split() for w in CORPORATE_STOPWORDS) else 0.0

    has_digits = 1.0 if digit_count > 0 else 0.0
    is_pure_name = 1.0 if (len(tokens) in (1, 2, 3, 4) and t.replace(" ", "").replace(".", "").isalpha() and any(w[0].isupper() for w in tokens if w)) else 0.0
    is_masked_ssn = 1.0 if re.search(r'\b(?:XXX|xxx|\*\*\*)[- ]', t) else 0.0
    is_masked_email = 1.0 if re.search(r'[\w\.-]+\*+@', t) else 0.0
    is_masked_cc = 1.0 if re.search(r'\*{4}', t) else 0.0

    return {
        "token_count": min(50.0, token_count),
        "char_count": min(500.0, float(len(t))),
        "uppercase_ratio": round(upper_count / total_len, 4),
        "digit_ratio": round(digit_count / total_len, 4),
        "punctuation_ratio": round(punct_count / total_len, 4),
        "alphanumeric_ratio": round(alnum_count / total_len, 4),
        "has_at_symbol": has_at,
        "has_phone_separators": has_phone_sep,
        "has_ssn_pattern": has_ssn_pattern,
        "has_pan_pattern": has_pan_pattern,
        "has_masked_pattern": has_masked_pattern,
        "has_secret_shape": has_secret_shape,
        "is_replacement_token": is_replacement_token,
        "is_corporate_stopword": is_corporate_stopword,
        "has_digits": has_digits,
        "is_pure_name": is_pure_name,
        "is_masked_ssn": is_masked_ssn,
        "is_masked_email": is_masked_email,
        "is_masked_cc": is_masked_cc,
    }


def evaluate_ocr_candidate_repairs(text: str, is_ocr: bool) -> Tuple[Dict[str, float], Optional[str]]:
    """
    Evaluate optical noise indicators and check if OCR substitutions yield valid PII.
    Only repairs when is_ocr=True and validation strictly succeeds.
    """
    if not is_ocr:
        return {"ocr_has_noise_chars": 0.0, "ocr_repair_validated": 0.0}, None

    t = text.strip()
    has_ambiguous_chars = 1.0 if re.search(r'[0O1Il5S8B2Z]', t) else 0.0

    # Attempt targeted candidate repairs:
    # 1. PAN candidate repair: e.g. ABCPEI234K -> ABCPE1234K
    repaired_pan = None
    if len(t) == 10 and re.match(r'^[A-Z]{3}[A-Z]{2}[0-9A-Z]{4}[A-Z]$', t):
        # Substitute common OCR digit confusions in digit positions (index 5 to 8)
        prefix = t[:5]
        digits_part = t[5:9].replace('I', '1').replace('l', '1').replace('O', '0').replace('S', '5').replace('B', '8').replace('Z', '2')
        suffix = t[9]
        candidate = f"{prefix}{digits_part}{suffix}"
        if re.match(r'^[A-Z]{5}\d{4}[A-Z]$', candidate):
            is_valid_pan, _ = validate_pan(candidate)
            if is_valid_pan:
                repaired_pan = candidate

    # 2. SSN candidate repair: 000-4S-782I -> 000-45-7821
    repaired_ssn = None
    if len(t) == 11 and t[3] in "- " and t[6] in "- ":
        c_ssn = t.replace('S', '5').replace('s', '5').replace('O', '0').replace('o', '0').replace('I', '1').replace('l', '1')
        if re.match(r'^\d{3}[- ]\d{2}[- ]\d{4}$', c_ssn):
            if validate_ssn(c_ssn):
                repaired_ssn = c_ssn

    best_repair = repaired_pan or repaired_ssn
    repair_valid = 1.0 if best_repair is not None else 0.0

    return {
        "ocr_has_noise_chars": has_ambiguous_chars,
        "ocr_repair_validated": repair_valid,
    }, best_repair


class MultimodalFeatureExtractor:
    """
    Master feature extractor combining text, spatial layout, context window,
    table structures, relationship graphs, and OCR repairs.
    """
    def __init__(self):
        # Standard ordered list of feature names to guarantee deterministic alignment
        self.feature_names = [
            # Text surface features
            "token_count", "char_count", "uppercase_ratio", "digit_ratio",
            "punctuation_ratio", "alphanumeric_ratio", "has_at_symbol",
            "has_phone_separators", "has_ssn_pattern", "has_pan_pattern",
            "has_masked_pattern", "has_secret_shape", "is_replacement_token",
            "is_corporate_stopword", "has_digits", "is_pure_name",
            "is_masked_ssn", "is_masked_email", "is_masked_cc",
            # OCR features
            "ocr_has_noise_chars", "ocr_repair_validated",
            # Layout features
            "width", "height", "area", "aspect_ratio", "center_x", "center_y",
            "is_header_region", "is_footer_region", "is_left_margin", "is_right_margin",
            "nearby_block_count", "nearest_block_distance", "has_left_neighbor",
            "has_top_neighbor", "horizontally_aligned_count", "vertically_aligned_count",
            # Context & anchor features
            "anchor_name", "anchor_email", "anchor_phone", "anchor_empid",
            "anchor_ssn", "anchor_pan", "anchor_din", "anchor_vendid",
            "anchor_bank", "anchor_secret",
            # Table features
            "is_table_cell", "table_row_idx", "table_col_idx",
            "header_has_name", "header_has_email", "header_has_phone",
            "header_has_id", "header_has_bank",
            # Relationship features
            "relationship_count", "rel_manages", "rel_reports_to", "rel_same_entity",
            "rel_belongs_to", "rel_associated_with", "is_org_chart_node",
            # Source flags
            "is_ocr_source", "ocr_confidence", "is_shape_source", "is_metadata_source"
        ]

    def extract_features(
        self,
        target_item: MultimodalCandidateItem,
        all_items: Optional[List[MultimodalCandidateItem]] = None
    ) -> Tuple[Dict[str, float], Optional[str]]:
        """
        Extract complete feature map and repaired normalized text (if applicable).
        """
        features: Dict[str, float] = {}

        # 1. Text features
        features.update(extract_text_surface_features(target_item.text))

        # 2. OCR candidate features
        ocr_feats, repaired_text = evaluate_ocr_candidate_repairs(target_item.text, target_item.is_ocr)
        features.update(ocr_feats)

        # 3. Layout features
        features.update(extract_layout_features(target_item, all_items))

        # 4. Context, Table, and Relationship features
        features.update(extract_context_features(target_item, all_items))

        # Ensure all registered feature names exist with defaults
        for fname in self.feature_names:
            if fname not in features:
                features[fname] = 0.0

        return features, repaired_text

    def to_vector(self, feature_map: Dict[str, float]) -> List[float]:
        """Convert feature dictionary to ordered float vector for scikit-learn model."""
        return [float(feature_map.get(k, 0.0)) for k in self.feature_names]
