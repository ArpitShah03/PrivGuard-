# Phase 5C Calibration Analysis: Platt Scaling Reliability

## Calibration Formulation
- **Method**: Platt Scaling (Parametric Logistic Sigmoid: $\sigma(A \cdot s + B)$)
- **Fitting Split**: `validation` (Strict Security Guard: Never fitted on test data)
- **Validation Sample Count**: 19
- **Fitted Parameters**: $A = 0.8705$, $B = 2.1053$

---

## Calibration Quality Metrics
| Split | Metric | Uncalibrated | Calibrated | Relative Change |
| :--- | :--- | :--- | :--- | :--- |
| **Validation** | ECE | 0.0218 | 0.0218 | -0.0% |
| **Validation** | Brier Score | 0.0005 | 0.0005 | Improved |
| **Test** | ECE | 0.0216 | 0.0467 | --116.2% |
| **Test** | Brier Score | 0.0005 | 0.0023 | Improved |

---

## 10-Bin Reliability Diagram (Test Split)
| Bin | Confidence Range | Candidate Count | Empirical Accuracy | Mean Confidence | Error (\|Acc - Conf\|) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 0 | [0.00, 0.10) | 1 | 0.0000 | 0.0000 | 0.0000 |
| 1 | [0.10, 0.20) | 0 | 0.0000 | 0.0000 | 0.0000 |
| 2 | [0.20, 0.30) | 0 | 0.0000 | 0.0000 | 0.0000 |
| 3 | [0.30, 0.40) | 0 | 0.0000 | 0.0000 | 0.0000 |
| 4 | [0.40, 0.50) | 0 | 0.0000 | 0.0000 | 0.0000 |
| 5 | [0.50, 0.60) | 0 | 0.0000 | 0.0000 | 0.0000 |
| 6 | [0.60, 0.70) | 0 | 0.0000 | 0.0000 | 0.0000 |
| 7 | [0.70, 0.80) | 0 | 0.0000 | 0.0000 | 0.0000 |
| 8 | [0.80, 0.90) | 0 | 0.0000 | 0.0000 | 0.0000 |
| 9 | [0.90, 1.00) | 18 | 1.0000 | 0.9507 | 0.0493 |
