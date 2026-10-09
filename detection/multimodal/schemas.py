from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional


@dataclass
class EvidenceBreakdown:
    """
    Explainable evidence breakdown across all multimodal dimensions.
    """
    text_pattern: float = 0.0
    layout_context: float = 0.0
    table_context: float = 0.0
    ocr_evidence: float = 0.0
    relationship_context: float = 0.0
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MultimodalPrediction:
    """
    Prediction result from the Multimodal / Layout-Aware PII Detector.
    """
    pii_type: str
    score: float
    confidence_level: str  # "HIGH", "MEDIUM", "LOW"
    evidence: EvidenceBreakdown
    bbox: List[float]
    source: str
    method: str = "multimodal_layout"
    text: str = ""
    normalized_text: Optional[str] = None
    entity_id: Optional[str] = None
    is_ocr: bool = False
    is_masked: bool = False
    is_uncertain: bool = False
    uncertainty_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["evidence"] = self.evidence.to_dict()
        return d


@dataclass
class MultimodalCandidateItem:
    """
    Standardized input item consumed by the multimodal detection pipeline.
    Compatible with Phase 1 DocumentBlock and Phase 5A DatasetSample blocks.
    """
    sample_id: str
    block_id: str
    text: str
    normalized_text: Optional[str] = None
    bbox: List[float] = field(default_factory=lambda: [0.0, 0.0, 1.0, 1.0])
    page_or_slide: int = 1
    source: str = "native_text"
    modality: str = "TEXT"
    is_ocr: bool = False
    ocr_confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    parent_id: Optional[str] = None
    relationships: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
