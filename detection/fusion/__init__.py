"""
Phase 5C: Evidence Fusion & Confidence Calibration Subsystem.
Provides multi-detector arbitration, Platt scaling calibration,
and a strict fail-closed decision hierarchy.
"""

from detection.fusion.schemas import (
    EvidenceSource,
    EvidenceRecord,
    FusionResult,
)
from detection.fusion.conflict_resolution import (
    ConflictResolver,
    ResolutionOutcome,
)
from detection.fusion.calibration import (
    ConfidenceCalibrator,
    CalibrationError,
    compute_ece_and_brier,
)
from detection.fusion.threshold_manager import (
    ThresholdManager,
)
from detection.fusion.fusion_engine import (
    EvidenceFusionEngine,
    default_fusion_engine,
    check_is_block_uncertain,
)

__all__ = [
    "EvidenceSource",
    "EvidenceRecord",
    "FusionResult",
    "ConflictResolver",
    "ResolutionOutcome",
    "ConfidenceCalibrator",
    "CalibrationError",
    "compute_ece_and_brier",
    "ThresholdManager",
    "EvidenceFusionEngine",
    "default_fusion_engine",
    "check_is_block_uncertain",
]
