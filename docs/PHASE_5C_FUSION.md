# Phase 5C: Detector Fusion & Confidence Calibration Architecture

## 1. Executive Summary & Objectives
Phase 5C completes the transition from disconnected individual detectors to a unified, explainable, and security-governed decision layer. It synthesizes evidence across 7 detection modalities, applies Platt scaling confidence calibration, and enforces a strict fail-closed decision hierarchy.

### Core Architectural Principles
1. **Extraction Uncertainty Priority**: A document block with uncertain or failed extraction (e.g. `OCR_UNAVAILABLE`, `IMAGE_OCR_UNAVAILABLE`, malformed text) can never be marked safe or suppressed; it is strictly routed to `HUMAN_REVIEW`.
2. **Deterministic Dominance**: Mathematical checksums (Luhn algorithm for credit cards, PESEL modulo-10, PAN structural patterns, Shannon entropy secrets) possess near-certain empirical reliability and strictly dominate probabilistic model disagreement. Probabilistic ML cannot veto a valid checksum.
3. **Explainable Weighted Fusion**: Multi-detector evidence is combined using configurable reliability weights and an agreement synergy bonus, rather than unsubstantiated mathematical claims.
4. **Platt Scaling Confidence Calibration**: Uncalibrated heuristic and model confidences are mapped to empirical probabilities using a 1D logistic sigmoid $\sigma(A \cdot s + B)$ fitted exclusively on the validation split. The test split remains completely untouched during training.
5. **Token Immunity**: Synthetic replacement tokens (e.g. `[PERSON_001]`, `[SSN_002]`) are protected from circular re-detection.
6. **Strict Privacy Safeguards**: Zero raw personal data is ever stored in fusion results, evidence records, model artifacts, or generated reports.

---

## 2. Multi-Detector Evidence Sources
The gateway arbitrates across 7 distinct evidence sources:

| Source | Identifier | Primary Target Entities | Reliability Weight (Default) |
| :--- | :--- | :--- | :--- |
| **Algorithmic** | `ALGORITHMIC` | Credit Card (Luhn), PESEL checksum, PAN tax format, Secrets (Entropy) | `1.00` |
| **Regex** | `REGEX` | Email, Phone, IP Address, SSN (bounded) | `0.90` |
| **Multimodal** | `MULTIMODAL` | Bounding boxes, layout, table cells, OCR noise, org-chart shapes | `0.85` |
| **Entity Resolution** | `ENTITY_RESOLUTION` | Cross-block identity linkage, graph corroborated variants | `0.85` |
| **Context Rules** | `CONTEXT` | Employee ID, Director DIN, Vendor ID, Date of Birth | `0.80` |
| **Masked PII** | `MASKED_PII` | Partially masked credentials (`***-**-1234`, `4111****1111`) | `0.80` |
| **spaCy NER** | `SPACY` | Statistical Person, Address, Organization | `0.75` |

*Note: Weights represent initial baseline configuration assumptions in `config/fusion_config.yaml` and are fully configurable.*

---

## 3. Decision Policy Hierarchy
Decisions are evaluated according to a deterministic security tree:

```
                    EXTRACTION UNCERTAINTY?
                         /          \
                       YES           NO
                       ↓              ↓
                HUMAN_REVIEW    Strong deterministic?
                                  /          \
                                YES           NO
                                ↓              ↓
                              DETECT      Calibrated score
                                           /       |       \
                                       HIGH     BORDERLINE   LOW
                                        ↓          ↓          ↓
                                      DETECT   HUMAN_REVIEW SUPPRESS
```

### Decision Rules
- **Extraction Uncertainty**: If `is_uncertain=True` or `OCR_UNAVAILABLE`, output `HUMAN_REVIEW`. SUPPRESS is forbidden.
- **Strong Deterministic**: If an algorithmic checksum or strong deterministic validator fires, output `DETECT` with `DETERMINISTIC_OVERRIDE` or `UNANIMOUS`.
- **Token Immunity / Hard Negative**: If synthetic token or uncorroborated corporate stop-word, output `SUPPRESS`.
- **Calibrated Score Tiers**:
  - `calibrated_confidence >= 0.70`: `DETECT`
  - `0.45 <= calibrated_confidence < 0.70`: `HUMAN_REVIEW`
  - `calibrated_confidence < 0.45`: `SUPPRESS`

---

## 4. Multi-Detector Agreement Classification
Every fusion decision is categorized into an auditable agreement state:
- `UNANIMOUS`: All active detectors concurred on the candidate entity type.
- `MAJORITY`: Consensus achieved across multiple detectors.
- `SINGLE_DETECTOR`: Exactly one detector identified the candidate.
- `DETERMINISTIC_OVERRIDE`: Algorithmic validator overrode conflicting probabilistic predictions.
- `CONFLICT`: Disagreement between detectors within the uncertainty window, routed to `HUMAN_REVIEW`.

---

## 5. Confidence Calibration Formulation
### Platt Scaling
$$\hat{P}(Y=1 \mid s) = \frac{1}{1 + \exp(-(A \cdot s + B))}$$
- **Fitted On**: Phase 5A `validation` split (19 candidate regions, 5 samples).
- **Fitted Parameters**: $A = 0.8705$, $B = 2.1053$.
- **Test Invariant**: Strictly forbidden from fitting on the test split.

### Calibration Quality Metrics
- **ECE (Expected Calibration Error)**: Evaluated across 10 equal-width bins in $[0, 1]$.
- **Brier Score**: $\frac{1}{N} \sum_{i=1}^N (p_i - y_i)^2$.

---

## 6. Empirical Benchmark Results (Phase 5A Test Split)
Evaluated on the untouched Phase 5A benchmark test set:

### Overall Test Metrics
- **Precision**: 100.00% (18 TP, 0 FP)
- **Recall**: 100.00% (18 TP, 0 FN)
- **F1 Score**: 1.0000
- **Hard Negative False Positive Rate**: 0.0000 (1 TN, 0 FP)

### 4-Tier Ablation Study
| Tier | Configuration | Precision | Recall | F1 Score | ECE | Brier Score |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Tier A** | Det + spaCy (Phase 4) | 0.9000 | 0.5000 | 0.6429 | 0.4974 | 0.2520 |
| **Tier B** | Det + spaCy + Multimodal | 1.0000 | 1.0000 | 1.0000 | 0.0216 | 0.0005 |
| **Tier C** | Det + spaCy + Context + Multimodal | 1.0000 | 1.0000 | 1.0000 | 0.0216 | 0.0005 |
| **Tier D** | Full Fusion + Platt Calibration (Phase 5C) | 1.0000 | 1.0000 | 1.0000 | 0.0467 | 0.0023 |

*Benchmark Caveat: These metrics reflect evaluation on the curated Phase 5A multimodal benchmark dataset. In real-world enterprise deployments with open-domain documents, recall and precision will vary according to OCR noise levels and document format complexity.*

---

## 7. Hard Cases Verification
1. **Extraction Uncertainty**: Verified that OCR-unavailable blocks route to `HUMAN_REVIEW` regardless of confidence.
2. **Deterministic Dominance**: Verified that Luhn and PESEL checksums override probabilistic model disagreement.
3. **Token Immunity**: Verified that synthetic replacement tokens are protected from circular re-detection.
4. **Corporate Stop-Words**: Verified that "Optiv Inc." is suppressed without corroborating identity evidence.
5. **Rotated OCR Noise**: Verified that OCR character noise is normalized and detected algorithmically.
6. **Table Spatial Context**: Verified that table headers associate with data cells.
7. **Org Chart Hierarchy**: Verified that executive reporting links are captured without corporate entity confusion.
8. **Partially Masked PII**: Verified that masked credentials (`***-**-1234`) are detected and sanitized.

---

## 8. Verification & Test Suite Status
- Total automated tests passing: **108 / 108 tests (100% green)**
- Regression coverage: Phases 1–5B remain 100% passing (95 tests), Phase 5C adds 13 tests.
