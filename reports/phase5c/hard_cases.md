# Phase 5C Hard Cases Empirical Inspection

This document verifies the 8 critical edge cases evaluated under Phase 5C.

## 1. Extraction Uncertainty Fail-Closed Gate
- **Scenario**: Document block extraction is marked uncertain, failed, or OCR-unavailable.
- **Security Invariant**: Even if fused or calibrated confidence is 0.0, the decision MUST remain `HUMAN_REVIEW`. SUPPRESS is forbidden.
- **Verification Result**: **PASS**. Tested with OCR-unavailable block; correctly routed to `HUMAN_REVIEW` with auditable reason.

## 2. Deterministic Dominance (Algorithmic Checksums)
- **Scenario**: Valid credit card with Luhn checksum or PESEL with modulo-10 checksum encounters probabilistic ML model disagreement.
- **Security Invariant**: Algorithmic certainty dominates; model disagreement cannot veto or suppress a valid checksum. Decision is `DETECT`.
- **Verification Result**: **PASS**. Luhn checksum overrides weak probabilistic ML predictions with `DETERMINISTIC_OVERRIDE`.

## 3. Token Immunity Protection
- **Scenario**: Synthetic replacement token `[PERSON_001]` or `[SSN_002]` is re-scanned in subsequent document passes.
- **Security Invariant**: Tokens must never be re-flagged as PII.
- **Verification Result**: **PASS**. Resolved to `SUPPRESS` via explicit token immunity check.

## 4. Corporate Stop-Word Hard Negative Suppression
- **Scenario**: Organizational terms such as "Optiv Inc.", "Operations", or "Risk Management Policy" flagged as `PERSON` by statistical NER.
- **Security Invariant**: In the absence of corroborating attributes (email, employee ID) and moderate confidence, corporate stop-words are suppressed.
- **Verification Result**: **PASS**. Suppressed without false positive escalation.

## 5. Rotated OCR Noise + Checksum Recovery
- **Scenario**: OCR text with noise characters (e.g., 'O' substituted for '0').
- **Security Invariant**: Repaired candidates that validate algorithmically are detected with deterministic priority.
- **Verification Result**: **PASS**. Successfully recovered and classified as `DETECT`.

## 6. Table Header Spatial Association
- **Scenario**: Values in table cells without inline labels (e.g., column header "National ID").
- **Security Invariant**: Multimodal detector layout features associate column header with cell value.
- **Verification Result**: **PASS**. Multimodal evidence record generated and fused into final detection.

## 7. Org Chart Dotted-Line Context
- **Scenario**: Executive names in presentation slide hierarchy with dashed reporting lines.
- **Security Invariant**: Relationship context supports person classification without false corporate entity merge.
- **Verification Result**: **PASS**. Successfully classified as `PERSON` with corroborating evidence.

## 8. Partially Masked Identification Numbers
- **Scenario**: Partially masked credentials (`***-**-1234`).
- **Security Invariant**: Detected as `SSN` / `MASKED_PII` and sanitized without regex bounds failure.
- **Verification Result**: **PASS**. Classified as `SSN` with masked evidence record.
