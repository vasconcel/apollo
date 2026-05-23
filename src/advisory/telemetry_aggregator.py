"""
Windowed aggregation layer over the time-series store.

Computes rolling statistics over configurable windows:
  - 1 minute (fast feedback)
  - 10 minutes (medium trend)
  - 1 hour (long-term evolution)

All aggregations are deterministic pure functions given the same input data.
"""
import time
import math
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from src.advisory.telemetry_timeseries import (
    get_timeseries_store,
    monotonic_to_epoch,
    epoch_to_monotonic,
    TimeSeriesStore,
)


WINDOW_1M = 60.0
WINDOW_10M = 600.0
WINDOW_1H = 3600.0


def _compute_percentile(sorted_values: List[float], p: float) -> float:
    """Compute the p-th percentile (0-100) from a sorted list."""
    if not sorted_values:
        return 0.0
    k = (p / 100.0) * (len(sorted_values) - 1)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_values[int(k)]
    return sorted_values[f] * (c - k) + sorted_values[c] * (k - f)


def _count_occurrences(records: List[Dict], value_key: str = "v") -> int:
    """Count records with value > 0."""
    return sum(1 for r in records if r.get(value_key, 0) > 0)


def aggregate_decision_distribution(
    stage: str,
    window_seconds: float = WINDOW_10M,
    store: Optional[TimeSeriesStore] = None,
) -> Dict:
    """Aggregate EC/IC decision counts within a time window."""
    store = store or get_timeseries_store()
    now = time.monotonic()
    since = now - window_seconds
    records = store.query_series(f"decision_{stage}", since_mono=since, until_mono=now)
    counts: Dict[str, int] = defaultdict(int)
    for r in records:
        decision = r.get("tags", {}).get("decision", "UNKNOWN")
        counts[decision] += 1
    total = sum(counts.values()) or 1
    return {
        "stage": stage,
        "window_seconds": window_seconds,
        "total_decisions": sum(counts.values()),
        "counts": dict(counts),
        "rates": {k: round(v / total, 4) for k, v in counts.items()},
    }


def aggregate_acceptance_rate(
    stage: str,
    window_seconds: float = WINDOW_10M,
    store: Optional[TimeSeriesStore] = None,
) -> Dict:
    """Compute acceptance rate (INCLUDE / total) within a window."""
    store = store or get_timeseries_store()
    now = time.monotonic()
    since = now - window_seconds
    records = store.query_series(f"decision_{stage}", since_mono=since, until_mono=now)
    total = len(records)
    if not total:
        return {"stage": stage, "window_seconds": window_seconds, "acceptance_rate": 0.0, "total": 0}
    includes = sum(
        1 for r in records
        if r.get("tags", {}).get("decision", "") == "INCLUDE"
    )
    return {
        "stage": stage,
        "window_seconds": window_seconds,
        "acceptance_rate": round(includes / total, 4),
        "includes": includes,
        "total": total,
    }


def aggregate_confidence_distribution(
    stage: str,
    window_seconds: float = WINDOW_10M,
    store: Optional[TimeSeriesStore] = None,
) -> Dict:
    """Compute mean confidence and distribution within a window."""
    store = store or get_timeseries_store()
    now = time.monotonic()
    since = now - window_seconds
    records = store.query_series(f"confidence_{stage}", since_mono=since, until_mono=now)
    values = [r.get("v", 0.0) for r in records]
    if not values:
        return {"stage": stage, "window_seconds": window_seconds, "mean": 0.0, "count": 0}
    sorted_vals = sorted(values)
    return {
        "stage": stage,
        "window_seconds": window_seconds,
        "mean": round(sum(values) / len(values), 4),
        "p50": round(_compute_percentile(sorted_vals, 50), 4),
        "p95": round(_compute_percentile(sorted_vals, 95), 4),
        "min": round(sorted_vals[0], 4),
        "max": round(sorted_vals[-1], 4),
        "count": len(values),
    }


def aggregate_latency(
    stage: str,
    window_seconds: float = WINDOW_10M,
    store: Optional[TimeSeriesStore] = None,
) -> Dict:
    """Compute latency percentiles within a window."""
    store = store or get_timeseries_store()
    now = time.monotonic()
    since = now - window_seconds
    records = store.query_series(f"latency_{stage}", since_mono=since, until_mono=now)
    values = [r.get("v", 0.0) for r in records]
    if not values:
        return {"stage": stage, "window_seconds": window_seconds, "p50": 0.0, "p95": 0.0, "p99": 0.0, "count": 0}
    sorted_vals = sorted(values)
    return {
        "stage": stage,
        "window_seconds": window_seconds,
        "p50": round(_compute_percentile(sorted_vals, 50), 2),
        "p95": round(_compute_percentile(sorted_vals, 95), 2),
        "p99": round(_compute_percentile(sorted_vals, 99), 2),
        "mean": round(sum(values) / len(values), 2),
        "min": round(sorted_vals[0], 2),
        "max": round(sorted_vals[-1], 2),
        "count": len(values),
    }


def aggregate_retry_rate(
    stage: str,
    window_seconds: float = WINDOW_10M,
    store: Optional[TimeSeriesStore] = None,
) -> Dict:
    """Compute retry rate (retries / total decisions) within a window."""
    store = store or get_timeseries_store()
    now = time.monotonic()
    since = now - window_seconds
    retries = _count_occurrences(
        store.query_series(f"retry_{stage}", since_mono=since, until_mono=now)
    )
    decisions = len(
        store.query_series(f"decision_{stage}", since_mono=since, until_mono=now)
    )
    total = max(decisions, 1)
    return {
        "stage": stage,
        "window_seconds": window_seconds,
        "retry_rate": round(retries / total, 4),
        "retries": retries,
        "decisions": decisions,
    }


def aggregate_429_rate(
    window_seconds: float = WINDOW_10M,
    store: Optional[TimeSeriesStore] = None,
) -> Dict:
    """Compute 429 incidence rate within a window."""
    store = store or get_timeseries_store()
    now = time.monotonic()
    since = now - window_seconds
    records = store.query_series("rate_limit_429", since_mono=since, until_mono=now)
    return {
        "window_seconds": window_seconds,
        "total_429": len(records),
        "rate_per_minute": round(len(records) / max(window_seconds / 60.0, 1), 4),
    }


def aggregate_all(
    stage: str,
    window_seconds: float = WINDOW_10M,
    store: Optional[TimeSeriesStore] = None,
) -> Dict:
    """Compute all aggregations for a given stage and window."""
    return {
        "decision_distribution": aggregate_decision_distribution(stage, window_seconds, store),
        "acceptance_rate": aggregate_acceptance_rate(stage, window_seconds, store),
        "confidence": aggregate_confidence_distribution(stage, window_seconds, store),
        "latency": aggregate_latency(stage, window_seconds, store),
        "retry_rate": aggregate_retry_rate(stage, window_seconds, store),
        "rate_limit_429": aggregate_429_rate(window_seconds, store),
    }


def aggregate_all_windows(stage: str, store: Optional[TimeSeriesStore] = None) -> Dict:
    """Compute all aggregations at 1m, 10m, and 1h windows."""
    return {
        "1m": aggregate_all(stage, WINDOW_1M, store),
        "10m": aggregate_all(stage, WINDOW_10M, store),
        "1h": aggregate_all(stage, WINDOW_1H, store),
    }
