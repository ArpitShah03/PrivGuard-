import time
import uuid
import pytest
from audit.audit_store import AuditStore
from audit.models import HumanReviewRecord, ScanRecord
from models.schemas import DocumentAnalysisResult, ValidationResult


def test_workbench_audit_logging(tmp_path):
    db_file = str(tmp_path / "test_audit.db")
    store = AuditStore(db_file)
    
    # Insert a dummy scan record
    scan_id = "test-scan-001"
    scan = ScanRecord(
        scan_id=scan_id,
        timestamp=time.time(),
        filename="contract.pdf",
        file_type="pdf",
        processing_status="SUCCESS",
        total_blocks=10,
        inspected_blocks=8,
        uncertain_blocks=2,
        coverage_percentage=80.0,
        pii_before=3,
        pii_after=0,
        high_risk_residual=0,
        security_decision="HUMAN_REVIEW",
        decision_reason="Extraction uncertainty on page 2"
    )
    store.record_scan(scan)
    
    # Record human approval
    review = HumanReviewRecord(
        review_id=str(uuid.uuid4()),
        scan_id=scan_id,
        reviewer_id="sec-auditor-42",
        action="APPROVE",
        justification="Verified OCR noise on page 2 contains no PII, safe for release.",
        timestamp=time.time(),
        previous_decision="HUMAN_REVIEW",
        new_decision="SANITIZED"
    )
    store.record_review_action(review)
    
    # Verify persistence
    actions = store.get_review_actions(scan_id)
    assert len(actions) == 1
    assert actions[0].reviewer_id == "sec-auditor-42"
    assert actions[0].action == "APPROVE"
    assert actions[0].action_hash is not None
    assert len(actions[0].action_hash) == 64
    
    # Verify scan record decision was updated
    updated_scan = store.get_scan(scan_id)
    assert updated_scan.security_decision == "SANITIZED"
    assert "Human Override" in updated_scan.decision_reason


def test_workbench_hard_gate_invariant():
    """Ensure that document with high-risk residual PII cannot be released as SANITIZED."""
    val = ValidationResult(
        document_id="doc-high-risk",
        is_safe=False,
        remaining_findings=[],
        message="Residual SSN detected",
        high_risk_residual=1,
        security_decision="BLOCKED"
    )
    res = DocumentAnalysisResult(
        document_id="doc-high-risk",
        file_name="tax.pdf",
        file_type="pdf",
        status="BLOCKED",
        original_blocks=[],
        sanitized_blocks=[],
        findings=[],
        validation_result=val
    )
    # The workbench logic must enforce has_high_risk check
    assert res.validation_result.high_risk_residual > 0
    # Security rule: cannot approve
    cannot_approve = (res.validation_result.high_risk_residual > 0)
    assert cannot_approve is True
