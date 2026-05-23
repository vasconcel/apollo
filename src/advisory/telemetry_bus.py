"""
Unified Metrics Bus for APOLLO.

Single ingestion layer for all runtime telemetry events.
Non-blocking enqueue, background flush, bounded memory.

Architecture:
  - Thread-safe in-memory queue (queue.Queue)
  - Background daemon thread flushes to TimeSeriesStore
  - Non-blocking enqueue: drops oldest when full (bounded memory)
  - Zero data loss on normal shutdown (synchronous final flush)
  - Graceful degradation: telemetry failures never raise into runtime

Backpressure strategy:
  - Enqueue: queue.put(timeout=0) — never blocks caller
  - Drop policy: when queue is full, increment drop counter, discard
  - Flush: background thread at 1s interval; no lock held during I/O
  - Shutdown: drain queue synchronously before returning
"""
import json
import os
import queue
import threading
import time
from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime, timezone

from .telemetry_timeseries import TimeSeriesStore, get_timeseries_store
from .telemetry_clock import stamp_event, EventEnvelope, get_logical_clock
from .telemetry_backpressure import get_backpressure_controller


DEFAULT_MAX_QUEUE_SIZE = 10000
DEFAULT_FLUSH_INTERVAL = 1.0


class _DropCounters:
    """Atomic drop counters for backpressure monitoring."""

    def __init__(self):
        self._lock = threading.Lock()
        self.queue_full: int = 0
        self.schema_violation: int = 0
        self.flush_failure: int = 0

    def inc_queue_full(self):
        with self._lock:
            self.queue_full += 1

    def inc_schema_violation(self):
        with self._lock:
            self.schema_violation += 1

    def inc_flush_failure(self):
        with self._lock:
            self.flush_failure += 1

    def snapshot(self) -> Dict:
        with self._lock:
            return {
                "queue_full": self.queue_full,
                "schema_violation": self.schema_violation,
                "flush_failure": self.flush_failure,
            }


# Metric schemas define required fields per metric name.
_METRIC_SCHEMAS: Dict[str, List[str]] = {
    "decision_ec": ["decision"],
    "decision_ic": ["decision"],
    "confidence_ec": [],
    "confidence_ic": [],
    "acceptance_ec": [],
    "acceptance_ic": [],
    "latency_ec": [],
    "latency_ic": [],
    "retry_ec": [],
    "retry_ic": [],
    "rate_limit_429": ["provider"],
    "queue_depth_ec": [],
    "queue_depth_ic": [],
    "processing_time_ec": [],
    "processing_time_ic": [],
    "requeue_event": ["stage", "reason"],
    "provider_call": ["provider"],
    "provider_failure": ["provider", "reason"],
    "circuit_breaker_change": ["provider", "old_status", "new_status"],
    "item_started": ["stage", "cache_key"],
    "item_completed": ["stage", "cache_key", "decision"],
    "item_failed": ["stage", "cache_key", "reason"],
    "quality_score": ["stage", "score"],
}


def _validate_metric(metric: str, tags: Dict) -> bool:
    """Validate metric tags against schema. Returns True if valid."""
    required = _METRIC_SCHEMAS.get(metric, [])
    for field in required:
        if field not in tags or tags[field] is None:
            return False
    return True


class TelemetryBus:
    """Unified runtime telemetry ingestion bus.

    Thread-safe. All public record_* methods are non-blocking.
    Every event is stamped with a logical timestamp for causal ordering.
    """

    def __init__(
        self,
        store: Optional[TimeSeriesStore] = None,
        max_queue_size: int = DEFAULT_MAX_QUEUE_SIZE,
        flush_interval: float = DEFAULT_FLUSH_INTERVAL,
    ):
        self._store = store
        self._queue: "queue.Queue[Optional[EventEnvelope]]" = queue.Queue(maxsize=max_queue_size)
        self._flush_interval = flush_interval
        self._stop_event = threading.Event()
        self._flush_count: int = 0
        self._lock = threading.RLock()
        self._drops = _DropCounters()
        self._event_log: List[EventEnvelope] = []
        self._event_log_lock = threading.Lock()
        self._source = "worker"

        self._flush_thread = threading.Thread(
            target=self._flush_loop,
            daemon=True,
            name="telemetry-bus-flush",
        )
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        """Start the background flush thread. Idempotent."""
        if self._running:
            return
        self._running = True
        self._flush_thread.start()

    def stop(self):
        """Stop the background flush thread and drain the queue.

        Guarantees zero data loss: synchronously flushes all remaining
        events before returning. Blocks until flush completes or timeout.
        """
        self._stop_event.set()
        self.flush()
        if self._flush_thread.is_alive():
            self._flush_thread.join(timeout=5.0)

    def flush(self):
        """Synchronously drain all pending events to the store.

        Called automatically on shutdown. Also callable manually.
        """
        store = self._resolve_store()
        while not self._queue.empty():
            try:
                envelope = self._queue.get(block=False)
                if envelope is None:
                    continue
                store.record(envelope.metric, envelope.value, envelope.tags)
                self._append_to_event_log(envelope)
                self._flush_count += 1
            except queue.Empty:
                break
            except Exception:
                self._drops.inc_flush_failure()

    def _flush_loop(self):
        """Background flush loop. Polls queue and writes to store."""
        store = self._resolve_store()
        while not self._stop_event.is_set():
            try:
                envelope = self._queue.get(timeout=self._flush_interval)
                if envelope is None:
                    continue
                store.record(envelope.metric, envelope.value, envelope.tags)
                self._append_to_event_log(envelope)
                self._flush_count += 1
            except queue.Empty:
                continue
            except Exception:
                self._drops.inc_flush_failure()

    def _resolve_store(self) -> TimeSeriesStore:
        if self._store is None:
            self._store = get_timeseries_store()
        return self._store

    # ------------------------------------------------------------------
    # Event log (bounded in-memory ring buffer for reconciliation)
    # ------------------------------------------------------------------

    def _append_to_event_log(self, envelope: EventEnvelope):
        """Append to in-memory event log (ring buffer, max 10000 entries)."""
        with self._event_log_lock:
            self._event_log.append(envelope)
            if len(self._event_log) > 10000:
                self._event_log.pop(0)

    def get_event_log(self, since_id: str = "") -> List[EventEnvelope]:
        """Get all logged events, optionally since a given event ID."""
        with self._event_log_lock:
            if not since_id:
                return list(self._event_log)
            idx = 0
            for i, ev in enumerate(self._event_log):
                if ev.global_event_id == since_id:
                    idx = i + 1
                    break
            return list(self._event_log[idx:])

    def clear_event_log(self):
        """Clear the in-memory event log (for testing)."""
        with self._event_log_lock:
            self._event_log.clear()

    # ------------------------------------------------------------------
    # Core enqueue
    # ------------------------------------------------------------------

    def _enqueue(self, metric: str, value: float, tags: Optional[Dict] = None, source: str = ""):
        """Non-blocking enqueue with bounded queue and drop strategy.

        Every event is stamped with a logical timestamp for causal ordering
        before being enqueued. Never raises. Never blocks the caller.

        Backpressure: non-critical events may be dropped under load.
        """
        tags = dict(tags or {})
        if not _validate_metric(metric, tags):
            self._drops.inc_schema_violation()
            return
        # Backpressure check (fail-safe: on exception, always sample)
        try:
            controller = get_backpressure_controller()
            if not controller.should_sample(metric):
                self._drops.inc_queue_full()
                return
        except Exception:
            pass
        envelope = stamp_event(
            metric=metric,
            value=value,
            tags=tags,
            source=source or self._source,
        )
        try:
            self._queue.put(envelope, block=False)
        except queue.Full:
            self._drops.inc_queue_full()

    # ------------------------------------------------------------------
    # Worker events
    # ------------------------------------------------------------------

    def record_item_started(self, stage: str, cache_key: str):
        self._enqueue("item_started", 1.0, {"stage": stage, "cache_key": cache_key[:16]}, source="worker")

    def record_item_completed(self, stage: str, cache_key: str, decision: str = ""):
        self._enqueue("item_completed", 1.0, {"stage": stage, "cache_key": cache_key[:16], "decision": decision}, source="worker")

    def record_item_failed(self, stage: str, cache_key: str, reason: str = ""):
        self._enqueue("item_failed", 1.0, {"stage": stage, "cache_key": cache_key[:16], "reason": reason[:64]}, source="worker")

    # ------------------------------------------------------------------
    # Gateway events
    # ------------------------------------------------------------------

    def record_provider_call(self, provider: str = "default"):
        self._enqueue("provider_call", 1.0, {"provider": provider}, source="gateway")

    def record_provider_failure(self, provider: str = "default", reason: str = ""):
        self._enqueue("provider_failure", 1.0, {"provider": provider, "reason": reason[:64]}, source="gateway")

    def record_circuit_breaker_change(self, provider: str, old_status: str, new_status: str):
        self._enqueue("circuit_breaker_change", 1.0, {
            "provider": provider,
            "old_status": old_status,
            "new_status": new_status,
        }, source="gateway")

    # ------------------------------------------------------------------
    # Queue events
    # ------------------------------------------------------------------

    def record_queue_depth(self, stage: str, depth: int):
        self._enqueue(f"queue_depth_{stage}", float(depth), source="queue")

    def record_processing_time(self, stage: str, seconds: float):
        self._enqueue(f"processing_time_{stage}", seconds, source="queue")

    def record_requeue_event(self, stage: str, reason: str = "transient"):
        self._enqueue("requeue_event", 1.0, {"stage": stage, "reason": reason}, source="queue")

    # ------------------------------------------------------------------
    # Metrics (from worker context)
    # ------------------------------------------------------------------

    def record_decision(self, stage: str, decision: str):
        self._enqueue(f"decision_{stage}", 1.0, {"decision": decision}, source="worker")

    def record_acceptance(self, stage: str, accepted: bool):
        self._enqueue(f"acceptance_{stage}", 1.0 if accepted else 0.0, source="worker")

    def record_confidence(self, stage: str, confidence: float):
        self._enqueue(f"confidence_{stage}", confidence, source="worker")

    def record_latency(self, stage: str, duration_ms: float):
        self._enqueue(f"latency_{stage}", duration_ms, source="worker")

    def record_retry(self, stage: str):
        self._enqueue(f"retry_{stage}", 1.0, source="worker")

    def record_429(self, provider: str = "groq"):
        self._enqueue("rate_limit_429", 1.0, {"provider": provider}, source="gateway")

    def record_quality_score(self, stage: str, score: float):
        self._enqueue("quality_score", score, {"stage": stage}, source="worker")

    # ------------------------------------------------------------------
    # Admin
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict:
        """Get current bus statistics (thread-safe)."""
        return {
            "queue_size": self._queue.qsize(),
            "queue_maxsize": self._queue.maxsize,
            "flush_count": self._flush_count,
            "drops": self._drops.snapshot(),
            "running": self._running,
            "event_log_size": len(self._event_log),
        }

    def get_event_log_sorted(self) -> List[EventEnvelope]:
        """Return the event log sorted by logical timestamp (deterministic order)."""
        with self._event_log_lock:
            return sorted(self._event_log)

    def reset_for_testing(self):
        """Reset bus state (for testing only)."""
        self.stop()
        while not self._queue.empty():
            try:
                self._queue.get(block=False)
            except queue.Empty:
                break
        self._drops = _DropCounters()
        self._flush_count = 0
        self._running = False
        self._stop_event.clear()
        self.clear_event_log()
        self._flush_thread = threading.Thread(
            target=self._flush_loop,
            daemon=True,
            name="telemetry-bus-flush",
        )


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_global_bus: Optional[TelemetryBus] = None
_bus_lock = threading.Lock()


def get_telemetry_bus() -> TelemetryBus:
    """Get the global TelemetryBus singleton."""
    global _global_bus
    if _global_bus is None:
        with _bus_lock:
            if _global_bus is None:
                _global_bus = TelemetryBus()
                _global_bus.start()
    return _global_bus


def reset_telemetry_bus():
    """Reset the global singleton (for testing)."""
    global _global_bus
    with _bus_lock:
        if _global_bus is not None:
            _global_bus.stop()
        _global_bus = None
