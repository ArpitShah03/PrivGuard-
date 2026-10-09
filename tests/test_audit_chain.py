import time
import pytest
from reporting.audit_hasher import AuditHasher, GENESIS_HASH
from audit.audit_store import AuditStore
from audit.models import AuditEvent, ScanRecord


def test_audit_hasher_hash_computation():
    hasher = AuditHasher
    prev_hash = GENESIS_HASH
    ts = 1700000000.0
    payload = {"event_id": "ev-1", "stage": "SCAN", "message": "Started"}
    
    h1 = hasher.compute_hash(prev_hash, ts, "SCAN", payload)
    assert len(h1) == 64
    # Determinism test
    h2 = hasher.compute_hash(prev_hash, ts, "SCAN", payload)
    assert h1 == h2


def test_audit_store_hash_chain_verification(tmp_path):
    db_file = str(tmp_path / "chain_audit.db")
    store = AuditStore(db_file)
    
    # Insert multiple sequential events
    scan_id = "scan-chain-01"
    store.record_scan(ScanRecord(
        scan_id=scan_id, timestamp=time.time(), filename="test.pdf",
        file_type="pdf", processing_status="SUCCESS", total_blocks=5,
        inspected_blocks=5, uncertain_blocks=0, coverage_percentage=100.0,
        pii_before=1, pii_after=0, high_risk_residual=0,
        security_decision="SANITIZED", decision_reason="Clean"
    ))
    
    ev1 = AuditEvent(event_id="e1", scan_id=scan_id, timestamp=time.time(), stage="EXTRACTION", status="SUCCESS", message="Extracted 5 blocks")
    store.record_event(ev1)
    
    ev2 = AuditEvent(event_id="e2", scan_id=scan_id, timestamp=time.time() + 0.1, stage="DETECTION", status="SUCCESS", message="Found 1 PII")
    store.record_event(ev2)
    
    ev3 = AuditEvent(event_id="e3", scan_id=scan_id, timestamp=time.time() + 0.2, stage="DECISION", status="SUCCESS", message="Sanitized safe")
    store.record_event(ev3)
    
    # Verify chain
    is_valid, count, err = AuditHasher.verify_event_chain(db_file)
    assert is_valid is True
    assert count == 3
    assert err is None


def test_audit_chain_detects_tampering(tmp_path):
    import sqlite3
    db_file = str(tmp_path / "tampered_audit.db")
    store = AuditStore(db_file)
    scan_id = "scan-tamper-01"
    
    ev1 = AuditEvent(event_id="e1", scan_id=scan_id, timestamp=100.0, stage="STAGE1", status="SUCCESS", message="Original msg 1")
    store.record_event(ev1)
    ev2 = AuditEvent(event_id="e2", scan_id=scan_id, timestamp=101.0, stage="STAGE2", status="SUCCESS", message="Original msg 2")
    store.record_event(ev2)
    
    # Tamper with message in e1 directly in sqlite
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    c.execute("UPDATE audit_events SET message = 'MALICIOUS MODIFICATION' WHERE event_id = 'e1'")
    conn.commit()
    conn.close()
    
    # Chain verification MUST fail
    is_valid, count, err = AuditHasher.verify_event_chain(db_file)
    assert is_valid is False
    assert "tampering detected" in err.lower() or "broken" in err.lower()
