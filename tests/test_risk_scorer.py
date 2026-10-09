import pytest
from models.schemas import PIIFinding
from models.risk_scorer import PIIRiskScorer, default_risk_scorer


def test_risk_scorer_zero_pii():
    score = default_risk_scorer.calculate_risk(findings=[], uncertain_blocks=0, residual_pii=0)
    assert score.score == 0
    assert score.category == "LOW"
    assert score.hard_gate_active is False


def test_risk_scorer_critical_pii():
    f1 = PIIFinding("1", "d", "f", "l", 0, 5, "x", "SSN", 0.9, ["REGEX"], "CRITICAL")
    f2 = PIIFinding("2", "d", "f", "l", 0, 5, "x", "CREDIT_CARD", 0.9, ["ALGO"], "CRITICAL")
    
    score = default_risk_scorer.calculate_risk(findings=[f1, f2], uncertain_blocks=0, residual_pii=0)
    assert score.score >= 50
    assert score.severity_breakdown["CRITICAL"] == 2


def test_risk_scorer_identity_correlation():
    f_person = PIIFinding("1", "d", "f", "l", 0, 5, "x", "PERSON", 0.9, ["NER"], "HIGH")
    f_ssn = PIIFinding("2", "d", "f", "l", 0, 5, "x", "SSN", 0.9, ["REGEX"], "CRITICAL")
    f_email = PIIFinding("3", "d", "f", "l", 0, 5, "x", "EMAIL", 0.9, ["REGEX"], "HIGH")
    
    score = default_risk_scorer.calculate_risk(findings=[f_person, f_ssn, f_email])
    assert score.identity_correlation_detected is True
    assert score.score >= 65  # Base 10 + 25 + 10 + 20 (correlation) = 65


def test_risk_scorer_residual_pii_hard_gate():
    score = default_risk_scorer.calculate_risk(findings=[], uncertain_blocks=0, residual_pii=1)
    assert score.score == 100
    assert score.category == "CRITICAL"
    assert score.hard_gate_active is True
