from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
from enum import Enum


class PolicyAction(str, Enum):
    DETECT = "DETECT"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    BLOCK = "BLOCK"
    ALLOW = "ALLOW"


@dataclass
class FilePolicy:
    """Input file restriction policy."""
    allowed_extensions: List[str] = field(default_factory=lambda: ["pdf", "docx", "pptx", "txt"])
    max_file_size_mb: float = 25.0
    on_unsupported_file: str = "BLOCKED"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EntityRule:
    """Governance rule for a specific PII entity type."""
    entity_type: str
    enabled: bool = True
    action: str = "DETECT"  # DETECT, HUMAN_REVIEW, BLOCK, ALLOW
    severity: str = "HIGH"
    min_confidence: float = 0.50
    redaction_mode: str = "TOKEN"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ThresholdPolicy:
    """Confidence threshold boundaries."""
    high_threshold: float = 0.70
    lower_threshold: float = 0.45
    per_type_thresholds: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class UncertaintyPolicy:
    """Policy governing extraction uncertainty and uninspected blocks."""
    require_100_coverage: bool = True
    on_extraction_uncertainty: str = "HUMAN_REVIEW"  # MUST be HUMAN_REVIEW or BLOCKED
    uncertainty_reason: str = "Extraction coverage incomplete; uninspected blocks mandate human review"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VerificationGatePolicy:
    """Post-rescan verification gate policy governing final release."""
    max_residual_allowed: int = 0
    max_high_risk_residual_allowed: int = 0
    on_high_risk_residual: str = "BLOCKED"
    on_low_risk_residual: str = "HUMAN_REVIEW"
    on_clean_rescan: str = "SAFE"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RedactionPolicy:
    """Settings controlling redaction execution."""
    replacement_mode: str = "TOKEN"
    preserve_structure: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SecurityPolicy:
    """
    Lightweight enterprise security policy.
    Zero raw PII is ever stored in policy representations.
    """
    name: str = "Enterprise Default Data Security Policy"
    version: str = "1.0.0"
    description: str = ""
    policy_status: str = "ACTIVE"               # ACTIVE, FALLBACK_STRICT
    effective_policy: str = "CONFIGURED"         # CONFIGURED, STRICT_FAIL_CLOSED
    policy_error: Optional[str] = None
    file_policy: FilePolicy = field(default_factory=FilePolicy)
    thresholds: ThresholdPolicy = field(default_factory=ThresholdPolicy)
    uncertainty_policy: UncertaintyPolicy = field(default_factory=UncertaintyPolicy)
    gate_policy: VerificationGatePolicy = field(default_factory=VerificationGatePolicy)
    redaction_policy: RedactionPolicy = field(default_factory=RedactionPolicy)
    entity_rules: Dict[str, EntityRule] = field(default_factory=dict)
    raw_config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["file_policy"] = self.file_policy.to_dict()
        d["thresholds"] = self.thresholds.to_dict()
        d["uncertainty_policy"] = self.uncertainty_policy.to_dict()
        d["gate_policy"] = self.gate_policy.to_dict()
        d["redaction_policy"] = self.redaction_policy.to_dict()
        d["entity_rules"] = {k: v.to_dict() for k, v in self.entity_rules.items()}
        return d


@dataclass
class PolicyValidationResult:
    """Outcome of validating a security policy against safety invariants."""
    is_valid: bool
    policy_status: str = "ACTIVE"
    effective_policy: str = "CONFIGURED"
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    validated_policy: Optional[SecurityPolicy] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if self.validated_policy:
            d["validated_policy"] = self.validated_policy.to_dict()
        return d


@dataclass
class PolicyFindingDecision:
    """
    Decision produced by PolicyEngine for an individual PII finding.
    Zero raw PII text is stored.
    """
    finding_id: str
    entity_type: str
    action: str  # DETECT, HUMAN_REVIEW, BLOCK, ALLOW
    is_allowed: bool
    is_blocked: bool
    decision_rationale: str
    policy_version: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
