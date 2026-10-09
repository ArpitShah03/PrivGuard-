from typing import Dict, Any, Optional, Tuple


class ThresholdManager:
    """
    Manages decision boundaries according to the strict security hierarchy:

                    EXTRACTION UNCERTAINTY?
                         /          \\
                       YES           NO
                       ↓              ↓
                HUMAN_REVIEW    Strong deterministic?
                                  /          \\
                                YES           NO
                                ↓              ↓
                              DETECT      Calibrated score
                                           /       |       \\
                                       HIGH     BORDERLINE   LOW
                                        ↓          ↓          ↓
                                      DETECT   HUMAN_REVIEW SUPPRESS
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or {}
        fusion_cfg = cfg.get("fusion", {})
        self.high_threshold = float(fusion_cfg.get("high_threshold", 0.70))
        self.lower_threshold = float(fusion_cfg.get("lower_threshold", 0.45))
        self.security_policy = cfg.get("security_policy", {})

    def determine_decision(
        self,
        calibrated_confidence: float,
        is_deterministic: bool = False,
        is_extraction_uncertain: bool = False,
        is_suppressed_by_rule: bool = False,
        uncertainty_reason: Optional[str] = None
    ) -> Tuple[str, Optional[str]]:
        """
        Evaluate candidate confidence against decision policy hierarchy.
        Returns (decision, uncertainty_reason) where decision is one of:
        - "DETECT"
        - "HUMAN_REVIEW"
        - "SUPPRESS"
        """
        # GATE 1: Extraction uncertainty priority (fail-closed)
        # SUPPRESS must NEVER override extraction uncertainty!
        if is_extraction_uncertain:
            reason = uncertainty_reason or "Extraction uncertainty detected; cannot verify safe classification"
            return "HUMAN_REVIEW", reason

        # GATE 2: Strong deterministic evidence priority
        if is_deterministic:
            return "DETECT", None

        # GATE 3: Explicit rule suppression (Token immunity / Hard negatives)
        if is_suppressed_by_rule:
            return "SUPPRESS", None

        # GATE 4: Calibrated confidence tiers
        if calibrated_confidence >= self.high_threshold:
            return "DETECT", None
        elif calibrated_confidence >= self.lower_threshold:
            reason = uncertainty_reason or f"Borderline calibrated confidence ({calibrated_confidence:.2f}) in uncertainty window [{self.lower_threshold}, {self.high_threshold})"
            return "HUMAN_REVIEW", reason
        else:
            return "SUPPRESS", None
