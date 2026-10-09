# Phase 8: Adversarial Security Evaluation Report

## 1. Overview & Objective
Phase 8 tested the PII Security Gateway against deliberate adversarial evasion attacks. The primary security invariant enforced is:
**`UNKNOWN / UNCERTAIN / FAILED VERIFICATION -> HUMAN_REVIEW or BLOCKED`**, never silently **`SAFE`**.

---

## 2. Attack Categories & Empirical Results

### Category 1: Unicode & Whitespace Evasion (5 Tests)
- **Vectors Tested**: Non-breaking spaces (`\u00A0`), full-width digits (`\uFF11\uFF12\uFF13...`), zero-width spaces (`\u200B`), dot-separated SSNs, multi-space delimiters.
- **Outcome**: All 5 vectors detected or flagged with extraction uncertainty. Zero-width obfuscation routes to `HUMAN_REVIEW`.

### Category 2: OCR Confusion (5 Tests)
- **Vectors Tested**: Alphanumeric substitutions (O/0, I/1, S/5, B/8, Z/2) across PAN and SSN; degraded scans (<0.35 confidence); partially masked credit cards and SSNs.
- **Outcome**: Deterministic OCR character repairs successfully restored valid candidates; unreadable pages triggered `BLOCKED`/`HUMAN_REVIEW`.

### Category 3: Split Layout PII (3 Tests)
- **Vectors Tested**: Label-value split across neighboring presentation shapes, table cell value with column header context, fragmented layout blocks.
- **Outcome**: Layout-aware multimodal detector utilized table header context and spatial neighbors; unresolvable fragments routed to `HUMAN_REVIEW`.

### Category 4: Token Immunity & Redaction Bypass (4 Tests)
- **Vectors Tested**: Legitimate session tokens, attacker bracket injection (`[john.doe@cadence.com]`), residual PII on disk, missing sanitized file.
- **Outcome**: Only legitimate tokens receive immunity; attacker brackets fail regex; residual disk PII triggers `BLOCKED`.

### Category 5: Policy Bypass & Threshold Boundaries (4 Tests)
- **Vectors Tested**: Insecure policy YAML (`on_extraction_uncertainty: SAFE`), inverted thresholds, fallback strict status, low-confidence PII with extraction uncertainty.
- **Outcome**: Malicious policy configurations rejected by `PolicyValidator`; extraction uncertainty strictly overrides confidence scores.

### Category 6: Fail-Closed & Entity Ambiguity (4 Tests)
- **Vectors Tested**: Malicious extension (`.exe`), zero-finding OCR failure, conflicting emails with identical surnames (anti-merge), regression against image OCR unavailability.
- **Outcome**: All malformed inputs blocked; conflicting identities prevented from merging; 0 false-safe releases.

### Category 7: Metadata Evasion (2 Tests)
- **Vectors Tested**: Author metadata PII, unreadable/corrupted metadata streams.
- **Outcome**: Metadata converted to `DocumentBlock` and inspected; corrupted metadata routes to `HUMAN_REVIEW`.

---

## 3. Vulnerabilities & Hardening Patches
1. **SSN Delimiter Evasion**: Expanded `SSN_PATTERN` to `[- .\t]+` in `detection/enterprise_patterns.py`.
2. **Masked SSN Boundary Flaw**: Fixed `\b` boundary failure on asterisks in `detection/masked_detector.py` using non-whitespace lookbehind `(?:(?<!\S)|\b)`.

---

## 4. Final Assessment
- **Adversarial Tests**: 27 / 27 Passed (100%)
- **Total Test Suite**: 160 / 160 Passed (100% Green in 9.82s)
- **False-Safe Count**: **0**
