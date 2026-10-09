from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

@dataclass
class DocumentBlock:
    document_id: str
    file_name: str
    file_type: str
    location: str
    block_type: str
    text: str
    order: int
    bbox: Optional[Dict[str, float]] = None
    is_ocr: bool = False
    ocr_confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    parent_id: Optional[str] = None

@dataclass
class PIIFinding:
    finding_id: str
    document_id: str
    file_name: str
    location: str
    start: int
    end: int
    text: str
    pii_type: str
    confidence: float
    detection_method: List[str]
    severity: str
    bbox: Optional[Dict[str, float]] = None
    is_ocr: bool = False
    replacement_token: Optional[str] = None
    entity_id: Optional[str] = None
    is_masked: bool = False
    normalized_text: Optional[str] = None
    validation_details: Dict[str, Any] = field(default_factory=dict)
    evidence: Dict[str, Any] = field(default_factory=dict)
    fusion_confidence: Optional[float] = None
    calibrated_confidence: Optional[float] = None
    detector_sources: List[str] = field(default_factory=list)
    detector_agreement: Optional[str] = None
    fusion_decision: Optional[str] = None
    uncertainty_reason: Optional[str] = None
    evidence_summary: Optional[str] = None

@dataclass
class RedactionResult:
    document_id: str
    original_text: str
    sanitized_text: str
    findings: List[PIIFinding]
    placeholder_map: Dict[str, str]

@dataclass
class ValidationResult:
    document_id: str
    is_safe: bool
    remaining_findings: List[PIIFinding]
    message: str
    requires_human_review: bool = False
    uncertain_blocks_count: int = 0
    pii_before: int = 0
    pii_after: int = 0
    high_risk_residual: int = 0
    sanitized_file_path: Optional[str] = None
    re_scanned_blocks_count: int = 0
    security_decision: str = "BLOCKED"
    applied_redactions_count: int = 0

@dataclass
class DocumentAnalysisResult:
    document_id: str
    file_name: str
    file_type: str
    status: str  # e.g., "SANITIZED", "BLOCKED", "HUMAN_REVIEW", "ERROR", "PROCESSING"
    original_blocks: List[DocumentBlock]
    sanitized_blocks: List[DocumentBlock]
    findings: List[PIIFinding]
    validation_result: Optional[ValidationResult] = None
    error_message: Optional[str] = None
    extraction_metadata: Dict[str, Any] = field(default_factory=dict)
    ocr_coverage: float = 0.0
    original_file_path: Optional[str] = None
    sanitized_file_path: Optional[str] = None
    re_scanned_blocks: List[DocumentBlock] = field(default_factory=list)
    security_summary: Dict[str, Any] = field(default_factory=dict)

