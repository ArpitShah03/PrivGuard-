from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

# Canonical Enterprise PII types recognized by the Gateway
CANONICAL_PII_TYPES = {
    "PERSON",
    "EMAIL",
    "PHONE",
    "ADDRESS",
    "DOB",
    "SSN",
    "PAN",
    "PASSPORT",
    "PESEL",
    "EMPLOYEE_ID",
    "DIRECTOR_ID",
    "VENDOR_ID",
    "CUSTOMER_ID",
    "CREDIT_CARD",
    "BANK_ACCOUNT",
    "IFSC",
    "SECRET",
}

# Allowed Ground-Truth Source Contexts
ALLOWED_SOURCES = {
    "native_text",
    "OCR",
    "metadata",
    "table",
    "shape",
    "image",
    "header",
    "footer",
    "notes",
}

# Allowed Relationship Types
ALLOWED_RELATIONSHIPS = {
    "SAME_ENTITY",
    "ASSOCIATED_WITH",
    "LOCATED_NEAR",
    "BELONGS_TO",
    "MANAGES",
    "REPORTS_TO",
    "CORROBORATES",
}

# Allowed Document Modalities
ALLOWED_MODALITIES = {
    "TEXT",
    "TABLE",
    "PDF-LIKE PAGE",
    "PPTX-LIKE SLIDE",
    "DOCX-LIKE PAGE",
    "IMAGE/OCR",
}


@dataclass
class PIIAnnotation:
    """
    Ground-truth fine-grained annotation for a PII mention in a multimodal document.
    Bounding box format: [x1, y1, x2, y2] in normalized coordinates [0.0, 1.0].
    """
    annotation_id: str
    sample_id: str
    pii_type: str
    text: str
    normalized_text: str
    bbox: List[float]
    page_or_slide: int
    source: str
    confidence_ground_truth: float = 1.0
    is_masked: bool = False
    is_indirect: bool = False
    is_partial: bool = False
    entity_id: Optional[str] = None
    relationship_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BlockAnnotation:
    """
    Structural layout block representation (paragraph, table cell, shape, header, etc.).
    """
    block_id: str
    sample_id: str
    block_type: str
    text: str
    bbox: List[float]
    page_or_slide: int
    order: int
    is_ocr: bool = False
    parent_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RelationshipAnnotation:
    """
    Explicit contextual / structural relationship between two PII annotations.
    """
    relationship_id: str
    sample_id: str
    source_annotation_id: str
    target_annotation_id: str
    relationship_type: str
    evidence: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VisualAnnotation:
    """
    Visual element annotation (chart, screenshot, badge, diagram, etc.).
    """
    visual_id: str
    sample_id: str
    visual_type: str
    bbox: List[float]
    page_or_slide: int
    has_embedded_text: bool = False
    ocr_confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DocumentAnnotation:
    """
    Document-level metadata and structure descriptor.
    """
    document_title: str
    file_type: str
    total_pages_or_slides: int = 1
    metadata_attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DatasetSample:
    """
    Full multimodal sample encapsulating text, layout blocks, ground-truth PII annotations,
    visual regions, and cross-entity relationships.
    """
    sample_id: str
    split: str  # 'train', 'validation', 'test'
    category: str
    document_modality: str
    text_content: str
    document_info: DocumentAnnotation
    blocks: List[BlockAnnotation] = field(default_factory=list)
    pii_annotations: List[PIIAnnotation] = field(default_factory=list)
    relationships: List[RelationshipAnnotation] = field(default_factory=list)
    visuals: List[VisualAnnotation] = field(default_factory=list)
    is_hard_negative: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
