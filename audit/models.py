import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class FindingAuditRecord:
    """
    Audit record for a single finding.
    STRICT PRIVACY POLICY: NEVER STORES RAW PII OR RAW SECRET VALUES.
    """
    finding_id: str
    scan_id: str
    pii_type: str
    replacement_token: str
    confidence: float
    detection_method: str
    location: str
    severity: str
    is_ocr: bool = False
    is_masked: bool = False
    entity_id: Optional[str] = None
    fusion_confidence: Optional[float] = None
    detector_sources: Optional[str] = None
    fusion_decision: Optional[str] = None


@dataclass
class AuditEvent:
    """
    Timeline event for a document scanning lifecycle step.
    """
    event_id: str
    scan_id: str
    timestamp: float
    stage: str  # EXTRACTION, DETECTION, REDACTION, RESCAN, DECISION
    status: str  # SUCCESS, FAILED, WARNING
    message: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    previous_event_hash: Optional[str] = None
    event_hash: Optional[str] = None


@dataclass
class HumanReviewRecord:
    """
    Actionable reviewer audit record with cryptographic hash integrity.
    """
    review_id: str
    scan_id: str
    reviewer_id: str
    action: str  # APPROVE, REJECT, MARK_FALSE_POSITIVE, REQUEST_RESCAN
    justification: str
    timestamp: float
    previous_decision: str
    new_decision: str
    action_hash: Optional[str] = None


@dataclass
class ScanRecord:
    """
    Persistent audit record for a single document scan operation.
    """
    scan_id: str
    timestamp: float
    filename: str
    file_type: str
    processing_status: str  # SUCCESS, ERROR
    total_blocks: int
    inspected_blocks: int
    uncertain_blocks: int
    coverage_percentage: float
    pii_before: int
    pii_after: int
    high_risk_residual: int
    security_decision: str  # SANITIZED, BLOCKED, HUMAN_REVIEW, ERROR
    decision_reason: str
    sanitized_file_path: Optional[str] = None
    extraction_time_ms: float = 0.0
    detection_time_ms: float = 0.0
    redaction_time_ms: float = 0.0
    rescan_time_ms: float = 0.0
    total_time_ms: float = 0.0
