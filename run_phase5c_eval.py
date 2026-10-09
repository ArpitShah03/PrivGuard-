import sys
import os
import json

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath("."))

from detection.fusion.evaluator import Phase5CEvaluator
from detection.fusion.report_generator import Phase5CReportGenerator


def main():
    print("=" * 60)
    print("Starting Phase 5C Benchmark & Calibration Evaluation")
    print("=" * 60)

    evaluator = Phase5CEvaluator()
    report_gen = Phase5CReportGenerator()

    # Step 1: Train calibrator on validation split ONLY
    print("\n[Step 1] Fitting Platt Scaling on Validation Split ONLY...")
    calib_meta = evaluator.train_calibrator_on_validation()
    print(f"-> Calibration fitted on {calib_meta['sample_count']} validation samples.")
    print(f"-> Uncalibrated ECE: {calib_meta['uncalibrated_ece']:.4f} -> Calibrated ECE: {calib_meta['calibrated_ece']:.4f} (-{calib_meta['ece_reduction_pct']}%)")
    print(f"-> Parameters: A={calib_meta['coef_A']}, B={calib_meta['intercept_B']}")

    # Step 2: Evaluate on untouched test split
    print("\n[Step 2] Evaluating on untouched Phase 5A Test Split...")
    eval_results = evaluator.evaluate_test_split()
    ov = eval_results["overall"]
    print(f"-> Overall Test F1: {ov['f1']:.4f} (Precision: {ov['precision']:.4f}, Recall: {ov['recall']:.4f})")
    print(f"-> Decisions: {eval_results['decisions']}")
    print(f"-> Agreements: {eval_results['agreements']}")
    cal = eval_results["calibration"]
    print(f"-> Test Split Uncalibrated ECE: {cal['uncalibrated_ece']:.4f} -> Calibrated ECE: {cal['calibrated_ece']:.4f} (-{cal['ece_improvement_pct']}%)")

    # Step 3: 4-Tier Ablation Study
    print("\n[Step 3] Running 4-Tier Ablation Study...")
    ablation_results = evaluator.run_ablation_study()
    for t_key, t_data in ablation_results.items():
        m = t_data["metrics"]
        print(f"-> {t_data['name']}: F1={m['f1']:.4f}, Prec={m['precision']:.4f}, Rec={m['recall']:.4f}, ECE={m['ece']:.4f}")

    # Step 4: Generate reports
    print("\n[Step 4] Writing reports to reports/phase5c/...")
    generated_files = report_gen.generate_all_reports(eval_results, ablation_results, calib_meta)
    for f in generated_files:
        print(f"-> Generated: {f}")

    print("\nPhase 5C Benchmark & Calibration Evaluation Complete!")


if __name__ == "__main__":
    main()
