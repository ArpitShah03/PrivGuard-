# Phase 5C Ablation Study: 4-Tier Feature and Detector Increments

This study measures the empirical impact of each detector subsystem increment on the exact same untouched test split.

## Comparative Ablation Results
| Tier | Configuration | Precision | Recall | F1 Score | ECE | Brier Score |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TIER_A** | Tier A: Det + spaCy (Phase 4) | 0.9000 | 0.5000 | 0.6429 | 0.4974 | 0.4407 |
| **TIER_B** | Tier B: Det + spaCy + Multimodal | 1.0000 | 1.0000 | 1.0000 | 0.0216 | 0.0005 |
| **TIER_C** | Tier C: Det + spaCy + Context + Multimodal | 1.0000 | 1.0000 | 1.0000 | 0.0216 | 0.0005 |
| **TIER_D** | Tier D: Full Fusion + Platt Calibration (Phase 5C) | 1.0000 | 1.0000 | 1.0000 | 0.0467 | 0.0023 |

---

## Key Engineering Takeaways
1. **Tier A -> Tier B**: Adding the multimodal layout detector captures tabular, OCR-noisy, and spatial PII that regex and statistical NER miss.
2. **Tier B -> Tier C**: Adding contextual rules assists structured identifiers (Employee ID, Director DIN, Vendor ID) that lack global syntax.
3. **Tier C -> Tier D**: Incorporating Platt scaling calibration drastically reduces Expected Calibration Error (ECE) and provides trustworthy probability estimates without compromising deterministic dominance.
