from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from enum import Enum


class EvidenceSource(str, Enum):
    REGEX = "REGEX"
    ALGORITHMIC = "ALGORITHMIC"
    SPACY = "SPACY"
    CONTEXT = "CONTEXT"
    MASKED_PII = "MASKED_PII"
    ENTITY_RESOLUTION = "ENTITY_RESOLUTION"
    MULTIMODAL = "MULTIMODAL"


@dataclass
class EvidenceRecord:
    """
    Standardized, safe evidence record emitted by an individual detector.
    STRICT PRIVACY GUARANTEE: Never stores raw personal sensitive text.
    """
    detector_source: str  # REGEX, ALGORITHMIC, SPACY, CONTEXT, MASKED_PII, ENTITY_RESOLUTION, MULTIMODAL
    entity_type: str      # PERSON, SSN, EMAIL, etc.
    raw_score: float      # Uncalibrated score from detector
    normalized_score: float # Mapped score [0.0, 1.0]
    evidence_strength: str  # "STRONG", "MODERATE", "WEAK"
    location: str          # block_id or paragraph location
    safe_metadata: Dict[str, Any] = field(default_factory=dict)
    span_start: int = 0
    span_end: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FusionResult:
    """
    Synthesized decision from the Evidence Fusion and Calibration layer.
    """
    finding_id: str
    pii_type: str
    fused_confidence: float
    calibrated_confidence: float
    decision: str  # "DETECT", "HUMAN_REVIEW", "SUPPRESS"
    detector_sources: List[str] = field(default_factory=list)
    detector_agreement: str = "SINGLE_DETECTOR"  # UNANIMOUS, MAJORITY, CONFLICT, SINGLE_DETECTOR, DETERMINISTIC_OVERRIDE
    uncertainty_reason: Optional[str] = None
    evidence_summary: str = ""
    evidence_records: List[EvidenceRecord] = field(default_factory=list)
    is_uncertain: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["evidence_records"] = [e.to_dict() for e in self.evidence_records]
        return d
