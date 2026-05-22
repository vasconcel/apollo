"""
APOLLO Evaluation: Threshold Calibration Engine

Evaluates different autonomy threshold configurations and generates
Pareto-style tradeoff analysis for optimal operating point selection.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Callable
import copy


@dataclass
class ThresholdConfig:
    confidence_min: float = 0.95
    grounding_strength_min: float = 0.80
    evidence_strength_min: float = 0.60
    uncertainty_max: float = 0.20
    require_triggered_criteria: bool = True
    name: str = "default"

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ThresholdEvaluation:
    config: ThresholdConfig
    autonomous_count: int
    human_review_count: int
    abstention_count: int
    escalation_count: int
    autonomous_coverage: float
    human_review_reduction: float
    autonomous_precision: float
    autonomous_recall: float
    autonomous_f1: float
    autonomous_agreement: float
    false_positive_rate: float
    false_negative_rate: float
    catastrophic_exclusions: int
    safety_score: float

    def to_dict(self) -> Dict:
        return {
            "config": self.config.to_dict(),
            "autonomous_count": self.autonomous_count,
            "human_review_count": self.human_review_count,
            "abstention_count": self.abstention_count,
            "escalation_count": self.escalation_count,
            "autonomous_coverage": self.autonomous_coverage,
            "human_review_reduction": self.human_review_reduction,
            "autonomous_precision": self.autonomous_precision,
            "autonomous_recall": self.autonomous_recall,
            "autonomous_f1": self.autonomous_f1,
            "autonomous_agreement": self.autonomous_agreement,
            "false_positive_rate": self.false_positive_rate,
            "false_negative_rate": self.false_negative_rate,
            "catastrophic_exclusions": self.catastrophic_exclusions,
            "safety_score": self.safety_score,
        }


@dataclass
class CalibrationResult:
    evaluations: List[ThresholdEvaluation]
    recommended: List[ThresholdConfig]
    pareto_frontier: List[ThresholdConfig]

    def to_dict(self) -> Dict:
        return {
            "evaluations": [e.to_dict() for e in self.evaluations],
            "recommended": [c.to_dict() for c in self.recommended],
            "pareto_frontier": [c.to_dict() for c in self.pareto_frontier],
        }


DEFAULT_THRESHOLD_GRID: List[ThresholdConfig] = [
    ThresholdConfig(
        confidence_min=0.90, grounding_strength_min=0.70,
        evidence_strength_min=0.50, uncertainty_max=0.30,
        require_triggered_criteria=True, name="conservative",
    ),
    ThresholdConfig(
        confidence_min=0.95, grounding_strength_min=0.80,
        evidence_strength_min=0.60, uncertainty_max=0.20,
        require_triggered_criteria=True, name="balanced",
    ),
    ThresholdConfig(
        confidence_min=0.85, grounding_strength_min=0.60,
        evidence_strength_min=0.40, uncertainty_max=0.40,
        require_triggered_criteria=True, name="moderate",
    ),
    ThresholdConfig(
        confidence_min=0.80, grounding_strength_min=0.50,
        evidence_strength_min=0.30, uncertainty_max=0.50,
        require_triggered_criteria=False, name="aggressive",
    ),
    ThresholdConfig(
        confidence_min=0.99, grounding_strength_min=0.90,
        evidence_strength_min=0.80, uncertainty_max=0.10,
        require_triggered_criteria=True, name="ultra_conservative",
    ),
]


class ThresholdCalibrator:
    """Evaluates autonomy thresholds and recommends operating points."""

    @staticmethod
    def evaluate_threshold(
        config: ThresholdConfig,
        apollo_decisions: List[str],
        gold_decisions: List[str],
        confidences: List[float],
        grounding_strengths: List[float],
        evidence_strengths: List[float],
        uncertainty_scores: List[float],
        triggered_criteria_counts: List[int],
        routing_labels: Optional[List[str]] = None,
    ) -> ThresholdEvaluation:
        from src.evaluation.metrics import MetricsComputer
        n = len(apollo_decisions)
        simulated_routing: List[str] = []
        for i in range(n):
            apollo_decision = apollo_decisions[i].upper().strip()
            apollo_include = apollo_decision in ("INCLUDE", "AUTO_INCLUDE")
            apollo_exclude = apollo_decision in ("EXCLUDE", "AUTO_EXCLUDE")
            if apollo_decision in ("UNCERTAIN", "INSUFFICIENT_EVIDENCE", "CANNOT_DETERMINE", "UNAVAILABLE"):
                simulated_routing.append("HUMAN_REVIEW")
                continue
            confidence = confidences[i] if i < len(confidences) else 0.0
            grounding = grounding_strengths[i] if i < len(grounding_strengths) else 0.0
            evidence = evidence_strengths[i] if i < len(evidence_strengths) else 0.0
            uncertainty = uncertainty_scores[i] if i < len(uncertainty_scores) else 1.0
            has_criteria = triggered_criteria_counts[i] > 0 if i < len(triggered_criteria_counts) else False
            can_autonomize = (
                confidence >= config.confidence_min
                and grounding >= config.grounding_strength_min
                and evidence >= config.evidence_strength_min
                and uncertainty < config.uncertainty_max
            )
            if config.require_triggered_criteria:
                can_autonomize = can_autonomize and has_criteria
            if can_autonomize:
                if apollo_include:
                    simulated_routing.append("AUTO_INCLUDE")
                elif apollo_exclude:
                    simulated_routing.append("AUTO_EXCLUDE")
                else:
                    simulated_routing.append("HUMAN_REVIEW")
            elif uncertainty > 0.7:
                simulated_routing.append("ESCALATE")
            else:
                simulated_routing.append("HUMAN_REVIEW")
        autonomy_metrics = MetricsComputer.compute_autonomy(apollo_decisions, gold_decisions, simulated_routing)
        safety_metrics = MetricsComputer.compute_safety(apollo_decisions, gold_decisions, simulated_routing)
        eval_metrics = MetricsComputer.compute_classification(apollo_decisions, gold_decisions)
        fp_rate = eval_metrics.false_positives / (eval_metrics.false_positives + eval_metrics.true_negatives) if (eval_metrics.false_positives + eval_metrics.true_negatives) > 0 else 0.0
        fn_rate = eval_metrics.false_negatives / (eval_metrics.false_negatives + eval_metrics.true_positives) if (eval_metrics.false_negatives + eval_metrics.true_positives) > 0 else 0.0
        autonomous_agreement = (
            autonomy_metrics.autonomous_agreement_rate if hasattr(autonomy_metrics, 'autonomous_agreement_rate') else 0.0
        )
        safety_score = 1.0 - (safety_metrics.catastrophic_false_exclusion_rate * 3 + fp_rate * 1.5) / 4.5 if (safety_metrics.catastrophic_false_exclusion_rate * 3 + fp_rate * 1.5) <= 4.5 else 0.0
        return ThresholdEvaluation(
            config=config,
            autonomous_count=autonomy_metrics.total_autonomous,
            human_review_count=autonomy_metrics.total_human_review,
            abstention_count=autonomy_metrics.total_abstained,
            escalation_count=autonomy_metrics.total_escalated,
            autonomous_coverage=autonomy_metrics.autonomous_coverage,
            human_review_reduction=1.0 - autonomy_metrics.human_review_reduction_pct,
            autonomous_precision=autonomy_metrics.autonomous_precision,
            autonomous_recall=autonomy_metrics.autonomous_recall,
            autonomous_f1=autonomy_metrics.autonomous_f1,
            autonomous_agreement=autonomous_agreement,
            false_positive_rate=fp_rate,
            false_negative_rate=fn_rate,
            catastrophic_exclusions=safety_metrics.catastrophic_false_exclusions,
            safety_score=safety_score,
        )

    @staticmethod
    def grid_search(
        configs: List[ThresholdConfig],
        apollo_decisions: List[str],
        gold_decisions: List[str],
        confidences: List[float],
        grounding_strengths: List[float],
        evidence_strengths: List[float],
        uncertainty_scores: List[float],
        triggered_criteria_counts: List[int],
    ) -> CalibrationResult:
        evaluations: List[ThresholdEvaluation] = []
        for config in configs:
            ev = ThresholdCalibrator.evaluate_threshold(
                config, apollo_decisions, gold_decisions,
                confidences, grounding_strengths, evidence_strengths,
                uncertainty_scores, triggered_criteria_counts,
            )
            evaluations.append(ev)
        metrics_by_config: Dict[str, Tuple[float, float, float]] = {}
        for ev in evaluations:
            cov = ev.autonomous_coverage
            safe = ev.safety_score
            agreement = ev.autonomous_agreement
            metrics_by_config[ev.config.name] = (cov, safe, agreement)
        recommended = ThresholdCalibrator._recommend_operating_points(evaluations)
        pareto = ThresholdCalibrator._compute_pareto_frontier(evaluations)
        return CalibrationResult(
            evaluations=evaluations,
            recommended=recommended,
            pareto_frontier=pareto,
        )

    @staticmethod
    def _recommend_operating_points(
        evaluations: List[ThresholdEvaluation],
    ) -> List[ThresholdConfig]:
        if not evaluations:
            return []
        sorted_evals = sorted(evaluations, key=lambda e: e.safety_score, reverse=True)
        best_safety = sorted_evals[0].config
        sorted_by_coverage = sorted(evaluations, key=lambda e: e.autonomous_coverage, reverse=True)
        best_coverage = sorted_by_coverage[0].config
        scored = []
        for ev in evaluations:
            score = ev.safety_score * 0.5 + ev.autonomous_coverage * 0.3 + ev.autonomous_agreement * 0.2
            scored.append((score, ev.config))
        scored.sort(key=lambda x: x[0], reverse=True)
        best_balanced = scored[0][1] if scored else ThresholdConfig()
        seen_names = set()
        unique: List[ThresholdConfig] = []
        for c in [best_balanced, best_safety, best_coverage]:
            if c.name not in seen_names:
                unique.append(c)
                seen_names.add(c.name)
        if not unique:
            unique = [ThresholdConfig()]
        return unique

    @staticmethod
    def _compute_pareto_frontier(
        evaluations: List[ThresholdEvaluation],
    ) -> List[ThresholdConfig]:
        if not evaluations:
            return []
        points = [(e.safety_score, e.autonomous_coverage, e.config) for e in evaluations]
        points.sort(key=lambda p: (-p[0], -p[1]))
        frontier: List[ThresholdConfig] = []
        max_coverage = -1.0
        for safety, coverage, config in points:
            if coverage > max_coverage:
                frontier.append(config)
                max_coverage = coverage
        return frontier

    @staticmethod
    def sweep_confidence(
        apollo_decisions: List[str],
        gold_decisions: List[str],
        confidences: List[float],
        grounding_strengths: List[float],
        evidence_strengths: List[float],
        uncertainty_scores: List[float],
        triggered_criteria_counts: List[int],
        base_config: Optional[ThresholdConfig] = None,
        step: float = 0.05,
    ) -> List[ThresholdEvaluation]:
        if base_config is None:
            base_config = ThresholdConfig()
        results: List[ThresholdEvaluation] = []
        threshold = 0.50
        while threshold <= 1.0:
            config = copy.deepcopy(base_config)
            config.confidence_min = threshold
            config.name = f"conf_{threshold:.2f}"
            ev = ThresholdCalibrator.evaluate_threshold(
                config, apollo_decisions, gold_decisions,
                confidences, grounding_strengths, evidence_strengths,
                uncertainty_scores, triggered_criteria_counts,
            )
            results.append(ev)
            threshold = round(threshold + step, 2)
        return results
