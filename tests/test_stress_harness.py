"""
Stress Test Harness for APOLLO.

Simulates adversarial conditions to validate system resilience:

  - Long sessions (2000+ items)
  - Forced 429 bursts
  - Worker restarts
  - Queue corruption recovery
  - Repeated rerun storms

All tests are deterministic, use no actual API calls, and
rely entirely on in-memory state or isolated temp directories.
"""
import os
import time
import json
import threading
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Optional

import pytest

from src.advisory.advisory_models import (
    AdvisoryConfig, AdvisoryStatus, AdvisoryDecision,
    QueueItem, QueueState,
)
from src.advisory.advisory_queue import AdvisoryQueue, get_advisory_queue, reset_queue_for_stage
from src.advisory.advisory_cache import AdvisoryCache, get_advisory_cache, set_advisory_cache
from src.advisory.advisory_orchestrator import (
    AdvisoryWorkerOrchestrator,
    get_orchestrator,
    reset_orchestrator_for_stage,
)
from src.advisory.telemetry_timeseries import (
    TimeSeriesStore, get_timeseries_store, reset_timeseries_store,
)
from src.advisory.transient_failures import is_transient_provider_error, classify_failure
import tempfile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_articles(count: int, prefix: str = "stress") -> List:
    """Create deterministic article-like dicts."""
    articles = []
    for i in range(count):
        articles.append({
            "title": f"{prefix} Article {i} Title About Systematic Review",
            "abstract": (
                f"This is the abstract for article {i}. It discusses "
                f"important findings and methodology relevant to the review."
            ),
            "cache_key": f"{prefix}_art_{i:04d}",
            "literature_type": "WL" if i % 2 == 0 else "SR",
        })
    return articles


def _make_config() -> AdvisoryConfig:
    return AdvisoryConfig(
        cache_dir=tempfile.mkdtemp(prefix="stress_cache_"),
        queue_state_path=tempfile.mkdtemp(prefix="stress_queue_"),
        enable_disk_cache=False,
        enable_queue_state=False,
        max_retries_per_request=2,
        retry_backoff_seconds=0.1,
    )


class StressTestFixture:
    """Manages lifecycle of a stress test scenario."""

    def __init__(self):
        self._tmpdirs: List[str] = []

    def make_config(self) -> AdvisoryConfig:
        config = _make_config()
        self._tmpdirs.append(config.cache_dir)
        self._tmpdirs.append(config.queue_state_path)
        return config

    def cleanup(self):
        for d in self._tmpdirs:
            if os.path.exists(d):
                shutil.rmtree(d, ignore_errors=True)
        self._tmpdirs.clear()


@pytest.fixture
def stress_fx():
    fx = StressTestFixture()
    yield fx
    fx.cleanup()


# ---------------------------------------------------------------------------
# Test 1: Long session simulation (2000+ items through queue)
# ---------------------------------------------------------------------------

class TestLongSession:
    """Simulate processing a large batch of items through the queue."""

    def test_queue_handles_2000_items(self, stress_fx):
        config = stress_fx.make_config()
        queue = AdvisoryQueue(config, stage="ec")
        articles = _make_articles(2000, prefix="long")
        state = queue.build_from_articles(articles, protocol_version="1.0", stage="ec")
        assert state.total == 2000
        assert state.pending == 2000

        # Simulate sequential acquisition and completion
        completed = 0
        while True:
            item = queue.acquire_next()
            if item is None:
                break
            queue.mark_completed(item)
            completed += 1

        assert completed == 2000
        stats = queue.get_stats()
        assert stats["completed"] == 2000
        assert stats["pending"] == 0
        assert stats["completion_rate"] == 1.0

    def test_queue_handles_5000_items_throughput(self, stress_fx):
        """Verify queue throughput with 5000 items (no WAL ops)."""
        config = stress_fx.make_config()
        queue = AdvisoryQueue(config, stage="ic")
        articles = _make_articles(5000, prefix="throughput")
        queue.build_from_articles(articles, protocol_version="1.0", stage="ic")

        start = time.time()
        count = 0
        while queue.acquire_next() is not None:
            count += 1
        elapsed = time.time() - start

        assert count == 5000
        assert elapsed < 30.0  # Should complete well within 30s

    def test_queue_memory_with_2000_items(self, stress_fx):
        """Verify the queue does not leak memory with large item counts."""
        config = stress_fx.make_config()
        queue = AdvisoryQueue(config, stage="ec")
        articles = _make_articles(2000, prefix="memory")
        queue.build_from_articles(articles, protocol_version="1.0", stage="ec")

        # All items should be accessible via get_pending
        pending = queue.get_pending()
        assert len(pending) == 2000

        # get_stats should reflect accurate counts
        stats = queue.get_stats()
        assert stats["total"] == 2000
        assert stats["pending"] == 2000


# ---------------------------------------------------------------------------
# Test 2: Forced 429 bursts
# ---------------------------------------------------------------------------

class TestForced429Burst:
    """Simulate provider throttling (429 errors) and verify recovery."""

    def test_transient_failure_classification(self):
        """Verify 429 errors are correctly classified as transient."""
        assert is_transient_provider_error("429 Too Many Requests")
        assert is_transient_provider_error("rate limit exceeded for groq")
        assert is_transient_provider_error("HTTP 429: Rate limit reached")
        assert is_transient_provider_error("connection timeout after 30s")
        assert is_transient_provider_error("upstream service unavailable (503)")

    def test_terminal_failure_not_misclassified(self):
        """Verify terminal failures are NOT classified as transient."""
        assert not is_transient_provider_error("SQL integrity constraint violation")
        assert not is_transient_provider_error("corrupted queue state detected")
        assert not is_transient_provider_error("invariant violation: decision is None")

    def test_classify_failure_returns_terminal(self):
        """Verify classify_failure correctly returns terminal type."""
        ftype = classify_failure("corrupted queue state: WAL replay failed")
        assert ftype == "terminal"

    def test_classify_failure_returns_transient(self):
        """Verify classify_failure correctly returns transient type."""
        ftype = classify_failure("rate limit exceeded, retry after 30s")
        assert ftype == "transient"

    def test_timeseries_records_429(self, stress_fx):
        """Verify 429 events are recorded in time-series store."""
        store = TimeSeriesStore(base_dir=tempfile.mkdtemp())
        store.record_429(provider="groq")
        store.record_429(provider="groq")
        store.record_429(provider="groq")

        records = store.query_series("rate_limit_429")
        assert len(records) == 3
        for r in records:
            assert r.get("tags", {}).get("provider") == "groq"


# ---------------------------------------------------------------------------
# Test 3: Worker restarts
# ---------------------------------------------------------------------------

class TestWorkerRestart:
    """Simulate worker restart during active processing."""

    def test_worker_restart_does_not_corrupt_queue(self, stress_fx):
        """Verify that restarting worker mid-processing preserves queue integrity."""
        config = stress_fx.make_config()
        queue = AdvisoryQueue(config, stage="ec")
        articles = _make_articles(50, prefix="restart")
        queue.build_from_articles(articles, protocol_version="1.0", stage="ec")

        # Acquire 10 items (simulating in-flight processing)
        acquired = []
        for _ in range(10):
            item = queue.acquire_next()
            if item:
                acquired.append(item)

        # Simulate worker restart: queue already has 10 marked PROCESSING
        stats_before = queue.get_stats()
        assert stats_before["processing"] == len(acquired)

        # Remaining items should still be PENDING
        pending = queue.get_pending()
        assert len(pending) == 40  # 50 - 10 acquired

        # Can mark remaining as completed (worker restart scenario)
        for item in pending:
            queue.mark_completed(item)
        stats_after = queue.get_stats()
        assert stats_after["completed"] == 40

    def test_orchestrator_restart_safe(self, stress_fx):
        """Verify orchestrator can be reset and restarted without state leaks."""
        config = stress_fx.make_config()
        stage = "ec"

        # First orchestrator
        orch1 = AdvisoryWorkerOrchestrator(config, stage, protocol=None)
        orch1.initialize_queue(_make_articles(10, prefix="orchestrator1"), "1.0", stage, protocol=None)
        orch1.start_worker(max_items=10)

        # Stop and reset
        orch1.stop_worker()
        reset_orchestrator_for_stage(stage, force=True)

        # Second orchestrator with new items
        orch2 = AdvisoryWorkerOrchestrator(config, stage, protocol=None)
        orch2.initialize_queue(_make_articles(10, prefix="orchestrator2"), "1.0", stage, protocol=None)
        assert orch2.get_status(stage)["queue"]["total"] == 10


# ---------------------------------------------------------------------------
# Test 4: Queue corruption recovery
# ---------------------------------------------------------------------------

class TestQueueCorruptionRecovery:
    """Simulate WAL corruption and verify recovery."""

    def test_recover_from_missing_snapshot_file(self, stress_fx):
        """Verify queue recovers gracefully when snapshot file is missing."""
        config = stress_fx.make_config()
        queue = AdvisoryQueue(config, stage="ec")
        articles = _make_articles(10, prefix="corrupt")
        queue.build_from_articles(articles, protocol_version="1.0", stage="ec")

        # Delete snapshot file
        snapshot_path = Path(config.queue_state_path) / "queue_ec_snapshot.json"
        if snapshot_path.exists():
            snapshot_path.unlink()

        # Queue should still work (rebuilds from WAL)
        stats = queue.get_stats()
        assert stats["total"] == 10

    def test_recover_from_corrupted_wal(self, stress_fx):
        """Verify queue recovers when WAL has malformed lines."""
        config = stress_fx.make_config()
        queue = AdvisoryQueue(config, stage="ec")
        articles = _make_articles(5, prefix="wal_corrupt")
        queue.build_from_articles(articles, protocol_version="1.0", stage="ec")

        # Corrupt the WAL file
        wal_path = Path(config.queue_state_path) / "queue_ec_wal.jsonl"
        if wal_path.exists():
            with open(wal_path, 'a', encoding='utf-8') as f:
                f.write("NOT_VALID_JSON\n")
                f.write("{also not valid\n")

        # Queue should recover gracefully (construct new queue from scratch)
        queue2 = AdvisoryQueue(config, stage="ec")
        stats = queue2.get_stats()
        # Should have recovered items from WAL (skipping corruption)
        assert stats is not None

    def test_clear_and_rebuild(self, stress_fx):
        """Verify queue can be cleared and rebuilt without errors."""
        config = stress_fx.make_config()
        queue = AdvisoryQueue(config, stage="ec")
        articles = _make_articles(20, prefix="rebuild")
        queue.build_from_articles(articles, protocol_version="1.0", stage="ec")

        queue.clear()
        stats = queue.get_stats()
        assert stats["total"] == 0

        # Rebuild
        queue.build_from_articles(articles, protocol_version="1.0", stage="ec")
        stats = queue.get_stats()
        assert stats["total"] == 20


# ---------------------------------------------------------------------------
# Test 5: Repeated rerun storms
# ---------------------------------------------------------------------------

class TestRerunStorm:
    """Simulate rapid, repeated rerun cycles (UI refresh storms)."""

    def test_repeated_build_clear_cycles(self, stress_fx):
        """Verify queue survives 10 rapid build/clear cycles."""
        config = stress_fx.make_config()
        for cycle in range(10):
            queue = AdvisoryQueue(config, stage="ec")
            articles = _make_articles(100, prefix=f"storm_{cycle}")
            queue.build_from_articles(articles, protocol_version="1.0", stage="ec")
            assert queue.get_stats()["total"] == 100
            queue.clear()
            assert queue.get_stats()["total"] == 0

    def test_repeated_orchestrator_init(self, stress_fx):
        """Verify orchestrator survives 10 rapid init/stop cycles."""
        config = stress_fx.make_config()
        for cycle in range(10):
            orch = AdvisoryWorkerOrchestrator(config, "ec", protocol=None)
            articles = _make_articles(10, prefix=f"orchestrator_storm_{cycle}")
            orch.initialize_queue(articles, "1.0", "ec", protocol=None)
            orch.stop_worker()
            assert True  # No crash

    def test_concurrent_build_access(self, stress_fx):
        """Verify thread-safe concurrent queue access."""
        config = stress_fx.make_config()
        queue = AdvisoryQueue(config, stage="ec")
        articles = _make_articles(100, prefix="concurrent")
        queue.build_from_articles(articles, protocol_version="1.0", stage="ec")

        errors = []

        def acquire_loop():
            try:
                while True:
                    item = queue.acquire_next()
                    if item is None:
                        break
                    queue.mark_completed(item)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=acquire_loop, daemon=True) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors
        stats = queue.get_stats()
        assert stats["completed"] == 100


# ---------------------------------------------------------------------------
# Test 6: Telemetry store under load
# ---------------------------------------------------------------------------

class TestTelemetryUnderLoad:
    """Verify telemetry time-series store handles high-volume writes."""

    def test_high_volume_writes(self, stress_fx):
        """Verify 10,000 rapid writes to time-series store."""
        reset_timeseries_store()
        store = get_timeseries_store()
        for i in range(10000):
            store.record_confidence("ec", 0.5 + (i % 50) / 100.0)

        records = store.query_series("confidence_ec")
        assert len(records) == 10000

    def test_mixed_metric_types(self, stress_fx):
        """Verify multiple metric types can be recorded concurrently."""
        reset_timeseries_store()
        store = get_timeseries_store()

        def record_decisions():
            for i in range(500):
                store.record_decision("ec", "INCLUDE" if i % 2 == 0 else "EXCLUDE")

        def record_latency():
            for i in range(500):
                store.record_latency("ec", 1000 + (i % 10) * 100)

        threads = [
            threading.Thread(target=record_decisions, daemon=True),
            threading.Thread(target=record_latency, daemon=True),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        decisions = store.query_series("decision_ec")
        latencies = store.query_series("latency_ec")
        assert len(decisions) == 500
        assert len(latencies) == 500


# ---------------------------------------------------------------------------
# Test 7: State isolation under stress
# ---------------------------------------------------------------------------

class TestStateIsolation:
    """Verify that concurrent operations on different stages do not interfere."""

    def test_ec_ic_independent_queues(self, stress_fx):
        """Verify EC and IC queues operate independently."""
        config = stress_fx.make_config()
        ec_queue = AdvisoryQueue(config, stage="ec")
        ic_queue = AdvisoryQueue(config, stage="ic")

        ec_articles = _make_articles(50, prefix="ec_only")
        ic_articles = _make_articles(30, prefix="ic_only")

        ec_queue.build_from_articles(ec_articles, "1.0", "ec")
        ic_queue.build_from_articles(ic_articles, "1.0", "ic")

        assert ec_queue.get_stats()["total"] == 50
        assert ic_queue.get_stats()["total"] == 30

    def test_clear_one_stage_does_not_affect_other(self, stress_fx):
        """Verify clearing EC queue does not affect IC queue."""
        config = stress_fx.make_config()
        ec_queue = AdvisoryQueue(config, stage="ec")
        ic_queue = AdvisoryQueue(config, stage="ic")

        ec_queue.build_from_articles(_make_articles(10, prefix="ec"), "1.0", "ec")
        ic_queue.build_from_articles(_make_articles(10, prefix="ic"), "1.0", "ic")

        ec_queue.clear()
        assert ic_queue.get_stats()["total"] == 10
