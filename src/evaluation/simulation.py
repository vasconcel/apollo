"""
APOLLO Evaluation: Human Validation Reduction Simulation

Simulates workload reduction and error impact across different
autonomy scenarios on a corpus with gold-standard labels.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple
import random


class AutonomyScenario(str):
    AGGRESSIVE = "aggressive"
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    ULTRA_CONSERVATIVE = "ultra_conservative"


SCENARIO_THRESHOLDS = {
    "aggressive": {
        "confidence_min": 0.80,
        "grounding_strength_min": 0.50,
        "evidence_strength_min": 0.30,
        "uncertainty_max": 0.50,
        "require_triggered_criteria": False,
    },
    "conservative": {
        "confidence_min": 0.90,
        "grounding_strength_min": 0.70,
        "evidence_strength_min": 0.50,
        "uncertainty_max": 0.30,
        "require_triggered_criteria": True,
    },
    "balanced": {
        "confidence_min": 0.95,
        "grounding_strength_min": 0.80,
        "evidence_strength_min": 0.60,
        "uncertainty_max": 0.20,
        "require_triggered_criteria": True,
    },
    "ultra_conservative": {
        "confidence_min": 0.99,
        "grounding_strength_min": 0.90,
        "evidence_strength_min": 0.80,
        "uncertainty_max": 0.10,
        "require_triggered_criteria": True,
    },
}


@dataclass
class SimulationResult:
    scenario: str
    total_papers: int
    human_review_required: int
    autonomous_resolved: int
    autonomous_coverage: float
    human_review_reduction_pct: float
    catastrophic_errors: int
    catastrophic_error_rate: float
    false_positives: int
    false_negatives: int
    autonomous_agreement: float
    mean_autonomous_confidence: float
    papers_by_routing: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class SimulationReport:
    total_papers: int
    results: List[SimulationResult]
    recommended_scenario: str
    summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "total_papers": self.total_papers,
            "results": [r.to_dict() for r in self.results],
            "recommended_scenario": self.recommended_scenario,
            "summary": self.summary,
        }


def _check_autonomy(
    decision: str,
    confidence: float,
    grounding_strength: float,
    evidence_strength: float,
    uncertainty_score: float,
    has_triggered_criteria: bool,
    thresholds: Dict,
) -> bool:
    decision_upper = decision.upper().strip()
    if decision_upper not in ("INCLUDE", "EXCLUDE", "AUTO_INCLUDE", "AUTO_EXCLUDE"):
        return False
    if confidence < thresholds["confidence_min"]:
        return False
    if grounding_strength < thresholds["grounding_strength_min"]:
        return False
    if evidence_strength < thresholds["evidence_strength_min"]:
        return False
    if uncertainty_score >= thresholds["uncertainty_max"]:
        return False
    if thresholds["require_triggered_criteria"] and not has_triggered_criteria:
        return False
    return True


class WorkloadSimulator:
    """Simulates workload reduction across autonomy scenarios."""

    @staticmethod
    def simulate_scenario(
        scenario: str,
        decisions: List[str],
        gold_decisions: List[str],
        confidences: List[float],
        grounding_strengths: List[float],
        evidence_strengths: List[float],
        uncertainty_scores: List[float],
        triggered_criteria_counts: List[int],
        seed: Optional[int] = None,
    ) -> SimulationResult:
        if seed is not None:
            random.seed(seed)
        thresholds = SCENARIO_THRESHOLDS.get(scenario)
        if thresholds is None:
            raise ValueError(f"Unknown scenario: {scenario}")
        n = len(decisions)
        autonomous_resolved = 0
        human_review = 0
        catastrophic_errors = 0
        false_positives = 0
        false_negatives = 0
        autonomous_agreements = 0
        total_autonomous_decisions = 0
        confidence_sum = 0.0
        routing_counts: Dict[str, int] = {
            "AUTO_INCLUDE": 0,
            "AUTO_EXCLUDE": 0,
            "HUMAN_REVIEW": 0,
            "ESCALATE": 0,
        }
        for i in range(n):
            decision = decisions[i].upper().strip() if i < len(decisions) else "UNAVAILABLE"
            gold = gold_decisions[i].upper().strip() if i < len(gold_decisions) else "UNAVAILABLE"
            confidence = confidences[i] if i < len(confidences) else 0.0
            grounding = grounding_strengths[i] if i < len(grounding_strengths) else 0.0
            evidence = evidence_strengths[i] if i < len(evidence_strengths) else 0.0
            uncertainty = uncertainty_scores[i] if i < len(uncertainty_scores) else 1.0
            has_criteria = triggered_criteria_counts[i] > 0 if i < len(triggered_criteria_counts) else False
            decision_include = decision in ("INCLUDE", "AUTO_INCLUDE")
            gold_include = gold in ("INCLUDE", "AUTO_INCLUDE")
            if decision in ("UNCERTAIN", "INSUFFICIENT_EVIDENCE", "CANNOT_DETERMINE", "UNAVAILABLE"):
                human_review += 1
                routing_counts["HUMAN_REVIEW"] += 1
                continue
            can_auto = _check_autonomy(
                decision, confidence, grounding, evidence, uncertainty,
                has_criteria, thresholds,
            )
            if can_auto:
                total_autonomous_decisions += 1
                confidence_sum += confidence
                if decision_include:
                    routing_counts["AUTO_INCLUDE"] += 1
                else:
                    routing_counts["AUTO_EXCLUDE"] += 1
                autonomous_resolved += 1
                if decision_include == gold_include:
                    autonomous_agreements += 1
                else:
                    if decision_include and not gold_include:
                        false_positives += 1
                    elif not decision_include and gold_include:
                        false_negatives += 1
                        catastrophic_errors += 1
            elif uncertainty > 0.7:
                routing_counts["ESCALATE"] += 1
                human_review += 1
            else:
                routing_counts["HUMAN_REVIEW"] += 1
                human_review += 1
                if decision_include and not gold_include:
                    false_positives += 1
                elif not decision_include and gold_include:
                    false_negatives += 1
        autonomous_coverage = autonomous_resolved / n if n > 0 else 0.0
        review_reduction = 1.0 - (human_review / n) if n > 0 else 0.0
        catastrophic_rate = catastrophic_errors / n if n > 0 else 0.0
        agreement_rate = autonomous_agreements / total_autonomous_decisions if total_autonomous_decisions > 0 else 0.0
        mean_conf = confidence_sum / total_autonomous_decisions if total_autonomous_decisions > 0 else 0.0
        return SimulationResult(
            scenario=scenario,
            total_papers=n,
            human_review_required=human_review,
            autonomous_resolved=autonomous_resolved,
            autonomous_coverage=autonomous_coverage,
            human_review_reduction_pct=review_reduction,
            catastrophic_errors=catastrophic_errors,
            catastrophic_error_rate=catastrophic_rate,
            false_positives=false_positives,
            false_negatives=false_negatives,
            autonomous_agreement=agreement_rate,
            mean_autonomous_confidence=mean_conf,
            papers_by_routing=routing_counts,
        )

    @staticmethod
    def simulate_all_scenarios(
        decisions: List[str],
        gold_decisions: List[str],
        confidences: List[float],
        grounding_strengths: List[float],
        evidence_strengths: List[float],
        uncertainty_scores: List[float],
        triggered_criteria_counts: List[int],
        seed: Optional[int] = None,
        scenarios: Optional[List[str]] = None,
    ) -> SimulationReport:
        if scenarios is None:
            scenarios = ["ultra_conservative", "conservative", "balanced", "aggressive"]
        results: List[SimulationResult] = []
        for scenario in scenarios:
            sr = WorkloadSimulator.simulate_scenario(
                scenario, decisions, gold_decisions, confidences,
                grounding_strengths, evidence_strengths,
                uncertainty_scores, triggered_criteria_counts, seed,
            )
            results.append(sr)
        scored = []
        for sr in results:
            safety_weight = 0.5
            coverage_weight = 0.3
            agreement_weight = 0.2
            score = (
                safety_weight * (1.0 - sr.catastrophic_error_rate * 10)
                + coverage_weight * sr.autonomous_coverage
                + agreement_weight * sr.autonomous_agreement
            )
            scored.append((score, sr.scenario))
        scored.sort(key=lambda x: x[0], reverse=True)
        recommended = scored[0][1] if scored else "balanced"
        total = len(decisions)
        return SimulationReport(
            total_papers=total,
            results=results,
            recommended_scenario=recommended,
            summary={
                "total_papers": total,
                "recommended_scenario": recommended,
                "scenarios_evaluated": len(results),
                "best_coverage": max(r.autonomous_coverage for r in results),
                "best_safety": 1.0 - min(r.catastrophic_error_rate for r in results),
            },
        )
