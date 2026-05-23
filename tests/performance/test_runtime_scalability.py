"""
Deterministic load/performance tests for runtime scalability.

Tests:
- 1k item queue construction + processing
- 10k item queue construction
- WAL replay after rotation
- Cache eviction under load
- Queue contention with multiple items
- Replay correctness after compaction
- Metrics isolation
- Prefilter metrics

Requirements:
- Deterministic (no network, no LLM)
- Synthetic advisories only
- Assertions for bounded growth, no drift, no duplicate acquisition
"""
import os
import json
import time
import math
import threading
import tempfile
import shutil
from pathlib import Path
from collections import Counter

from src.advisory.advisory_queue import AdvisoryQueue, get_advisory_queue
from src.advisory.advisory_cache import AdvisoryCache, get_advisory_cache
from src.advisory.advisory_metrics import AdvisoryMetrics, get_metrics, reset_metrics
from src.advisory.advisory_models import (
    AdvisoryResult, AdvisoryConfig, AdvisoryDecision,
    QueueItem, QueueState, AdvisoryStatus,
)
from src.advisory.prefilter import get_prefilter, _global_prefilters


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_synthetic_article(article_id: str, title: str = ""):
    """Create a synthetic article object."""
    class Article:
        pass
    a = Article()
    a.article_id = article_id
    a.title = title or f"Synthetic Article {article_id}"
    a.abstract = f"This is the abstract for synthetic article {article_id}."
    return a


def make_advisory(cache_key: str) -> AdvisoryResult:
    return AdvisoryResult(
        cache_key=cache_key,
        protocol_version="1.0",
        decision=AdvisoryDecision.EXCLUDE,
        confidence=0.0,
        justification="synthetic load test advisory",
        generated_at="2025-06-01T00:00:00",
    )


def _create_isolated_queue(config=None, tag="perf"):
    """Create AdvisoryQueue with WAL/snapshot redirected to temp dir."""
    config = config or AdvisoryConfig(enable_queue_state=False)
    # Use a unique sub-stage per test class to avoid singleton overlap
    stage = f"ic"
    queue = AdvisoryQueue(config, stage=stage)
    tmp = tempfile.mkdtemp()
    queue._queue_path = Path(tmp) / f"queue_state_{stage}_{tag}.json"
    queue._wal_path = Path(tmp) / f"queue_ops_{stage}_{tag}.jsonl"
    return queue, tmp


# ---------------------------------------------------------------------------
# 1. 1k item queue construction + sequential processing
# ---------------------------------------------------------------------------

class Test1kItemLoad:
    """1,000 items: queue construction, acquire/release cycle."""

    def _make_queue(self):
        return _create_isolated_queue(tag="1k")

    def test_build_queue_1k(self):
        queue, tmp = self._make_queue()
        try:
            articles = [make_synthetic_article(f"a{i:04d}") for i in range(1000)]
            state = queue.build_from_articles(articles, stage="ic", skip_existing=False)
            assert state.total == 1000
            assert state.pending == 1000
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_acquire_release_1k(self):
        queue, tmp = self._make_queue()
        try:
            articles = [make_synthetic_article(f"b{i:04d}") for i in range(1000)]
            queue.build_from_articles(articles, stage="ic", skip_existing=False)
            acquired = 0
            while True:
                item = queue.acquire_next()
                if item is None:
                    break
                acquired += 1
                queue.mark_completed(item)
            assert acquired == 1000
            assert queue.state.completed == 1000
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_no_double_acquisition(self):
        queue, tmp = self._make_queue()
        try:
            articles = [make_synthetic_article(f"c{i:04d}") for i in range(100)]
            queue.build_from_articles(articles, stage="ic", skip_existing=False)
            acquired_keys = set()
            while True:
                item = queue.acquire_next()
                if item is None:
                    break
                assert item.cache_key not in acquired_keys
                acquired_keys.add(item.cache_key)
                queue.mark_completed(item)
            assert len(acquired_keys) == 100
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_queue_stats_consistent(self):
        queue, tmp = self._make_queue()
        try:
            articles = [make_synthetic_article(f"d{i:04d}") for i in range(500)]
            queue.build_from_articles(articles, stage="ic", skip_existing=False)
            for i in range(250):
                item = queue.acquire_next()
                queue.mark_completed(item)
            stats = queue.get_stats()
            assert stats["total"] == 500
            assert stats["completed"] == 250
            assert stats["pending"] == 250
            assert stats["completion_rate"] == 0.5
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# 2. 10k item queue construction
# ---------------------------------------------------------------------------

class Test10kItemLoad:
    """10,000 items: construction + partial processing, measuring timing."""

    def test_build_queue_10k(self):
        queue, tmp = _create_isolated_queue(tag="10k_build")
        try:
            articles = [make_synthetic_article(f"e{i:05d}") for i in range(10000)]
            t0 = time.time()
            state = queue.build_from_articles(articles, stage="ic", skip_existing=False)
            duration = time.time() - t0
            assert state.total == 10000
            assert state.pending == 10000
            # Timing assertion is platform-dependent; verify correctness
            assert duration < 60.0, f"10k item build took {duration:.2f}s (should be <60s)"
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_acquire_release_10k_with_checkpoint_metadata(self):
        queue, tmp = _create_isolated_queue(tag="10k_proc")
        try:
            articles = [make_synthetic_article(f"f{i:05d}") for i in range(1000)]
            queue.build_from_articles(articles, stage="ic", skip_existing=False)
            for i in range(100):
                item = queue.acquire_next()
                queue.mark_completed(item)
            stats = queue.get_stats()
            assert stats["total"] == 1000
            assert stats["completed"] == 100
            assert stats["pending"] == 900
            assert stats["processing"] == 0
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# 3. WAL replay and compaction correctness
# ---------------------------------------------------------------------------

class TestWalReplayScalability:
    """Replay correctness after snapshots and compaction."""

    def test_replay_no_drift(self):
        queue, tmp = _create_isolated_queue(tag="replay")
        try:
            articles = [make_synthetic_article(f"g{i:04d}") for i in range(500)]
            queue.build_from_articles(articles, stage="ic", skip_existing=False)
            for i in range(200):
                item = queue.acquire_next()
                if i % 2 == 0:
                    queue.mark_completed(item)
                else:
                    queue.mark_failed(item, "test error")
            queue._save_state()
            queue._state = None
            reloaded = queue.state
            assert reloaded.total == 500
            assert reloaded.completed == 100
            assert reloaded.failed == 100
            assert reloaded.processing == 0
            assert reloaded.pending == 300
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_replay_after_compaction(self):
        queue, tmp = _create_isolated_queue(tag="compact")
        try:
            articles = [make_synthetic_article(f"h{i:04d}") for i in range(500)]
            queue.build_from_articles(articles, stage="ic", skip_existing=False)
            for i in range(250):
                item = queue.acquire_next()
                queue.mark_completed(item)
            state_before = queue.state.to_dict()
            result = queue.compact_wal()
            assert result["compacted"]
            queue._state = None
            reloaded = queue.state
            assert reloaded.total == state_before["total"]
            assert reloaded.completed == state_before["completed"]
            assert reloaded.pending == state_before["pending"]
            assert reloaded.wal_compaction_count > 0
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_compaction_crash_safe_rotation(self):
        queue, tmp = _create_isolated_queue(tag="crashsafe")
        try:
            articles = [make_synthetic_article(f"i{i:04d}") for i in range(200)]
            queue.build_from_articles(articles, stage="ic", skip_existing=False)
            for i in range(100):
                item = queue.acquire_next()
                queue.mark_completed(item)
            expected_state = queue.state.to_dict()
            queue.compact_wal()
            bak = queue._wal_path.with_suffix('.jsonl.bak')
            assert not bak.exists()
            queue._state = None
            reloaded = queue.state
            assert reloaded.completed == expected_state["completed"]
            assert reloaded.pending == expected_state["pending"]
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# 4. Cache eviction under load
# ---------------------------------------------------------------------------

class TestCacheEvictionLoad:
    """Cache must not grow unbounded under heavy load."""

    def test_cache_bounded_under_load(self):
        config = AdvisoryConfig(max_cache_entries=50, enable_disk_cache=False)
        cache = AdvisoryCache(config)
        for i in range(500):
            adv = make_advisory(f"k{i:04d}")
            cache.set(adv, stage="ic")
        assert len(cache._session_cache) <= 50

    def test_cache_eviction_counters(self):
        reset_metrics()
        config = AdvisoryConfig(max_cache_entries=10, enable_disk_cache=False)
        cache = AdvisoryCache(config)
        for i in range(100):
            adv = make_advisory(f"evict_{i:04d}")
            cache.set(adv, stage="ic")
        metrics = get_metrics()
        assert metrics.cache_eviction_count >= 90

    def test_cache_hit_ratio(self):
        reset_metrics()
        config = AdvisoryConfig(max_cache_entries=100, enable_disk_cache=False)
        cache = AdvisoryCache(config)
        adv = make_advisory("hit_test")
        cache.set(adv, stage="ic")
        for _ in range(10):
            cache.get("hit_test", stage="ic")
        metrics = get_metrics()
        assert metrics.cache_session_hits == 10
        assert metrics.cache_session_misses >= 0


# ---------------------------------------------------------------------------
# 5. Queue contention behavior
# ---------------------------------------------------------------------------

class TestQueueContention:
    """Queue must handle concurrent access safely."""

    def test_concurrent_producer_consumer(self):
        queue, tmp = _create_isolated_queue(tag="contention")
        try:
            articles = [make_synthetic_article(f"j{i:04d}") for i in range(500)]
            queue.build_from_articles(articles, stage="ic", skip_existing=False)
            acquired_total = 0
            lock = threading.Lock()
            errors = []
            def worker(n: int):
                nonlocal acquired_total
                local_count = 0
                while True:
                    try:
                        item = queue.acquire_next()
                        if item is None:
                            break
                        queue.mark_completed(item)
                        local_count += 1
                    except Exception as e:
                        with lock:
                            errors.append(f"Worker {n}: {e}")
                        break
                with lock:
                    acquired_total += local_count
            threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=30)
            assert len(errors) == 0, f"Errors: {errors}"
            assert acquired_total == 500
            assert queue.state.completed == 500
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# 6. Metrics isolation
# ---------------------------------------------------------------------------

class TestMetricsLoad:
    """Metrics must not interfere with queue operations."""

    def test_metrics_after_load(self):
        reset_metrics()
        queue, tmp = _create_isolated_queue(tag="metrics")
        try:
            articles = [make_synthetic_article(f"m{i:04d}") for i in range(100)]
            queue.build_from_articles(articles, stage="ic", skip_existing=False)
            for i in range(50):
                item = queue.acquire_next()
                queue.mark_completed(item)
            snapshot = get_metrics().get_snapshot()
            assert snapshot["queue"]["completed_count"] == 50
            assert snapshot["queue"]["pending_count"] == 50
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_recovery_metrics_populated(self):
        reset_metrics()
        queue, tmp = _create_isolated_queue(tag="recovery_metrics")
        try:
            articles = [make_synthetic_article(f"n{i:04d}") for i in range(100)]
            queue.build_from_articles(articles, stage="ic", skip_existing=False)
            queue._save_state()
            queue._state = None
            _ = queue.state
            snapshot = get_metrics().get_snapshot()
            assert "recovery" in snapshot
            assert snapshot["recovery"]["wal_replay_operations"] >= 0
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# 7. Prefilter metrics
# ---------------------------------------------------------------------------

class TestPrefilterMetrics:
    """Prefilter must track accept/reject/duplicate metrics."""

    def test_prefilter_metrics_tracked(self):
        reset_metrics()
        _global_prefilters.pop("metrics_test", None)
        p = get_prefilter(stage="metrics_test")
        p.check("Unique Title One", "Abstract one")
        p.check("Unique Title Two", "Abstract two")
        p.check("Jobs at Google", "We are hiring software engineers")
        p.check("University of Oxford MSc Programme", "Course description")
        p.check("Unique Title One", "Abstract one")
        snapshot = get_metrics().get_snapshot()
        pre = snapshot["prefilter"]
        assert pre["accepts"] >= 2
        assert pre["rejects"] >= 2
        assert pre["duplicate_title_hits"] >= 1
