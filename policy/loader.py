import os
import yaml
from typing import Dict, Any, Optional
from policy.models import (
    SecurityPolicy,
    EntityRule,
    ThresholdPolicy,
    UncertaintyPolicy,
    FilePolicy,
    VerificationGatePolicy,
    RedactionPolicy,
)
from policy.validator import PolicyValidator, default_policy_validator


class PolicyLoader:
    """
    Loads and validates declarative enterprise security policies.
    ENFORCES FAIL-CLOSED SECURITY:
    If policy.yaml is missing, malformed, schema-invalid, or insecure:
    - Does NOT silently proceed as normal.
    - System transitions to FAIL-CLOSED (HUMAN_REVIEW / BLOCKED).
    - Returns a strict fail-closed fallback policy explicitly recording:
        policy_status: "FALLBACK_STRICT"
        policy_error: "<actual reason>"
        effective_policy: "STRICT_FAIL_CLOSED"
    """

    def __init__(
        self,
        default_path: str = "config/policy.yaml",
        validator: Optional[PolicyValidator] = None
    ):
        self.default_path = default_path
        self.validator = validator or default_policy_validator
        self._cached_policy: Optional[SecurityPolicy] = None

    def build_strict_fallback_policy(self, error_message: str) -> SecurityPolicy:
        """
        Construct an explicit, auditable fail-closed fallback policy.
        Never claims original policy was successfully loaded.
        """
        return SecurityPolicy(
            name="Strict Fail-Closed Fallback Policy",
            version="1.0.0-fallback",
            description="Emergency fail-closed policy activated due to policy loading or validation error.",
            policy_status="FALLBACK_STRICT",
            effective_policy="STRICT_FAIL_CLOSED",
            policy_error=error_message,
            file_policy=FilePolicy(
                allowed_extensions=["pdf", "docx", "pptx", "txt"],
                max_file_size_mb=25.0,
                on_unsupported_file="BLOCKED"
            ),
            thresholds=ThresholdPolicy(
                high_threshold=0.70,
                lower_threshold=0.45
            ),
            uncertainty_policy=UncertaintyPolicy(
                require_100_coverage=True,
                on_extraction_uncertainty="HUMAN_REVIEW",
                uncertainty_reason="Policy loading failed; fail-closed mandates HUMAN_REVIEW"
            ),
            gate_policy=VerificationGatePolicy(
                max_residual_allowed=0,
                max_high_risk_residual_allowed=0,
                on_high_risk_residual="BLOCKED",
                on_low_risk_residual="HUMAN_REVIEW",
                on_clean_rescan="SAFE"
            ),
            redaction_policy=RedactionPolicy(
                replacement_mode="TOKEN",
                preserve_structure=True
            ),
            entity_rules={},
            raw_config={}
        )

    def load_from_dict(self, data: Dict[str, Any]) -> SecurityPolicy:
        """Parse dictionary and validate against policy invariants."""
        if not isinstance(data, dict):
            return self.build_strict_fallback_policy("Policy data must be a dictionary.")

        try:
            # 1. Parse File Policy
            fp_raw = data.get("file_policy", {})
            file_policy = FilePolicy(
                allowed_extensions=fp_raw.get("allowed_extensions", ["pdf", "docx", "pptx", "txt"]),
                max_file_size_mb=float(fp_raw.get("max_file_size_mb", 25.0)),
                on_unsupported_file=fp_raw.get("on_unsupported_file", "BLOCKED")
            )

            # 2. Parse Thresholds
            th_raw = data.get("thresholds", {})
            thresholds = ThresholdPolicy(
                high_threshold=float(th_raw.get("high_threshold", 0.70)),
                lower_threshold=float(th_raw.get("lower_threshold", 0.45)),
                per_type_thresholds={k: float(v) for k, v in th_raw.get("per_type_thresholds", {}).items()}
            )

            # 3. Parse Uncertainty Policy
            unc_raw = data.get("uncertainty_policy", {})
            uncertainty_policy = UncertaintyPolicy(
                require_100_coverage=bool(unc_raw.get("require_100_coverage", True)),
                on_extraction_uncertainty=str(unc_raw.get("on_extraction_uncertainty", "HUMAN_REVIEW")),
                uncertainty_reason=str(unc_raw.get("uncertainty_reason", "Extraction coverage incomplete"))
            )

            # 4. Parse Gate Policy
            gp_raw = data.get("gate_policy", {})
            gate_policy = VerificationGatePolicy(
                max_residual_allowed=int(gp_raw.get("max_residual_allowed", 0)),
                max_high_risk_residual_allowed=int(gp_raw.get("max_high_risk_residual_allowed", 0)),
                on_high_risk_residual=str(gp_raw.get("on_high_risk_residual", "BLOCKED")),
                on_low_risk_residual=str(gp_raw.get("on_low_risk_residual", "HUMAN_REVIEW")),
                on_clean_rescan=str(gp_raw.get("on_clean_rescan", "SAFE"))
            )

            # 5. Parse Redaction Policy
            red_raw = data.get("redaction_policy", {})
            redaction_policy = RedactionPolicy(
                replacement_mode=str(red_raw.get("replacement_mode", "TOKEN")),
                preserve_structure=bool(red_raw.get("preserve_structure", True))
            )

            # 6. Parse Entity Rules
            entity_rules = {}
            for etype, r_raw in data.get("entity_rules", {}).items():
                if isinstance(r_raw, dict):
                    entity_rules[etype] = EntityRule(
                        entity_type=etype,
                        enabled=bool(r_raw.get("enabled", True)),
                        action=str(r_raw.get("action", "DETECT")),
                        severity=str(r_raw.get("severity", "HIGH")),
                        min_confidence=float(r_raw.get("min_confidence", 0.50)),
                        redaction_mode=str(r_raw.get("redaction_mode", "TOKEN"))
                    )

            policy = SecurityPolicy(
                name=str(data.get("name", "Custom Enterprise Policy")),
                version=str(data.get("version", "1.0.0")),
                description=str(data.get("description", "")),
                policy_status="ACTIVE",
                effective_policy="CONFIGURED",
                policy_error=None,
                file_policy=file_policy,
                thresholds=thresholds,
                uncertainty_policy=uncertainty_policy,
                gate_policy=gate_policy,
                redaction_policy=redaction_policy,
                entity_rules=entity_rules,
                raw_config=data
            )

            # Validate against security invariants
            val_result = self.validator.validate(policy)
            if not val_result.is_valid:
                error_msg = " | ".join(val_result.errors)
                return self.build_strict_fallback_policy(f"Policy validation failed: {error_msg}")

            return policy

        except Exception as e:
            return self.build_strict_fallback_policy(f"Schema parsing error: {str(e)}")

    def load_from_file(self, file_path: Optional[str] = None) -> SecurityPolicy:
        """
        Load policy YAML from file with fail-closed error handling.
        """
        target_path = file_path or self.default_path

        if not os.path.exists(target_path):
            fallback = self.build_strict_fallback_policy(f"Policy file not found: {target_path}")
            self._cached_policy = fallback
            return fallback

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                content = yaml.safe_load(f)

            if not isinstance(content, dict):
                fallback = self.build_strict_fallback_policy(f"Policy file '{target_path}' is empty or invalid YAML.")
                self._cached_policy = fallback
                return fallback

            policy = self.load_from_dict(content)
            self._cached_policy = policy
            return policy

        except yaml.YAMLError as ye:
            fallback = self.build_strict_fallback_policy(f"Malformed YAML syntax in '{target_path}': {str(ye)}")
            self._cached_policy = fallback
            return fallback
        except Exception as e:
            fallback = self.build_strict_fallback_policy(f"Error reading '{target_path}': {str(e)}")
            self._cached_policy = fallback
            return fallback

    def get_active_policy(self) -> SecurityPolicy:
        """Return cached policy or load default if not yet loaded."""
        if self._cached_policy is None:
            self._cached_policy = self.load_from_file()
        return self._cached_policy

    def reload(self, file_path: Optional[str] = None) -> SecurityPolicy:
        """Force reload from disk."""
        self._cached_policy = None
        return self.load_from_file(file_path)


default_policy_loader = PolicyLoader()
