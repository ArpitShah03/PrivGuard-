import os
from typing import List, Dict, Any, Optional, Tuple
from models.schemas import PIIFinding, DocumentBlock, ValidationResult
from policy.models import SecurityPolicy, PolicyFindingDecision, PolicyAction
from policy.loader import PolicyLoader, default_policy_loader


class PolicyEngine:
    """
    Lightweight Enterprise Policy Engine.
    Sits ABOVE Phase 5C Evidence Fusion and Phase 3 Sanitizer to govern:
    - Input file restrictions (file extension, max size)
    - PII-type policies (enabled/disabled, action: DETECT, HUMAN_REVIEW, BLOCK, ALLOW)
    - Threshold overrides
    - Extraction uncertainty policy (fail-closed enforcement)
    - Post-rescan gate policy (SAFE vs BLOCKED vs HUMAN_REVIEW)
    - Policy decision explanations without raw PII
    """

    def __init__(
        self,
        policy: Optional[SecurityPolicy] = None,
        loader: Optional[PolicyLoader] = None
    ):
        self.loader = loader or default_policy_loader
        self.policy: SecurityPolicy = policy or self.loader.get_active_policy()

    def set_policy(self, policy: SecurityPolicy) -> None:
        """Update active policy."""
        self.policy = policy

    def validate_input_file(
        self,
        file_path: str,
        file_size_bytes: Optional[int] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Evaluate input file against policy file restrictions.
        Returns (is_valid, error_reason).
        """
        ext = os.path.splitext(file_path)[1].lstrip(".").lower()
        allowed = [e.lower() for e in self.policy.file_policy.allowed_extensions]

        if ext not in allowed:
            return False, f"File extension '.{ext}' is not permitted by policy (allowed: {allowed})."

        if file_size_bytes is not None:
            size_mb = file_size_bytes / (1024 * 1024)
            if size_mb > self.policy.file_policy.max_file_size_mb:
                return False, f"File size ({size_mb:.2f} MB) exceeds maximum policy limit ({self.policy.file_policy.max_file_size_mb:.2f} MB)."

        return True, None

    def evaluate_findings(
        self,
        findings: List[PIIFinding],
        has_extraction_uncertainty: bool = False
    ) -> Tuple[List[PIIFinding], str, Optional[str]]:
        """
        Govern detected findings according to policy entity rules.
        Returns:
        - active_findings: findings requiring redaction (DETECT / HUMAN_REVIEW)
        - overall_status: "PROCEED_TO_REDACTION", "HUMAN_REVIEW", or "BLOCKED"
        - status_reason: explanation (strictly zero raw PII)
        """
        active_findings: List[PIIFinding] = []
        has_blocked_entity = False
        has_review_entity = False
        blocked_types = set()

        for f in findings:
            rule = self.policy.entity_rules.get(f.pii_type)

            # Check if entity type rule exists
            if rule is not None:
                # 1. If entity type is disabled or ALLOWed by policy:
                # ALLOW means entity is not protected under this policy (not redacted).
                # Note: ALLOW does not bypass extraction uncertainty or rescan gate.
                if not rule.enabled or rule.action == PolicyAction.ALLOW.value:
                    continue

                # 2. Check BLOCK action: policy forbids release if this entity exists
                if rule.action == PolicyAction.BLOCK.value:
                    has_blocked_entity = True
                    blocked_types.add(f.pii_type)
                    active_findings.append(f)
                    continue

                # 3. Check HUMAN_REVIEW action
                if rule.action == PolicyAction.HUMAN_REVIEW.value:
                    has_review_entity = True
                    f.fusion_decision = "HUMAN_REVIEW"
                    f.uncertainty_reason = f"Policy mandates HUMAN_REVIEW for {f.pii_type}"
                    active_findings.append(f)
                    continue

                # 4. Check min_confidence override
                if f.confidence < rule.min_confidence and f.severity not in ["CRITICAL"]:
                    # Below policy min_confidence threshold for this type
                    continue

            # Default: retain finding for detection and redaction
            active_findings.append(f)

        # Determine overall pre-redaction governance status
        if has_blocked_entity:
            reason = f"Policy BLOCKED: Document contains prohibited PII entity types: {sorted(list(blocked_types))}"
            return active_findings, "BLOCKED", reason

        # Check policy status fail-closed fallback
        if self.policy.policy_status == "FALLBACK_STRICT":
            reason = f"Policy in fail-closed fallback state: {self.policy.policy_error}"
            return active_findings, "HUMAN_REVIEW", reason

        if has_extraction_uncertainty:
            reason = self.policy.uncertainty_policy.uncertainty_reason
            return active_findings, "HUMAN_REVIEW", reason

        if has_review_entity:
            reason = "Policy specifies mandatory human review for detected entity types."
            return active_findings, "HUMAN_REVIEW", reason

        return active_findings, "PROCEED_TO_REDACTION", None

    def evaluate_rescan_gate(self, val: ValidationResult) -> ValidationResult:
        """
        Evaluate post-redaction re-scan validation against gate policy.
        ENFORCES STRICT INVARIANTS:
        - Extraction uncertainty -> HUMAN_REVIEW (cannot be SAFE)
        - Residual high-risk PII > max allowed -> BLOCKED (cannot be SAFE)
        - Re-scan failure / fallback -> HUMAN_REVIEW or BLOCKED (cannot be SAFE)
        """
        gp = self.policy.gate_policy
        up = self.policy.uncertainty_policy

        # Invariant 1: Extraction uncertainty priority
        if val.uncertain_blocks_count > 0:
            val.is_safe = False
            val.requires_human_review = True
            val.security_decision = up.on_extraction_uncertainty
            val.message = (
                f"Extraction coverage incomplete ({val.uncertain_blocks_count} uninspected/failed blocks). "
                f"Policy mandates {up.on_extraction_uncertainty}."
            )
            return val

        # Invariant 2: Residual high-risk findings
        if val.high_risk_residual > gp.max_high_risk_residual_allowed:
            val.is_safe = False
            val.requires_human_review = (gp.on_high_risk_residual == "HUMAN_REVIEW")
            val.security_decision = gp.on_high_risk_residual
            val.message = (
                f"Residual high-risk PII ({val.high_risk_residual} findings) exceeds policy limit "
                f"({gp.max_high_risk_residual_allowed}). Document is {gp.on_high_risk_residual}."
            )
            return val

        # Invariant 3: General residual findings
        if len(val.remaining_findings) > gp.max_residual_allowed:
            val.is_safe = False
            val.requires_human_review = (gp.on_low_risk_residual == "HUMAN_REVIEW")
            val.security_decision = gp.on_low_risk_residual
            val.message = (
                f"Residual PII ({len(val.remaining_findings)} findings) detected in re-scan. "
                f"Policy mandates {gp.on_low_risk_residual}."
            )
            return val

        # Invariant 4: Fail-closed fallback status
        if self.policy.policy_status == "FALLBACK_STRICT":
            val.is_safe = False
            val.requires_human_review = True
            val.security_decision = "HUMAN_REVIEW"
            val.message = f"Policy loaded in fallback state ({self.policy.policy_error}). Gate mandates HUMAN_REVIEW."
            return val

        # Invariant 5: Verified clean extraction & zero residual PII
        val.is_safe = True
        val.requires_human_review = False
        val.security_decision = gp.on_clean_rescan if gp.on_clean_rescan != "SAFE" else "SANITIZED"
        val.message = (
            f"Zero residual PII verified and 100% extraction coverage confirmed under policy '{self.policy.name}'. "
            f"Document safe for downstream AI release."
        )
        return val


default_policy_engine = PolicyEngine()
