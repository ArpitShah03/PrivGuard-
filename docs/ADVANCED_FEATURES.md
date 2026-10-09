# Advanced Features & Enterprise Governance Guide

## QuantumShield v2 — Modernized Architecture

This document describes the advanced capabilities delivered in the **P0 to P11 Product Modernization**:

---

### 1. 👁️ Before / After Document Viewer (P0)
- **PDF Documents:** Leverages PyMuPDF (`fitz`) to render high-resolution raster pixmaps of original and sanitized pages side-by-side. Includes interactive page navigation and zoom controls.
- **DOCX / PPTX / TXT:** Synchronized side-by-side block comparator highlighting token substitutions (e.g., `[PERSON_001]`, `[SSN_001]`) while keeping original raw text masked in review cards to prevent privacy leaks.

### 2. 📸 Multimodal Visual PII Detection (P1)
- **Signatures:** Inspects vector drawing paths and clusters of bezier strokes within proximity of signature keywords ("Authorized Signature", "Signed by").
- **ID Photos:** Classifies embedded portrait photographs (badge/passport dimensions 1:1 to 1:1.3) and distinguishes them from decorative headers, logos, and full-page backgrounds.
- **Official Stamps / Seals:** Detects circular/oval notarization marks.
- **Fail-Closed:** Unreadable or corrupt image streams trigger visual extraction uncertainty $\rightarrow$ `HUMAN_REVIEW`.

### 3. ⚙️ Advanced OCR Reliability & Multi-Pass Disagreement (P2)
- **Preprocessing:** Otsu binarization, noise reduction with median filters, and automatic contrast stretching.
- **Multi-Pass Retry:** Low-confidence blocks are retried with 2x resolution and enhanced contrast.
- **Disagreement Detection:** Flags substitution discrepancies on confusion characters (`O` $\leftrightarrow$ `0`, `S` $\leftrightarrow$ `5`, `I` $\leftrightarrow$ `1`) and triggers extraction uncertainty.

### 4. 👷 Human Review Workbench (P3)
- Dedicated console for compliance officers when files are held in `HUMAN_REVIEW`.
- Actions: `APPROVE`, `REJECT`, `REQUEST_RESCAN`.
- **Inviolable Invariant:** Human approval can NEVER release a document containing residual high-risk PII or credentials. Overrides are cryptographically signed with reviewer ID, rationale, and SHA-256 hash.

### 5. 🗺️ Multi-Modal PII Coverage Map (P4)
- Granular breakdown of Native Text (%), OCR Scanned (%), Visual (%), and Metadata (%).
- Page-level coverage evaluation: if any page drops below 90% or document overall drops below 95%, the gate flags a coverage deficit.

### 6. 💡 Explainable AI Evidence (P5)
- Every detected finding presents its provenance chain:
  - Primary detector and corroborating sources.
  - Context keywords identified in proximity.
  - Mathematical checksum verification (Luhn, Verhoeff).
  - Fusion agreement category.

### 7. 🛡️ Tamper-Evident Audit Hash Chaining (P6)
- Blockchain-style SHA-256 hash chaining:
  $$H_i = \text{SHA-256}(H_{i-1} \parallel \text{timestamp} \parallel \text{stage} \parallel \text{canonical\_payload})$$
- Automated integrity verification utility (`AuditHasher.verify_event_chain`) validates the entire event log on startup and detects unauthorized record modifications.

### 8. 📊 Deterministic PII Security Risk Score (P7)
- 0 to 100 risk score based on entity severity weights, extraction ambiguity penalties, and identity correlation bonuses (e.g. Person + SSN + Contact).
- Hard gates cannot be overridden by low risk scores.

### 9. ⚔️ Adversarial Attack Simulation Lab (P8)
- Interactive playground directly accessible in the sidebar to simulate and visualize defenses against:
  - Zero-width Unicode evasion
  - OCR character confusion
  - Bracket token spoofing
  - Split layout evasion
  - Masked PII correlation

### 10. 🔒 File Integrity & Secure Temp Lifecycle (P10 & P11)
- Input and output artifacts have SHA-256 hashes computed, stored in SQLite audit records, and displayed in the UI.
- Secure scratch workspace context manager guarantees zero residual sensitive temp files on disk.
