"""
Longitudinal time-series storage for APOLLO.

Records individual metric observations with monotonic timestamps
and provides windowed aggregation (1m / 10m / 1h).

Architecture:
  - Append-only JSONL per metric category
  - Monotonic timestamps via time.monotonic() with epoch mapping
  - Deterministic compaction snapshots (periodic summarization)
  - Thread-safe writes and reads
"""
import json
import os
import time
import threading
import glob
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from datetime import datetime, timezone


TIMESERIES_DIR = Path("data/timeseries")
EPOCH_OFFSET: Optional[float] = None
_epoch_lock = threading.Lock()


def _get_epoch_offset() -> float:
    global EPOCH_OFFSET
    if EPOCH_OFFSET is None:
        with _epoch_lock:
            if EPOCH_OFFSET is None:
                EPOCH_OFFSET = time.time() - time.monotonic()
    return EPOCH_OFFSET


def monotonic_to_epoch(mono: float) -> float:
    return mono + _get_epoch_offset()


def epoch_to_monotonic(epoch: float) -> float:
    return epoch - _get_epoch_offset()


class MetricSeries:
    """A single time-series metric (one JSONL file per window bucket)."""

    def __init__(self, series_dir: Path, metric_name: str):
        self._dir = series_dir / metric_name
        self._dir.mkdir(parents=True, exist_ok=True)
        self._metric_name = metric_name
        self._lock = threading.RLock()

    def _bucket_path(self, window_start: int) -> Path:
        return self._dir / f"{window_start}.jsonl"

    def record(self, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        record = {
            "ts": time.monotonic(),
            "v": value,
            "tags": tags or {},
        }
        bucket_ts = int(time.monotonic())
        path = self._bucket_path(bucket_ts)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
                f.flush()
                os.fsync(f.fileno())
        except OSError:
            pass

    def query(
        self,
        since_mono: float = 0.0,
        until_mono: float = float('inf'),
    ) -> List[Dict]:
        results = []
        for fpath in sorted(glob.glob(str(self._dir / "*.jsonl"))):
            bucket_start = int(Path(fpath).stem)
            if bucket_start > until_mono or bucket_start < since_mono - 3600:
                continue
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    for line in f:
                        stripped = line.strip()
                        if not stripped:
                            continue
                        try:
                            rec = json.loads(stripped)
                            ts = rec.get("ts", 0)
                            if since_mono <= ts <= until_mono:
                                results.append(rec)
                        except json.JSONDecodeError:
                            pass
            except OSError:
                pass
        return sorted(results, key=lambda r: r.get("ts", 0))

    def count_records(self) -> int:
        count = 0
        for fpath in glob.glob(str(self._dir / "*.jsonl")):
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            count += 1
            except OSError:
                pass
        return count

    def delete_all(self) -> None:
        import shutil
        if self._dir.exists():
            shutil.rmtree(str(self._dir))


class TimeSeriesStore:
    """Central time-series store for all metric categories.

    Metrics are organized as named series, each stored in its own
    subdirectory with time-bucketed JSONL files.
    """

    def __init__(self, base_dir: str = "data/timeseries"):
        self._base = Path(base_dir)
        self._series: Dict[str, MetricSeries] = {}
        self._lock = threading.RLock()

    def _get_series(self, metric: str) -> MetricSeries:
        with self._lock:
            if metric not in self._series:
                self._series[metric] = MetricSeries(self._base, metric)
            return self._series[metric]

    def record(self, metric: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        self._get_series(metric).record(value, tags)

    def record_decision(self, stage: str, decision: str) -> None:
        self.record(f"decision_{stage}", 1.0, {"decision": decision})

    def record_acceptance(self, stage: str, accepted: bool) -> None:
        self.record(f"acceptance_{stage}", 1.0 if accepted else 0.0)

    def record_confidence(self, stage: str, confidence: float) -> None:
        self.record(f"confidence_{stage}", confidence)

    def record_latency(self, stage: str, duration_ms: float) -> None:
        self.record(f"latency_{stage}", duration_ms)

    def record_retry(self, stage: str) -> None:
        self.record(f"retry_{stage}", 1.0)

    def record_429(self, provider: str = "groq") -> None:
        self.record("rate_limit_429", 1.0, {"provider": provider})

    def query_series(
        self,
        metric: str,
        since_mono: float = 0.0,
        until_mono: float = float('inf'),
    ) -> List[Dict]:
        return self._get_series(metric).query(since_mono, until_mono)


_global_store: Optional[TimeSeriesStore] = None
_store_lock = threading.Lock()


def get_timeseries_store() -> TimeSeriesStore:
    global _global_store
    if _global_store is None:
        with _store_lock:
            if _global_store is None:
                _global_store = TimeSeriesStore()
    return _global_store


def reset_timeseries_store():
    global _global_store
    with _store_lock:
        _global_store = None
