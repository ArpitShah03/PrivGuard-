import os
import json
import time
from typing import List, Dict, Any, Tuple
from evaluation.multimodal_dataset.schemas import DatasetSample
from evaluation.multimodal_dataset.generator import MultimodalDatasetGenerator
from detection.multimodal.detector import LightweightMultimodalDetector
from detection.multimodal.schemas import MultimodalCandidateItem, MultimodalPrediction
from evaluation.metrics import compute_prf1


def sample_to_candidate_items(sample: DatasetSample) -> List[MultimodalCandidateItem]:
    """Convert sample blocks and annotations into candidate items for evaluation."""
    items = []
    # For positive samples with annotations, include the ground truth regions
    for ann in sample.pii_annotations:
        items.append(MultimodalCandidateItem(
            sample_id=sample.sample_id,
            block_id=ann.annotation_id,
            text=ann.text,
            normalized_text=ann.normalized_text,
            bbox=ann.bbox,
            page_or_slide=ann.page_or_slide,
            source=ann.source,
            modality=sample.document_modality,
            is_ocr=(ann.source == "OCR"),
            relationships=[r.to_dict() for r in sample.relationships]
        ))

    # Also include the blocks themselves (especially for hard negatives)
    if sample.is_hard_negative or not sample.pii_annotations:
        for b in sample.blocks:
            items.append(MultimodalCandidateItem(
                sample_id=sample.sample_id,
                block_id=b.block_id,
                text=b.text,
                bbox=b.bbox,
                page_or_slide=b.page_or_slide,
                source="native_text",
                modality=sample.document_modality
            ))

    return items


class Phase5BEvaluator:
    """
    Evaluator executing test evaluation, 4-tier ablation study,
    and 8-hard-case empirical inspections on the Phase 5A benchmark.
    """
    def __init__(self, model_dir: str = "models/multimodal"):
        self.model_dir = model_dir
        self.generator = MultimodalDatasetGenerator(seed=42)
        self.detector = LightweightMultimodalDetector(model_dir=model_dir)

    def train_and_persist(self) -> Dict[str, Any]:
        """Train detector on train split, tune on validation, and save artifacts."""
        all_samples = self.generator.generate_dataset()
        train_samples = [s for s in all_samples if s.split == "train"]
        val_samples = [s for s in all_samples if s.split == "validation"]

        t0 = time.perf_counter()
        meta = self.detector.train(train_samples, val_samples)
        train_time_ms = (time.perf_counter() - t0) * 1000
        meta["train_time_ms"] = round(train_time_ms, 2)

        self.detector.save(self.model_dir)
        return meta

    def evaluate_test_split(self) -> Dict[str, Any]:
        """Evaluate on the untouched Phase 5A test split."""
        all_samples = self.generator.generate_dataset()
        test_samples = [s for s in all_samples if s.split == "test"]

        # Ensure model is loaded
        if not self.detector.is_loaded:
            self.detector.load(self.model_dir)

        tp = 0
        fp = 0
        fn = 0
        tn = 0

        type_metrics: Dict[str, Dict[str, int]] = {}
        hard_negative_tested = 0
        hard_negative_fp = 0

        for s in test_samples:
            items = sample_to_candidate_items(s)
            gt_anns = {a.annotation_id: a for a in s.pii_annotations}

            if s.is_hard_negative:
                hard_negative_tested += 1
                preds = self.detector.predict_batch(items)
                if preds:
                    fp += len(preds)
                    hard_negative_fp += len(preds)
                else:
                    tn += len(items)
                continue

            for item in items:
                gt = gt_anns.get(item.block_id)
                pred = self.detector.predict(item, context_items=items)

                if gt is not None:
                    g_type = gt.pii_type
                    if g_type not in type_metrics:
                        type_metrics[g_type] = {"tp": 0, "fp": 0, "fn": 0}

                    if pred is not None and pred.pii_type == g_type:
                        tp += 1
                        type_metrics[g_type]["tp"] += 1
                    elif pred is not None:
                        # Wrong type
                        fp += 1
                        fn += 1
                        type_metrics[g_type]["fn"] += 1
                    else:
                        fn += 1
                        type_metrics[g_type]["fn"] += 1
                else:
                    # Non-PII item
                    if pred is not None:
                        fp += 1
                    else:
                        tn += 1

        overall = compute_prf1(tp, fp, fn)
        overall["tn"] = tn
        overall["hard_negative_fp_rate"] = round(hard_negative_fp / max(1, hard_negative_tested), 4)

        per_type = {}
        for t, m in sorted(type_metrics.items()):
            per_type[t] = compute_prf1(m["tp"], m["fp"], m["fn"])

        return {
            "overall": overall,
            "per_type": per_type,
            "test_sample_count": len(test_samples),
            "disclaimer": "Metrics are measured only on the Phase 5A synthetic benchmark."
        }

    def run_ablation_study(self) -> Dict[str, Any]:
        """
        Compare 4 feature configurations on the test split:
        A. Text-only
        B. Text + Layout
        C. Text + Layout + Context
        D. Text + Layout + Context + Relationships
        """
        all_samples = self.generator.generate_dataset()
        train_samples = [s for s in all_samples if s.split == "train"]
        test_samples = [s for s in all_samples if s.split == "test"]

        feature_groups = {
            "A_text_only": [
                "token_count", "char_count", "uppercase_ratio", "digit_ratio",
                "punctuation_ratio", "alphanumeric_ratio", "has_at_symbol",
                "has_phone_separators", "has_ssn_pattern", "has_pan_pattern",
                "has_masked_pattern", "has_secret_shape", "is_replacement_token",
                "is_corporate_stopword"
            ],
            "B_text_layout": [
                "token_count", "char_count", "uppercase_ratio", "digit_ratio",
                "punctuation_ratio", "alphanumeric_ratio", "has_at_symbol",
                "has_phone_separators", "has_ssn_pattern", "has_pan_pattern",
                "has_masked_pattern", "has_secret_shape", "is_replacement_token",
                "is_corporate_stopword",
                "width", "height", "area", "aspect_ratio", "center_x", "center_y",
                "is_header_region", "is_footer_region", "is_left_margin", "is_right_margin",
                "nearby_block_count", "nearest_block_distance", "has_left_neighbor",
                "has_top_neighbor"
            ],
            "C_text_layout_context": [
                "token_count", "char_count", "uppercase_ratio", "digit_ratio",
                "punctuation_ratio", "alphanumeric_ratio", "has_at_symbol",
                "has_phone_separators", "has_ssn_pattern", "has_pan_pattern",
                "has_masked_pattern", "has_secret_shape", "is_replacement_token",
                "is_corporate_stopword",
                "width", "height", "area", "aspect_ratio", "center_x", "center_y",
                "is_header_region", "is_footer_region", "is_left_margin", "is_right_margin",
                "nearby_block_count", "nearest_block_distance", "has_left_neighbor",
                "has_top_neighbor",
                "anchor_name", "anchor_email", "anchor_phone", "anchor_empid",
                "anchor_ssn", "anchor_pan", "anchor_din", "anchor_vendid",
                "anchor_bank", "anchor_secret",
                "is_table_cell", "header_has_name", "header_has_email", "header_has_id"
            ],
            "D_full_multimodal": self.detector.feature_extractor.feature_names
        }

        ablation_results = {}

        for group_name, f_list in feature_groups.items():
            # Build training vectors with selected feature subset
            X_tr: List[List[float]] = []
            y_tr: List[str] = []

            for s in train_samples:
                items = sample_to_candidate_items(s)
                for ann in s.pii_annotations:
                    item = MultimodalCandidateItem(s.sample_id, ann.annotation_id, ann.text, bbox=ann.bbox)
                    feats, _ = self.detector.feature_extractor.extract_features(item, items)
                    sub_vec = [float(feats.get(f, 0.0)) for f in f_list]
                    X_tr.append(sub_vec)
                    y_tr.append(ann.pii_type)

                if s.is_hard_negative or not s.pii_annotations:
                    for b in s.blocks:
                        item = MultimodalCandidateItem(s.sample_id, b.block_id, b.text, bbox=b.bbox)
                        feats, _ = self.detector.feature_extractor.extract_features(item, items)
                        sub_vec = [float(feats.get(f, 0.0)) for f in f_list]
                        X_tr.append(sub_vec)
                        y_tr.append("NONE")

            # Train linear classifier for this ablation setting
            from sklearn.linear_model import LogisticRegression
            clf = LogisticRegression(max_iter=1000, random_state=42, class_weight="balanced")
            clf.fit(X_tr, y_tr)

            # Evaluate on test split
            tp, fp, fn = 0, 0, 0
            for s in test_samples:
                items = sample_to_candidate_items(s)
                gt_anns = {a.annotation_id: a for a in s.pii_annotations}

                if s.is_hard_negative:
                    for b in s.blocks:
                        item = MultimodalCandidateItem(s.sample_id, b.block_id, b.text, bbox=b.bbox)
                        feats, _ = self.detector.feature_extractor.extract_features(item, items)
                        sub_vec = [float(feats.get(f, 0.0)) for f in f_list]
                        pred_label = clf.predict([sub_vec])[0]
                        if pred_label != "NONE":
                            fp += 1
                    continue

                for it in items:
                    gt = gt_anns.get(it.block_id)
                    feats, _ = self.detector.feature_extractor.extract_features(it, items)
                    sub_vec = [float(feats.get(f, 0.0)) for f in f_list]
                    probs = clf.predict_proba([sub_vec])[0]
                    max_idx = int(clf.classes_.tolist().index(clf.predict([sub_vec])[0]))
                    p_label = clf.classes_[max_idx]
                    p_prob = probs[max_idx]

                    if gt:
                        if p_label == gt.pii_type and p_prob >= 0.50:
                            tp += 1
                        else:
                            fn += 1
                    else:
                        if p_label != "NONE" and p_prob >= 0.50:
                            fp += 1

            prf1 = compute_prf1(tp, fp, fn)
            ablation_results[group_name] = prf1

        return ablation_results

    def evaluate_hard_cases(self) -> List[Dict[str, Any]]:
        """
        Explicitly evaluate the 8 designated hard cases:
        1. Org-chart sample
        2. Table sample
        3. OCR-noisy sample
        4. Split-layout sample
        5. Same-person relationship sample
        6. Similar-name negative sample
        7. Hard-negative enterprise text
        8. Masked PII
        """
        all_samples = self.generator.generate_dataset()
        if not self.detector.is_loaded:
            self.detector.load(self.model_dir)

        # Target specific category archetypes
        case_targets = [
            ("org_chart", "Org-Chart Spatial Hierarchy"),
            ("tabular", "Table Cell Grid Layout"),
            ("ocr_noisy", "Controlled OCR Noise"),
            ("split_layout", "Split-Layout Multi-Shape"),
            ("entity_resolution", "Same-Person Relationship Memo"),
            ("similar_names", "Similar-Name Anti-Merge Roster"),
            ("hard_negative", "Hard-Negative Corporate Text"),
            ("masked_pii", "Partially Masked Account Data")
        ]

        case_results = []
        for cat, title in case_targets:
            target_sample = next((s for s in all_samples if s.category == cat), None)
            if not target_sample:
                continue

            items = sample_to_candidate_items(target_sample)
            preds = self.detector.predict_batch(items)

            expected_types = [a.pii_type for a in target_sample.pii_annotations]
            pred_types = [p.pii_type for p in preds]

            # Match status
            is_correct = False
            if target_sample.is_hard_negative:
                is_correct = (len(preds) == 0)
            else:
                is_correct = any(t in expected_types for t in pred_types) if pred_types else False

            sample_pred = preds[0] if preds else None
            score = sample_pred.score if sample_pred else 0.0
            evidence = sample_pred.evidence.summary if sample_pred else "No detection (Safe/Negative)"

            case_results.append({
                "case_name": title,
                "category": cat,
                "sample_id": target_sample.sample_id,
                "expected": expected_types if expected_types else ["NONE (Hard Negative)"],
                "predicted": pred_types if pred_types else ["NONE"],
                "score": score,
                "evidence": evidence,
                "correct": is_correct
            })

        return case_results
