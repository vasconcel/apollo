"""
APOLLO Evaluation: Observability Hooks

Provides telemetry collection for monitoring decision distributions,
confidence calibration, uncertainty patterns, and routing behavior
to detect regression (confidence inflation, over-inclusion drift,
abstention collapse).
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from collections import Counter
import json
import os
import time


@dataclass
class TelemetrySnapshot:
    timestamp: float
    decision_distribution: Dict[str, int]
    uncertainty_distribution: Dict[str, int]
    confidence_distribution: Dict[str, int]
    autonomy_routing_distribution: Dict[str, int]
    total_samples: int
    mean_confidence: float
    std_confidence: float
    uncertain_rate: float
    include_rate: float
    exclude_rate: float
    autonomous_rate: float
    escalation_rate: float

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class TelemetryHistory:
    snapshots: List[TelemetrySnapshot] = field(default_factory=list)
    window_size: int = 100

    def add_snapshot(self, snapshot: TelemetrySnapshot):
        self.snapshots.append(snapshot)
        if len(self.snapshots) > self.window_size:
            self.snapshots = self.snapshots[-self.window_size:]

    def get_latest(self) -> Optional[TelemetrySnapshot]:
        return self.snapshots[-1] if self.snapshots else None

    def get_trend(self, metric: str, n: int = 10) -> List[float]:
        recent = self.snapshots[-n:]
        return [getattr(s, metric, 0.0) for s in recent]

    def detect_drift(self) -> List[str]:
        warnings: List[str] = []
        if len(self.snapshots) < 5:
            return warnings
        recent = self.snapshots[-5:]
        older = self.snapshots[-10:-5]
        if older:
            recent_uncertain = sum(s.uncertain_rate for s in recent) / len(recent)
            older_uncertain = sum(s.uncertain_rate for s in older) / len(older)
            if recent_uncertain < older_uncertain * 0.5 and recent_uncertain < 0.1:
                warnings.append("ABSTENTION_COLLAPSE: UNCERTAIN rate dropped by >50%")
            recent_include = sum(s.include_rate for s in recent) / len(recent)
            older_include = sum(s.include_rate for s in older) / len(older)
            if recent_include > older_include * 1.5:
                warnings.append("OVER_INCLUSION_DRIFT: INCLUDE rate increased by >50%")
            recent_conf = sum(s.mean_confidence for s in recent) / len(recent)
            older_conf = sum(s.mean_confidence for s in older) / len(older)
            if recent_conf > older_conf * 1.2 and recent_uncertain < older_uncertain:
                warnings.append("CONFIDENCE_INFLATION: Mean confidence increased with decreasing uncertainty")
        return warnings


BUCKET_LABELS = ["0.0-0.2", "0.2-0.4", "0.4-0.6", "0.6-0.8", "0.8-1.0"]

UNCERTAINTY_BUCKETS = ["none", "low", "medium", "high", "critical"]

DECISIONS = ["INCLUDE", "EXCLUDE", "UNCERTAIN", "INSUFFICIENT_EVIDENCE",
             "CANNOT_DETERMINE", "SKIP", "UNAVAILABLE"]

ROUTINGS = ["AUTO_INCLUDE", "AUTO_EXCLUDE", "HUMAN_REVIEW", "ESCALATE"]


class TelemetryCollector:
    """Collects and analyzes telemetry snapshots from advisory outputs."""

    def __init__(self, history_size: int = 100):
        self.history = TelemetryHistory(window_size=history_size)

    @staticmethod
    def _bucket_confidence(confidence: float) -> str:
        if confidence < 0.2:
            return "0.0-0.2"
        elif confidence < 0.4:
            return "0.2-0.4"
        elif confidence < 0.6:
            return "0.4-0.6"
        elif confidence < 0.8:
            return "0.6-0.8"
        else:
            return "0.8-1.0"

    @staticmethod
    def _bucket_uncertainty(uncertainty_score: float) -> str:
        if uncertainty_score <= 0.0:
            return "none"
        elif uncertainty_score < 0.25:
            return "low"
        elif uncertainty_score < 0.50:
            return "medium"
        elif uncertainty_score < 0.75:
            return "high"
        else:
            return "critical"

    def snapshot_from_advisory_results(
        self,
        advisory_results: Dict[str, Any],
        autonomy_assessments: Optional[Dict[str, Any]] = None,
    ) -> TelemetrySnapshot:
        from src.advisory.advisory_models import AdvisoryResult, AutonomyAssessment
        decisions: List[str] = []
        confidences: List[float] = []
        uncertainty_scores: List[float] = []
        routings: List[str] = []
        for aid, result in advisory_results.items():
            if isinstance(result, AdvisoryResult):
                if result.decision:
                    decisions.append(result.decision.value)
                confidences.append(result.confidence)
            elif isinstance(result, dict):
                decisions.append(result.get("decision", "UNAVAILABLE"))
                confidences.append(result.get("confidence", 0.0))
            else:
                continue
        if autonomy_assessments:
            for aid, assessment in autonomy_assessments.items():
                if isinstance(assessment, AutonomyAssessment):
                    uncertainty_scores.append(assessment.uncertainty_score)
                    routings.append(assessment.routing.value if assessment.routing else "HUMAN_REVIEW")
                elif isinstance(assessment, dict):
                    uncertainty_scores.append(assessment.get("uncertainty_score", 1.0))
                    routings.append(assessment.get("routing", "HUMAN_REVIEW"))
        n = len(decisions)
        if n == 0:
            return TelemetrySnapshot(
                timestamp=time.time(),
                decision_distribution={},
                uncertainty_distribution={},
                confidence_distribution={},
                autonomy_routing_distribution={},
                total_samples=0,
                mean_confidence=0.0,
                std_confidence=0.0,
                uncertain_rate=0.0,
                include_rate=0.0,
                exclude_rate=0.0,
                autonomous_rate=0.0,
                escalation_rate=0.0,
            )
        decision_counts: Dict[str, int] = {}
        for d in DECISIONS:
            decision_counts[d] = 0
        for d in decisions:
            d_upper = d.upper().strip()
            if d_upper in decision_counts:
                decision_counts[d_upper] += 1
            else:
                decision_counts["UNAVAILABLE"] = decision_counts.get("UNAVAILABLE", 0) + 1
        confidence_buckets: Dict[str, int] = {b: 0 for b in BUCKET_LABELS}
        for c in confidences:
            bucket = self._bucket_confidence(c)
            confidence_buckets[bucket] = confidence_buckets.get(bucket, 0) + 1
        uncertainty_buckets: Dict[str, int] = {b: 0 for b in UNCERTAINTY_BUCKETS}
        for u in uncertainty_scores:
            bucket = self._bucket_uncertainty(u)
            uncertainty_buckets[bucket] = uncertainty_buckets.get(bucket, 0) + 1
        routing_counts: Dict[str, int] = {r: 0 for r in ROUTINGS}
        for r in routings:
            r_upper = r.upper().strip()
            if r_upper in routing_counts:
                routing_counts[r_upper] += 1
        mean_conf = sum(confidences) / n
        std_conf = (sum((c - mean_conf) ** 2 for c in confidences) / n) ** 0.5 if n > 1 else 0.0
        uncertain_count = decision_counts.get("UNCERTAIN", 0) + decision_counts.get("INSUFFICIENT_EVIDENCE", 0) + decision_counts.get("CANNOT_DETERMINE", 0)
        include_count = decision_counts.get("INCLUDE", 0)
        exclude_count = decision_counts.get("EXCLUDE", 0)
        autonomous_count = routing_counts.get("AUTO_INCLUDE", 0) + routing_counts.get("AUTO_EXCLUDE", 0)
        escalate_count = routing_counts.get("ESCALATE", 0)
        return TelemetrySnapshot(
            timestamp=time.time(),
            decision_distribution=decision_counts,
            uncertainty_distribution=uncertainty_buckets,
            confidence_distribution=confidence_buckets,
            autonomy_routing_distribution=routing_counts,
            total_samples=n,
            mean_confidence=mean_conf,
            std_confidence=std_conf,
            uncertain_rate=uncertain_count / n,
            include_rate=include_count / n,
            exclude_rate=exclude_count / n,
            autonomous_rate=autonomous_count / n,
            escalation_rate=escalate_count / n,
        )

    def snapshot_from_comparisons(
        self,
        comparisons: List[Any],
        decision_field: str = "apollo_decision",
        confidence_field: str = "apollo_confidence",
        routing_field: str = "apollo_routing",
        uncertainty_field: str = "apollo_uncertainty_reasoning",
    ) -> TelemetrySnapshot:
        decisions: List[str] = []
        confidences: List[float] = []
        routings: List[str] = []
        for comp in comparisons:
            if hasattr(comp, decision_field):
                decisions.append(getattr(comp, decision_field, "UNAVAILABLE"))
                confidences.append(getattr(comp, confidence_field, 0.0))
                routings.append(getattr(comp, routing_field, "HUMAN_REVIEW"))
            elif isinstance(comp, dict):
                decisions.append(comp.get(decision_field, "UNAVAILABLE"))
                confidences.append(comp.get(confidence_field, 0.0))
                routings.append(comp.get(routing_field, "HUMAN_REVIEW"))
        n = len(decisions)
        decision_counts: Dict[str, int] = {}
        for d in decisions:
            d_upper = d.upper().strip()
            decision_counts[d_upper] = decision_counts.get(d_upper, 0) + 1
        confidence_buckets: Dict[str, int] = {b: 0 for b in BUCKET_LABELS}
        for c in confidences:
            bucket = self._bucket_confidence(c)
            confidence_buckets[bucket] = confidence_buckets.get(bucket, 0) + 1
        routing_counts: Dict[str, int] = {r: 0 for r in ROUTINGS}
        for r in routings:
            r_upper = r.upper().strip()
            if r_upper in routing_counts:
                routing_counts[r_upper] += 1
        mean_conf = sum(confidences) / n if n > 0 else 0.0
        std_conf = (sum((c - mean_conf) ** 2 for c in confidences) / n) ** 0.5 if n > 1 else 0.0
        uncertain_count = sum(1 for d in decisions if d.upper().strip() in ("UNCERTAIN", "INSUFFICIENT_EVIDENCE", "CANNOT_DETERMINE"))
        include_count = sum(1 for d in decisions if d.upper().strip() in ("INCLUDE", "AUTO_INCLUDE"))
        exclude_count = sum(1 for d in decisions if d.upper().strip() in ("EXCLUDE", "AUTO_EXCLUDE"))
        autonomous_count = routing_counts.get("AUTO_INCLUDE", 0) + routing_counts.get("AUTO_EXCLUDE", 0)
        escalate_count = routing_counts.get("ESCALATE", 0)
        return TelemetrySnapshot(
            timestamp=time.time(),
            decision_distribution=decision_counts,
            uncertainty_distribution={},
            confidence_distribution=confidence_buckets,
            autonomy_routing_distribution=routing_counts,
            total_samples=n,
            mean_confidence=mean_conf,
            std_confidence=std_conf,
            uncertain_rate=uncertain_count / n if n > 0 else 0.0,
            include_rate=include_count / n if n > 0 else 0.0,
            exclude_rate=exclude_count / n if n > 0 else 0.0,
            autonomous_rate=autonomous_count / n if n > 0 else 0.0,
            escalation_rate=escalate_count / n if n > 0 else 0.0,
        )

    def record_snapshot(self, snapshot: TelemetrySnapshot):
        self.history.add_snapshot(snapshot)

    def check_regression(self) -> List[str]:
        return self.history.detect_drift()


class TelemetryStore:
    """Persists telemetry snapshots to disk for long-term monitoring."""

    def __init__(self, store_path: str = "data/evaluation/telemetry/"):
        self.store_path = store_path

    def save_snapshot(self, snapshot: TelemetrySnapshot, experiment_name: str = "live"):
        os.makedirs(self.store_path, exist_ok=True)
        path = os.path.join(self.store_path, f"{experiment_name}_telemetry.jsonl")
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(snapshot.to_dict()) + "\n")

    def load_history(self, experiment_name: str = "live") -> List[TelemetrySnapshot]:
        path = os.path.join(self.store_path, f"{experiment_name}_telemetry.jsonl")
        if not os.path.exists(path):
            return []
        snapshots: List[TelemetrySnapshot] = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    data = json.loads(line)
                    snapshots.append(TelemetrySnapshot(**data))
        return snapshots
