import time
from typing import List, Dict, Any, Optional
from models.schemas import DocumentBlock
from detection.regex_detector import detect_regex
from detection.ner_detector import detect_ner
from detection.pii_engine import detect_pii_in_block
from evaluation.dataset_generator import SyntheticDatasetGenerator, SyntheticSample, default_dataset_generator
from evaluation.metrics import EvaluationMetricsAccumulator


def run_baseline_detection(text: str) -> List[Dict[str, Any]]:
    """
    Baseline pipeline (Phase 1 Baseline):
    Native Regex + spaCy NER only.
    Lacks enterprise patterns, algorithmic checksums, masked PII, and DIN/Vendor context.
    """
    findings = []
    findings.extend(detect_regex(text))
    findings.extend(detect_ner(text))
    return findings


def run_full_pipeline_detection(text: str, is_ocr: bool = False) -> List[Dict[str, Any]]:
    """
    Full Phase 2/3 Pipeline:
    Multi-stage detection with enterprise patterns, algorithmic validators,
    entropy-based secrets, masked PII, OCR normalization, and context rules.
    """
    block = DocumentBlock(
        document_id="eval_doc",
        file_name="eval.txt",
        file_type="txt",
        location="eval_block_0",
        block_type="ocr_text" if is_ocr else "text",
        text=text,
        order=0,
        is_ocr=is_ocr,
        ocr_confidence=1.0 if not is_ocr else 0.85
    )
    pii_findings = detect_pii_in_block(block)
    # Convert PIIFinding objects to dicts for metric matching
    return [
        {
            "pii_type": f.pii_type,
            "text": f.text,
            "start": f.start,
            "end": f.end,
            "confidence": f.confidence,
            "detection_method": f.detection_method,
            "severity": f.severity
        }
        for f in pii_findings
    ]


class Evaluator:
    """
    Empirical benchmark evaluator comparing detection results against ground truth.
    Provides rigorous ablation comparison between Baseline and Full Enterprise Gateway.
    """
    def __init__(self, generator: Optional[SyntheticDatasetGenerator] = None):
        self.generator = generator or default_dataset_generator

    def evaluate_pipeline(
        self,
        samples: List[SyntheticSample],
        use_baseline: bool = False
    ) -> Dict[str, Any]:
        accumulator = EvaluationMetricsAccumulator()
        start_time = time.time()

        for s in samples:
            if use_baseline:
                preds = run_baseline_detection(s.text)
            else:
                preds = run_full_pipeline_detection(s.text, is_ocr=s.is_ocr)

            accumulator.add_result(
                ground_truth=s.entities,
                predictions=preds,
                category=s.category
            )

        duration_ms = round((time.time() - start_time) * 1000, 2)
        summary = accumulator.compute_summary()
        summary["evaluation_time_ms"] = duration_ms
        summary["pipeline_type"] = "Baseline (Regex + NER)" if use_baseline else "Full Enterprise Gateway"
        summary["samples_evaluated"] = len(samples)

        return summary

    def run_comparative_ablation(self, samples: Optional[List[SyntheticSample]] = None) -> Dict[str, Any]:
        """
        Execute controlled ablation comparing Baseline against Full Enterprise Gateway.
        Calculates honest empirical performance delta.
        """
        eval_samples = samples or self.generator.generate_dataset()

        baseline_results = self.evaluate_pipeline(eval_samples, use_baseline=True)
        full_results = self.evaluate_pipeline(eval_samples, use_baseline=False)

        # Calculate ablation deltas
        base_ov = baseline_results["overall"]
        full_ov = full_results["overall"]

        delta_precision = round(full_ov["precision"] - base_ov["precision"], 4)
        delta_recall = round(full_ov["recall"] - base_ov["recall"], 4)
        delta_f1 = round(full_ov["f1"] - base_ov["f1"], 4)

        return {
            "dataset_size": len(eval_samples),
            "baseline": baseline_results,
            "full_gateway": full_results,
            "ablation_delta": {
                "precision_delta": delta_precision,
                "recall_delta": delta_recall,
                "f1_delta": delta_f1,
                "additional_tp": full_ov["tp"] - base_ov["tp"],
                "reduction_in_fn": base_ov["fn"] - full_ov["fn"],
                "reduction_in_fp": base_ov["fp"] - full_ov["fp"]
            }
        }


default_evaluator = Evaluator()
