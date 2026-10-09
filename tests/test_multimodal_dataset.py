import os
import json
import csv
import pytest
from evaluation.multimodal_dataset.schemas import (
    DatasetSample,
    DocumentAnnotation,
    BlockAnnotation,
    PIIAnnotation,
    RelationshipAnnotation,
    CANONICAL_PII_TYPES,
)
from evaluation.multimodal_dataset.generator import MultimodalDatasetGenerator
from evaluation.multimodal_dataset.validators import (
    validate_dataset,
    validate_bbox,
    validate_sample,
    DatasetValidationError,
)
from evaluation.multimodal_dataset.exporters import (
    compute_dataset_statistics,
    export_multimodal_dataset,
)


@pytest.fixture(scope="module")
def default_dataset():
    """Generate the standard multimodal dataset once for testing."""
    generator = MultimodalDatasetGenerator(seed=42)
    return generator.generate_dataset()


def test_deterministic_generation(default_dataset):
    """Verify identical seeds produce identical samples, annotations, and IDs."""
    gen2 = MultimodalDatasetGenerator(seed=42)
    ds2 = gen2.generate_dataset()

    assert len(default_dataset) == len(ds2)
    for s1, s2 in zip(default_dataset, ds2):
        assert s1.sample_id == s2.sample_id
        assert s1.split == s2.split
        assert s1.category == s2.category
        assert len(s1.pii_annotations) == len(s2.pii_annotations)
        for a1, a2 in zip(s1.pii_annotations, s2.pii_annotations):
            assert a1.annotation_id == a2.annotation_id
            assert a1.text == a2.text
            assert a1.bbox == a2.bbox


def test_dataset_size_and_splits(default_dataset):
    """Verify >= 30 samples and 70/15/15 split distribution."""
    total = len(default_dataset)
    assert total >= 30

    train_count = sum(1 for s in default_dataset if s.split == "train")
    val_count = sum(1 for s in default_dataset if s.split == "validation")
    test_count = sum(1 for s in default_dataset if s.split == "test")

    assert train_count + val_count + test_count == total
    assert 0.65 <= (train_count / total) <= 0.75
    assert 0.10 <= (val_count / total) <= 0.20
    assert 0.10 <= (test_count / total) <= 0.20


def test_bounding_box_validation():
    """Verify bbox validation enforces [0.0, 1.0] and x1 <= x2, y1 <= y2."""
    # Valid box
    validate_bbox([0.1, 0.2, 0.5, 0.6], "test")

    # Out of bounds
    with pytest.raises(DatasetValidationError):
        validate_bbox([-0.1, 0.2, 0.5, 0.6], "test")

    with pytest.raises(DatasetValidationError):
        validate_bbox([0.1, 0.2, 1.5, 0.6], "test")

    # Inverted coordinates
    with pytest.raises(DatasetValidationError):
        validate_bbox([0.7, 0.2, 0.5, 0.6], "test")

    with pytest.raises(DatasetValidationError):
        validate_bbox([0.1, 0.8, 0.5, 0.6], "test")


def test_canonical_pii_types_coverage(default_dataset):
    """Verify canonical PII types are properly recognized and present."""
    found_types = set()
    for s in default_dataset:
        for ann in s.pii_annotations:
            assert ann.pii_type in CANONICAL_PII_TYPES
            found_types.add(ann.pii_type)

    # Must cover major categories
    assert "PERSON" in found_types
    assert "EMAIL" in found_types
    assert "PHONE" in found_types
    assert "SSN" in found_types
    assert "PAN" in found_types
    assert "PESEL" in found_types
    assert "IFSC" in found_types
    assert "EMPLOYEE_ID" in found_types
    assert "CREDIT_CARD" in found_types
    assert "SECRET" in found_types


def test_relationships_validity(default_dataset):
    """Verify all relationship annotations reference valid annotations within the same sample."""
    total_rels = 0
    for s in default_dataset:
        ann_ids = {a.annotation_id for a in s.pii_annotations}
        for rel in s.relationships:
            total_rels += 1
            assert rel.source_annotation_id in ann_ids
            assert rel.target_annotation_id in ann_ids
            assert rel.relationship_type in {
                "SAME_ENTITY", "ASSOCIATED_WITH", "LOCATED_NEAR",
                "BELONGS_TO", "MANAGES", "REPORTS_TO", "CORROBORATES"
            }
    assert total_rels > 0


def test_zero_entity_leakage_across_splits(default_dataset):
    """CRITICAL: Verify train, validation, and test splits have 0 entity ID overlap."""
    train_entities = {a.entity_id for s in default_dataset if s.split == "train" for a in s.pii_annotations if a.entity_id}
    val_entities = {a.entity_id for s in default_dataset if s.split == "validation" for a in s.pii_annotations if a.entity_id}
    test_entities = {a.entity_id for s in default_dataset if s.split == "test" for a in s.pii_annotations if a.entity_id}

    assert train_entities.intersection(val_entities) == set()
    assert train_entities.intersection(test_entities) == set()
    assert val_entities.intersection(test_entities) == set()


def test_hard_negative_ratio(default_dataset):
    """Verify hard negative samples constitute 20% to 30% of total samples."""
    stats = compute_dataset_statistics(default_dataset)
    neg_ratio = stats["hard_negative_ratio_pct"]
    assert 20.0 <= neg_ratio <= 30.0

    # Ensure hard negatives have zero PII annotations
    for s in default_dataset:
        if s.is_hard_negative:
            assert len(s.pii_annotations) == 0


def test_masked_pii_annotations(default_dataset):
    """Verify masked PII annotations have is_masked=True and valid canonical normalization."""
    masked_anns = [a for s in default_dataset for a in s.pii_annotations if a.is_masked]
    assert len(masked_anns) >= 3
    for a in masked_anns:
        assert a.is_masked is True
        assert a.normalized_text != a.text  # Normalized unmasked text differs from surface masked text


def test_ocr_noisy_variants(default_dataset):
    """Verify OCR noisy annotations preserve surface noise and canonical repaired text."""
    noisy_samples = [s for s in default_dataset if s.category == "ocr_noisy"]
    assert len(noisy_samples) >= 2
    for s in noisy_samples:
        for a in s.pii_annotations:
            assert a.source == "OCR"
            assert a.text != a.normalized_text  # Surface text has noise, normalized has canonical


def test_statistics_calculation_accuracy(default_dataset):
    """Verify statistics calculation aggregates accurately."""
    stats = compute_dataset_statistics(default_dataset)
    assert stats["total_samples"] == len(default_dataset)
    all_anns_count = sum(len(s.pii_annotations) for s in default_dataset)
    assert stats["total_pii_annotations"] == all_anns_count
    assert sum(stats["annotations_per_pii_type"].values()) == all_anns_count


def test_strict_synthetic_privacy(default_dataset):
    """Ensure no real human email domains or sensitive patterns exist in dataset."""
    allowed_domains = {"example.com", "example.org", "example.net", "testcorp.local", "cadence-synth.internal", "mockcorp.test"}
    for s in default_dataset:
        for a in s.pii_annotations:
            if a.pii_type == "EMAIL":
                domain = a.text.split("@")[-1].lower()
                assert domain in allowed_domains


def test_exporters_export_and_roundtrip(tmp_path, default_dataset):
    """Verify JSONL, JSON, CSV, Manifest, and Statistics file exports."""
    export_paths = export_multimodal_dataset(default_dataset, base_output_dir=str(tmp_path))

    # Check existence
    for path_key, p in export_paths.items():
        assert os.path.exists(p)
        assert os.path.getsize(p) > 0

    # Test JSONL roundtrip
    with open(export_paths["jsonl_all"], "r", encoding="utf-8") as f:
        lines = f.readlines()
    assert len(lines) == len(default_dataset)
    first_record = json.loads(lines[0])
    assert first_record["sample_id"] == default_dataset[0].sample_id

    # Test CSV format
    with open(export_paths["csv"], "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        assert "annotation_id" in header
        assert "pii_type" in header
        rows = list(reader)
        total_anns = sum(len(s.pii_annotations) for s in default_dataset)
        assert len(rows) == total_anns

    # Test Manifest schema
    with open(export_paths["manifest"], "r", encoding="utf-8") as f:
        manifest = json.load(f)
    assert manifest["seed"] == 42
    assert manifest["sample_count"] == len(default_dataset)
    assert manifest["zero_leakage_verified"] is True
