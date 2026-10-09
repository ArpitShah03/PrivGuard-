# Multimodal Synthetic PII Dataset Statistics Report
**PII Security Gateway — Evaluation & Benchmark Foundation**  
**Total Samples:** 35 | **Total Ground-Truth Annotations:** 119  

## 1. Split & Balance Overview
| Metric | Count | Percentage |
| :--- | :--- | :--- |
| **Split `test`** | 5 | 14.3% |
| **Split `train`** | 25 | 71.4% |
| **Split `validation`** | 5 | 14.3% |
| **Positive Samples** | 27 | 77.1% |
| **Hard Negatives** | 8 | 22.86% |

## 2. Ground-Truth PII Type Distribution
| Canonical PII Type | Ground-Truth Count | Share |
| :--- | :--- | :--- |
| **ADDRESS** | 3 | 2.5% |
| **BANK_ACCOUNT** | 1 | 0.8% |
| **CREDIT_CARD** | 3 | 2.5% |
| **CUSTOMER_ID** | 1 | 0.8% |
| **DIRECTOR_ID** | 4 | 3.4% |
| **DOB** | 1 | 0.8% |
| **EMAIL** | 21 | 17.6% |
| **EMPLOYEE_ID** | 14 | 11.8% |
| **IFSC** | 7 | 5.9% |
| **PAN** | 3 | 2.5% |
| **PASSPORT** | 1 | 0.8% |
| **PERSON** | 37 | 31.1% |
| **PESEL** | 1 | 0.8% |
| **PHONE** | 12 | 10.1% |
| **SECRET** | 2 | 1.7% |
| **SSN** | 7 | 5.9% |
| **VENDOR_ID** | 1 | 0.8% |

## 3. Modality & Layout Distribution
| Modality | Sample Count |
| :--- | :--- |
| `DOCX-LIKE PAGE` | 7 |
| `IMAGE/OCR` | 4 |
| `PDF-LIKE PAGE` | 4 |
| `PPTX-LIKE SLIDE` | 4 |
| `TABLE` | 3 |
| `TEXT` | 13 |

## 4. Edge-Case Coverage & Relationships
| Edge Case Dimension | Count |
| :--- | :--- |
| `masked_pii` | 6 |
| `indirect_pii` | 0 |
| `partial_pii` | 2 |
| `ocr_source_annotations` | 14 |
| `table_cell_annotations` | 28 |
| `shape_layout_annotations` | 24 |
| `metadata_annotations` | 2 |
| `total_relationships` | 45 |
| `relationship_ASSOCIATED_WITH` | 9 |
| `relationship_BELONGS_TO` | 3 |
| `relationship_MANAGES` | 3 |
| `relationship_REPORTS_TO` | 5 |
| `relationship_SAME_ENTITY` | 25 |