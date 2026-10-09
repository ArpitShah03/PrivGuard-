import os
import tempfile
import pytest
from audit.audit_store import AuditStore
from audit.audit_logger import AuditLogger, generate_decision_reason
from models.schemas import PIIFinding


@pytest.fixture
def temp_audit_store():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test_audit.db")
        store = AuditStore(db_path=db_path)
        yield store


def test_audit_event_creation_and_timeline(temp_audit_store):
    """Verify chronological event recording and retrieval in audit timeline."""
    logger = AuditLogger(store=temp_audit_store)
    scan_id = "scan_test_001"

    logger.log_event(scan_id, "EXTRACTION", "SUCCESS", "Extracted 25 blocks", {"count": 25})
    logger.log_event(scan_id, "DETECTION", "SUCCESS", "Detected 3 findings", {"count": 3})
    logger.log_event(scan_id, "DECISION", "SUCCESS", "Final decision: SANITIZED", {"safe": True})

    events = temp_audit_store.get_events_for_scan(scan_id)
    assert len(events) == 3
    assert events[0].stage == "EXTRACTION"
    assert events[1].stage == "DETECTION"
    assert events[2].stage == "DECISION"
    assert events[0].metadata["count"] == 25


def test_raw_pii_strictly_not_written_to_audit_logs(temp_audit_store):
    """
    CRITICAL ENTERPRISE PRIVACY TEST:
    Raw PII, raw passwords, raw SSNs, and raw secrets must NEVER be written to audit tables.
    Only replacement tokens and safe metadata are permitted.
    """
    logger = AuditLogger(store=temp_audit_store)
    scan_id = "scan_privacy_001"

    raw_ssn = "219-45-7821"
    raw_secret = "a8f9c2d1e0b4a7c9d3e5f1b2"
    raw_email = "victim@confidential.corp"

    findings = [
        PIIFinding("f1", scan_id, "doc.txt", "p1", 0, 11, raw_ssn, "SSN", 0.98, ["REGEX"], "CRITICAL", replacement_token="[SSN_001]"),
        PIIFinding("f2", scan_id, "doc.txt", "p2", 0, 24, raw_secret, "SECRET", 0.95, ["ENTROPY"], "CRITICAL", replacement_token="[SECRET_001]"),
        PIIFinding("f3", scan_id, "doc.txt", "p3", 0, 24, raw_email, "EMAIL", 0.95, ["REGEX"], "HIGH", replacement_token="[EMAIL_001]")
    ]

    logger.log_findings(scan_id, findings)

    # Directly inspect database rows
    records = temp_audit_store.get_findings_for_scan(scan_id)
    assert len(records) == 3

    # Check finding audit records
    for r in records:
        # replacement_token must be present
        assert r.replacement_token in ["[SSN_001]", "[SECRET_001]", "[EMAIL_001]"]
        # Raw text must NOT exist on finding audit record
        assert not hasattr(r, "text")

    # Inspect raw SQLite database content as plain text
    with open(temp_audit_store.db_path, "rb") as f:
        db_raw_bytes = f.read()

    assert raw_ssn.encode("utf-8") not in db_raw_bytes
    assert raw_secret.encode("utf-8") not in db_raw_bytes
    assert raw_email.encode("utf-8") not in db_raw_bytes


def test_security_decision_reason_generation():
    """Verify explainable, explicit security decision explanations."""
    r_san = generate_decision_reason("SANITIZED")
    assert "inspected" in r_san
    assert "no residual high-risk PII" in r_san

    r_blk = generate_decision_reason("BLOCKED", residual_count=3)
    assert "residual high-risk PII" in r_blk
    assert "3 findings" in r_blk

    r_rev = generate_decision_reason("HUMAN_REVIEW", uncertain_blocks=9)
    assert "could not be inspected" in r_rev
    assert "9 uncertain" in r_rev
    assert "Fail-closed" in r_rev
