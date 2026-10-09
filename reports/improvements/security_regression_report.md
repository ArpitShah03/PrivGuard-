# Security Regression & Adversarial Verification Report

## Verification Summary
- **Execution Date:** 2026-10-09
- **Platform:** Windows (Python 3.12.4, PyTest 9.1.1)
- **Total Tests Executed:** 186
- **Passed:** 186 (100%)
- **Failed:** 0
- **False-Safe Cases:** 0

---

## Adversarial Test Matrix (27 Tests)

| Category | Test File | Test Case | Expected Security Decision | Result |
| :--- | :--- | :--- | :---: | :---: |
| **Fail-Closed** | `test_fail_closed.py` | `test_corrupted_extension_routed_fail_closed` | `BLOCKED` / `HUMAN_REVIEW` | ✅ PASSED |
| **Fail-Closed** | `test_fail_closed.py` | `test_extraction_uncertainty_zero_findings_never_safe` | `HUMAN_REVIEW` | ✅ PASSED |
| **Fail-Closed** | `test_fail_closed.py` | `test_conflicting_entities_anti_merge` | Distinct Entities / No Unsafe Merge | ✅ PASSED |
| **Fail-Closed** | `test_fail_closed.py` | `test_top_false_safe_regressions` | `HUMAN_REVIEW` / `BLOCKED` | ✅ PASSED |
| **Layout Evasion** | `test_layout_evasion.py` | `test_split_pii_across_adjacent_shapes` | Correlated & Redacted | ✅ PASSED |
| **Layout Evasion** | `test_layout_evasion.py` | `test_split_table_cell_identifier_context` | Correlated & Redacted | ✅ PASSED |
| **Layout Evasion** | `test_layout_evasion.py` | `test_unresolvable_fragmented_layout_routes_to_human_review` | `HUMAN_REVIEW` | ✅ PASSED |
| **Metadata** | `test_metadata_evasion.py` | `test_pii_hidden_in_metadata_block_detected` | `DETECT` & Masked | ✅ PASSED |
| **Metadata** | `test_metadata_evasion.py` | `test_uninspected_corrupted_metadata_routes_to_human_review` | `HUMAN_REVIEW` | ✅ PASSED |
| **OCR Confusion** | `test_ocr_evasion.py` | `test_ocr_substitution_pan_repair` | Repaired & Redacted | ✅ PASSED |
| **OCR Confusion** | `test_ocr_evasion.py` | `test_ocr_substitution_ssn_repair` | Repaired & Redacted | ✅ PASSED |
| **OCR Confusion** | `test_ocr_evasion.py` | `test_ambiguous_ocr_forces_human_review_never_safe` | `HUMAN_REVIEW` | ✅ PASSED |
| **Masked PII** | `test_ocr_evasion.py` | `test_partially_masked_ssn_detected` | Detected & Redacted | ✅ PASSED |
| **Masked PII** | `test_ocr_evasion.py` | `test_partially_masked_cc_detected` | Detected & Redacted | ✅ PASSED |
| **Policy Governance** | `test_policy_bypass.py` | `test_insecure_policy_extraction_uncertainty_safe_rejected` | Fallback Strict Policy | ✅ PASSED |
| **Policy Governance** | `test_policy_bypass.py` | `test_inverted_thresholds_rejected` | Strict Validation Rejection | ✅ PASSED |
| **Policy Governance** | `test_policy_bypass.py` | `test_fallback_strict_policy_mandates_human_review` | `HUMAN_REVIEW` | ✅ PASSED |
| **Policy Governance** | `test_policy_bypass.py` | `test_extraction_uncertainty_overrides_low_confidence` | `HUMAN_REVIEW` | ✅ PASSED |
| **Redaction Gate** | `test_redaction_bypass.py` | `test_legitimate_tokens_receive_immunity` | Immunity Preserved | ✅ PASSED |
| **Redaction Gate** | `test_redaction_bypass.py` | `test_attacker_bracketed_text_not_immune_if_invalid_format` | Detected & Blocked | ✅ PASSED |
| **Redaction Gate** | `test_redaction_bypass.py` | `test_residual_pii_on_rescan_forces_blocked` | `BLOCKED` | ✅ PASSED |
| **Redaction Gate** | `test_redaction_bypass.py` | `test_missing_output_file_fails_closed` | `NOT_SAFE` | ✅ PASSED |
| **Unicode Evasion** | `test_unicode_evasion.py` | `test_unicode_non_breaking_space_in_email` | Normalized & Redacted | ✅ PASSED |
| **Unicode Evasion** | `test_unicode_evasion.py` | `test_unicode_fullwidth_digits_ssn` | Normalized & Redacted | ✅ PASSED |
| **Unicode Evasion** | `test_unicode_evasion.py` | `test_ssn_separator_evasion_dots` | Normalized & Redacted | ✅ PASSED |
| **Unicode Evasion** | `test_unicode_evasion.py` | `test_ssn_separator_evasion_multi_spaces` | Normalized & Redacted | ✅ PASSED |
| **Unicode Evasion** | `test_unicode_evasion.py` | `test_unicode_zero_width_space_evasion_flag` | Flagged & Intercepted | ✅ PASSED |

---

## Newly Added Feature Test Verification (26 Tests)

- `test_visual_pii.py`: 4 / 4 passed (Signatures, ID photos vs banners, visual uncertainty fail-closed).
- `test_ocr_reliability.py`: 5 / 5 passed (Otsu binarization, noise filtering, disagreement detection).
- `test_workbench.py`: 2 / 2 passed (Signed audit overrides, hard gate invariance enforcement).
- `test_audit_chain.py`: 3 / 3 passed (SHA-256 hash chaining, tamper detection on direct SQLite edits).
- `test_coverage_map.py`: 3 / 3 passed (Page-level and modality coverage gates).
- `test_explainability.py`: 2 / 2 passed (Decision provenance, context keywords, checksum rationale).
- `test_risk_scorer.py`: 4 / 4 passed (0–100 deterministic scoring, identity correlation boost, residual lock).
- `test_file_security.py`: 3 / 3 passed (SHA-256 integrity check, atomic writes, temp file cleanup).

---

## Conclusion
The gateway maintains **100% test pass rate with 0 false-safe escapes**, successfully hardened against evasion while adding enterprise operations capability.
