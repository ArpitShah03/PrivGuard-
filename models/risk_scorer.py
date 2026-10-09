from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from models.schemas import PIIFinding


@dataclass
class RiskScore:
    score: int  # 0 to 100
    category: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    severity_breakdown: Dict[str, int]
    contributing_factors: List[str]
    identity_correlation_detected: bool
    hard_gate_active: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "category": self.category,
            "severity_breakdown": self.severity_breakdown,
            "contributing_factors": self.contributing_factors,
            "identity_correlation_detected": self.identity_correlation_detected,
            "hard_gate_active": self.hard_gate_active
        }


class PIIRiskScorer:
    """
    Deterministic Document PII Risk Scorer (0 to 100).
    Aggregates findings, severity weights, identity correlation, and extraction uncertainty.
    HARD GATE INVARIANT: Risk score NEVER overrides security decisions or gates.
    """

    SEVERITY_WEIGHTS = {
        "CRITICAL": 25,
        "HIGH": 10,
        "MEDIUM": 5,
        "LOW": 2
    }

    @classmethod
    def calculate_risk(
        cls,
        findings: List[PIIFinding],
        uncertain_blocks: int = 0,
        residual_pii: int = 0
    ) -> RiskScore:
        factors: List[str] = []
        sev_counts: Dict[str, int] = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}

        # 1. Base Score from Findings
        raw_score = 0
        detected_types = set()

        for f in findings:
            sev = f.severity.upper() if f.severity else "LOW"
            if sev not in sev_counts:
                sev = "LOW"
            sev_counts[sev] += 1
            raw_score += cls.SEVERITY_WEIGHTS.get(sev, 2)
            detected_types.add(f.pii_type.upper())

        if findings:
            factors.append(f"Identified {len(findings)} sensitive entities across {len(detected_types)} categories.")

        # 2. Multi-Entity Identity Correlation Penalty
        has_person = "PERSON" in detected_types
        has_id_secret = bool(detected_types.intersection({"SSN", "GOVERNMENT_ID", "CREDIT_CARD", "PAN", "PASSPORT", "SECRET"}))
        has_contact = bool(detected_types.intersection({"EMAIL", "PHONE", "ADDRESS"}))

        identity_corr = False
        if has_person and has_id_secret and has_contact:
            raw_score += 20
            identity_corr = True
            factors.append("Multi-entity correlation detected: Full identity vector (Person + Government/Financial ID + Contact Details).")

        # 3. Extraction Uncertainty Penalty
        if uncertain_blocks > 0:
            raw_score += 15
            factors.append(f"Extraction ambiguity: {uncertain_blocks} blocks have uninspected/low-confidence OCR text.")

        # 4. Residual PII Penalty (Instant Critical Max)
        hard_gate = False
        if residual_pii > 0:
            raw_score = 100
            hard_gate = True
            factors.append(f"CRITICAL GATE: {residual_pii} residual PII entities detected post-redaction.")

        # Clamp score to [0, 100]
        final_score = min(100, max(0, int(raw_score)))

        # Categorize
        if final_score >= 70 or residual_pii > 0:
            category = "CRITICAL"
        elif final_score >= 40:
            category = "HIGH"
        elif final_score >= 20:
            category = "MEDIUM"
        else:
            category = "LOW"

        return RiskScore(
            score=final_score,
            category=category,
            severity_breakdown=sev_counts,
            contributing_factors=factors,
            identity_correlation_detected=identity_corr,
            hard_gate_active=hard_gate
        )


default_risk_scorer = PIIRiskScorer()
