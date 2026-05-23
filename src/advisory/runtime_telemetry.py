"""
Persistent time-series telemetry for APOLLO.

Append-only JSONL storage with bounded retention and periodic snapshot
compaction. Thread-safe writes with crash-safe semantics.

Architecture:
  - One JSONL file per time bucket (configurable duration)
  - Bounded retention: oldest files pruned on rotation
  - Snapshot compaction: aggregates old buckets into summary records
  - All writes are fsync'd for crash safety
  - Reader queries merge across files in time range

Telemetry record types:
  - metrics_snapshot: full metrics snapshot at a point in time
  - worker_event: worker lifecycle event
  - provider_event: provider throttle/cooldown/error
  - retry_event: item retry lifecycle
  - calibration_event: calibration agreement trend
  - throughput_sample: per-minute throughput
"""
import os
import json
import time
import threading
import glob
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timezone


TELEMETRY_DIR = Path("data/runtime")
DEFAULT_BUCKET_SECONDS = 3600  # 1 hour per file
DEFAULT_RETENTION_BUCKETS = 48  # 48 hours retention
DEFAULT_BUCKET_PREFIX = "telemetry"


class TelemetryBucket:
    """A single time-bucketed JSONL file."""

    def __init__(self, path: Path):
        self._path = path
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: dict) -> bool:
        """Append a record with crash-safe write. Returns True on success."""
        try:
            with self._lock:
                with open(self._path, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(record, ensure_ascii=False) + '\n')
                    f.flush()
                    os.fsync(f.fileno())
            return True
        except OSError:
            return False

    def read_lines(self) -> List[Dict]:
        """Read all records from this bucket (thread-safe, snapshot)."""
        if not self._path.exists():
            return []
        with self._lock:
            try:
                with open(self._path, 'r', encoding='utf-8') as f:
                    lines = []
                    for line in f:
                        stripped = line.strip()
                        if not stripped:
                            continue
                        try:
                            lines.append(json.loads(stripped))
                        except json.JSONDecodeError:
                            lines.append({"type": "malformed", "raw": stripped[:80]})
                    return lines
            except (OSError, json.JSONDecodeError):
                return []

    def count_lines(self) -> int:
        """Count lines without loading into memory."""
        if not self._path.exists():
            return 0
        with self._lock:
            try:
                with open(self._path, 'r', encoding='utf-8') as f:
                    return sum(1 for _ in f if _.strip())
            except OSError:
                return 0

    def rotate(self, new_path: Path) -> bool:
        """Rename current file to new_path (for compaction)."""
        with self._lock:
            try:
                if self._path.exists():
                    os.rename(str(self._path), str(new_path))
                    return True
            except OSError:
                pass
            return False

    def delete(self) -> bool:
        """Delete this bucket file."""
        with self._lock:
            try:
                if self._path.exists():
                    self._path.unlink()
                    return True
            except OSError:
                pass
            return False

    @property
    def size_bytes(self) -> int:
        try:
            return self._path.stat().st_size if self._path.exists() else 0
        except OSError:
            return 0

    @property
    def path(self) -> Path:
        return self._path


class RuntimeTelemetry:
    """Persistent time-series telemetry with bounded retention.

    Thread-safe. All public methods are safe for concurrent access.
    """

    def __init__(
        self,
        telemetry_dir: str = "data/runtime",
        bucket_seconds: float = 3600.0,
        retention_buckets: int = 48,
    ):
        self._dir = Path(telemetry_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._bucket_seconds = bucket_seconds
        self._retention_buckets = retention_buckets
        self._lock = threading.RLock()
        self._current_bucket: Optional[TelemetryBucket] = None
        self._current_bucket_ts: int = 0
        self._write_count: int = 0
        self._append_failures: int = 0

    # ------------------------------------------------------------------
    # Bucket management
    # ------------------------------------------------------------------

    def _bucket_timestamp(self, ts: float) -> int:
        """Map a timestamp to its bucket key."""
        return int(ts // self._bucket_seconds) * int(self._bucket_seconds)

    def _bucket_path(self, bucket_ts: int) -> Path:
        """Get file path for a bucket timestamp."""
        return self._dir / f"{DEFAULT_BUCKET_PREFIX}_{bucket_ts}.jsonl"

    def _get_or_create_bucket(self, ts: float) -> TelemetryBucket:
        """Get the current bucket, creating a new one if time has advanced."""
        bucket_ts = self._bucket_timestamp(ts)
        with self._lock:
            if bucket_ts != self._current_bucket_ts or self._current_bucket is None:
                self._current_bucket = TelemetryBucket(self._bucket_path(bucket_ts))
                self._current_bucket_ts = bucket_ts
            return self._current_bucket

    # ------------------------------------------------------------------
    # Write API
    # ------------------------------------------------------------------

    def record(self, record_type: str, data: dict) -> None:
        """Record a telemetry event (thread-safe, crash-safe)."""
        record = {
            "t": time.time(),
            "type": record_type,
            "d": data,
        }
        bucket = self._get_or_create_bucket(record["t"])
        if bucket.append(record):
            with self._lock:
                self._write_count += 1
        else:
            with self._lock:
                self._append_failures += 1

    def record_metrics_snapshot(self, snapshot: dict) -> None:
        """Record a full metrics snapshot."""
        self.record("metrics_snapshot", snapshot)

    def record_worker_event(self, event_type: str, stage: str, detail: str = "") -> None:
        """Record a worker lifecycle event."""
        self.record("worker_event", {
            "event": event_type,
            "stage": stage,
            "detail": detail,
        })

    def record_provider_event(self, provider: str, event: str, detail: str = "") -> None:
        """Record a provider throttle/cooldown/error event."""
        self.record("provider_event", {
            "provider": provider,
            "event": event,
            "detail": detail,
        })

    def record_retry_event(self, cache_key: str, stage: str, attempt: int, reason: str) -> None:
        """Record an item retry lifecycle event."""
        self.record("retry_event", {
            "cache_key": cache_key[:16],
            "stage": stage,
            "attempt": attempt,
            "reason": reason,
        })

    def record_calibration_event(self, protocol_hash: str, metric: str, value: float) -> None:
        """Record a calibration agreement trend data point."""
        self.record("calibration_event", {
            "protocol": protocol_hash[:12],
            "metric": metric,
            "value": round(value, 4),
        })

    def record_throughput_sample(self, stage: str, requests_per_minute: float) -> None:
        """Record per-minute throughput sample."""
        self.record("throughput_sample", {
            "stage": stage,
            "rpm": round(requests_per_minute, 2),
        })

    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------

    def query(
        self,
        record_types: Optional[List[str]] = None,
        since: float = 0.0,
        until: float = float('inf'),
        limit: int = 10000,
    ) -> List[Dict]:
        """Query telemetry records within a time range (newest first)."""
        results: List[Dict] = []
        bucket_keys = sorted(self._list_bucket_keys(), reverse=True)

        for bucket_ts in bucket_keys:
            if len(results) >= limit:
                break
            bucket_start = bucket_ts
            bucket_end = bucket_ts + self._bucket_seconds
            if bucket_end < since or bucket_start > until:
                continue

            bucket = TelemetryBucket(self._bucket_path(bucket_ts))
            for record in bucket.read_lines():
                if len(results) >= limit:
                    break
                record_type = record.get("type", "unknown")
                if record_types and record_type not in record_types:
                    continue
                record_time = record.get("t", 0)
                if record_time < since or record_time > until:
                    continue
                results.append(record)

        return results

    def _list_bucket_keys(self) -> List[int]:
        """List all bucket timestamps found on disk."""
        keys = []
        pattern = str(self._dir / f"{DEFAULT_BUCKET_PREFIX}_*.jsonl")
        for path_str in glob.glob(pattern):
            try:
                key = int(Path(path_str).stem.split("_")[-1])
                keys.append(key)
            except (ValueError, IndexError):
                pass
        return keys

    # ------------------------------------------------------------------
    # Retention
    # ------------------------------------------------------------------

    def enforce_retention(self) -> int:
        """Prune buckets older than retention window. Returns count pruned."""
        cutoff = self._bucket_timestamp(time.time()) - (
            self._retention_buckets * self._bucket_seconds
        )
        pruned = 0
        for key in self._list_bucket_keys():
            if key < cutoff:
                bucket = TelemetryBucket(self._bucket_path(key))
                if bucket.delete():
                    pruned += 1
        return pruned

    def compact_old_buckets(self, max_before_compact: int = 50000) -> int:
        """Compact buckets that exceed line count threshold.

        Replaces oversized buckets with a single summary record.
        Returns number of buckets compacted.
        """
        compacted = 0
        now = time.time()
        cutoff = self._bucket_timestamp(now) - (2 * self._bucket_seconds)
        for key in self._list_bucket_keys():
            if key >= cutoff:
                continue
            bucket = TelemetryBucket(self._bucket_path(key))
            if bucket.count_lines() > max_before_compact:
                summary = self._summarize_bucket(bucket)
                if summary:
                    temp_path = self._bucket_path(key).with_suffix(".jsonl.compacting")
                    temp_bucket = TelemetryBucket(temp_path)
                    temp_bucket.append(summary)
                    if bucket.rotate(self._bucket_path(key).with_suffix(".jsonl.old")):
                        os.rename(str(temp_path), str(self._bucket_path(key)))
                        Path(str(self._bucket_path(key)) + ".old").unlink(missing_ok=True)
                        compacted += 1
        return compacted

    def _summarize_bucket(self, bucket: TelemetryBucket) -> Optional[Dict]:
        """Aggregate a bucket's records into a single summary."""
        lines = bucket.read_lines()
        if not lines:
            return None
        counts: Dict[str, int] = {}
        for line in lines:
            t = line.get("type", "unknown")
            counts[t] = counts.get(t, 0) + 1
        return {
            "t": time.time(),
            "type": "compact_summary",
            "d": {
                "source_records": len(lines),
                "record_counts": counts,
            },
        }

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict:
        """Get telemetry system stats."""
        with self._lock:
            bucket_count = len(self._list_bucket_keys())
            return {
                "bucket_count": bucket_count,
                "current_bucket_ts": self._current_bucket_ts,
                "total_writes": self._write_count,
                "append_failures": self._append_failures,
                "bucket_seconds": self._bucket_seconds,
                "retention_buckets": self._retention_buckets,
                "telemetry_dir": str(self._dir),
            }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_global_telemetry: Optional[RuntimeTelemetry] = None
_telemetry_lock = threading.Lock()


def get_runtime_telemetry() -> RuntimeTelemetry:
    """Get global RuntimeTelemetry singleton."""
    global _global_telemetry
    if _global_telemetry is None:
        with _telemetry_lock:
            if _global_telemetry is None:
                _global_telemetry = RuntimeTelemetry()
    return _global_telemetry


def reset_runtime_telemetry():
    """Reset global singleton (for testing)."""
    global _global_telemetry
    with _telemetry_lock:
        _global_telemetry = None
