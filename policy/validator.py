from typing import List, Dict, Any, Optional
from policy.models import (
    SecurityPolicy,
    PolicyValidationResult,
    PolicyAction,
)


class PolicyValidationError(Exception):
    """Raised when an enterprise security policy violates fundamental security invariants."""
    pass


class PolicyValidator:
    """
    Validates enterprise policies against strict safety and compliance invariants:
    1. Fail-closed extraction uncertainty: Cannot be routed to SAFE or SUPPRESS.
    2. Threshold consistency: 0.0 <= lower_threshold <= high_threshold <= 1.0.
    3. Gate policy safety: High-risk residual PII cannot be released as SAFE.
    4. Valid action enums and entity type bindings.
    5. Valid input file policy bounds.
    """

    VALID_ACTIONS = {a.value for a in PolicyAction}
    VALID_UNCERTAINTY_ACTIONS = {"HUMAN_REVIEW", "BLOCKED"}
    VALID_HIGH_RISK_GATE_ACTIONS = {"BLOCKED", "HUMAN_REVIEW"}
    VALID_CLEAN_GATE_ACTIONS = {"SAFE", "SANITIZED"}

    # Canonical known PII types from Phases 1-5
    KNOWN_PII_TYPES = {
        "CREDIT_CARD", "SSN", "SECRET", "PAN", "PESEL", "PASSPORT", "BANK_ACCOUNT",
        "IFSC", "PERSON", "EMAIL", "PHONE", "EMPLOYEE_ID", "DIRECTOR_ID",
        "VENDOR_ID", "DATE_OF_BIRTH", "ADDRESS", "CUSTOMER_ID", "IP_ADDRESS"
    }

    def validate(self, policy: SecurityPolicy) -> PolicyValidationResult:
        """Evaluate policy safety invariants and return validation summary."""
        errors: List[str] = []
        warnings: List[str] = []

        # 1. File / Input Policy
        fp = policy.file_policy
        if not fp.allowed_extensions or not isinstance(fp.allowed_extensions, list):
            errors.append("file_policy.allowed_extensions must be a non-empty list.")
        if fp.max_file_size_mb <= 0:
            errors.append(f"file_policy.max_file_size_mb ({fp.max_file_size_mb}) must be positive.")

        # 2. Threshold Consistency
        th = policy.thresholds
        if not (0.0 <= th.lower_threshold <= 1.0):
            errors.append(f"lower_threshold ({th.lower_threshold}) must be between 0.0 and 1.0.")
        if not (0.0 <= th.high_threshold <= 1.0):
            errors.append(f"high_threshold ({th.high_threshold}) must be between 0.0 and 1.0.")
        if th.lower_threshold > th.high_threshold:
            errors.append(f"lower_threshold ({th.lower_threshold}) cannot exceed high_threshold ({th.high_threshold}).")

        for etype, p_th in th.per_type_thresholds.items():
            if not (0.0 <= p_th <= 1.0):
                errors.append(f"Per-type threshold for '{etype}' ({p_th}) must be between 0.0 and 1.0.")

        # 3. STRICT SECURITY INVARIANT: Extraction Uncertainty Priority
        unc_action = (policy.uncertainty_policy.on_extraction_uncertainty or "").upper()
        if unc_action not in self.VALID_UNCERTAINTY_ACTIONS:
            errors.append(
                f"Security Invariant Violated: on_extraction_uncertainty '{unc_action}' is invalid. "
                f"Fail-closed policy requires HUMAN_REVIEW or BLOCKED. Cannot be routed to SAFE or SUPPRESS."
            )

        # 4. Post-Rescan Verification Gate Policy
        gp = policy.gate_policy
        if gp.max_residual_allowed < 0:
            errors.append(f"max_residual_allowed ({gp.max_residual_allowed}) cannot be negative.")
        if gp.max_high_risk_residual_allowed < 0:
            errors.append(f"max_high_risk_residual_allowed ({gp.max_high_risk_residual_allowed}) cannot be negative.")

        high_gate_action = (gp.on_high_risk_residual or "").upper()
        if high_gate_action not in self.VALID_HIGH_RISK_GATE_ACTIONS:
            errors.append(
                f"Security Invariant Violated: on_high_risk_residual '{high_gate_action}' is invalid. "
                f"Must be BLOCKED or HUMAN_REVIEW. Cannot release residual high-risk PII as SAFE."
            )

        clean_gate_action = (gp.on_clean_rescan or "").upper()
        if clean_gate_action not in self.VALID_CLEAN_GATE_ACTIONS:
            errors.append(
                f"on_clean_rescan '{clean_gate_action}' is invalid. Must be SAFE or SANITIZED."
            )

        # 5. Entity Rule Actions and Types
        for etype, rule in policy.entity_rules.items():
            if etype not in self.KNOWN_PII_TYPES and etype != "*":
                warnings.append(f"Entity rule specifies non-standard or custom entity type: '{etype}'.")
            action = (rule.action or "").upper()
            if action not in self.VALID_ACTIONS:
                errors.append(f"Entity rule '{etype}' has invalid action '{action}'. Must be one of {self.VALID_ACTIONS}.")
            if not (0.0 <= rule.min_confidence <= 1.0):
                errors.append(f"Entity rule '{etype}' min_confidence ({rule.min_confidence}) must be between 0.0 and 1.0.")

        is_valid = len(errors) == 0
        status = "ACTIVE" if is_valid else "INVALID"
        eff = "CONFIGURED" if is_valid else "STRICT_FAIL_CLOSED"

        return PolicyValidationResult(
            is_valid=is_valid,
            policy_status=status,
            effective_policy=eff,
            errors=errors,
            warnings=warnings,
            validated_policy=policy if is_valid else None
        )

    def validate_or_raise(self, policy: SecurityPolicy) -> SecurityPolicy:
        """Validate policy and return it if safe, or raise PolicyValidationError."""
        res = self.validate(policy)
        if not res.is_valid:
            error_msg = " | ".join(res.errors)
            raise PolicyValidationError(f"Invalid security policy: {error_msg}")
        return policy


default_policy_validator = PolicyValidator()
