# Phase 6: Enterprise Security Policy Layer Documentation

## 1. Executive Summary & Purpose
Phase 6 establishes a declarative, lightweight enterprise security policy engine (`policy.yaml` -> Policy Loader -> Policy Validator -> Policy Engine) sitting above the Phase 5C Evidence Fusion and Phase 3 Sanitization layers.

The Policy Layer provides organizational governance over:
- Input file restrictions (allowed extensions, maximum file size)
- Entity-level PII actions (`DETECT`, `HUMAN_REVIEW`, `BLOCK`, `ALLOW`)
- Confidence threshold boundaries
- Extraction uncertainty fail-closed enforcement
- Post-redaction re-scan gate governance (`SAFE` vs `BLOCKED` vs `HUMAN_REVIEW`)

---

## 2. Architecture & Control Flow

```
                  policy.yaml
                       ↓
                 Policy Loader (Fail-closed fallback tracking)
                       ↓
               Policy Validator (Security invariant enforcement)
                       ↓
                 Policy Object
                       ↓
DOCUMENT → EXISTING GATEWAY
              ↓
       Detection + Fusion (Phase 5C: Multimodal + Deterministic Dominance)
              ↓
        Policy Evaluation (Entity rules, threshold overrides, file check)
              ↓
      DETECT / REVIEW / BLOCK
              ↓
           REDACTION (Phase 3: Structure-preserving DOCX/PPTX/PDF/TXT)
              ↓
            RE-SCAN (Phase 3: Re-extraction & Verification Gate)
              ↓
        FINAL SECURITY GATE (Phase 6 Policy Verification Gate)
              ↓
   SAFE / BLOCKED / HUMAN_REVIEW
```

---

## 3. Policy Schema Specification

The declarative schema in `config/policy.yaml` defines:
```yaml
name: "Enterprise Default Data Security Policy"
version: "1.0.0"

file_policy:
  allowed_extensions: ["pdf", "docx", "pptx", "txt"]
  max_file_size_mb: 25.0
  on_unsupported_file: "BLOCKED"

thresholds:
  high_threshold: 0.70
  lower_threshold: 0.45

uncertainty_policy:
  require_100_coverage: true
  on_extraction_uncertainty: "HUMAN_REVIEW"

gate_policy:
  max_residual_allowed: 0
  max_high_risk_residual_allowed: 0
  on_high_risk_residual: "BLOCKED"
  on_low_risk_residual: "HUMAN_REVIEW"
  on_clean_rescan: "SAFE"

redaction_policy:
  replacement_mode: "TOKEN"
  preserve_structure: true

entity_rules:
  CREDIT_CARD:
    enabled: true
    action: "DETECT"
    severity: "CRITICAL"
    min_confidence: 0.50
    redaction_mode: "TOKEN"
  # ... additional canonical types
```

---

## 4. Policy Actions & Security Bounds
- `DETECT`: Finding is retained and scheduled for structure-preserving token replacement.
- `HUMAN_REVIEW`: Finding or document is routed to human review.
- `BLOCK`: Document is immediately prohibited from downstream release.
- `ALLOW`: The entity type is permitted / unredacted under policy.
  - **Security Invariant**: `ALLOW` only applies to entity-level classification; it **never** bypasses extraction uncertainty (`HUMAN_REVIEW`) or re-scan residual failures (`BLOCKED`).

---

## 5. Fail-Closed Policy Loading Behavior
If `policy.yaml` is missing, unreadable, syntax-invalid, or contains insecure rules (such as attempting to route extraction uncertainty to `SAFE`):
- System **fails closed**.
- Activates an auditable fallback policy:
  - `policy_status: "FALLBACK_STRICT"`
  - `effective_policy: "STRICT_FAIL_CLOSED"`
  - `policy_error: "<detailed failure reason>"`
- Document processing routes to `HUMAN_REVIEW` with an auditable fallback reason.

---

## 6. Zero Raw PII Guarantee
Policy objects, validation results, gate decisions, audit records, and error messages never record or log raw sensitive values. Abstract metadata only (`finding_id`, `pii_type`, `location`, `confidence`, `policy_version`, `decision`) is preserved.

---

## 7. Verification Results
- **Phase 6 Tests**: 16 dedicated automated tests passing in [`tests/test_policy.py`](file:///c:/Users/ShahA/OneDrive/Desktop/raikta/tests/test_policy.py).
- **Total Test Suite**: 124 / 124 automated tests passing (100% green).
- **Zero Regressions**: All 108 baseline tests across Phases 1–5C remain green.
