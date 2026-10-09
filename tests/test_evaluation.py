import pytest
from evaluation.metrics import compute_prf1, match_entities, EvaluationMetricsAccumulator
from evaluation.dataset_generator import SyntheticDatasetGenerator
from evaluation.evaluator import Evaluator


def test_precision_recall_f1_calculation():
    """Verify PRF1 edge cases, perfect scores, and zero division safeguards."""
    # 1. Perfect detection (10 TP, 0 FP, 0 FN)
    perfect = compute_prf1(10, 0, 0)
    assert perfect["precision"] == 1.0
    assert perfect["recall"] == 1.0
    assert perfect["f1"] == 1.0

    # 2. No detections with ground truth (0 TP, 0 FP, 5 FN)
    zero_recall = compute_prf1(0, 0, 5)
    assert zero_recall["precision"] == 0.0
    assert zero_recall["recall"] == 0.0
    assert zero_recall["f1"] == 0.0

    # 3. Only false positives, no ground truth (0 TP, 5 FP, 0 FN)
    pure_fp = compute_prf1(0, 5, 0)
    assert pure_fp["precision"] == 0.0
    assert pure_fp["recall"] == 0.0
    assert pure_fp["f1"] == 0.0

    # 4. Standard 50% precision and recall (5 TP, 5 FP, 5 FN)
    balanced = compute_prf1(5, 5, 5)
    assert balanced["precision"] == 0.5
    assert balanced["recall"] == 0.5
    assert balanced["f1"] == 0.5


def test_ground_truth_matching_overlap_and_text():
    """Verify greedy entity matching by normalized type and span/text overlap."""
    gt = [
        {"type": "PERSON", "text": "Tobias Lindqvist", "start": 10, "end": 26},
        {"type": "EMAIL", "text": "tlindqvist@cadence.com", "start": 35, "end": 57}
    ]
    preds = [
        # Prediction with slight offset but overlapping span
        {"pii_type": "PERSON", "text": "Tobias Lindqvist", "start": 10, "end": 25},
        # Exact match
        {"pii_type": "EMAIL", "text": "tlindqvist@cadence.com", "start": 35, "end": 57},
        # False positive
        {"pii_type": "PHONE", "text": "555-1234", "start": 60, "end": 68}
    ]

    tps, fps, fns = match_entities(gt, preds)
    assert len(tps) == 2
    assert len(fps) == 1
    assert len(fns) == 0
    assert fps[0]["pii_type"] == "PHONE"


def test_synthetic_dataset_generation_coverage():
    """Verify synthetic dataset generator produces samples with expected entity types."""
    gen = SyntheticDatasetGenerator(seed=42)
    samples = gen.generate_dataset()

    assert len(samples) >= 20
    categories = {s.category for s in samples}
    assert "normal_prose" in categories
    assert "financial_banking" in categories
    assert "national_ids" in categories
    assert "corporate_ids" in categories
    assert "secrets_tokens" in categories
    assert "negative_controls" in categories
    assert "masked_pii" in categories

    # Collect all ground-truth types
    types = {e["type"] for s in samples for e in s.entities}
    assert "PERSON" in types
    assert "EMAIL" in types
    assert "SSN" in types
    assert "PAN" in types
    assert "PESEL" in types
    assert "IFSC" in types
    assert "BANK_ACCOUNT" in types
    assert "DIRECTOR_ID" in types
    assert "VENDOR_ID" in types
    assert "SECRET" in types


def test_dataset_reproducibility_with_seed():
    """Verify deterministic generation: identical seeds produce identical samples."""
    gen1 = SyntheticDatasetGenerator(seed=123)
    gen2 = SyntheticDatasetGenerator(seed=123)

    samples1 = gen1.generate_dataset()
    samples2 = gen2.generate_dataset()

    assert len(samples1) == len(samples2)
    for s1, s2 in zip(samples1, samples2):
        assert s1.sample_id == s2.sample_id
        assert s1.text == s2.text
        assert len(s1.entities) == len(s2.entities)


def test_comparative_ablation_delta():
    """Verify that full gateway improves recall and F1 over baseline on enterprise patterns."""
    evaluator = Evaluator(SyntheticDatasetGenerator(seed=42))
    ablation = evaluator.run_comparative_ablation()

    base_ov = ablation["baseline"]["overall"]
    full_ov = ablation["full_gateway"]["overall"]
    delta = ablation["ablation_delta"]

    # Full gateway should detect additional enterprise types that baseline lacks
    assert full_ov["tp"] > base_ov["tp"]
    assert delta["additional_tp"] > 0
    assert full_ov["recall"] > base_ov["recall"]
    assert delta["f1_delta"] > 0
