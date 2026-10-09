from typing import Dict, Any, List, Optional
from detection.multimodal.schemas import EvidenceBreakdown, MultimodalPrediction


class MultimodalEvidenceScorer:
    """
    Computes explainable evidence breakdowns across text, layout, table,
    OCR, and relationship dimensions, and calibrates confidence tiers.
    """
    def __init__(
        self,
        high_threshold: float = 0.85,
        medium_threshold: float = 0.65,
        low_threshold: float = 0.45
    ):
        self.high_threshold = high_threshold
        self.medium_threshold = medium_threshold
        self.low_threshold = low_threshold

    def calculate_evidence(self, feature_map: Dict[str, float]) -> EvidenceBreakdown:
        """Calculate normalized dimensional evidence scores from feature map."""
        # 1. Text Pattern Evidence (0.0 to 1.0)
        text_signals = [
            feature_map.get("has_at_symbol", 0.0) * 1.0,
            feature_map.get("has_phone_separators", 0.0) * 0.9,
            feature_map.get("has_ssn_pattern", 0.0) * 0.95,
            feature_map.get("has_pan_pattern", 0.0) * 0.95,
            feature_map.get("has_secret_shape", 0.0) * 0.98,
            feature_map.get("has_masked_pattern", 0.0) * 0.85,
            (0.8 if 0.1 <= feature_map.get("digit_ratio", 0.0) <= 0.8 else 0.0),
            (0.6 if feature_map.get("uppercase_ratio", 0.0) >= 0.25 else 0.0)
        ]
        text_score = min(1.0, max(text_signals))

        # 2. Layout Context Evidence
        layout_signals = [
            feature_map.get("has_left_neighbor", 0.0) * 0.8,
            feature_map.get("has_top_neighbor", 0.0) * 0.7,
            (0.6 if feature_map.get("nearby_block_count", 0.0) >= 2 else 0.2),
            (0.5 if feature_map.get("aspect_ratio", 1.0) >= 2.0 else 0.1)
        ]
        layout_score = min(1.0, sum(layout_signals) / max(1.0, len(layout_signals)) * 1.5)

        # 3. Table Context Evidence
        table_signals = [
            feature_map.get("is_table_cell", 0.0) * 0.5,
            feature_map.get("header_has_name", 0.0) * 0.95,
            feature_map.get("header_has_email", 0.0) * 0.95,
            feature_map.get("header_has_phone", 0.0) * 0.95,
            feature_map.get("header_has_id", 0.0) * 0.95,
            feature_map.get("header_has_bank", 0.0) * 0.95,
        ]
        table_score = min(1.0, max(table_signals))

        # 4. OCR Evidence
        ocr_repair = feature_map.get("ocr_repair_validated", 0.0)
        ocr_conf = feature_map.get("ocr_confidence", 1.0)
        is_ocr = feature_map.get("is_ocr_source", 0.0)
        ocr_score = 0.95 if ocr_repair > 0.0 else (0.4 if is_ocr else 0.0)

        # 5. Relationship Context Evidence
        rel_signals = [
            feature_map.get("rel_same_entity", 0.0) * 0.95,
            feature_map.get("rel_manages", 0.0) * 0.90,
            feature_map.get("rel_reports_to", 0.0) * 0.90,
            feature_map.get("rel_belongs_to", 0.0) * 0.85,
            feature_map.get("rel_associated_with", 0.0) * 0.75,
            (0.5 if feature_map.get("relationship_count", 0.0) > 0 else 0.0)
        ]
        rel_score = min(1.0, max(rel_signals))

        summary_parts = []
        if text_score >= 0.7:
            summary_parts.append(f"Strong text pattern ({text_score:.2f})")
        if table_score >= 0.7:
            summary_parts.append(f"Table header alignment ({table_score:.2f})")
        if rel_score >= 0.7:
            summary_parts.append(f"Relationship graph link ({rel_score:.2f})")
        if ocr_score >= 0.7:
            summary_parts.append(f"Validated OCR candidate repair ({ocr_score:.2f})")

        return EvidenceBreakdown(
            text_pattern=round(text_score, 3),
            layout_context=round(layout_score, 3),
            table_context=round(table_score, 3),
            ocr_evidence=round(ocr_score, 3),
            relationship_context=round(rel_score, 3),
            summary="; ".join(summary_parts) if summary_parts else "Standard multimodal features"
        )

    def calibrate_confidence_level(self, score: float) -> str:
        """Categorize raw probability into standardized enterprise confidence tier."""
        if score >= self.high_threshold:
            return "HIGH"
        elif score >= self.medium_threshold:
            return "MEDIUM"
        return "LOW"
