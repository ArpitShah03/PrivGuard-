# Phase 5B Multimodal Feature Ablation Study
Comparative study measuring incremental contribution of text, layout, context, and relationship features on the untouched Phase 5A test split:

| Setting | Description | Precision | Recall | F1 Score |
| :--- | :--- | :--- | :--- | :--- |
| **A_text_only** | Lexical & structural surface patterns | 100.00% | 44.44% | **61.54%** |
| **B_text_layout** | Text + Normalized spatial geometry (bbox, alignment) | 100.00% | 61.11% | **75.86%** |
| **C_text_layout_context** | Text + Layout + Neighboring blocks & table context | 100.00% | 66.67% | **80.00%** |
| **D_full_multimodal** | Full Multimodal: Text + Layout + Context + Relationships | 100.00% | 83.33% | **90.91%** |

### Ablation Findings:
1. **Spatial Layout Contribution:** Bounding box aspect ratios and vertical/horizontal neighbor alignments improved candidate isolation over pure surface regex.
2. **Context Window & Table Headers:** Neighboring labels (`Employee ID:`) and table header associations provided strong disambiguation signals for short alphanumeric tokens.
3. **Relationship Graphs:** Explicit graph edges (`MANAGES`, `SAME_ENTITY`) substantially boosted multi-shape identity linkage in complex slides.