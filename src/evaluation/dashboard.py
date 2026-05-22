"""
APOLLO Evaluation: Dashboard Hooks

Provides live progress data structures and hook APIs for future
visualization/UI integration. No frontend — only data structures.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any


@dataclass
class DashboardState:
    experiment_name: str = ""
    stage: str = ""
    total_articles: int = 0
    processed: int = 0
    failed: int = 0
    running: bool = False
    progress_pct: float = 0.0
    elapsed_seconds: float = 0.0
    estimated_remaining_seconds: float = 0.0

    routing_distribution: Dict[str, int] = field(default_factory=lambda: {
        "AUTO_INCLUDE": 0, "AUTO_EXCLUDE": 0,
        "HUMAN_REVIEW": 0, "ESCALATE": 0, "UNCERTAIN": 0,
    })
    decision_distribution: Dict[str, int] = field(default_factory=lambda: {
        "INCLUDE": 0, "EXCLUDE": 0, "UNCERTAIN": 0,
        "INSUFFICIENT_EVIDENCE": 0, "UNAVAILABLE": 0,
    })
    uncertainty_distribution: Dict[str, int] = field(default_factory=lambda: {
        "none": 0, "low": 0, "medium": 0, "high": 0, "critical": 0,
    })

    current_metrics: Dict[str, float] = field(default_factory=lambda: {
        "precision": 0.0, "recall": 0.0, "f1": 0.0,
        "autonomous_coverage": 0.0, "abstention_rate": 0.0,
    })
    workload_reduction_estimate: float = 0.0
    catastrophic_error_count: int = 0

    def to_dict(self) -> Dict:
        return {
            "experiment_name": self.experiment_name,
            "stage": self.stage,
            "total_articles": self.total_articles,
            "processed": self.processed,
            "failed": self.failed,
            "running": self.running,
            "progress_pct": self.progress_pct,
            "elapsed_seconds": self.elapsed_seconds,
            "estimated_remaining_seconds": self.estimated_remaining_seconds,
            "routing_distribution": self.routing_distribution,
            "decision_distribution": self.decision_distribution,
            "uncertainty_distribution": self.uncertainty_distribution,
            "current_metrics": self.current_metrics,
            "workload_reduction_estimate": self.workload_reduction_estimate,
            "catastrophic_error_count": self.catastrophic_error_count,
        }


ProgressCallback = Callable[[DashboardState], None]


class DashboardHook:
    """Hook for UI integration. Supports callbacks for live state updates."""

    def __init__(self):
        self._callbacks: List[ProgressCallback] = []
        self._state = DashboardState()

    @property
    def state(self) -> DashboardState:
        return self._state

    def register_callback(self, callback: ProgressCallback):
        self._callbacks.append(callback)

    def unregister_callback(self, callback: ProgressCallback):
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def _notify(self):
        for cb in self._callbacks:
            try:
                cb(self._state)
            except Exception:
                pass

    def update(
        self,
        processed: Optional[int] = None,
        failed: Optional[int] = None,
        routing: Optional[str] = None,
        decision: Optional[str] = None,
        uncertainty: Optional[str] = None,
        total: Optional[int] = None,
        running: Optional[bool] = None,
        elapsed: Optional[float] = None,
    ):
        if total is not None:
            self._state.total_articles = total
        if processed is not None:
            self._state.processed = processed
        if failed is not None:
            self._state.failed = failed
        if running is not None:
            self._state.running = running
        if elapsed is not None:
            self._state.elapsed_seconds = elapsed
        if routing:
            routing_upper = routing.upper().strip()
            if routing_upper in self._state.routing_distribution:
                self._state.routing_distribution[routing_upper] += 1
        if decision:
            decision_upper = decision.upper().strip()
            if decision_upper in self._state.decision_distribution:
                self._state.decision_distribution[decision_upper] += 1
            elif decision_upper in ("UNCERTAIN", "INSUFFICIENT_EVIDENCE", "CANNOT_DETERMINE"):
                self._state.decision_distribution["UNCERTAIN"] += 1
        if uncertainty:
            unc_key = uncertainty.lower().strip()
            if unc_key in self._state.uncertainty_distribution:
                self._state.uncertainty_distribution[unc_key] += 1
        if self._state.total_articles > 0:
            self._state.progress_pct = self._state.processed / self._state.total_articles
            if self._state.processed > 0 and self._state.elapsed_seconds > 0:
                rate = self._state.processed / self._state.elapsed_seconds
                remaining = self._state.total_articles - self._state.processed
                self._state.estimated_remaining_seconds = remaining / rate if rate > 0 else 0.0
        self._notify()

    def update_metrics(self, metrics: Dict[str, float]):
        for key in self._state.current_metrics:
            if key in metrics:
                self._state.current_metrics[key] = metrics[key]
        self._notify()

    def update_workload_estimate(self, reduction: float, catastrophic: int):
        self._state.workload_reduction_estimate = reduction
        self._state.catastrophic_error_count = catastrophic
        self._notify()

    def reset(self):
        self._state = DashboardState()
        self._notify()

    def get_snapshot(self) -> Dict:
        return self._state.to_dict()
