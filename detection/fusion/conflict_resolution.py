import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from detection.fusion.schemas import EvidenceRecord, EvidenceSource
from detection.multimodal.feature_extractor import CORPORATE_STOPWORDS


@dataclass
class ResolutionOutcome:
    """Outcome of conflict resolution and weighted evidence combination."""
    pii_type: str
    fused_confidence: float
    agreement_status: str  # UNANIMOUS, MAJORITY, CONFLICT, SINGLE_DETECTOR, DETERMINISTIC_OVERRIDE
    is_deterministic_dominant: bool
    is_suppressed: bool
    suppression_reason: Optional[str] = None
    is_uncertain: bool = False
    uncertainty_reason: Optional[str] = None
    evidence_summary: str = ""
    detector_sources: List[str] = field(default_factory=list)


class ConflictResolver:
    """
    Arbitrates multi-detector evidence using:
    1. Fail-closed extraction uncertainty tracking.
    2. Token immunity protection.
    3. Deterministic dominance (algorithmic checksums/validators override ML).
    4. Corporate stop-word hard-negative suppression.
    5. Explainable weighted evidence fusion with detector reliability weights.
    6. Conflict detection across competing entity types.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or {}
        self.weights = cfg.get("weights", {
            "algorithmic": 1.00,
            "regex": 0.90,
            "multimodal": 0.85,
            "spacy": 0.75,
            "context": 0.80,
            "masked_pii": 0.80,
            "entity_resolution": 0.85
        })
        self.security_policy = cfg.get("security_policy", {
            "fail_closed_on_error": True,
            "deterministic_dominance": True,
            "extraction_uncertainty_priority": True,
            "token_immunity_enabled": True,
            "suppress_corporate_stopwords": True
        })

    def check_token_immunity(self, text: str) -> bool:
        """Synthetic replacement tokens like [PERSON_001] must never be re-flagged."""
        if not text or not isinstance(text, str):
            return False
        t = text.strip()
        return bool(re.match(r"^\[[A-Z_]+_\d+\]$", t) or re.match(r"^\[[A-Z_]+\]$", t))

    def check_corporate_stopword(self, text: str) -> bool:
        """Check if candidate text matches organizational/corporate stop words."""
        if not text or not isinstance(text, str):
            return False
        tokens = [w.lower().strip(",.!?\"'();:") for w in text.split()]
        return any(w in CORPORATE_STOPWORDS for w in tokens if w)

    def get_source_weight(self, source: str) -> float:
        """Retrieve reliability weight for a given detector source."""
        s = source.lower()
        if "algo" in s:
            return float(self.weights.get("algorithmic", 1.00))
        elif "regex" in s:
            return float(self.weights.get("regex", 0.90))
        elif "multimodal" in s or "layout" in s:
            return float(self.weights.get("multimodal", 0.85))
        elif "spacy" in s or "ner" in s:
            return float(self.weights.get("spacy", 0.75))
        elif "context" in s:
            return float(self.weights.get("context", 0.80))
        elif "masked" in s:
            return float(self.weights.get("masked_pii", 0.80))
        elif "entity" in s:
            return float(self.weights.get("entity_resolution", 0.85))
        return 0.70

    def resolve_candidate(
        self,
        text: str,
        evidence_records: List[EvidenceRecord],
        is_block_uncertain: bool = False,
        uncertainty_context: Optional[str] = None
    ) -> ResolutionOutcome:
        """
        Synthesize evidence records for a single candidate span.
        """
        sources = sorted(list(set(r.detector_source for r in evidence_records)))

        # 1. Token Immunity Check
        if self.security_policy.get("token_immunity_enabled", True) and self.check_token_immunity(text):
            return ResolutionOutcome(
                pii_type="NONE",
                fused_confidence=0.0,
                agreement_status="SINGLE_DETECTOR",
                is_deterministic_dominant=False,
                is_suppressed=True,
                suppression_reason="Token immunity: Synthetic replacement token is protected from re-detection",
                is_uncertain=is_block_uncertain,
                uncertainty_reason=uncertainty_context if is_block_uncertain else None,
                evidence_summary="Token immunity triggered",
                detector_sources=sources
            )

        # Handle empty evidence records
        if not evidence_records:
            return ResolutionOutcome(
                pii_type="NONE",
                fused_confidence=0.0,
                agreement_status="SINGLE_DETECTOR",
                is_deterministic_dominant=False,
                is_suppressed=True,
                suppression_reason="No detector evidence found",
                is_uncertain=is_block_uncertain,
                uncertainty_reason=uncertainty_context if is_block_uncertain else None,
                evidence_summary="No evidence records",
                detector_sources=[]
            )

        # 2. Deterministic Dominance Check
        # Algorithmic checksums (Luhn, PESEL, PAN, etc.) or high-certainty deterministic regexes
        if self.security_policy.get("deterministic_dominance", True):
            algo_records = [
                r for r in evidence_records
                if r.detector_source in (EvidenceSource.ALGORITHMIC.value, "ALGORITHMIC_VALIDATOR")
                or (r.detector_source == EvidenceSource.REGEX.value and r.evidence_strength == "STRONG" and r.normalized_score >= 0.90)
            ]
            if algo_records:
                # Strongest algorithmic record dominates
                dominant = max(algo_records, key=lambda x: x.normalized_score)
                dominant_type = dominant.entity_type
                # Check agreement among other detectors
                other_types = set(r.entity_type for r in evidence_records if r != dominant)
                if not other_types or other_types == {dominant_type}:
                    agreement = "UNANIMOUS" if len(evidence_records) > 1 else "SINGLE_DETECTOR"
                else:
                    agreement = "DETERMINISTIC_OVERRIDE"

                evidence_summary = f"Deterministic Dominance: {dominant.detector_source} validated {dominant_type} (score: {dominant.normalized_score:.2f})"
                return ResolutionOutcome(
                    pii_type=dominant_type,
                    fused_confidence=max(0.95, dominant.normalized_score),
                    agreement_status=agreement,
                    is_deterministic_dominant=True,
                    is_suppressed=False,
                    suppression_reason=None,
                    is_uncertain=is_block_uncertain,
                    uncertainty_reason=uncertainty_context if is_block_uncertain else None,
                    evidence_summary=evidence_summary,
                    detector_sources=sources
                )

        # 3. Corporate Stop-Word Hard Negative Check
        if self.security_policy.get("suppress_corporate_stopwords", True) and self.check_corporate_stopword(text):
            # Corporate stopword matches without algorithmic corroboration
            has_corroboration = len(sources) > 1 and any(
                r.detector_source in [EvidenceSource.CONTEXT.value, EvidenceSource.ENTITY_RESOLUTION.value]
                for r in evidence_records
            )
            max_score = max(r.normalized_score for r in evidence_records)
            if not has_corroboration and max_score < 0.85:
                return ResolutionOutcome(
                    pii_type="NONE",
                    fused_confidence=max_score,
                    agreement_status="SINGLE_DETECTOR",
                    is_deterministic_dominant=False,
                    is_suppressed=True,
                    suppression_reason="Hard negative corporate stop-word without strong corroboration",
                    is_uncertain=is_block_uncertain,
                    uncertainty_reason=uncertainty_context if is_block_uncertain else None,
                    evidence_summary=f"Suppressed corporate stop-word: '{text}'",
                    detector_sources=sources
                )

        # 4. Group evidence by candidate entity_type
        type_groups: Dict[str, List[EvidenceRecord]] = {}
        for r in evidence_records:
            type_groups.setdefault(r.entity_type, []).append(r)

        # Compute explainable weighted score for each candidate type
        type_scores: Dict[str, float] = {}
        for etype, records in type_groups.items():
            total_weight = sum(self.get_source_weight(r.detector_source) for r in records)
            if total_weight > 0:
                weighted_sum = sum(
                    self.get_source_weight(r.detector_source) * r.normalized_score
                    for r in records
                )
                base_score = weighted_sum / total_weight
            else:
                base_score = sum(r.normalized_score for r in records) / len(records)

            # Explainable agreement synergy bonus
            # Bounded bonus of 0.04 per corroborating detector (max 0.12)
            corroborating_bonus = min(0.12, 0.04 * max(0, len(records) - 1))
            final_type_score = min(0.98, base_score + corroborating_bonus)
            type_scores[etype] = round(final_type_score, 3)

        # Rank candidate types by score
        sorted_types = sorted(type_scores.items(), key=lambda x: x[1], reverse=True)
        winning_type, winning_score = sorted_types[0]

        # Determine agreement status and conflict
        is_uncertain = is_block_uncertain
        uncertainty_reason = uncertainty_context if is_block_uncertain else None

        if len(type_groups) == 1:
            if len(evidence_records) > 1:
                agreement_status = "UNANIMOUS"
            else:
                agreement_status = "SINGLE_DETECTOR"
        else:
            # Multiple competing types exist
            runner_up_type, runner_up_score = sorted_types[1]
            margin = winning_score - runner_up_score
            if margin < 0.15 and winning_score < 0.80:
                agreement_status = "CONFLICT"
                is_uncertain = True
                uncertainty_reason = (
                    f"Conflicting predictions between {winning_type} ({winning_score:.2f}) "
                    f"and {runner_up_type} ({runner_up_score:.2f})"
                )
            else:
                agreement_status = "MAJORITY"

        # Safe summary (strictly no raw PII text)
        records_summary = ", ".join(
            f"{r.detector_source}:{r.entity_type}({r.normalized_score:.2f})"
            for r in evidence_records
        )
        evidence_summary = f"Fused [{records_summary}] -> {winning_type} (score: {winning_score:.2f}, agreement: {agreement_status})"

        return ResolutionOutcome(
            pii_type=winning_type,
            fused_confidence=winning_score,
            agreement_status=agreement_status,
            is_deterministic_dominant=False,
            is_suppressed=False,
            suppression_reason=None,
            is_uncertain=is_uncertain,
            uncertainty_reason=uncertainty_reason,
            evidence_summary=evidence_summary,
            detector_sources=sources
        )
