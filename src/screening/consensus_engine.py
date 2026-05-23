"""Phase 5A: Deterministic Consensus Engine.

Combines multiple evidence sources into a single consensus decision:
- Rule-based evidence (from RuleEngine)
- Semantic similarity (TF-IDF, BM25, embedding)
- Metadata evidence
- Hard-negative evidence
- Protocol signals
- Study-type evidence
- Lexicon evidence

Each source contributes weighted signals with full provenance.
"""

from typing import Any, Dict, List, Optional, Tuple

from .screening_result import ScreeningDecision, Evidence, ScreeningResult


DEFAULT_CONSENSUS_WEIGHTS: Dict[str, float] = {
    "semantic_signals": 0.15,
    "hard_negative": 0.20,
    "study_type": 0.10,
    "lexicon": 0.10,
    "metadata": 0.05,
}

INCLUDE_THRESHOLD = 0.6
EXCLUDE_THRESHOLD = 0.6


class ConsensusEngine:
    """Deterministic consensus layer for multi-source decision making.

    Combines all evidence sources into a single confidence score
    and decision, with full provenance tracking for auditability.
    """

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        include_threshold: float = INCLUDE_THRESHOLD,
        exclude_threshold: float = EXCLUDE_THRESHOLD,
    ) -> None:
        self._weights = dict(weights or DEFAULT_CONSENSUS_WEIGHTS)
        self._include_threshold = include_threshold
        self._exclude_threshold = exclude_threshold

    def _normalize_weights(self) -> Dict[str, float]:
        total = sum(self._weights.values())
        if total <= 0:
            return {}
        return {k: v / total for k, v in self._weights.items()}

    def evaluate(
        self,
        rule_evidence: List[Evidence],
        rule_confidence: float = 0.0,
        semantic_signals: Optional[Dict[str, float]] = None,
        hard_negative_evidence: Optional[List[Evidence]] = None,
        study_type: str = "",
        study_type_bonus: float = 0.0,
        lexicon_evidence: Optional[List[Evidence]] = None,
        lexicon_score: float = 0.0,
        metadata_boost: float = 0.0,
    ) -> Tuple[float, ScreeningDecision, Dict[str, Any]]:
        """Compute consensus confidence and decision.

        rule_confidence is the base. Other signals are adjustments
        on top, weighted by their respective coefficients.
        Returns (consensus_confidence, decision, provenance_trace).
        """
        trace: Dict[str, Any] = {
            "source_contributions": {},
            "weights": dict(self._weights),
            "thresholds": {
                "include": self._include_threshold,
                "exclude": self._exclude_threshold,
            },
        }

        if hard_negative_evidence:
            all_evidence = list(rule_evidence)
            all_evidence.extend(hard_negative_evidence)
            trace["hard_negative_override"] = True
            trace["hard_negative_evidence"] = [
                e.to_dict() for e in hard_negative_evidence
            ]
            return 0.95, ScreeningDecision.EXCLUDE, trace

        semantic = semantic_signals or {}
        lexicon_ev = lexicon_evidence or []

        sig_max = max(semantic.values()) if semantic else 0.0
        sig_mean = (
            sum(semantic.values()) / len(semantic) if semantic else 0.0
        )

        sem_score = sig_mean * 0.6 + sig_max * 0.4

        lex_score = lexicon_score
        study_adj = study_type_bonus

        # Rule confidence is the base; other signals are additive adjustments
        combo_confidence = rule_confidence + (
            self._weights.get("semantic_signals", 0.15) * sem_score
            + self._weights.get("study_type", 0.10) * study_adj
            + self._weights.get("lexicon", 0.10) * lex_score
            + self._weights.get("metadata", 0.05) * metadata_boost
        )

        trace["source_contributions"] = {
            "rule_evidence": {
                "raw_confidence": rule_confidence,
                "contribution": rule_confidence,
            },
            "semantic_signals": {
                "max_similarity": sig_max,
                "mean_similarity": sig_mean,
                "score": sem_score,
                "weight": self._weights.get("semantic_signals", 0.15),
                "contribution": self._weights.get("semantic_signals", 0.15)
                * sem_score,
            },
            "study_type": {
                "type": study_type or "unknown",
                "bonus": study_adj,
                "weight": self._weights.get("study_type", 0.10),
                "contribution": self._weights.get("study_type", 0.10)
                * study_adj,
            },
            "lexicon": {
                "matched_terms": len(lexicon_ev),
                "score": lex_score,
                "weight": self._weights.get("lexicon", 0.10),
                "contribution": self._weights.get("lexicon", 0.10)
                * lex_score,
            },
            "metadata": {
                "boost": metadata_boost,
                "weight": self._weights.get("metadata", 0.05),
                "contribution": self._weights.get("metadata", 0.05)
                * metadata_boost,
            },
        }

        clamped = max(-1.0, min(1.0, combo_confidence))
        trace["raw_confidence"] = combo_confidence
        trace["clamped_confidence"] = clamped

        if clamped >= self._include_threshold:
            decision = ScreeningDecision.INCLUDE
        elif clamped <= -self._exclude_threshold:
            decision = ScreeningDecision.EXCLUDE
        else:
            decision = ScreeningDecision.REVIEW

        trace["decision"] = decision.value

        return clamped, decision, trace

    def build_result(
        self,
        article_id: str,
        rule_evidence: List[Evidence],
        triggered_rules: List[str],
        rule_confidence: float,
        semantic_signals: Optional[Dict[str, float]] = None,
        hard_negative_evidence: Optional[List[Evidence]] = None,
        study_type: str = "",
        study_type_bonus: float = 0.0,
        lexicon_evidence: Optional[List[Evidence]] = None,
        lexicon_score: float = 0.0,
        metadata_boost: float = 0.0,
        processing_stage: str = "ec",
        rationale_extra: str = "",
    ) -> ScreeningResult:
        """Build a complete ScreeningResult from consensus evaluation."""
        all_evidence = list(rule_evidence)
        is_hard_negative = False

        if hard_negative_evidence:
            all_evidence.extend(hard_negative_evidence)
            is_hard_negative = True

        if lexicon_evidence:
            seen_ids = {ev.rule_id for ev in all_evidence}
            for ev in lexicon_evidence:
                if ev.rule_id not in seen_ids:
                    all_evidence.append(ev)
                    seen_ids.add(ev.rule_id)

        confidence, decision, trace = self.evaluate(
            rule_evidence=rule_evidence,
            rule_confidence=rule_confidence,
            semantic_signals=semantic_signals,
            hard_negative_evidence=hard_negative_evidence,
            study_type=study_type,
            study_type_bonus=study_type_bonus,
            lexicon_evidence=lexicon_evidence,
            lexicon_score=lexicon_score,
            metadata_boost=metadata_boost,
        )

        if is_hard_negative:
            decision = ScreeningDecision.EXCLUDE
            confidence = 0.95

        parts = [f"Consensus={decision.value} confidence={confidence:.3f}"]
        if hard_negative_evidence:
            parts.append("HARD NEGATIVE")
            rationale_extra = f"HARD NEGATIVE EXCLUDE: {hard_negative_evidence[0].rule_name}"
            parts.append(rationale_extra)
        elif study_type:
            parts.append(f"study_type={study_type}")

        if rule_evidence:
            ev_parts = []
            for ev in rule_evidence:
                w = "exclusion" if ev.evidence_type == "exclusion_pattern" else "inclusion"
                ev_parts.append(f"[{w}] {ev.rule_name}: '{ev.match}'")
            if ev_parts:
                parts.append("evidence: " + "; ".join(ev_parts[:5]))

        if rationale_extra:
            parts.append(rationale_extra)

        rationale = " | ".join(parts)

        return ScreeningResult(
            article_id=article_id,
            decision=decision,
            confidence=confidence,
            evidence=all_evidence,
            triggered_rules=triggered_rules,
            semantic_signals=semantic_signals or {},
            escalation_required=False,
            rationale=rationale,
            processing_stage=processing_stage,
            study_type=study_type,
            consensus_trace=trace,
            hard_negative=is_hard_negative,
        )
