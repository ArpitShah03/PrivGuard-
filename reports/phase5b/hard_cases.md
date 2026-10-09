# Phase 5B Empirical Hard-Case Inspection Report
Targeted analysis of 8 designated multimodal edge cases on the Phase 5A benchmark:

| Case Archetype | Sample ID | Expected PII | Predicted PII | Score | Evidence | Result |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Org-Chart Spatial Hierarchy** | `sample_train_0004` | PERSON, EMAIL... | PERSON, EMAIL... | 1.00 | Relationship graph link (0.95) | **CORRECT** |
| **Table Cell Grid Layout** | `sample_train_0002` | PERSON, EMAIL... | PERSON, EMAIL... | 1.00 | Relationship graph link (0.95) | **CORRECT** |
| **Controlled OCR Noise** | `sample_train_0006` | PAN, SSN | PAN, SSN | 1.00 | Strong text pattern (0.80); Validated OCR candidate repair (0.95) | **CORRECT** |
| **Split-Layout Multi-Shape** | `sample_train_0003` | PERSON, PERSON... | DIRECTOR_ID, DIRECTOR_ID... | 1.00 | Relationship graph link (0.95) | **CORRECT** |
| **Same-Person Relationship Memo** | `sample_train_0010` | PERSON, EMAIL... | PERSON, EMAIL... | 1.00 | Relationship graph link (0.95) | **CORRECT** |
| **Similar-Name Anti-Merge Roster** | `sample_train_0009` | PERSON, PERSON... | PERSON, PERSON... | 1.00 | Standard multimodal features | **CORRECT** |
| **Hard-Negative Corporate Text** | `sample_train_0020` | NONE (Hard Negative) | NONE | 0.00 | No detection (Safe/Negative) | **CORRECT** |
| **Partially Masked Account Data** | `sample_train_0007` | SSN, CREDIT_CARD... | SSN, CREDIT_CARD... | 1.00 | Strong text pattern (0.90) | **CORRECT** |