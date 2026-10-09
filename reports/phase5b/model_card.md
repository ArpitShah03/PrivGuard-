# Model Card: Lightweight Multimodal PII Detector
## Model Details
- **Model Type:** LogisticRegression
- **Version:** 1.0.0
- **Training Samples:** 25 (Phase 5A Train Split)
- **Training Instances:** 89
- **Tuned Decision Threshold:** 0.55
- **Feature Dimensions:** 56 multimodal features across text, layout, context, tables, and relationships.

## Intended Use
- Designed as an explainable, lightweight spatial and contextual PII detector within the Optiv AI Data Security Gateway.
- Augments deterministic regex and algorithmic checksum validators.

## Security & Privacy Considerations
- **Fail-Closed:** In the event of missing model files or malformed inputs, the system signals uncertainty and routes to `HUMAN_REVIEW`.
- **Zero Raw PII Storage:** Neither model weights nor metadata artifacts store raw personal identities.
- **Token Immunity:** Synthesized tokens (e.g. `[PERSON_001]`) are never re-classified as PII.

## Scope & Limitations
- *Metrics are measured strictly on the Phase 5A synthetic benchmark.* Universal production recall is not claimed.