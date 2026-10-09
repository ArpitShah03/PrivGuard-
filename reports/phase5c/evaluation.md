# Phase 5C Evaluation Report: Detector Fusion & Confidence Calibration

## Executive Summary
This report summarizes the benchmark evaluation of the Phase 5C Evidence Fusion and Confidence Calibration subsystem on the untouched Phase 5A test split.

### Overall Performance Metrics
- **Test Samples**: 5
- **Precision**: 1.0000 (100.00%)
- **Recall**: 1.0000 (100.00%)
- **F1 Score**: 1.0000 (100.00%)
- **True Positives (TP)**: 18
- **False Positives (FP)**: 0
- **False Negatives (FN)**: 0
- **True Negatives (TN)**: 1
- **Hard Negative FP Rate**: 0.0000

---

## Decision Policy Distribution
| Decision | Count | Percentage |
| :--- | :--- | :--- |
| **DETECT** | 18 | 94.7% |
| **HUMAN_REVIEW** | 0 | 0.0% |
| **SUPPRESS** | 1 | 5.3% |

---

## Multi-Detector Agreement Classification
| Agreement Status | Count | Description |
| :--- | :--- | :--- |
| **UNANIMOUS** | 9 | All active detectors concurred on entity type |
| **MAJORITY** | 1 | Majority consensus across active detectors |
| **SINGLE_DETECTOR** | 9 | Exactly one detector fired |
| **DETERMINISTIC_OVERRIDE** | 0 | Algorithmic checksum/validator dominated |
| **CONFLICT** | 0 | Disagreement routed to HUMAN_REVIEW |

---

## Calibration Metrics (Test Split)
- **Uncalibrated ECE**: 0.0216
- **Calibrated ECE**: 0.0467
- **ECE Reduction**: -116.2%
- **Uncalibrated Brier Score**: 0.0005
- **Calibrated Brier Score**: 0.0023

---

## Per-PII Type Breakdown
| Entity Type | Precision | Recall | F1 Score | TP | FP | FN |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `DIRECTOR_ID` | 1.00 | 1.00 | 1.00 | 1 | 0 | 0 |
| `EMAIL` | 1.00 | 1.00 | 1.00 | 3 | 0 | 0 |
| `EMPLOYEE_ID` | 1.00 | 1.00 | 1.00 | 4 | 0 | 0 |
| `PERSON` | 1.00 | 1.00 | 1.00 | 7 | 0 | 0 |
| `PHONE` | 1.00 | 1.00 | 1.00 | 1 | 0 | 0 |
| `SECRET` | 1.00 | 1.00 | 1.00 | 1 | 0 | 0 |
| `SSN` | 1.00 | 1.00 | 1.00 | 1 | 0 | 0 |
