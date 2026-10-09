import time
import uuid
from typing import List, Dict, Any, Optional
from models.schemas import PIIFinding, DocumentBlock, ValidationResult
from audit.models import ScanRecord, FindingAuditRecord, AuditEvent
from audit.audit_store import AuditStore, default_audit_store


def generate_decision_reason(decision: str, uncertain_blocks: int = 0, residual_count: int = 0) -> str:
    """
    Standardized, explainable enterprise security decision explanations.
    """
    if decision == "SANITIZED":
        return "All extracted content was inspected, PII was redacted, and post-redaction verification found no residual high-risk PII."
    elif decision == "BLOCKED":
        return f"Post-redaction verification detected residual high-risk PII ({residual_count} findings). Downstream release denied."
    elif decision == "HUMAN_REVIEW":
        return f"One or more document regions could not be inspected ({uncertain_blocks} uncertain/unprocessed blocks). Fail-closed policy requires human review."
    else:
        return f"Document processing finished with status: {decision}."


class AuditLogger:
    """
    Enterprise audit logger.
    Manages structured event logging, timing instrumentation,
    and safe finding metadata persistence without leaking raw PII.
    """
    def __init__(self, store: Optional[AuditStore] = None):
        self.store = store or default_audit_store

    def log_event(self, scan_id: str, stage: str, status: str, message: str, metadata: Optional[Dict[str, Any]] = None):
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            scan_id=scan_id,
            timestamp=time.time(),
            stage=stage,
            status=status,
            message=message,
            metadata=metadata or {}
        )
        self.store.record_event(event)

    def log_findings(self, scan_id: str, findings: List[PIIFinding]):
        """
        Record finding metadata in audit store.
        MANDATORY PRIVACY REQUIREMENT: Raw finding text is completely omitted.
        """
        for f in findings:
            record = FindingAuditRecord(
                finding_id=f.finding_id,
                scan_id=scan_id,
                pii_type=f.pii_type,
                replacement_token=f.replacement_token or f"[{f.pii_type}_REDACTED]",
                confidence=f.confidence,
                detection_method="+".join(f.detection_method) if isinstance(f.detection_method, list) else str(f.detection_method),
                location=f.location,
                severity=f.severity,
                is_ocr=getattr(f, "is_ocr", False),
                is_masked=getattr(f, "is_masked", False),
                entity_id=getattr(f, "entity_id", None)
            )
            self.store.record_finding(record)

    def finalize_scan(
        self,
        scan_id: str,
        filename: str,
        file_type: str,
        total_blocks: int,
        uncertain_blocks: int,
        pii_before: int,
        pii_after: int,
        high_risk_residual: int,
        security_decision: str,
        sanitized_file_path: Optional[str] = None,
        timing_stats: Optional[Dict[str, float]] = None,
        custom_reason: Optional[str] = None
    ) -> ScanRecord:
        """
        Construct and persist the final scan record with operational metrics.
        """
        inspected_blocks = max(0, total_blocks - uncertain_blocks)
        coverage_pct = round((inspected_blocks / total_blocks * 100.0) if total_blocks > 0 else 100.0, 2)
        
        reason = custom_reason or generate_decision_reason(security_decision, uncertain_blocks, high_risk_residual)
        timing = timing_stats or {}

        scan_record = ScanRecord(
            scan_id=scan_id,
            timestamp=time.time(),
            filename=filename,
            file_type=file_type,
            processing_status="SUCCESS" if security_decision != "ERROR" else "ERROR",
            total_blocks=total_blocks,
            inspected_blocks=inspected_blocks,
            uncertain_blocks=uncertain_blocks,
            coverage_percentage=coverage_pct,
            pii_before=pii_before,
            pii_after=pii_after,
            high_risk_residual=high_risk_residual,
            security_decision=security_decision,
            decision_reason=reason,
            sanitized_file_path=sanitized_file_path,
            extraction_time_ms=timing.get("extraction_ms", 0.0),
            detection_time_ms=timing.get("detection_ms", 0.0),
            redaction_time_ms=timing.get("redaction_ms", 0.0),
            rescan_time_ms=timing.get("rescan_ms", 0.0),
            total_time_ms=timing.get("total_ms", 0.0)
        )

        self.store.record_scan(scan_record)

        # Log final decision event
        self.log_event(
            scan_id=scan_id,
            stage="DECISION",
            status="SUCCESS" if security_decision == "SANITIZED" else "WARNING",
            message=f"Final security decision: {security_decision}. {reason}",
            metadata={
                "coverage_percentage": coverage_pct,
                "pii_before": pii_before,
                "pii_after": pii_after,
                "decision": security_decision
            }
        )

        return scan_record


default_audit_logger = AuditLogger()
