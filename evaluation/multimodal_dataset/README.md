# Multimodal Synthetic PII Dataset & Ground Truth

## 1. Overview & Purpose
This module provides a reproducible, deterministic synthetic multimodal dataset designed as the empirical benchmark and training foundation for advanced layout-aware and multimodal PII detectors (Phase 5).

In enterprise environments (such as Optiv cybersecurity audits), sensitive information does not solely exist in plain text paragraphs. It appears across:
- **Spatial shapes & diagrams** (e.g. PPTX organizational charts where names, roles, and employee IDs occupy adjacent visual shapes).
- **Tabular layouts** (DOCX tables and spreadsheet grids where column headers provide the semantic anchor for cell data).
- **Scanned pages & embedded screenshots** (low-resolution OCR text, character substitutions like `O` $\leftrightarrow$ `0`, and bounding boxes).
- **Document properties & metadata** (hidden author names, email handles, and corporate identifiers).
- **Partially masked records & indirect identifiers** (where multiple non-PII attributes combine to uniquely isolate an identity).

This dataset models all these modalities with **fine-grained bounding-box coordinates**, **entity identity keys**, and **relationship graphs**, while ensuring **strict zero real PII** and **provable zero train/test entity leakage**.

---

## 2. Directory Structure

```
evaluation/multimodal_dataset/
├── __init__.py        # Public module exports
├── schemas.py         # Dataclasses (DatasetSample, PIIAnnotation, BlockAnnotation, etc.)
├── scenarios.py       # 12 multimodal scenario builders (A through L)
├── generator.py       # Master deterministic generator (seed=42)
├── validators.py      # Strict schema, bbox, relationship, and leakage validators
├── exporters.py       # JSONL, JSON, CSV, Manifest, and Statistics report generators
└── README.md          # Technical documentation

data/multimodal_dataset/
├── raw/               # 35 raw text files ({sample_id}.txt)
├── annotations/       # 35 per-sample JSON ground-truth records
├── manifests/         # manifest.json (dataset version, seed, distributions)
├── statistics/        # statistics.json & statistics.md
└── exports/           # dataset_train.jsonl, dataset_validation.jsonl, dataset_test.jsonl,
                       # dataset_all.jsonl, multimodal_dataset_full.json, annotations_flattened.csv
```

---

## 3. Schema & Coordinate System

### Coordinate Standard
All bounding boxes (`bbox`) use **normalized float coordinates** `[x1, y1, x2, y2]`:
- $0.0 \le x_1 \le x_2 \le 1.0$ (horizontal proportion from left edge)
- $0.0 \le y_1 \le y_2 \le 1.0$ (vertical proportion from top edge)

Normalized coordinates ensure annotations remain completely resolution-independent whether rendered at 72 DPI, 300 DPI, or on high-resolution displays.

### Core Schemas (`schemas.py`)
- **`DatasetSample`**: Complete sample container holding text, blocks, annotations, relationships, and visuals.
- **`BlockAnnotation`**: Layout block representation (`paragraph`, `table_cell`, `shape`, `image_region`, `metadata`).
- **`PIIAnnotation`**: Fine-grained PII ground truth:
  - `annotation_id`: Deterministic ID (`ann_{split}_{idx}`)
  - `pii_type`: Canonical PII type (e.g. `PERSON`, `EMAIL`, `PAN`, `SECRET`)
  - `text`: Exact surface text
  - `normalized_text`: Canonical repaired / unmasked text
  - `bbox`: `[x1, y1, x2, y2]`
  - `source`: Allowed source (`native_text`, `OCR`, `metadata`, `table`, `shape`, `image`, `header`, `footer`, `notes`)
  - `is_masked`: Boolean flag
  - `is_indirect`: Boolean flag
  - `is_partial`: Boolean flag
  - `entity_id`: Global entity key (`entity_{split}_{idx}`)
  - `relationship_ids`: References to connected `RelationshipAnnotation` records
- **`RelationshipAnnotation`**: Explicit contextual or structural relationship:
  - `relationship_type`: `SAME_ENTITY`, `ASSOCIATED_WITH`, `LOCATED_NEAR`, `BELONGS_TO`, `MANAGES`, `REPORTS_TO`, `CORROBORATES`
  - `evidence`: Explanation of contextual linkage
- **`VisualAnnotation`**: High-level visual element (`screenshot`, `table_grid`, `diagram`, `badge`).

---

## 4. Supported PII Types
Covers all 16 canonical enterprise types recognized by the gateway:
1. `PERSON`
2. `EMAIL`
3. `PHONE`
4. `ADDRESS`
5. `DOB`
6. `SSN`
7. `PAN`
8. `PASSPORT`
9. `PESEL`
10. `EMPLOYEE_ID`
11. `DIRECTOR_ID`
12. `VENDOR_ID`
13. `CUSTOMER_ID`
14. `CREDIT_CARD`
15. `BANK_ACCOUNT`
16. `IFSC`
17. `SECRET`

---

## 5. Splitting Strategy & Zero Entity Leakage

The dataset is partitioned deterministically:
- **Train Split**: 25 samples (~71.4%)
- **Validation Split**: 5 samples (~14.3%)
- **Test Split**: 5 samples (~14.3%)

### Mathematical Leakage Guarantee
To prevent evaluation inflation:
- Synthetic identities (names, emails, employee IDs, phone numbers, and entity IDs) are partitioned into **strictly disjoint pools**.
- Entities appearing in `train` (e.g. `entity_train_0001` - Vikram Malhotra) **NEVER** appear in `validation` or `test`.
- The dataset validator automatically asserts:
  $$\text{Entities}(\text{Train}) \cap \text{Entities}(\text{Val}) = \emptyset$$
  $$\text{Entities}(\text{Train}) \cap \text{Entities}(\text{Test}) = \emptyset$$
  $$\text{Entities}(\text{Val}) \cap \text{Entities}(\text{Test}) = \emptyset$$

---

## 6. Hard Negatives (False-Alarm Protection)
**8 samples (22.86%)** are dedicated hard negatives containing enterprise terminology that often confuses naive detectors:
- Corporate names (`Amazon`, `Optiv`)
- Department titles (`Department of Finance`, `Security Operations`)
- Handbook titles (`Employee Handbook Section 4.2`)
- Project IDs and Error codes (`Project 10291`, `Error 123456`)
- Standard non-birth dates (`2026-10-09`)
- Public system emails (`public-support@example.com`)

---

## 7. Reproducibility & Generation
The dataset generation is 100% deterministic using random seed `42`. To regenerate:
```bash
python -m evaluation.multimodal_dataset.generator
```
All samples, annotation IDs, and hashes are identical across environments.

---

## 8. Known Limitations
- The dataset utilizes synthetic geometric coordinates rather than rendering actual bitmap PDFs/PPTXs to disk.
- Designed as benchmark ground-truth for Phase 5B multimodal evaluation rather than a massive pretraining corpus.
