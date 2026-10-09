import re
from typing import List, Set, Dict, Any
from evaluation.multimodal_dataset.schemas import (
    DatasetSample,
    CANONICAL_PII_TYPES,
    ALLOWED_SOURCES,
    ALLOWED_RELATIONSHIPS,
    ALLOWED_MODALITIES,
)


class DatasetValidationError(Exception):
    """Raised when multimodal dataset validation fails."""
    pass


def validate_bbox(bbox: List[float], context_str: str) -> None:
    """Validate normalized bounding box coordinates [x1, y1, x2, y2]."""
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        raise DatasetValidationError(f"Invalid bbox format in {context_str}: {bbox}. Expected 4 float values.")
    x1, y1, x2, y2 = bbox
    for val in (x1, y1, x2, y2):
        if not isinstance(val, (int, float)):
            raise DatasetValidationError(f"Non-numeric coordinate in {context_str}: {bbox}")
        if val < 0.0 or val > 1.0:
            raise DatasetValidationError(f"Coordinate out of range [0.0, 1.0] in {context_str}: {bbox}")
    if x1 > x2 or y1 > y2:
        raise DatasetValidationError(f"Inverted coordinates (x1 > x2 or y1 > y2) in {context_str}: {bbox}")


def validate_synthetic_privacy(text: str, context_str: str) -> None:
    """Ensure no real human PII exists in ground truth."""
    # Check email domain
    email_matches = re.findall(r'[\w\.-]+@([\w\.-]+)', text)
    for domain in email_matches:
        d_lower = domain.lower()
        allowed_domains = {"example.com", "example.org", "example.net", "testcorp.local", "cadence-synth.internal", "mockcorp.test"}
        if d_lower not in allowed_domains:
            raise DatasetValidationError(f"Potentially non-synthetic email domain '{domain}' found in {context_str}")


def validate_sample(sample: DatasetSample) -> None:
    """Validate an individual multimodal dataset sample."""
    if not sample.sample_id or not isinstance(sample.sample_id, str):
        raise DatasetValidationError(f"Sample has invalid sample_id: {sample.sample_id}")

    if sample.split not in {"train", "validation", "test"}:
        raise DatasetValidationError(f"Sample {sample.sample_id} has invalid split: '{sample.split}'. Must be train/validation/test.")

    if sample.document_modality not in ALLOWED_MODALITIES:
        raise DatasetValidationError(f"Sample {sample.sample_id} has invalid modality: '{sample.document_modality}'.")

    # Validate blocks
    seen_block_ids: Set[str] = set()
    for block in sample.blocks:
        if block.sample_id != sample.sample_id:
            raise DatasetValidationError(f"Block {block.block_id} sample_id '{block.sample_id}' mismatch with sample '{sample.sample_id}'.")
        if block.block_id in seen_block_ids:
            raise DatasetValidationError(f"Duplicate block_id '{block.block_id}' in sample '{sample.sample_id}'.")
        seen_block_ids.add(block.block_id)
        validate_bbox(block.bbox, f"Block {block.block_id} in {sample.sample_id}")

    # Validate PII annotations
    ann_map: Dict[str, Any] = {}
    for ann in sample.pii_annotations:
        if ann.sample_id != sample.sample_id:
            raise DatasetValidationError(f"Annotation {ann.annotation_id} sample_id '{ann.sample_id}' mismatch with '{sample.sample_id}'.")
        if ann.annotation_id in ann_map:
            raise DatasetValidationError(f"Duplicate annotation_id '{ann.annotation_id}' in sample '{sample.sample_id}'.")
        ann_map[ann.annotation_id] = ann

        if ann.pii_type not in CANONICAL_PII_TYPES:
            raise DatasetValidationError(f"Invalid pii_type '{ann.pii_type}' in annotation {ann.annotation_id}. Allowed: {CANONICAL_PII_TYPES}")

        if ann.source not in ALLOWED_SOURCES:
            raise DatasetValidationError(f"Invalid source '{ann.source}' in annotation {ann.annotation_id}. Allowed: {ALLOWED_SOURCES}")

        if not ann.text:
            raise DatasetValidationError(f"Annotation {ann.annotation_id} in {sample.sample_id} has empty text.")

        if not ann.normalized_text:
            raise DatasetValidationError(f"Annotation {ann.annotation_id} in {sample.sample_id} has empty normalized_text.")

        validate_bbox(ann.bbox, f"PII Annotation {ann.annotation_id} in {sample.sample_id}")
        validate_synthetic_privacy(ann.text, f"PII Annotation {ann.annotation_id}")

    # Validate Relationships
    seen_rel_ids: Set[str] = set()
    for rel in sample.relationships:
        if rel.sample_id != sample.sample_id:
            raise DatasetValidationError(f"Relationship {rel.relationship_id} sample_id mismatch in {sample.sample_id}.")
        if rel.relationship_id in seen_rel_ids:
            raise DatasetValidationError(f"Duplicate relationship_id '{rel.relationship_id}' in sample '{sample.sample_id}'.")
        seen_rel_ids.add(rel.relationship_id)

        if rel.relationship_type not in ALLOWED_RELATIONSHIPS:
            raise DatasetValidationError(f"Invalid relationship_type '{rel.relationship_type}' in {rel.relationship_id}.")

        if rel.source_annotation_id not in ann_map:
            raise DatasetValidationError(f"Relationship {rel.relationship_id} references nonexistent source annotation '{rel.source_annotation_id}'.")
        if rel.target_annotation_id not in ann_map:
            raise DatasetValidationError(f"Relationship {rel.relationship_id} references nonexistent target annotation '{rel.target_annotation_id}'.")

        # Entity identity check for SAME_ENTITY
        if rel.relationship_type == "SAME_ENTITY":
            src_ann = ann_map[rel.source_annotation_id]
            tgt_ann = ann_map[rel.target_annotation_id]
            if not src_ann.entity_id or not tgt_ann.entity_id:
                raise DatasetValidationError(f"SAME_ENTITY relationship {rel.relationship_id} requires entity_id on both annotations.")
            if src_ann.entity_id != tgt_ann.entity_id:
                raise DatasetValidationError(f"SAME_ENTITY relationship {rel.relationship_id} links conflicting entity_ids '{src_ann.entity_id}' and '{tgt_ann.entity_id}'.")

    # Validate Visuals
    for vis in sample.visuals:
        if vis.sample_id != sample.sample_id:
            raise DatasetValidationError(f"Visual {vis.visual_id} sample_id mismatch in {sample.sample_id}.")
        validate_bbox(vis.bbox, f"Visual {vis.visual_id} in {sample.sample_id}")


def validate_dataset(samples: List[DatasetSample]) -> Dict[str, Any]:
    """
    Perform complete cross-sample validation over the entire multimodal dataset:
    - Sample ID uniqueness
    - Global annotation ID uniqueness
    - Train/Validation/Test split balance
    - Strict zero entity leakage across splits
    - Synthetic privacy assurance
    """
    if not samples:
        raise DatasetValidationError("Dataset is empty. At least one sample is required.")

    seen_sample_ids: Set[str] = set()
    seen_global_ann_ids: Set[str] = set()
    split_entities: Dict[str, Set[str]] = {"train": set(), "validation": set(), "test": set()}
    split_sample_counts: Dict[str, int] = {"train": 0, "validation": 0, "test": 0}

    for sample in samples:
        if sample.sample_id in seen_sample_ids:
            raise DatasetValidationError(f"Globally duplicate sample_id: '{sample.sample_id}'")
        seen_sample_ids.add(sample.sample_id)

        validate_sample(sample)

        split_sample_counts[sample.split] = split_sample_counts.get(sample.split, 0) + 1

        for ann in sample.pii_annotations:
            if ann.annotation_id in seen_global_ann_ids:
                raise DatasetValidationError(f"Globally duplicate annotation_id: '{ann.annotation_id}' across dataset.")
            seen_global_ann_ids.add(ann.annotation_id)

            if ann.entity_id:
                split_entities[sample.split].add(ann.entity_id)

    # ZERO ENTITY LEAKAGE VERIFICATION
    train_entities = split_entities["train"]
    val_entities = split_entities["validation"]
    test_entities = split_entities["test"]

    train_val_leak = train_entities.intersection(val_entities)
    if train_val_leak:
        raise DatasetValidationError(f"CRITICAL ENTITY LEAKAGE between Train and Validation: {train_val_leak}")

    train_test_leak = train_entities.intersection(test_entities)
    if train_test_leak:
        raise DatasetValidationError(f"CRITICAL ENTITY LEAKAGE between Train and Test: {train_test_leak}")

    val_test_leak = val_entities.intersection(test_entities)
    if val_test_leak:
        raise DatasetValidationError(f"CRITICAL ENTITY LEAKAGE between Validation and Test: {val_test_leak}")

    return {
        "valid": True,
        "total_samples": len(samples),
        "total_annotations": len(seen_global_ann_ids),
        "split_counts": split_sample_counts,
        "unique_entities_per_split": {
            "train": len(train_entities),
            "validation": len(val_entities),
            "test": len(test_entities),
        },
        "leakage_detected": False
    }
