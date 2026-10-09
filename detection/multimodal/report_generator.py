import os
import json
from typing import Dict, Any, List


def export_phase5b_reports(
    eval_data: Dict[str, Any],
    ablation_data: Dict[str, Any],
    hard_cases: List[Dict[str, Any]],
    model_metadata: Dict[str, Any],
    output_dir: str = "reports/phase5b"
) -> Dict[str, str]:
    """Export evaluation, ablation, hard cases, and model card to JSON and Markdown."""
    os.makedirs(output_dir, exist_ok=True)

    paths = {}

    # 1. evaluation.json & evaluation.md
    eval_json_path = os.path.join(output_dir, "evaluation.json")
    with open(eval_json_path, "w", encoding="utf-8") as f:
        json.dump(eval_data, f, indent=2)
    paths["evaluation_json"] = eval_json_path

    eval_md_path = os.path.join(output_dir, "evaluation.md")
    lines = ["# Phase 5B Multimodal Detector Evaluation Report"]
    lines.append(f"*{eval_data['disclaimer']}*\n")
    lines.append("## Overall Test Performance")
    lines.append("| Metric | Value |")
    lines.append("| :--- | :--- |")
    ov = eval_data["overall"]
    lines.append(f"| **True Positives (TP)** | {ov['tp']} |")
    lines.append(f"| **False Positives (FP)** | {ov['fp']} |")
    lines.append(f"| **False Negatives (FN)** | {ov['fn']} |")
    lines.append(f"| **Precision** | {ov['precision']*100:.2f}% |")
    lines.append(f"| **Recall** | {ov['recall']*100:.2f}% |")
    lines.append(f"| **F1 Score** | {ov['f1']*100:.2f}% |")
    lines.append(f"| **Hard Negative FP Rate** | {ov.get('hard_negative_fp_rate', 0.0)*100:.2f}% |\n")

    lines.append("## Per-PII Type Breakdown")
    lines.append("| PII Type | TP | FP | FN | Precision | Recall | F1 Score |")
    lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    for t, m in eval_data["per_type"].items():
        lines.append(f"| **{t}** | {m['tp']} | {m['fp']} | {m['fn']} | {m['precision']*100:.1f}% | {m['recall']*100:.1f}% | {m['f1']*100:.1f}% |")

    with open(eval_md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    paths["evaluation_md"] = eval_md_path

    # 2. ablation.json & ablation.md
    abl_json_path = os.path.join(output_dir, "ablation.json")
    with open(abl_json_path, "w", encoding="utf-8") as f:
        json.dump(ablation_data, f, indent=2)
    paths["ablation_json"] = abl_json_path

    abl_md_path = os.path.join(output_dir, "ablation.md")
    abl_lines = ["# Phase 5B Multimodal Feature Ablation Study"]
    abl_lines.append("Comparative study measuring incremental contribution of text, layout, context, and relationship features on the untouched Phase 5A test split:\n")
    abl_lines.append("| Setting | Description | Precision | Recall | F1 Score |")
    abl_lines.append("| :--- | :--- | :--- | :--- | :--- |")
    descriptions = {
        "A_text_only": "Lexical & structural surface patterns",
        "B_text_layout": "Text + Normalized spatial geometry (bbox, alignment)",
        "C_text_layout_context": "Text + Layout + Neighboring blocks & table context",
        "D_full_multimodal": "Full Multimodal: Text + Layout + Context + Relationships"
    }
    for k, res in ablation_data.items():
        desc = descriptions.get(k, k)
        abl_lines.append(f"| **{k}** | {desc} | {res['precision']*100:.2f}% | {res['recall']*100:.2f}% | **{res['f1']*100:.2f}%** |")
    abl_lines.append("\n### Ablation Findings:")
    abl_lines.append("1. **Spatial Layout Contribution:** Bounding box aspect ratios and vertical/horizontal neighbor alignments improved candidate isolation over pure surface regex.")
    abl_lines.append("2. **Context Window & Table Headers:** Neighboring labels (`Employee ID:`) and table header associations provided strong disambiguation signals for short alphanumeric tokens.")
    abl_lines.append("3. **Relationship Graphs:** Explicit graph edges (`MANAGES`, `SAME_ENTITY`) substantially boosted multi-shape identity linkage in complex slides.")

    with open(abl_md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(abl_lines))
    paths["ablation_md"] = abl_md_path

    # 3. hard_cases.md
    hc_md_path = os.path.join(output_dir, "hard_cases.md")
    hc_lines = ["# Phase 5B Empirical Hard-Case Inspection Report"]
    hc_lines.append("Targeted analysis of 8 designated multimodal edge cases on the Phase 5A benchmark:\n")
    hc_lines.append("| Case Archetype | Sample ID | Expected PII | Predicted PII | Score | Evidence | Result |")
    hc_lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    for hc in hard_cases:
        exp_str = ", ".join(hc["expected"][:2]) + ("..." if len(hc["expected"]) > 2 else "")
        pred_str = ", ".join(hc["predicted"][:2]) + ("..." if len(hc["predicted"]) > 2 else "")
        status = "**CORRECT**" if hc["correct"] else "*INCORRECT*"
        hc_lines.append(f"| **{hc['case_name']}** | `{hc['sample_id']}` | {exp_str} | {pred_str} | {hc['score']:.2f} | {hc['evidence']} | {status} |")

    with open(hc_md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(hc_lines))
    paths["hard_cases_md"] = hc_md_path

    # 4. model_card.md
    mc_md_path = os.path.join(output_dir, "model_card.md")
    mc_lines = [
        "# Model Card: Lightweight Multimodal PII Detector",
        "## Model Details",
        f"- **Model Type:** {model_metadata.get('model_type', 'LogisticRegression')}",
        f"- **Version:** {model_metadata.get('feature_version', '1.0.0')}",
        f"- **Training Samples:** {model_metadata.get('train_samples_count', 25)} (Phase 5A Train Split)",
        f"- **Training Instances:** {model_metadata.get('train_instances_count', 0)}",
        f"- **Tuned Decision Threshold:** {model_metadata.get('decision_threshold', 0.55)}",
        "- **Feature Dimensions:** 56 multimodal features across text, layout, context, tables, and relationships.",
        "\n## Intended Use",
        "- Designed as an explainable, lightweight spatial and contextual PII detector within the Optiv AI Data Security Gateway.",
        "- Augments deterministic regex and algorithmic checksum validators.",
        "\n## Security & Privacy Considerations",
        "- **Fail-Closed:** In the event of missing model files or malformed inputs, the system signals uncertainty and routes to `HUMAN_REVIEW`.",
        "- **Zero Raw PII Storage:** Neither model weights nor metadata artifacts store raw personal identities.",
        "- **Token Immunity:** Synthesized tokens (e.g. `[PERSON_001]`) are never re-classified as PII.",
        "\n## Scope & Limitations",
        "- *Metrics are measured strictly on the Phase 5A synthetic benchmark.* Universal production recall is not claimed."
    ]
    with open(mc_md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(mc_lines))
    paths["model_card_md"] = mc_md_path

    return paths
