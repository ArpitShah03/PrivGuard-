"""
Multimodal / Layout-Aware PII Detection Module
Provides spatial, structural, contextual, and OCR-aware feature extraction,
calibrated evidence scoring, and clean gateway fusion.
"""

from detection.multimodal.schemas import (
    EvidenceBreakdown,
    MultimodalPrediction,
    MultimodalCandidateItem,
)
from detection.multimodal.feature_extractor import MultimodalFeatureExtractor
from detection.multimodal.layout_features import extract_layout_features
from detection.multimodal.context_features import extract_context_features
from detection.multimodal.scorer import MultimodalEvidenceScorer
from detection.multimodal.detector import (
    BaseMultimodalDetector,
    LightweightMultimodalDetector,
    MultimodalDetectorError,
)
from detection.multimodal.fusion import fuse_multimodal_findings

__all__ = [
    "EvidenceBreakdown",
    "MultimodalPrediction",
    "MultimodalCandidateItem",
    "MultimodalFeatureExtractor",
    "extract_layout_features",
    "extract_context_features",
    "MultimodalEvidenceScorer",
    "BaseMultimodalDetector",
    "LightweightMultimodalDetector",
    "MultimodalDetectorError",
    "fuse_multimodal_findings",
]
