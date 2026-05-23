"""
Runtime operational metrics for APOLLO advisory system.

Thread-safe singleton providing lightweight counters, timings, and
structured recovery telemetry. Zero external dependencies.

Usage:
    from .advisory_metrics import get_metrics
    metrics = get_metrics()
    metrics.worker_generation_count += 1
    metrics.record_worker_latency(1234.5)
    snapshot = metrics.get_snapshot()
"""

import os
import json
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional


class _RunningStats:
    """O(1) running statistics (min, max, count, sum for mean)."""
    __slots__ = ("count", "sum", "min_val", "max_val")

    def __init__(self):
        self.count: int = 0
        self.sum: float = 0.0
        self.min_val: float = float('inf')
        self.max_val: float = float('-inf')

    def record(self, value: float):
        self.count += 1
        self.sum += value
        if value < self.min_val:
            self.min_val = value
        if value > self.max_val:
            self.max_val = value

    @property
    def avg(self) -> float:
        return self.sum / self.count if self.count else 0.0

    def to_dict(self) -> Dict:
        return {
            "count": self.count,
            "avg_ms": round(self.avg, 2),
            "min_ms": round(self.min_val, 2) if self.count else 0.0,
            "max_ms": round(self.max_val, 2) if self.count else 0.0,
        }


class _RecoveryEvent:
    """A structured recovery telemetry event."""
    __slots__ = ("event_type", "stage", "timestamp", "duration_ms",
                 "operation_count", "outcome", "detail")

    def __init__(self, event_type: str, stage: str = "",
                 duration_ms: float = 0.0, operation_count: int = 0,
                 outcome: str = "ok", detail: str = ""):
        self.event_type = event_type
        self.stage = stage
        self.timestamp = time.time()
        self.duration_ms = duration_ms
        self.operation_count = operation_count
        self.outcome = outcome
        self.detail = detail

    def to_dict(self) -> Dict:
        return {
            "event_type": self.event_type,
            "stage": self.stage,
            "timestamp": self.timestamp,
            "duration_ms": round(self.duration_ms, 2),
            "operation_count": self.operation_count,
            "outcome": self.outcome,
            "detail": self.detail,
        }


class AdvisoryMetrics:
    """
    Thread-safe singleton runtime metrics tracker.

    All counters are increment-only with O(1) overhead.
    Timings use running stats (no percentile arrays).
    Recovery events are stored as a bounded ring buffer.
    """

    _instance: Optional["AdvisoryMetrics"] = None
    _lock: threading.RLock = threading.RLock()

    def __new__(cls) -> "AdvisoryMetrics":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        with self._lock:
            if getattr(self, '_initialized', False):
                return
            self._initialized = True

            # Queue counters
            self.queue_pending_count: int = 0
            self.queue_processing_count: int = 0
            self.queue_completed_count: int = 0
            self.queue_failed_count: int = 0
            self.queue_retry_count: int = 0
            self.queue_wait_time = _RunningStats()

            # Worker counters
            self.worker_generation_count: int = 0
            self.worker_failure_count: int = 0
            self.worker_idle_cycles: int = 0
            self.worker_stop_count: int = 0
            self.worker_latency = _RunningStats()

            # Cache counters
            self.cache_session_hits: int = 0
            self.cache_session_misses: int = 0
            self.cache_disk_hits: int = 0
            self.cache_disk_misses: int = 0
            self.cache_eviction_count: int = 0

            # Recovery counters
            self.wal_replay_operations: int = 0
            self.wal_replay_duration = _RunningStats()
            self.stale_processing_requeues: int = 0
            self.corrupted_snapshot_recoveries: int = 0
            self.malformed_wal_entries: int = 0

            # Prefilter counters
            self.prefilter_duplicate_hits: int = 0
            self.prefilter_accepts: int = 0
            self.prefilter_rejects: int = 0

            # Auto-compaction counters
            self.auto_compaction_trigger_count: int = 0
            self.auto_compaction_skipped_lock: int = 0

            # Recovery event ring buffer (max 200 events)
            self._recovery_events: List[Dict] = []
            self._max_recovery_events: int = 200

            # Metrics log persistence
            self._metrics_log_path: Optional[Path] = None
            self._metrics_log_retention: int = 1000

    # ------------------------------------------------------------------
    # Worker helpers
    # ------------------------------------------------------------------

    def record_worker_latency(self, ms: float):
        with self._lock:
            self.worker_latency.record(ms)

    # ------------------------------------------------------------------
    # Queue helpers
    # ------------------------------------------------------------------

    def record_queue_wait(self, ms: float):
        with self._lock:
            self.queue_wait_time.record(ms)

    # ------------------------------------------------------------------
    # Recovery helpers
    # ------------------------------------------------------------------

    def record_replay(self, duration_ms: float, operations: int):
        with self._lock:
            self.wal_replay_duration.record(duration_ms)
            self.wal_replay_operations += operations

    def record_recovery_event(self, event: _RecoveryEvent):
        with self._lock:
            self._recovery_events.append(event.to_dict())
            if len(self._recovery_events) > self._max_recovery_events:
                self._recovery_events.pop(0)

    # ------------------------------------------------------------------
    # Metrics log persistence
    # ------------------------------------------------------------------

    def configure(self, metrics_log_path: str = "", retention: int = 1000):
        """Configure metrics log path and retention (thread-safe)."""
        with self._lock:
            if metrics_log_path:
                self._metrics_log_path = Path(metrics_log_path)
                self._metrics_log_path.parent.mkdir(parents=True, exist_ok=True)
            self._metrics_log_retention = max(retention, 10)

    def _append_metrics_log(self, record: dict):
        """Crash-safe append to metrics JSONL (caller must hold _lock)."""
        if self._metrics_log_path is None:
            return
        try:
            self._metrics_log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._metrics_log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
                f.flush()
                os.fsync(f.fileno())
        except OSError:
            pass

    def flush_metrics(self):
        """Append a metrics snapshot to the persistent log."""
        snapshot = self.get_snapshot()
        record = {
            "timestamp": time.time(),
            "type": "metrics_snapshot",
            "data": snapshot,
        }
        with self._lock:
            self._append_metrics_log(record)

    def rotate_metrics_log(self):
        """Trim metrics log to retention count (oldest entries removed)."""
        with self._lock:
            if self._metrics_log_path is None or not self._metrics_log_path.exists():
                return
            try:
                lines = self._metrics_log_path.read_text(encoding='utf-8').splitlines()
                if len(lines) <= self._metrics_log_retention:
                    return
                trimmed = lines[-self._metrics_log_retention:]
                temp = self._metrics_log_path.with_suffix('.jsonl.tmp')
                temp.write_text('\n'.join(trimmed) + '\n', encoding='utf-8')
                os.replace(str(temp), str(self._metrics_log_path))
            except OSError:
                pass

    def log_event_to_file(self, event_type: str, data: dict):
        """Append a structured operational event to the metrics log."""
        record = {
            "timestamp": time.time(),
            "type": event_type,
            "data": data,
        }
        with self._lock:
            self._append_metrics_log(record)

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def get_snapshot(self) -> Dict:
        """Get complete metrics snapshot (thread-safe)."""
        with self._lock:
            queue_section = {
                "pending_count": self.queue_pending_count,
                "processing_count": self.queue_processing_count,
                "completed_count": self.queue_completed_count,
                "failed_count": self.queue_failed_count,
                "retry_count": self.queue_retry_count,
                "wait_time_ms": self.queue_wait_time.to_dict(),
            }
            worker_section = {
                "generation_count": self.worker_generation_count,
                "failure_count": self.worker_failure_count,
                "idle_cycles": self.worker_idle_cycles,
                "stop_count": self.worker_stop_count,
                "latency_ms": self.worker_latency.to_dict(),
            }
            cache_section = {
                "session_hits": self.cache_session_hits,
                "session_misses": self.cache_session_misses,
                "disk_hits": self.cache_disk_hits,
                "disk_misses": self.cache_disk_misses,
                "eviction_count": self.cache_eviction_count,
                "hit_ratio": (
                    round(self.cache_session_hits / (self.cache_session_hits + self.cache_session_misses), 4)
                    if (self.cache_session_hits + self.cache_session_misses) > 0
                    else 0.0
                ),
            }
            recovery_section = {
                "wal_replay_operations": self.wal_replay_operations,
                "wal_replay_duration_ms": self.wal_replay_duration.to_dict(),
                "stale_processing_requeues": self.stale_processing_requeues,
                "corrupted_snapshot_recoveries": self.corrupted_snapshot_recoveries,
                "malformed_wal_entries": self.malformed_wal_entries,
            }
            prefilter_section = {
                "duplicate_title_hits": self.prefilter_duplicate_hits,
                "accepts": self.prefilter_accepts,
                "rejects": self.prefilter_rejects,
            }
            compaction_section = {
                "auto_compaction_trigger_count": self.auto_compaction_trigger_count,
                "auto_compaction_skipped_lock": self.auto_compaction_skipped_lock,
            }
            return {
                "queue": queue_section,
                "worker": worker_section,
                "cache": cache_section,
                "recovery": recovery_section,
                "prefilter": prefilter_section,
                "auto_compaction": compaction_section,
            }

    def get_recovery_events(self, limit: int = 50) -> List[Dict]:
        """Get recent recovery events (newest first)."""
        with self._lock:
            return list(reversed(self._recovery_events[-limit:]))

    def reset(self):
        """Reset all metrics to zero."""
        self.__init__()


# ---------------------------------------------------------------------------
# Module-level access
# ---------------------------------------------------------------------------

def get_metrics() -> AdvisoryMetrics:
    """Get the global AdvisoryMetrics singleton."""
    return AdvisoryMetrics()


def get_metrics_snapshot() -> Dict:
    """Convenience: get metrics snapshot."""
    return get_metrics().get_snapshot()


def reset_metrics():
    """Convenience: reset all metrics."""
    get_metrics().reset()


def flush_metrics():
    """Convenience: flush metrics snapshot to persistent log."""
    get_metrics().flush_metrics()


def configure_metrics(metrics_log_path: str = "", retention: int = 1000):
    """Convenience: configure metrics persistence."""
    get_metrics().configure(metrics_log_path, retention)
