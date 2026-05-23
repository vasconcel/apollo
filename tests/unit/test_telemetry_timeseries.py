"""Tests for telemetry_timeseries.py."""
import time
import pytest
import tempfile

from src.advisory.telemetry_timeseries import (
    TimeSeriesStore, MetricSeries, get_timeseries_store, reset_timeseries_store,
    monotonic_to_epoch, epoch_to_monotonic,
)
from src.advisory.telemetry_aggregator import (
    aggregate_decision_distribution,
    aggregate_acceptance_rate,
    aggregate_confidence_distribution,
    aggregate_latency,
    aggregate_retry_rate,
    aggregate_429_rate,
    aggregate_all,
    aggregate_all_windows,
    WINDOW_1M, WINDOW_10M, WINDOW_1H,
)


def _make_store():
    return TimeSeriesStore(base_dir=tempfile.mkdtemp())


class TestMetricSeries:
    def test_record_and_query(self, tmp_path):
        series = MetricSeries(tmp_path, "test_metric")
        series.record(0.5, {"tag": "a"})
        series.record(0.8, {"tag": "b"})

        results = series.query()
        assert len(results) == 2
        assert results[0]["v"] == 0.5
        assert results[1]["v"] == 0.8

    def test_query_time_range(self, tmp_path):
        series = MetricSeries(tmp_path, "test_range")
        series.record(1.0)
        time.sleep(0.01)
        mid = time.monotonic()
        series.record(2.0)

        after = series.query(since_mono=mid)
        assert len(after) == 1
        assert after[0]["v"] == 2.0

    def test_empty_query(self, tmp_path):
        series = MetricSeries(tmp_path, "empty")
        assert series.query() == []

    def test_count_records(self, tmp_path):
        series = MetricSeries(tmp_path, "count_test")
        assert series.count_records() == 0
        series.record(1.0)
        assert series.count_records() == 1
        series.record(2.0)
        series.record(3.0)
        assert series.count_records() == 3


class TestTimeSeriesStore:
    def test_record_and_query_series(self):
        store = _make_store()
        store.record("my_metric", 42.0, {"source": "test"})

        results = store.query_series("my_metric")
        assert len(results) == 1
        assert results[0]["v"] == 42.0
        assert results[0]["tags"]["source"] == "test"

    def test_convenience_methods(self):
        store = _make_store()
        store.record_decision("ec", "INCLUDE")
        store.record_acceptance("ec", True)
        store.record_confidence("ec", 0.85)
        store.record_latency("ec", 1500.0)
        store.record_retry("ec")
        store.record_429("groq")

        assert len(store.query_series("decision_ec")) == 1
        assert len(store.query_series("acceptance_ec")) == 1
        assert len(store.query_series("confidence_ec")) == 1
        assert len(store.query_series("latency_ec")) == 1
        assert len(store.query_series("retry_ec")) == 1
        assert len(store.query_series("rate_limit_429")) == 1

    def test_multiple_records_same_series(self):
        store = _make_store()
        for i in range(10):
            store.record_decision("ec", "INCLUDE" if i % 2 == 0 else "EXCLUDE")
        results = store.query_series("decision_ec")
        assert len(results) == 10


class TestTelemetryAggregator:
    def test_aggregate_decision_distribution_empty(self):
        store = _make_store()
        result = aggregate_decision_distribution("ec", WINDOW_10M, store)
        assert result["total_decisions"] == 0

    def test_aggregate_decision_distribution_with_data(self):
        store = _make_store()
        store.record_decision("ec", "INCLUDE")
        store.record_decision("ec", "INCLUDE")
        store.record_decision("ec", "EXCLUDE")

        result = aggregate_decision_distribution("ec", WINDOW_10M, store)
        assert result["total_decisions"] == 3
        assert result["counts"]["INCLUDE"] == 2
        assert result["counts"]["EXCLUDE"] == 1

    def test_aggregate_acceptance_rate(self):
        store = _make_store()
        store.record_decision("ec", "INCLUDE")
        store.record_decision("ec", "EXCLUDE")
        store.record_decision("ec", "INCLUDE")

        result = aggregate_acceptance_rate("ec", WINDOW_10M, store)
        assert result["total"] == 3
        assert result["acceptance_rate"] == round(2 / 3, 4)

    def test_aggregate_confidence_distribution(self):
        store = _make_store()
        store.record_confidence("ec", 0.5)
        store.record_confidence("ec", 0.7)
        store.record_confidence("ec", 0.9)

        result = aggregate_confidence_distribution("ec", WINDOW_10M, store)
        assert result["count"] == 3
        assert result["mean"] == 0.7
        assert result["p50"] == 0.7

    def test_aggregate_latency_percentiles(self):
        store = _make_store()
        for ms in [100, 200, 300, 400, 500]:
            store.record_latency("ec", ms)

        result = aggregate_latency("ec", WINDOW_10M, store)
        assert result["count"] == 5
        assert result["p50"] == 300.0
        assert 470 <= result["p95"] <= 510

    def test_aggregate_retry_rate(self):
        store = _make_store()
        for _ in range(5):
            store.record_decision("ec", "INCLUDE")
        for _ in range(2):
            store.record_retry("ec")

        result = aggregate_retry_rate("ec", WINDOW_10M, store)
        assert result["retries"] == 2
        assert result["decisions"] == 5
        assert result["retry_rate"] == 0.4

    def test_aggregate_429_rate(self):
        store = _make_store()
        store.record_429()
        store.record_429()
        store.record_429()

        result = aggregate_429_rate(WINDOW_10M, store)
        assert result["total_429"] == 3

    def test_aggregate_all(self):
        store = _make_store()
        store.record_decision("ec", "INCLUDE")
        store.record_confidence("ec", 0.8)
        store.record_latency("ec", 500.0)

        result = aggregate_all("ec", WINDOW_10M, store)
        assert "decision_distribution" in result
        assert "acceptance_rate" in result
        assert "confidence" in result
        assert "latency" in result
        assert "retry_rate" in result
        assert "rate_limit_429" in result

    def test_aggregate_all_windows(self):
        store = _make_store()
        store.record_decision("ec", "INCLUDE")

        result = aggregate_all_windows("ec", store)
        assert "1m" in result
        assert "10m" in result
        assert "1h" in result
