import pytest
from models.schemas import PIIFinding
from detection.explainability import DetectionExplainer, default_explainer


def test_explainer_with_algorithmic_and_context_finding():
    finding = PIIFinding(
        finding_id="find-ssn-01",
        document_id="doc-01",
        file_name="payroll.pdf",
        location="Page 1, Para 2",
        start=10,
        end=21,
        text="[REDACTED]",
        pii_type="SSN",
        confidence=0.98,
        detection_method=["ALGORITHMIC_VALIDATOR", "REGEX_PATTERNS", "CONTEXT_RULES"],
        severity="CRITICAL",
        validation_details={"format_valid": True, "trigger_keyword": "SSN:"},
        evidence={"context_keyword": "Social Security Number"}
    )

    exp = default_explainer.explain_finding(finding)
    
    assert exp.finding_id == "find-ssn-01"
    assert exp.primary_detector == "ALGORITHMIC_VALIDATOR"
    assert "REGEX_PATTERNS" in exp.corroborating_sources
    assert len(exp.algorithmic_checks) >= 1
    assert any("SSN:" in kw or "Social Security" in kw for kw in exp.trigger_keywords)
    assert "Classified as 'SSN'" in exp.decision_summary
    assert exp.agreement_category == "MULTI_DETECTOR_AGREEMENT"


def test_explainer_single_detector():
    finding = PIIFinding(
        finding_id="find-email-01",
        document_id="doc-02",
        file_name="memo.txt",
        location="Line 4",
        start=0,
        end=15,
        text="[REDACTED]",
        pii_type="EMAIL",
        confidence=0.90,
        detection_method=["REGEX_PATTERNS"],
        severity="HIGH"
    )

    exp = default_explainer.explain_finding(finding)
    assert exp.primary_detector == "REGEX_PATTERNS"
    assert exp.corroborating_sources == []
    assert exp.agreement_category == "SINGLE_DETECTOR"
