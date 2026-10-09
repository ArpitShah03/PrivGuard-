# Phase 8: Adversarial Testing & Security Hardening Documentation

## 1. Threat Model & Security Objectives
The PII Security Gateway operates as a fail-closed pre-LLM sanitization gate for sensitive enterprise documents. The adversarial testing phase evaluates whether motivated attackers can exploit parser, detector, tokenizer, or policy edge cases to trigger an unintended `SAFE` release.

### Core Security Invariant
```text
UNKNOWN / UNCERTAIN / FAILED VERIFICATION
                  ↓
        HUMAN_REVIEW or BLOCKED

NEVER:
UNKNOWN → SAFE
```

---

## 2. Attack Categories & Methodologies

1. **Unicode & Separator Evasion**:
   - Assesses evasion via full-width digits, non-breaking spaces, zero-width characters, dots, and multi-space delimiters.
   - Defense: NFKC normalization and delimiter-flexible regex patterns.

2. **OCR Confusion**:
   - Assesses OCR digit-letter substitutions (O↔0, I↔1, S↔5, B↔8, Z↔2) and degraded page scans.
   - Defense: Algorithmic checksum validation on repaired candidates; low-confidence scans trigger fail-closed gating.

3. **Split-Layout PII**:
   - Assesses hiding PII across separate shape objects, table header/data cells, and fragmented sections.
   - Defense: Layout-aware multimodal detector combining spatial bounding boxes, neighbor texts, and structural metadata.

4. **Token Immunity Manipulation**:
   - Assesses attacker-crafted bracketed text to bypass post-redaction re-scan.
   - Defense: Strict regex restricting immunity to legitimate session-generated token syntaxes.

5. **Policy Bypass**:
   - Assesses hostile configuration edits (e.g., forcing `on_extraction_uncertainty: SAFE`).
   - Defense: Static validation with `PolicyValidator` rejecting insecure configurations and falling back to `STRICT_FAIL_CLOSED`.

6. **Identity Resolution Ambiguity**:
   - Assesses adversarial attempts to merge distinct identities sharing names or surnames.
   - Defense: Anti-merge rules requiring corroborating secondary evidence and rejecting conflicting strong identifiers (different emails/IDs).

---

## 3. Results Summary

- **Adversarial Test Suite**: 27 dedicated automated tests under `tests/adversarial/`.
- **Adversarial Results**: 27 / 27 Passed (100%).
- **Total Test Suite**: 160 / 160 Passed (100% Green in 9.82s).
- **False-Safe Count**: **0**.

---

## 4. Operational Boundaries & Known Limitations
- The gateway assumes local execution.
- Steganographic image payload analysis outside standard OCR rendering remains outside the local gateway scope.
- Normal application performance was unaffected (<5s test execution overhead).
