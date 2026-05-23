"""
Cross-layer Consistency Validator for APOLLO.

Runs deterministic checks across all observable layers:
  - Telemetry event stream vs actual queue state
  - Cache entries vs queue completion state
  - Observed metrics vs computed aggregate metrics
  - Drift between telemetry-derived quality metrics and cache state

Output:
  - consistency_score ∈ [0, 1]
  - typed list of violations with severity levels
  - per-layer detailed diagnostics

All checks are PURE and DETERMINISTIC.
"""
import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

from .telemetry_clock import EventEnvelope
from .telemetry_bus import get_telemetry_bus
from .telemetry_reconciliation import Violation, SEVERITY_CRITICAL, SEVERITY_WARNING, SEVERITY_INFO


# ---------------------------------------------------------------------------
# ConsistencyReport
# ---------------------------------------------------------------------------

@dataclass
class ConsistencyReport:
    """Full cross-layer consistency check result."""
    timestamp: str = ""
    consistency_score: float = 1.0
    violations: List[Dict] = field(default_factory=list)
    layer_results: Dict = field(default_factory=dict)
    telemetry_queue_score: float = 1.0
    telemetry_cache_score: float = 1.0
    metric_drift_score: float = 1.0
    quality_drift_score: float = 1.0
    total_events_checked: int = 0
    total_cache_entries_checked: int = 0

    def to_dict(self) -> Dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def is_healthy(self) -> bool:
        return self.consistency_score >= 0.95


# ---------------------------------------------------------------------------
# ConsistencyChecker
# ---------------------------------------------------------------------------

CONSISTENCY_DIR = Path("data/consistency")


class ConsistencyChecker:
    """Cross-layer consistency validator.

    Runs 4 independent checks:
      1. Telemetry ↔ Queue state
      2. Telemetry ↔ Cache state
      3. Metric drift (observed vs computed)
      4. Quality drift (telemetry-derived vs cached)

    Thread-safe. All checks PURE and DETERMINISTIC.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._dir = CONSISTENCY_DIR
        self._dir.mkdir(parents=True, exist_ok=True)

    def check_all(
        self,
        events: Optional[List[EventEnvelope]] = None,
        queue_state: Optional[Dict] = None,
        cache_stats: Optional[Dict] = None,
        computed_metrics: Optional[Dict] = None,
        save: bool = False,
    ) -> ConsistencyReport:
        """Run all consistency checks and produce a report.

        Args:
            events: Sorted list of EventEnvelope. If None, fetches from bus.
            queue_state: Current queue state dict (from get_stats()).
            cache_stats: Cache statistics (from get_cache_stats()).
            computed_metrics: Computed aggregate metrics for drift comparison.
            save: If True, persist report to disk.

        Returns:
            ConsistencyReport with per-layer scores and violations.
        """
        if events is None:
            bus = get_telemetry_bus()
            events = bus.get_event_log_sorted()

        violations: List[Violation] = []

        # Layer 1: Telemetry vs Queue
        tvq_violations, tvq_score = self._check_telemetry_vs_queue(events, queue_state or {})
        violations.extend(tvq_violations)

        # Layer 2: Telemetry vs Cache
        tvc_violations, tvc_score = self._check_telemetry_vs_cache(events, cache_stats or {})
        violations.extend(tvc_violations)

        # Layer 3: Metric drift
        md_violations, md_score = self._check_metric_drift(events, computed_metrics or {})
        violations.extend(md_violations)

        # Layer 4: Quality drift
        qd_violations, qd_score = self._check_quality_drift(events, computed_metrics or {})
        violations.extend(qd_violations)

        # Composite score: average of all layer scores
        scores = [tvq_score, tvc_score, md_score, qd_score]
        composite = sum(scores) / len(scores)

        report = ConsistencyReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            consistency_score=round(composite, 4),
            violations=[v.to_dict() for v in violations],
            layer_results={
                "telemetry_vs_queue": {"score": tvq_score, "violations": len(tvq_violations)},
                "telemetry_vs_cache": {"score": tvc_score, "violations": len(tvc_violations)},
                "metric_drift": {"score": md_score, "violations": len(md_violations)},
                "quality_drift": {"score": qd_score, "violations": len(qd_violations)},
            },
            telemetry_queue_score=tvq_score,
            telemetry_cache_score=tvc_score,
            metric_drift_score=md_score,
            quality_drift_score=qd_score,
            total_events_checked=len(events),
        )

        if save:
            self._save_report(report)

        return report

    # ------------------------------------------------------------------
    # Layer 1: Telemetry vs Queue
    # ------------------------------------------------------------------

    def _check_telemetry_vs_queue(
        self,
        events: List[EventEnvelope],
        queue_state: Dict,
    ) -> Tuple[List[Violation], float]:
        """Check that telemetry event counts match queue state counts."""
        violations: List[Violation] = []

        if not queue_state:
            return violations, 1.0

        # Count terminal events from telemetry
        completed = sum(1 for e in events if e.metric == "item_completed")
        failed = sum(1 for e in events if e.metric == "item_failed")
        started = sum(1 for e in events if e.metric == "item_started")

        q_completed = queue_state.get("completed", 0)
        q_failed = queue_state.get("failed", 0)

        if completed != q_completed:
            violations.append(Violation(
                violation_type="telemetry_queue_completed_mismatch",
                severity=SEVERITY_WARNING,
                detail=f"Telemetry: {completed} completed, Queue: {q_completed}",
                source="consistency",
            ))

        if failed != q_failed:
            violations.append(Violation(
                violation_type="telemetry_queue_failed_mismatch",
                severity=SEVERITY_WARNING,
                detail=f"Telemetry: {failed} failed, Queue: {q_failed}",
                source="consistency",
            ))

        # Check: no more completed than started
        if completed > 0:
            total_processing = started - completed - failed
            if total_processing < 0:
                violations.append(Violation(
                    violation_type="excess_terminal_events",
                    severity=SEVERITY_CRITICAL,
                    detail=f"More terminal events ({completed}+{failed}) than start events ({started})",
                    source="consistency",
                ))

        score = max(0.0, 1.0 - len(violations) * 0.1)
        return violations, round(score, 4)

    # ------------------------------------------------------------------
    # Layer 2: Telemetry vs Cache
    # ------------------------------------------------------------------

    def _check_telemetry_vs_cache(
        self,
        events: List[EventEnvelope],
        cache_stats: Dict,
    ) -> Tuple[List[Violation], float]:
        """Check that telemetry completion events match cache entries."""
        violations: List[Violation] = []

        if not cache_stats:
            return violations, 1.0

        telemetry_completed = sum(1 for e in events if e.metric == "item_completed")
        cache_count = cache_stats.get("total_cached", 0)
        cache_total = cache_stats.get("total", 0)

        cache_entries = cache_count or cache_total

        if cache_entries > 0 and telemetry_completed != cache_entries:
            violations.append(Violation(
                violation_type="telemetry_cache_completed_mismatch",
                severity=SEVERITY_WARNING,
                detail=f"Telemetry: {telemetry_completed} completed, Cache: {cache_entries} entries",
                source="consistency",
            ))

        score = max(0.0, 1.0 - len(violations) * 0.1)
        return violations, round(score, 4)

    # ------------------------------------------------------------------
    # Layer 3: Metric drift
    # ------------------------------------------------------------------

    def _check_metric_drift(
        self,
        events: List[EventEnvelope],
        computed_metrics: Dict,
    ) -> Tuple[List[Violation], float]:
        """Detect drift between telemetry-derived and computed metrics."""
        violations: List[Violation] = []

        if not computed_metrics:
            return violations, 1.0

        # Compute observed metrics from event stream
        observed = {
            "total_events": len(events),
            "completed": sum(1 for e in events if e.metric == "item_completed"),
            "failed": sum(1 for e in events if e.metric == "item_failed"),
            "retries": sum(1 for e in events if e.metric.startswith("retry_")),
            "provider_calls": sum(1 for e in events if e.metric == "provider_call"),
            "provider_failures": sum(1 for e in events if e.metric == "provider_failure"),
        }

        # Compare with computed metrics
        for key, observed_val in observed.items():
            computed_val = computed_metrics.get(key, -1)
            if computed_val >= 0 and observed_val != computed_val:
                violations.append(Violation(
                    violation_type="metric_drift",
                    severity=SEVERITY_WARNING,
                    detail=f"Observed '{key}': {observed_val}, Computed: {computed_val}",
                    source="consistency",
                ))

        score = max(0.0, 1.0 - len(violations) * 0.1)
        return violations, round(score, 4)

    # ------------------------------------------------------------------
    # Layer 4: Quality drift
    # ------------------------------------------------------------------

    def _check_quality_drift(
        self,
        events: List[EventEnvelope],
        computed_metrics: Dict,
    ) -> Tuple[List[Violation], float]:
        """Check for drift in quality-related metrics."""
        violations: List[Violation] = []

        if not computed_metrics:
            return violations, 1.0

        quality_events = [e for e in events if e.metric == "quality_score"]
        observed_avg = (
            sum(e.value for e in quality_events) / len(quality_events)
            if quality_events else 0.0
        )

        computed_quality = computed_metrics.get("avg_quality_score", -1.0)
        if computed_quality >= 0 and observed_avg > 0:
            drift = abs(observed_avg - computed_quality)
            if drift > 0.1:
                violations.append(Violation(
                    violation_type="quality_drift",
                    severity=SEVERITY_WARNING,
                    detail=f"Observed avg quality: {observed_avg:.3f}, Computed: {computed_quality:.3f}, Drift: {drift:.3f}",
                    source="consistency",
                ))

        score = max(0.0, 1.0 - len(violations) * 0.15)
        return violations, round(score, 4)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save_report(self, report: ConsistencyReport):
        """Save report to disk."""
        ts = report.timestamp.replace(":", "_").replace(".", "_")
        path = self._dir / f"consistency_{ts}.json"
        with open(path, 'w', encoding='utf-8') as f:
            f.write(report.to_json())
            f.flush()
            os.fsync(f.fileno())

    def list_reports(self) -> List[Dict]:
        """List all saved consistency reports."""
        reports = []
        for fpath in sorted(self._dir.glob("consistency_*.json")):
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                reports.append({
                    "path": str(fpath),
                    "timestamp": data.get("timestamp", ""),
                    "score": data.get("consistency_score", 0.0),
                    "violations": len(data.get("violations", [])),
                })
            except (json.JSONDecodeError, OSError):
                pass
        return reports


def run_consistency_check(
    events: Optional[List[EventEnvelope]] = None,
    queue_state: Optional[Dict] = None,
    cache_stats: Optional[Dict] = None,
    computed_metrics: Optional[Dict] = None,
    save: bool = False,
) -> ConsistencyReport:
    """Convenience function to run full consistency check."""
    checker = ConsistencyChecker()
    return checker.check_all(
        events=events,
        queue_state=queue_state,
        cache_stats=cache_stats,
        computed_metrics=computed_metrics,
        save=save,
    )
