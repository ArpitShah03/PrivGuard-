from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from models.schemas import PIIFinding


@dataclass
class FindingExplanation:
    finding_id: str
    pii_type: str
    primary_detector: str
    corroborating_sources: List[str]
    trigger_keywords: List[str]
    algorithmic_checks: List[str]
    confidence_score: float
    agreement_category: str
    decision_summary: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "pii_type": self.pii_type,
            "primary_detector": self.primary_detector,
            "corroborating_sources": self.corroborating_sources,
            "trigger_keywords": self.trigger_keywords,
            "algorithmic_checks": self.algorithmic_checks,
            "confidence_score": round(self.confidence_score, 3),
            "agreement_category": self.agreement_category,
            "decision_summary": self.decision_summary
        }


class DetectionExplainer:
    """
    Generates explainable AI provenance records and decision rationale for PII findings.
    Provides complete audit transparency without leaking raw PII values.
    """

    @classmethod
    def explain_finding(cls, finding: PIIFinding) -> FindingExplanation:
        methods = finding.detection_method or []
        primary = methods[0] if methods else "UNKNOWN"
        corroborating = methods[1:] if len(methods) > 1 else []

        val_details = getattr(finding, "validation_details", {}) or {}
        evidence = getattr(finding, "evidence", {}) or {}

        # Algorithmic checks passed
        algo_checks = []
        if val_details.get("luhn_valid"):
            algo_checks.append("Luhn Checksum (ISO/IEC 7812) PASSED")
        if val_details.get("verhoeff_valid"):
            algo_checks.append("Verhoeff Checksum PASSED")
        if val_details.get("checksum_valid"):
            algo_checks.append("Mathematical Checksum PASSED")
        if val_details.get("format_valid"):
            algo_checks.append("Standard Pattern Format VALID")

        # Context keywords
        trigger_kws = []
        if "context_keyword" in evidence:
            trigger_kws.append(evidence["context_keyword"])
        if "surrounding_context" in evidence and evidence["surrounding_context"]:
            ctx = evidence["surrounding_context"]
            if isinstance(ctx, str):
                trigger_kws.append(ctx[:30])
        if "trigger_keyword" in val_details:
            trigger_kws.append(val_details["trigger_keyword"])

        # Determine agreement category
        agreement = getattr(finding, "detector_agreement", None)
        if not agreement:
            if len(methods) > 1:
                agreement = "MULTI_DETECTOR_AGREEMENT"
            elif any("ALGO" in m.upper() for m in methods):
                agreement = "CHECKSUM_VERIFIED"
            elif any("VISUAL" in m.upper() for m in methods):
                agreement = "VISUAL_DETECTION"
            else:
                agreement = "SINGLE_DETECTOR"

        # Formulate human-readable decision summary
        summary_parts = [
            f"Classified as '{finding.pii_type}' with {finding.confidence*100:.1f}% confidence."
        ]
        if algo_checks:
            summary_parts.append(f"Mathematical verification confirmed: {', '.join(algo_checks)}.")
        if trigger_kws:
            summary_parts.append(f"Corroborated by context signals: {', '.join(set(trigger_kws))}.")
        if finding.is_masked:
            summary_parts.append("Identified as partially masked/tokenized sensitive entity.")
        if getattr(finding, "is_ocr", False):
            summary_parts.append("Extracted via optical character recognition with normalizer recovery.")

        decision_summary = " ".join(summary_parts)

        return FindingExplanation(
            finding_id=finding.finding_id,
            pii_type=finding.pii_type,
            primary_detector=primary,
            corroborating_sources=corroborating,
            trigger_keywords=trigger_kws,
            algorithmic_checks=algo_checks,
            confidence_score=finding.confidence,
            agreement_category=agreement,
            decision_summary=decision_summary
        )

    @classmethod
    def explain_all(cls, findings: List[PIIFinding]) -> List[FindingExplanation]:
        return [cls.explain_finding(f) for f in findings]


default_explainer = DetectionExplainer()
