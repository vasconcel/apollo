"""
APOLLO Evaluation: Autonomous Screening Metrics Module

Computes classification, safety, autonomy, calibration, and queue metrics
for evaluating autonomous screening performance against gold-standard labels.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple
import math


@dataclass
class ClassificationMetrics:
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    specificity: float = 0.0
    balanced_accuracy: float = 0.0
    true_positives: int = 0
    true_negatives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    total: int = 0

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class SafetyMetrics:
    false_inclusion_rate: float = 0.0
    false_exclusion_rate: float = 0.0
    catastrophic_false_exclusions: int = 0
    catastrophic_false_exclusion_rate: float = 0.0
    total_human_included: int = 0
    safe_autonomous_rate: float = 0.0

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class AutonomyMetrics:
    autonomous_coverage: float = 0.0
    human_review_reduction_pct: float = 0.0
    abstention_rate: float = 0.0
    escalation_rate: float = 0.0
    autonomous_precision: float = 0.0
    autonomous_recall: float = 0.0
    autonomous_f1: float = 0.0
    autonomous_agreement_rate: float = 0.0
    total_autonomous: int = 0
    total_human_review: int = 0
    total_abstained: int = 0
    total_escalated: int = 0
    total_samples: int = 0

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class CalibrationMetrics:
    expected_calibration_error: float = 0.0
    maximum_calibration_error: float = 0.0
    confidence_correctness_correlation: float = 0.0
    bins: List[Dict] = field(default_factory=list)
    bin_count: int = 10

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class QueueMetrics:
    auto_include: int = 0
    auto_exclude: int = 0
    human_review: int = 0
    escalate: int = 0
    uncertain: int = 0
    total: int = 0

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class EvaluationMetrics:
    classification: ClassificationMetrics = field(default_factory=ClassificationMetrics)
    safety: SafetyMetrics = field(default_factory=SafetyMetrics)
    autonomy: AutonomyMetrics = field(default_factory=AutonomyMetrics)
    calibration: CalibrationMetrics = field(default_factory=CalibrationMetrics)
    queue: QueueMetrics = field(default_factory=QueueMetrics)

    def to_dict(self) -> Dict:
        return {
            "classification": self.classification.to_dict(),
            "safety": self.safety.to_dict(),
            "autonomy": self.autonomy.to_dict(),
            "calibration": self.calibration.to_dict(),
            "queue": self.queue.to_dict(),
        }


class MetricsComputer:
    """Computes all evaluation metrics from APOLLO-vs-gold-standard comparisons."""

    @staticmethod
    def compute_classification(
        apollo_decisions: List[str],
        gold_decisions: List[str],
        autonomous_flags: Optional[List[bool]] = None,
    ) -> ClassificationMetrics:
        if len(apollo_decisions) != len(gold_decisions):
            raise ValueError("Decision lists must have equal length")
        total = len(apollo_decisions)
        if total == 0:
            return ClassificationMetrics()
        tp = tn = fp = fn = 0
        for i in range(total):
            a = apollo_decisions[i].upper().strip()
            g = gold_decisions[i].upper().strip()
            a_include = a in ("INCLUDE", "AUTO_INCLUDE")
            g_include = g in ("INCLUDE", "AUTO_INCLUDE")
            if a_include and g_include:
                tp += 1
            elif not a_include and not g_include:
                tn += 1
            elif a_include and not g_include:
                fp += 1
            elif not a_include and g_include:
                fn += 1
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
        ba = (recall + specificity) / 2
        return ClassificationMetrics(
            precision=precision,
            recall=recall,
            f1_score=f1,
            specificity=specificity,
            balanced_accuracy=ba,
            true_positives=tp,
            true_negatives=tn,
            false_positives=fp,
            false_negatives=fn,
            total=total,
        )

    @staticmethod
    def compute_safety(
        apollo_decisions: List[str],
        gold_decisions: List[str],
        routing_labels: Optional[List[str]] = None,
    ) -> SafetyMetrics:
        if len(apollo_decisions) != len(gold_decisions):
            raise ValueError("Decision lists must have equal length")
        total = len(apollo_decisions)
        if total == 0:
            return SafetyMetrics()
        human_included = 0
        false_inclusions = 0
        false_exclusions = 0
        catastrophic = 0
        safe_autonomous = 0
        for i in range(total):
            a = apollo_decisions[i].upper().strip()
            g = gold_decisions[i].upper().strip()
            routing = routing_labels[i].upper().strip() if routing_labels else ""
            a_include = a in ("INCLUDE", "AUTO_INCLUDE")
            g_include = g in ("INCLUDE", "AUTO_INCLUDE")
            is_autonomous = routing == "AUTO_INCLUDE" or routing == "AUTO_EXCLUDE"
            if g_include:
                human_included += 1
                if not a_include:
                    false_exclusions += 1
                    if is_autonomous:
                        catastrophic += 1
            if a_include and not g_include:
                false_inclusions += 1
            if is_autonomous and a_include == g_include:
                safe_autonomous += 1
        fir = false_inclusions / total if total > 0 else 0.0
        fer = false_exclusions / total if total > 0 else 0.0
        cfr = catastrophic / human_included if human_included > 0 else 0.0
        total_autonomous_decisions = sum(
            1 for r in (routing_labels or []) if r.upper().strip() in ("AUTO_INCLUDE", "AUTO_EXCLUDE")
        )
        sar = safe_autonomous / total_autonomous_decisions if total_autonomous_decisions > 0 else 0.0
        return SafetyMetrics(
            false_inclusion_rate=fir,
            false_exclusion_rate=fer,
            catastrophic_false_exclusions=catastrophic,
            catastrophic_false_exclusion_rate=cfr,
            total_human_included=human_included,
            safe_autonomous_rate=sar,
        )

    @staticmethod
    def compute_autonomy(
        apollo_decisions: List[str],
        gold_decisions: List[str],
        routing_labels: List[str],
    ) -> AutonomyMetrics:
        if not (len(apollo_decisions) == len(gold_decisions) == len(routing_labels)):
            raise ValueError("All lists must have equal length")
        total = len(apollo_decisions)
        if total == 0:
            return AutonomyMetrics()
        autonomous = 0
        human_review = 0
        abstained = 0
        escalated = 0
        auto_include_total = 0
        auto_exclude_total = 0
        auto_include_correct = 0
        auto_exclude_correct = 0
        for i in range(total):
            routing = routing_labels[i].upper().strip()
            a = apollo_decisions[i].upper().strip()
            g = gold_decisions[i].upper().strip()
            g_include = g in ("INCLUDE", "AUTO_INCLUDE")
            if routing == "AUTO_INCLUDE":
                autonomous += 1
                auto_include_total += 1
                if g_include:
                    auto_include_correct += 1
            elif routing == "AUTO_EXCLUDE":
                autonomous += 1
                auto_exclude_total += 1
                if not g_include:
                    auto_exclude_correct += 1
            elif routing == "HUMAN_REVIEW":
                human_review += 1
            elif routing == "ESCALATE":
                escalated += 1
            if a in ("UNCERTAIN", "INSUFFICIENT_EVIDENCE", "CANNOT_DETERMINE"):
                abstained += 1
        auto_total = auto_include_total + auto_exclude_total
        autonomous_coverage = autonomous / total if total > 0 else 0.0
        human_review_pct = human_review / total if total > 0 else 0.0
        abstention_rate = abstained / total if total > 0 else 0.0
        escalation_rate = escalated / total if total > 0 else 0.0
        auto_precision = auto_include_correct / auto_include_total if auto_include_total > 0 else 0.0
        auto_include_false_neg = sum(
            1 for i in range(total)
            if gold_decisions[i].upper().strip() in ("INCLUDE", "AUTO_INCLUDE")
            and routing_labels[i].upper().strip() not in ("AUTO_INCLUDE",)
        )
        auto_recall = auto_include_correct / (auto_include_correct + auto_include_false_neg) if (auto_include_correct + auto_include_false_neg) > 0 else 0.0
        auto_f1 = 2 * auto_precision * auto_recall / (auto_precision + auto_recall) if (auto_precision + auto_recall) > 0 else 0.0
        autonomous_agreement = (auto_include_correct + auto_exclude_correct) / auto_total if auto_total > 0 else 0.0
        return AutonomyMetrics(
            autonomous_coverage=autonomous_coverage,
            human_review_reduction_pct=human_review_pct,
            abstention_rate=abstention_rate,
            escalation_rate=escalation_rate,
            autonomous_precision=auto_precision,
            autonomous_recall=auto_recall,
            autonomous_f1=auto_f1,
            autonomous_agreement_rate=autonomous_agreement,
            total_autonomous=autonomous,
            total_human_review=human_review,
            total_abstained=abstained,
            total_escalated=escalated,
            total_samples=total,
        )

    @staticmethod
    def compute_calibration(
        confidences: List[float],
        is_correct: List[bool],
        bin_count: int = 10,
    ) -> CalibrationMetrics:
        if len(confidences) != len(is_correct):
            raise ValueError("Confidence and correctness lists must have equal length")
        total = len(confidences)
        if total == 0:
            return CalibrationMetrics(bin_count=bin_count)
        bins: List[Dict] = []
        for b in range(bin_count):
            low = b / bin_count
            high = (b + 1) / bin_count
            indices = [i for i in range(total) if low <= confidences[i] < high]
            if not indices:
                bins.append({
                    "bin": b, "low": low, "high": high,
                    "count": 0, "avg_confidence": 0.0,
                    "accuracy": 0.0, "gap": 0.0,
                })
                continue
            bin_confidences = [confidences[i] for i in indices]
            bin_correct = [is_correct[i] for i in indices]
            avg_conf = sum(bin_confidences) / len(bin_confidences)
            accuracy = sum(bin_correct) / len(bin_correct)
            bins.append({
                "bin": b, "low": low, "high": high,
                "count": len(indices),
                "avg_confidence": avg_conf,
                "accuracy": accuracy,
                "gap": abs(avg_conf - accuracy),
            })
        ece = sum(b["gap"] * b["count"] for b in bins) / total
        mce = max((b["gap"] for b in bins), default=0.0)
        n = total
        mean_conf = sum(confidences) / n
        mean_correct = sum(is_correct) / n
        var_conf = sum((c - mean_conf) ** 2 for c in confidences) / n
        var_correct = sum((c - mean_correct) ** 2 for c in is_correct) / n
        corr = 0.0
        if var_conf > 0 and var_correct > 0:
            cov = sum((confidences[i] - mean_conf) * (is_correct[i] - mean_correct) for i in range(n)) / n
            corr = cov / (math.sqrt(var_conf) * math.sqrt(var_correct))
            corr = max(-1.0, min(1.0, corr))
        return CalibrationMetrics(
            expected_calibration_error=ece,
            maximum_calibration_error=mce,
            confidence_correctness_correlation=corr,
            bins=bins,
            bin_count=bin_count,
        )

    @staticmethod
    def compute_queue(
        routing_labels: List[str],
    ) -> QueueMetrics:
        total = len(routing_labels)
        if total == 0:
            return QueueMetrics()
        ai = ae = hr = esc = unc = 0
        for r in routing_labels:
            r_upper = r.upper().strip()
            if r_upper == "AUTO_INCLUDE":
                ai += 1
            elif r_upper == "AUTO_EXCLUDE":
                ae += 1
            elif r_upper == "HUMAN_REVIEW":
                hr += 1
            elif r_upper == "ESCALATE":
                esc += 1
            elif r_upper in ("UNCERTAIN", "INSUFFICIENT_EVIDENCE", "CANNOT_DETERMINE"):
                unc += 1
        return QueueMetrics(
            auto_include=ai,
            auto_exclude=ae,
            human_review=hr,
            escalate=esc,
            uncertain=unc,
            total=total,
        )

    @staticmethod
    def compute_all(
        apollo_decisions: List[str],
        gold_decisions: List[str],
        routing_labels: List[str],
        confidences: List[float],
    ) -> EvaluationMetrics:
        classification = MetricsComputer.compute_classification(apollo_decisions, gold_decisions)
        safety = MetricsComputer.compute_safety(apollo_decisions, gold_decisions, routing_labels)
        autonomy = MetricsComputer.compute_autonomy(apollo_decisions, gold_decisions, routing_labels)
        is_correct = [
            a.upper().strip() in ("INCLUDE", "AUTO_INCLUDE") == g.upper().strip() in ("INCLUDE", "AUTO_INCLUDE")
            for a, g in zip(apollo_decisions, gold_decisions)
        ]
        calibration = MetricsComputer.compute_calibration(confidences, is_correct)
        queue = MetricsComputer.compute_queue(routing_labels)
        return EvaluationMetrics(
            classification=classification,
            safety=safety,
            autonomy=autonomy,
            calibration=calibration,
            queue=queue,
        )
