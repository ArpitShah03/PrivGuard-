import os
import pytest
from detection.multimodal.schemas import (
    MultimodalCandidateItem,
    MultimodalPrediction,
    EvidenceBreakdown,
)
from detection.multimodal.layout_features import compute_bbox_geometry, compute_neighbor_layout_relationships
from detection.multimodal.context_features import (
    extract_table_context_features,
    extract_relationship_context_features,
    detect_label_value_cues,
)
from detection.multimodal.feature_extractor import MultimodalFeatureExtractor
from detection.multimodal.detector import (
    LightweightMultimodalDetector,
    MultimodalDetectorError,
)
from detection.multimodal.fusion import fuse_multimodal_findings, block_to_candidate_item
from models.schemas import DocumentBlock, PIIFinding
from evaluation.multimodal_dataset.generator import MultimodalDatasetGenerator


@pytest.fixture(scope="module")
def trained_detector(tmp_path_factory):
    """Train and return detector instance in temporary test directory."""
    temp_dir = str(tmp_path_factory.mktemp("multimodal_model"))
    gen = MultimodalDatasetGenerator(seed=42)
    dataset = gen.generate_dataset()
    train_samples = [s for s in dataset if s.split == "train"]
    val_samples = [s for s in dataset if s.split == "validation"]

    detector = LightweightMultimodalDetector(model_dir=temp_dir)
    detector.train(train_samples, val_samples)
    detector.save()
    return detector


def test_feature_extraction_dimensions():
    """Verify master feature extractor produces all registered feature dimensions."""
    fe = MultimodalFeatureExtractor()
    item = MultimodalCandidateItem("s1", "b1", "Vikram Malhotra", bbox=[0.1, 0.1, 0.4, 0.2])
    feats, rep = fe.extract_features(item)

    assert len(feats) == len(fe.feature_names)
    assert "token_count" in feats
    assert "width" in feats
    assert "aspect_ratio" in feats
    assert "is_replacement_token" in feats


def test_bbox_geometry_calculation():
    """Verify normalized bounding box geometry metrics."""
    geom = compute_bbox_geometry([0.1, 0.2, 0.5, 0.6])
    assert geom["width"] == 0.4
    assert geom["height"] == 0.4
    assert geom["area"] == 0.16
    assert geom["center_x"] == 0.3
    assert geom["center_y"] == 0.4


def test_neighboring_block_context():
    """Verify horizontal/vertical neighbor relationship calculation."""
    b1 = MultimodalCandidateItem("s1", "b1", "Employee ID:", bbox=[0.05, 0.2, 0.25, 0.25])
    b2 = MultimodalCandidateItem("s1", "b2", "EMP-10291", bbox=[0.27, 0.2, 0.45, 0.25])
    rel = compute_neighbor_layout_relationships(b2, [b1, b2])

    assert rel["nearby_block_count"] == 1.0
    assert rel["has_left_neighbor"] == 1.0


def test_table_context_features():
    """Verify table cell index and header association features."""
    item = MultimodalCandidateItem(
        "s1", "b1", "rahul@example.com",
        source="table",
        metadata={"is_table_cell": True, "row_idx": 2, "col_idx": 1, "header_text": "Corporate Email"}
    )
    t_feats = extract_table_context_features(item)

    assert t_feats["is_table_cell"] == 1.0
    assert t_feats["header_has_email"] == 1.0
    assert t_feats["table_row_idx"] == 2.0


def test_relationship_context_features():
    """Verify graph relationship edge flags (MANAGES, SAME_ENTITY)."""
    item = MultimodalCandidateItem(
        "s1", "b1", "Elena Rostova",
        relationships=[
            {"relationship_type": "MANAGES", "evidence": "CEO link"},
            {"relationship_type": "SAME_ENTITY", "evidence": "DIN link"}
        ]
    )
    r_feats = extract_relationship_context_features(item)

    assert r_feats["rel_manages"] == 1.0
    assert r_feats["rel_same_entity"] == 1.0
    assert r_feats["is_org_chart_node"] == 1.0


def test_ocr_candidate_normalization():
    """Verify OCR optical noise repair on validated candidate."""
    fe = MultimodalFeatureExtractor()
    item_ocr = MultimodalCandidateItem("s1", "b1", "ABCPEI234K", is_ocr=True, source="OCR")
    feats, rep = fe.extract_features(item_ocr)

    assert rep == "ABCPE1234K"
    assert feats["ocr_repair_validated"] == 1.0


def test_model_training_and_weights(trained_detector):
    """Verify model training succeeds and produces calibrated probabilities."""
    assert trained_detector.is_loaded is True
    assert trained_detector.classifier is not None
    assert len(trained_detector.classes_) > 5


def test_model_persistence_and_reload(tmp_path, trained_detector):
    """Verify model artifacts can be serialized to disk and cleanly reloaded."""
    save_dir = str(tmp_path / "saved_model")
    trained_detector.save(save_dir)

    assert os.path.exists(os.path.join(save_dir, "detector.joblib"))
    assert os.path.exists(os.path.join(save_dir, "model_metadata.json"))

    loaded_detector = LightweightMultimodalDetector(model_dir=save_dir)
    loaded_detector.load()
    assert loaded_detector.is_loaded is True
    assert loaded_detector.classes_ == trained_detector.classes_


def test_deterministic_prediction(trained_detector):
    """Verify identical candidate inputs produce identical predictions and evidence."""
    item = MultimodalCandidateItem("s1", "b1", "vikram.malhotra@example.com", bbox=[0.1, 0.1, 0.4, 0.15])
    p1 = trained_detector.predict(item)
    p2 = trained_detector.predict(item)

    assert p1 is not None and p2 is not None
    assert p1.pii_type == p2.pii_type
    assert p1.score == p2.score
    assert p1.evidence.to_dict() == p2.evidence.to_dict()


def test_hard_negative_rejection(trained_detector):
    """Verify corporate terminology and non-PII tokens are rejected."""
    neg_item = MultimodalCandidateItem("s1", "b1", "Optiv cybersecurity framework mandates Amazon AWS infrastructure.", bbox=[0.05, 0.1, 0.95, 0.3])
    p = trained_detector.predict(neg_item)
    assert p is None


def test_replacement_token_immunity(trained_detector):
    """CRITICAL SECURITY TEST: Replacement tokens must NEVER be re-flagged."""
    token_item = MultimodalCandidateItem("s1", "b1", "[PERSON_001]", bbox=[0.1, 0.1, 0.3, 0.15])
    p = trained_detector.predict(token_item)
    assert p is None


def test_masked_pii_detection(trained_detector):
    """Verify partially masked PII triggers detection with is_masked=True."""
    masked_item = MultimodalCandidateItem("s1", "b1", "XXX-XX-1234", bbox=[0.1, 0.1, 0.3, 0.15])
    p = trained_detector.predict(masked_item)

    assert p is not None
    assert p.is_masked is True
    assert p.pii_type == "SSN"


def test_split_layout_shape_detection(trained_detector):
    """Verify split name layout in PPTX shapes."""
    s_item = MultimodalCandidateItem(
        "s1", "b1", "Marcus",
        source="shape",
        modality="PPTX-LIKE SLIDE",
        bbox=[0.10, 0.20, 0.30, 0.30]
    )
    p = trained_detector.predict(s_item)
    assert p is not None
    assert p.pii_type == "PERSON"


def test_org_chart_detection_with_evidence(trained_detector):
    """Verify org chart hierarchy node produces explainable relationship evidence."""
    ceo_item = MultimodalCandidateItem(
        "s1", "b1", "Elena Rostova",
        source="shape",
        relationships=[{"relationship_type": "MANAGES", "evidence": "Org chart"}]
    )
    p = trained_detector.predict(ceo_item)

    assert p is not None
    assert p.evidence.relationship_context > 0.5
    assert "relationship" in p.evidence.summary.lower()


def test_malformed_input_fail_closed(trained_detector):
    """Verify non-string or malformed candidate input triggers fail-closed uncertainty."""
    bad_item = MultimodalCandidateItem("s1", "b1", None)  # type: ignore
    p = trained_detector.predict(bad_item)

    assert p is not None
    assert p.is_uncertain is True
    assert "Malformed" in str(p.uncertainty_reason)


def test_missing_model_fail_closed(tmp_path):
    """Verify uninitialized/missing model triggers fail-closed behavior."""
    empty_dir = str(tmp_path / "empty_model")
    detector = LightweightMultimodalDetector(model_dir=empty_dir, fail_closed=True)
    with pytest.raises(MultimodalDetectorError):
        detector.load()


def test_gateway_fusion_integration(trained_detector):
    """Verify multimodal findings cleanly fuse with existing DocumentBlock findings."""
    block = DocumentBlock("doc1", "test.txt", "txt", "p1", "paragraph", "Kavita Patel can be contacted at kavita.patel@example.com", 1)
    existing_finding = PIIFinding("f1", "doc1", "test.txt", "p1", 0, 12, "Kavita Patel", "PERSON", 0.85, ["NER"], "HIGH")

    fused = fuse_multimodal_findings([block], [existing_finding], trained_detector)
    assert len(fused) >= 1
    # Check that existing finding was boosted or retained
    person_finding = next(f for f in fused if f.pii_type == "PERSON")
    assert person_finding.confidence >= 0.85


def test_phase5a_dataset_compatibility(trained_detector):
    """Verify detector processes full Phase 5A DatasetSample blocks without errors."""
    gen = MultimodalDatasetGenerator(seed=42)
    sample = gen.generate_dataset()[0]
    items = [block_to_candidate_item(
        DocumentBlock(sample.sample_id, "doc.txt", "txt", "p1", b.block_type, b.text, b.order, bbox={"x0": b.bbox[0], "y0": b.bbox[1], "x1": b.bbox[2], "y1": b.bbox[3]})
    ) for b in sample.blocks]

    preds = trained_detector.predict_batch(items)
    assert isinstance(preds, list)
