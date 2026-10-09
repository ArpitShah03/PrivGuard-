import os
import tempfile
import pytest
from audit.models import ScanRecord
from audit.audit_store import AuditStore
from audit.audit_logger import AuditLogger
from metrics.security_metrics import compute_operational_and_security_metrics


def test_operational_and_security_metrics_calculation():
    """Verify aggregated operational and security metrics across multiple scans."""
    scans = [
        ScanRecord("s1", 100.0, "clean.docx", "docx", "SUCCESS", 100, 100, 0, 100.0, 5, 0, 0, "SANITIZED", "Safe", total_time_ms=120.0),
        ScanRecord("s2", 101.0, "leaked.pptx", "pptx", "SUCCESS", 50, 50, 0, 100.0, 8, 2, 2, "BLOCKED", "Blocked", total_time_ms=90.0),
        ScanRecord("s3", 102.0, "scanned.pdf", "pdf", "SUCCESS", 40, 5, 35, 12.5, 2, 2, 2, "HUMAN_REVIEW", "Review needed", total_time_ms=210.0),
    ]

    metrics = compute_operational_and_security_metrics(scans)

    assert metrics["total_documents_scanned"] == 3
    assert metrics["documents_sanitized"] == 1
    assert metrics["documents_blocked"] == 1
    assert metrics["documents_human_review"] == 1
    assert metrics["sanitization_rate_pct"] == 33.33
    assert metrics["block_rate_pct"] == 33.33
    assert metrics["human_review_rate_pct"] == 33.33
    assert metrics["total_blocks"] == 190
    assert metrics["inspected_blocks"] == 155
    assert metrics["uncertain_blocks"] == 35
    assert metrics["overall_extraction_coverage_pct"] == round(155 / 190 * 100.0, 2)
    assert metrics["total_pii_detected_before"] == 15
    assert metrics["total_residual_pii_after"] == 4
    assert metrics["total_high_risk_residual"] == 4
    assert metrics["average_processing_time_ms"] == round((120.0 + 90.0 + 210.0) / 3, 2)
    assert "docx" in metrics["avg_processing_time_by_type"]
    assert "pdf" in metrics["avg_processing_time_by_type"]


def test_coverage_calculation_and_recall_separation():
    """
    CRITICAL EVALUATION DISTINCTION:
    Verify extraction coverage measures block visibility, not detection recall.
    Ensure disclaimer is present.
    """
    scans = [
        ScanRecord("s4", 200.0, "org.pptx", "pptx", "SUCCESS", 388, 379, 9, 97.68, 88, 6, 6, "HUMAN_REVIEW", "Review", total_time_ms=150.0)
    ]
    metrics = compute_operational_and_security_metrics(scans)

    assert metrics["overall_extraction_coverage_pct"] == 97.68
    assert "coverage_disclaimer" in metrics
    assert "distinct from detection recall" in metrics["coverage_disclaimer"]


def test_sqlite_persistence_and_querying():
    """Verify that scan records persist cleanly across separate AuditStore instances."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "persist_test.db")

        store1 = AuditStore(db_path=db_path)
        logger1 = AuditLogger(store=store1)
        logger1.finalize_scan(
            scan_id="persist_001",
            filename="test.docx",
            file_type="docx",
            total_blocks=50,
            uncertain_blocks=0,
            pii_before=4,
            pii_after=0,
            high_risk_residual=0,
            security_decision="SANITIZED",
            timing_stats={"total_ms": 145.2}
        )

        # Open completely new store connection to same SQLite file
        store2 = AuditStore(db_path=db_path)
        record = store2.get_scan("persist_001")

        assert record is not None
        assert record.filename == "test.docx"
        assert record.security_decision == "SANITIZED"
        assert record.coverage_percentage == 100.0
        assert record.total_time_ms == 145.2
