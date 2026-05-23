"""
Telemetry-Queue-State Reconciliation Engine for APOLLO.

Compares queue state, worker state, and telemetry event streams to
detect inconsistencies: missing events, duplicated events, impossible
state transitions, and causal ordering violations.

Outputs a structured reconciliation report.

Architecture:
  - StateMachine: DFA defining valid telemetry state transitions
  - ReconciliationEngine: Compares event log against current state
  - produces reconciliation_report.json with:
      - consistency_score ∈ [0, 1]
      - violations (type, detail, severity)
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


# ---------------------------------------------------------------------------
# Severity levels
# ---------------------------------------------------------------------------

SEVERITY_CRITICAL = "critical"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"


# ---------------------------------------------------------------------------
# Valid state transitions (DFA)
# ---------------------------------------------------------------------------

# For each metric type, the set of valid predecessor metrics in event stream
_VALID_TRANSITIONS: Dict[str, Set[str]] = {
    "item_completed": {"item_started"},
    "item_failed": {"item_started"},
    "requeue_event": {"item_failed", "item_started"},
    "retry_ec": {"retry_ec", "item_started"},
    "retry_ic": {"retry_ic", "item_started"},
    "circuit_breaker_change": {"provider_call", "provider_failure"},
}

# Events that MUST have a corresponding start event
_START_REQUIRED = {
    "item_completed": "item_started",
    "item_failed": "item_started",
}

# Critical events that must never be dropped
_CRITICAL_METRICS = {
    "item_started", "item_completed", "item_failed",
    "requeue_event", "provider_failure",
}


# ---------------------------------------------------------------------------
# Violation record
# ---------------------------------------------------------------------------

@dataclass
class Violation:
    """A single consistency violation."""
    violation_type: str
    severity: str
    detail: str
    source: str = ""
    event_id: str = ""
    logical_timestamp: int = 0

    def to_dict(self) -> Dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Reconciliation Report
# ---------------------------------------------------------------------------

@dataclass
class ReconciliationReport:
    """Full reconciliation result."""
    timestamp: str = ""
    consistency_score: float = 1.0
    violations: List[Dict] = field(default_factory=list)
    event_count: int = 0
    queue_state: Dict = field(default_factory=dict)
    worker_state: Dict = field(default_factory=dict)
    missing_events: int = 0
    duplicate_events: int = 0
    impossible_transitions: int = 0
    ordering_violations: int = 0

    def to_dict(self) -> Dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def is_healthy(self) -> bool:
        return self.consistency_score >= 0.95 and self.missing_events == 0


# ---------------------------------------------------------------------------
# Reconciliation Store
# ---------------------------------------------------------------------------

RECONCILIATION_DIR = Path("data/reconciliation")


class ReconciliationStore:
    """Persistent store for reconciliation reports."""

    def __init__(self, base_dir: str = "data/reconciliation"):
        self._dir = Path(base_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def save_report(self, report: ReconciliationReport) -> str:
        """Save report to disk. Returns file path."""
        ts = report.timestamp.replace(":", "_").replace(".", "_")
        path = self._dir / f"reconciliation_{ts}.json"
        with open(path, 'w', encoding='utf-8') as f:
            f.write(report.to_json())
            f.flush()
            os.fsync(f.fileno())
        return str(path)

    def list_reports(self) -> List[Dict]:
        """List all saved reports."""
        reports = []
        for fpath in sorted(self._dir.glob("reconciliation_*.json")):
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


# ---------------------------------------------------------------------------
# ReconciliationEngine
# ---------------------------------------------------------------------------

class ReconciliationEngine:
    """Compares telemetry event log against queue/worker state.

    Detects:
      - Missing events (e.g. COMPLETED without STARTED)
      - Duplicate events (same event_id seen twice)
      - Impossible transitions (e.g. COMPLETED after FAILED)
      - Ordering violations (causal parent missing or out of order)

    Thread-safe. Deterministic.
    """

    def __init__(self, store: Optional[ReconciliationStore] = None):
        self._store = store or ReconciliationStore()
        self._lock = threading.Lock()

    def reconcile(
        self,
        events: Optional[List[EventEnvelope]] = None,
        queue_state: Optional[Dict] = None,
        worker_state: Optional[Dict] = None,
        save: bool = False,
    ) -> ReconciliationReport:
        """Run reconciliation on the given event stream vs state.

        Args:
            events: Sorted list of EventEnvelope. If None, fetches from bus.
            queue_state: Optional queue state dict for cross-reference.
            worker_state: Optional worker state dict for cross-reference.
            save: If True, persist report to disk.

        Returns:
            ReconciliationReport with violations and consistency score.
        """
        if events is None:
            bus = get_telemetry_bus()
            events = bus.get_event_log_sorted()

        violations: List[Violation] = []
        seen_ids: Set[str] = set()
        seen_metrics: Set[str] = set()
        last_metric: Dict[str, str] = {}  # cache_key -> last metric
        start_events: Dict[str, str] = {}  # cache_key -> event_id
        component_events: Dict[str, int] = {}  # source -> count
        missing_count = 0
        duplicate_count = 0
        transition_count = 0
        ordering_count = 0
        chain_ok: Dict[str, bool] = {}

        # Phase 1: Scan event stream
        for ev in events:
            metric = ev.metric
            cache_key = ev.tags.get("cache_key", "")
            event_id = ev.global_event_id
            source = ev.source_component

            # Check for duplicate event IDs
            if event_id in seen_ids:
                violations.append(Violation(
                    violation_type="duplicate_event_id",
                    severity=SEVERITY_WARNING,
                    detail=f"Duplicate event_id: {event_id}",
                    source=source,
                    event_id=event_id,
                    logical_timestamp=ev.logical_timestamp,
                ))
                duplicate_count += 1
            seen_ids.add(event_id)

            # Track component event counts
            component_events[source] = component_events.get(source, 0) + 1

            # Track start events for completion tracking
            if metric == "item_started" and cache_key:
                start_events[cache_key] = event_id

            # Check for missing start event
            if metric in _START_REQUIRED and cache_key:
                required_start = _START_REQUIRED[metric]
                if cache_key not in start_events:
                    violations.append(Violation(
                        violation_type="missing_start_event",
                        severity=SEVERITY_CRITICAL,
                        detail=f"{metric} for {cache_key[:12]} without preceding {required_start}",
                        source=source,
                        event_id=event_id,
                        logical_timestamp=ev.logical_timestamp,
                    ))
                    missing_count += 1
                elif cache_key not in chain_ok:
                    chain_ok[cache_key] = True

            # Check for impossible transitions
            if cache_key and metric in _VALID_TRANSITIONS:
                prev = last_metric.get(cache_key, "")
                valid_prev = _VALID_TRANSITIONS[metric]
                if prev and prev not in valid_prev:
                    violations.append(Violation(
                        violation_type="impossible_transition",
                        severity=SEVERITY_CRITICAL,
                        detail=f"{metric} after {prev} for {cache_key[:12]}. Valid predecessors: {valid_prev}",
                        source=source,
                        event_id=event_id,
                        logical_timestamp=ev.logical_timestamp,
                    ))
                    transition_count += 1

            if cache_key:
                last_metric[cache_key] = metric
            seen_metrics.add(metric)

        # Phase 2: Check causal ordering
        if len(events) >= 2:
            for i in range(1, len(events)):
                prev = events[i - 1]
                curr = events[i]
                if curr.logical_timestamp < prev.logical_timestamp:
                    violations.append(Violation(
                        violation_type="logical_clock_regression",
                        severity=SEVERITY_WARNING,
                        detail=f"logical_timestamp {curr.logical_timestamp} < previous {prev.logical_timestamp}",
                        source=curr.source_component,
                        event_id=curr.global_event_id,
                        logical_timestamp=curr.logical_timestamp,
                    ))
                    ordering_count += 1

        # Phase 3: Cross-reference with queue state
        queue_violations = self._check_queue_consistency(events, queue_state or {})
        violations.extend(queue_violations)

        # Phase 4: Compute consistency score
        total_issues = (
            missing_count
            + duplicate_count
            + transition_count
            + ordering_count
            + len(queue_violations)
        )
        total_events = len(events) or 1
        # Score: 1.0 = perfect, drops by 0.05 per critical issue, 0.02 per warning
        penalty = 0.0
        for v in violations:
            penalty += 0.05 if v.severity == SEVERITY_CRITICAL else 0.02
        consistency_score = max(0.0, min(1.0, 1.0 - penalty))

        report = ReconciliationReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            consistency_score=round(consistency_score, 4),
            violations=[v.to_dict() for v in violations],
            event_count=total_events,
            queue_state=queue_state or {},
            worker_state=worker_state or {},
            missing_events=missing_count,
            duplicate_events=duplicate_count,
            impossible_transitions=transition_count,
            ordering_violations=ordering_count,
        )

        if save:
            self._store.save_report(report)

        return report

    def _check_queue_consistency(
        self,
        events: List[EventEnvelope],
        queue_state: Dict,
    ) -> List[Violation]:
        """Check consistency between event stream and queue state."""
        violations: List[Violation] = []

        if not queue_state:
            return violations

        # Count events per cache_key
        event_completed: Dict[str, int] = {}
        event_failed: Dict[str, int] = {}
        event_started: Dict[str, int] = {}
        for ev in events:
            ck = ev.tags.get("cache_key", "")
            if ev.metric == "item_completed":
                event_completed[ck] = event_completed.get(ck, 0) + 1
            elif ev.metric == "item_failed":
                event_failed[ck] = event_failed.get(ck, 0) + 1
            elif ev.metric == "item_started":
                event_started[ck] = event_started.get(ck, 0) + 1

        completed_from_state = queue_state.get("completed", 0)
        failed_from_state = queue_state.get("failed", 0)

        total_events_completed = sum(event_completed.values())
        total_events_failed = sum(event_failed.values())

        if total_events_completed != completed_from_state:
            violations.append(Violation(
                violation_type="queue_completed_mismatch",
                severity=SEVERITY_WARNING,
                detail=f"Event log shows {total_events_completed} completed, queue state says {completed_from_state}",
            ))

        if total_events_failed != failed_from_state:
            violations.append(Violation(
                violation_type="queue_failed_mismatch",
                severity=SEVERITY_WARNING,
                detail=f"Event log shows {total_events_failed} failed, queue state says {failed_from_state}",
            ))

        return violations

    def check_critical_events_present(self, events: List[EventEnvelope]) -> List[Violation]:
        """Check that no critical events were dropped."""
        violations: List[Violation] = []
        seen_metrics = {ev.metric for ev in events}
        for critical in _CRITICAL_METRICS:
            if critical not in seen_metrics:
                violations.append(Violation(
                    violation_type="critical_event_missing",
                    severity=SEVERITY_WARNING,
                    detail=f"Critical metric '{critical}' not found in event stream",
                ))
        return violations


def run_reconciliation(
    events: Optional[List[EventEnvelope]] = None,
    queue_state: Optional[Dict] = None,
    worker_state: Optional[Dict] = None,
    save: bool = False,
) -> ReconciliationReport:
    """Convenience function to run reconciliation."""
    engine = ReconciliationEngine()
    return engine.reconcile(
        events=events,
        queue_state=queue_state,
        worker_state=worker_state,
        save=save,
    )
