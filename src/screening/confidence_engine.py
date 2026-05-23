"""
Evidence Weight Calibration & Confidence Engine.

Phase 4B: Explicit weight registry — no magic numbers.
Phase 4A: False-negative defense — weak exclusion protection, inclusion dominance,
          conflict escalation, empty/low-info protection.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .screening_result import ScreeningDecision, Evidence


@dataclass(frozen=True)
class EvidenceWeight:
    """Weight profile for a rule evidence type."""

    rule_type: str
    base_weight: float
    is_exclusionary: bool = False
    requires_corroboration: bool = False
    description: str = ""


WEIGHT_REGISTRY: Dict[str, EvidenceWeight] = {
    "keyword": EvidenceWeight(
        "keyword", 0.6, description="Exact keyword match in title/abstract"
    ),
    "regex": EvidenceWeight(
        "regex", 0.5, description="Regex pattern match"
    ),
    "exclusion_pattern": EvidenceWeight(
        "exclusion_pattern", 0.7, is_exclusionary=True,
        description="Explicit exclusion pattern matched",
    ),
    "inclusion_pattern": EvidenceWeight(
        "inclusion_pattern", 0.8,
        description="Protocol inclusion pattern matched",
    ),
    "metadata": EvidenceWeight(
        "metadata", 0.3, requires_corroboration=True,
        description="Metadata field match (weak alone)",
    ),
    "publication_year": EvidenceWeight(
        "publication_year", 0.4, requires_corroboration=True,
        description="Publication year filter",
    ),
    "venue": EvidenceWeight(
        "venue", 0.5, requires_corroboration=True,
        description="Venue/journal match",
    ),
    "language": EvidenceWeight(
        "language", 0.4, requires_corroboration=True,
        description="Language filter",
    ),
    "document_type": EvidenceWeight(
        "document_type", 0.4, requires_corroboration=True,
        description="Document type filter",
    ),
}

_METADATA_TYPES = frozenset(
    {
        "metadata",
        "publication_year",
        "venue",
        "language",
        "document_type",
    }
)


def get_weight(evidence_type: str) -> EvidenceWeight:
    return WEIGHT_REGISTRY.get(
        evidence_type,
        EvidenceWeight(evidence_type, 0.3, requires_corroboration=True),
    )


class ConfidenceEngine:
    def __init__(
        self,
        include_threshold: float = 0.6,
        exclude_threshold: float = 0.6,
        escalation_threshold: float = 0.4,
        weak_exclusion_threshold: float = 0.5,
        inclusion_dominance_threshold: float = 0.3,
    ) -> None:
        self._include_threshold = include_threshold
        self._exclude_threshold = exclude_threshold
        self._escalation_threshold = escalation_threshold
        self._weak_exclusion_threshold = weak_exclusion_threshold
        self._inclusion_dominance_threshold = inclusion_dominance_threshold

    def compute(
        self,
        evidence: List[Evidence],
        semantic_signals: Optional[Dict[str, float]] = None,
    ) -> Tuple[float, Dict[str, Any]]:
        """Compute confidence with full provenance trail."""
        provenance: Dict[str, Any] = {
            "include_score": 0.0,
            "exclude_score": 0.0,
            "total_weight": 0.0,
            "semantic_boost": 0.0,
            "evidence_breakdown": [],
        }

        if not evidence:
            return 0.0, provenance

        include_score = 0.0
        exclude_score = 0.0
        total_weight = 0.0
        has_include = False
        has_exclude = False
        weak_exclusions = 0
        strong_exclusions = 0

        for ev in evidence:
            weight = get_weight(ev.evidence_type)
            w = ev.confidence * weight.base_weight

            if weight.is_exclusionary:
                exclude_score += w
                has_exclude = True
                if weight.requires_corroboration or weight.base_weight < 0.6:
                    weak_exclusions += 1
                else:
                    strong_exclusions += 1
            else:
                include_score += w
                has_include = True

            total_weight += ev.confidence

            provenance["evidence_breakdown"].append({
                "rule_id": ev.rule_id,
                "evidence_type": ev.evidence_type,
                "base_weight": weight.base_weight,
                "confidence": ev.confidence,
                "contribution": w,
                "is_exclusionary": weight.is_exclusionary,
            })

        if total_weight == 0:
            return 0.0, provenance

        provenance["include_score"] = include_score
        provenance["exclude_score"] = exclude_score
        provenance["total_weight"] = total_weight
        provenance["has_include"] = has_include
        provenance["has_exclude"] = has_exclude
        provenance["weak_exclusions"] = weak_exclusions
        provenance["strong_exclusions"] = strong_exclusions

        semantic_boost = 0.0
        if semantic_signals:
            sig_sum = sum(semantic_signals.values())
            semantic_boost = sig_sum * 0.3
            provenance["semantic_boost"] = semantic_boost

        net = (include_score - exclude_score) / total_weight + semantic_boost
        clamped = max(-1.0, min(1.0, net))
        provenance["net_raw"] = net
        provenance["net_clamped"] = clamped
        return clamped, provenance

    def classify(self, confidence: float) -> ScreeningDecision:
        if confidence >= self._include_threshold:
            return ScreeningDecision.INCLUDE
        elif confidence <= -self._exclude_threshold:
            return ScreeningDecision.EXCLUDE
        else:
            return ScreeningDecision.REVIEW

    def requires_escalation(
        self,
        decision: ScreeningDecision,
        confidence: float,
        evidence: List[Evidence],
        provenance: Optional[Dict[str, Any]] = None,
        hard_negative: bool = False,
    ) -> Tuple[bool, List[str]]:
        """Returns (should_escalate, reasons).
        Phase 5A: REVIEW is a valid terminal state — never escalates.
        Hard negatives never escalate.
        LLM escalation is optional, disabled by default.
        """
        if hard_negative:
            return False, []

        if decision == ScreeningDecision.REVIEW:
            return False, []

        reasons: List[str] = []

        if decision == ScreeningDecision.UNCERTAIN:
            reasons.append("uncertain decision")
            return True, reasons

        if not evidence:
            reasons.append("no deterministic evidence")
            return True, reasons

        if abs(confidence) < self._escalation_threshold:
            reasons.append("low confidence")

        if self._has_conflicting_signals(evidence):
            reasons.append("conflicting inclusion and exclusion signals")

        if self._is_weak_exclusion(decision, evidence, provenance):
            reasons.append("weak exclusion without corroboration")

        include_strength = self._include_evidence_strength(evidence)
        exclude_strength = self._exclude_evidence_strength(evidence)
        if (
            include_strength > self._inclusion_dominance_threshold
            and exclude_strength > 0
            and include_strength > exclude_strength * 1.5
        ):
            if decision == ScreeningDecision.EXCLUDE:
                reasons.append("inclusion evidence dominates weak exclusion")

        return len(reasons) > 0, reasons

    @staticmethod
    def _has_conflicting_signals(evidence: List[Evidence]) -> bool:
        has_include = False
        has_exclude = False
        for ev in evidence:
            w = get_weight(ev.evidence_type)
            if w.is_exclusionary:
                has_exclude = True
            else:
                has_include = True
        return has_include and has_exclude

    def _is_weak_exclusion(
        self,
        decision: ScreeningDecision,
        evidence: List[Evidence],
        provenance: Optional[Dict[str, Any]] = None,
    ) -> bool:
        if decision != ScreeningDecision.EXCLUDE:
            return False

        all_metadata = all(
            get_weight(ev.evidence_type).requires_corroboration
            for ev in evidence
        )
        if all_metadata:
            return True

        if provenance:
            weak = provenance.get("weak_exclusions", 0)
            strong = provenance.get("strong_exclusions", 0)
            has_include = provenance.get("has_include", False)

            if weak > 0 and strong == 0 and not has_include:
                return True
            return False

        weak_exclusions = 0
        strong_exclusions = 0
        has_include = False

        for ev in evidence:
            w = get_weight(ev.evidence_type)
            if w.is_exclusionary:
                if w.requires_corroboration or w.base_weight < 0.6:
                    weak_exclusions += 1
                else:
                    strong_exclusions += 1
            else:
                has_include = True

        return weak_exclusions > 0 and strong_exclusions == 0 and not has_include

    @staticmethod
    def _include_evidence_strength(evidence: List[Evidence]) -> float:
        score = 0.0
        for ev in evidence:
            w = get_weight(ev.evidence_type)
            if not w.is_exclusionary:
                score += ev.confidence * w.base_weight
        return score

    @staticmethod
    def _exclude_evidence_strength(evidence: List[Evidence]) -> float:
        score = 0.0
        for ev in evidence:
            w = get_weight(ev.evidence_type)
            if w.is_exclusionary:
                score += ev.confidence * w.base_weight
        return score
