"""
Multimodal Synthetic PII Dataset & Ground Truth Module
Provides deterministic dataset generation, validation, splitting, and multi-format exports.
"""

from evaluation.multimodal_dataset.schemas import (
    DatasetSample,
    DocumentAnnotation,
    BlockAnnotation,
    PIIAnnotation,
    RelationshipAnnotation,
    VisualAnnotation,
    CANONICAL_PII_TYPES,
    ALLOWED_SOURCES,
    ALLOWED_RELATIONSHIPS,
    ALLOWED_MODALITIES,
)
from evaluation.multimodal_dataset.generator import MultimodalDatasetGenerator
from evaluation.multimodal_dataset.validators import validate_dataset, validate_sample, DatasetValidationError
from evaluation.multimodal_dataset.exporters import export_multimodal_dataset, compute_dataset_statistics

__all__ = [
    "DatasetSample",
    "DocumentAnnotation",
    "BlockAnnotation",
    "PIIAnnotation",
    "RelationshipAnnotation",
    "VisualAnnotation",
    "CANONICAL_PII_TYPES",
    "ALLOWED_SOURCES",
    "ALLOWED_RELATIONSHIPS",
    "ALLOWED_MODALITIES",
    "MultimodalDatasetGenerator",
    "validate_dataset",
    "validate_sample",
    "DatasetValidationError",
    "export_multimodal_dataset",
    "compute_dataset_statistics",
]
