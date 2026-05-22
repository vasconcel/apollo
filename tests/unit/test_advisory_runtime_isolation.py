"""
Tests for advisory runtime isolation.

Ensures:
1. Stage-scoped prefilter singleton (EC vs IC do not share dedup state)
2. Prefilter reset on pipeline init (session-scoped isolation)
3. Graceful worker stop via stop_event (no dangling threads)
4. Bounded cache eviction (LRU, no unbounded growth)
5. O(1) telemetry counters (session_hits/misses/sets tracked without iteration)
6. Queue crash recovery (stale PROCESSING items requeued to PENDING)
"""
import os
import json
import time
import threading
import tempfile
from pathlib import Path
from collections import OrderedDict

from src.advisory.prefilter import get_prefilter, PrefilterEngine, _global_prefilters, _prefilter_lock
from src.advisory.advisory_cache import AdvisoryCache, get_advisory_cache, _mem_snapshot_cache
from src.advisory.advisory_queue import AdvisoryQueue
from src.advisory.advisory_orchestrator import AdvisoryWorkerOrchestrator
from src.advisory.advisory_models import (
    AdvisoryResult, AdvisoryConfig, AdvisoryDecision,
    QueueItem, QueueState, AdvisoryStatus,
)
from src.advisory.advisory_worker import AdvisoryWorker


# ---------------------------------------------------------------------------
# 1. Stage-scoped prefilter singleton
# ---------------------------------------------------------------------------

class TestPrefilterStageIsolation:
    """Each stage must have its own dedup context."""

    def setup_method(self):
        _global_prefilters.clear()

    def test_different_stages_get_different_instances(self):
        ec = get_prefilter(stage="ec")
        ic = get_prefilter(stage="ic")
        qc = get_prefilter(stage="qc")
        assert ec is not ic
        assert ec is not qc
        assert ic is not qc

    def test_same_stage_returns_same_instance(self):
        a = get_prefilter(stage="ic")
        b = get_prefilter(stage="ic")
        assert a is b

    def test_dedup_context_not_shared_across_stages(self):
        ec = get_prefilter(stage="ec")
        ic = get_prefilter(stage="ic")
        ec.check("Machine Learning for Beginners", "")
        ec.check("Advanced Python Programming", "")
        assert len(ec._seen_titles) == 2
        assert len(ic._seen_titles) == 0

    def test_empty_stage_default(self):
        default = get_prefilter()
        assert default._stage == ""

    def test_reset_clears_dedup_state(self):
        p = get_prefilter(stage="ic")
        p.check("Duplicate Title", "")
        assert len(p._seen_titles) == 1
        p.reset()
        assert len(p._seen_titles) == 0


# ---------------------------------------------------------------------------
# 2. Prefilter dedup isolation across pipeline inits
# ---------------------------------------------------------------------------

class TestPrefilterPipelineReset:
    """Pipeline initialization must reset prefilter dedup state."""

    def test_orchestrator_initialize_queue_resets_prefilter(self):
        p = get_prefilter(stage="ic")
        p.check("Some Title", "")
        assert len(p._seen_titles) == 1

        orch = AdvisoryWorkerOrchestrator(stage="ic")
        orch.initialize_queue([], stage="ic")

        assert len(p._seen_titles) == 0

    def test_reset_does_not_affect_other_stages(self):
        ic_pre = get_prefilter(stage="ic")
        ec_pre = get_prefilter(stage="ec")
        ic_pre.check("IC Title", "")
        ec_pre.check("EC Title", "")
        assert len(ic_pre._seen_titles) == 1
        assert len(ec_pre._seen_titles) == 1

        orch = AdvisoryWorkerOrchestrator(stage="ic")
        orch.initialize_queue([], stage="ic")

        assert len(ic_pre._seen_titles) == 0
        assert len(ec_pre._seen_titles) == 1  # untouched


# ---------------------------------------------------------------------------
# 3. Graceful worker stop via stop_event
# ---------------------------------------------------------------------------

class TestWorkerStopEvent:
    """Worker must stop promptly when stop_event is set."""

    def test_stop_event_breaks_process_loop(self):
        worker = AdvisoryWorker()
        queue = AdvisoryQueue(AdvisoryConfig(enable_queue_state=False), stage="ic")
        queue._state = QueueState(
            total=2, pending=2, processing=0, completed=0, failed=0,
            items=[
                QueueItem(cache_key="k1", protocol_version="1.0", article_id="a1", stage="ic", status=AdvisoryStatus.PENDING, priority=0, title="T1", abstract="A1"),
                QueueItem(cache_key="k2", protocol_version="1.0", article_id="a2", stage="ic", status=AdvisoryStatus.PENDING, priority=1, title="T2", abstract="A2"),
            ],
        )

        stop_event = threading.Event()

        def delayed_stop():
            time.sleep(0.05)
            stop_event.set()

        t = threading.Thread(target=delayed_stop)
        t.start()

        result = worker.process_all(stage="ic", stop_event=stop_event)
        t.join()

        # Should have stopped early (at most 1 item processed)
        assert result["processed"] < 2

    def test_stop_event_causes_idle_status(self):
        worker = AdvisoryWorker()
        queue = AdvisoryWorker()
        stop_event = threading.Event()
        stop_event.set()
        result = worker.process_all(stage="ic", stop_event=stop_event)
        assert result["status"] == "IDLE" or result["status"] == "PAUSED"


# ---------------------------------------------------------------------------
# 4. Bounded cache with LRU eviction
# ---------------------------------------------------------------------------

class TestBoundedCacheLRU:
    """Cache must evict oldest entries when over max_cache_entries."""

    def make_advisory(self, key: str) -> AdvisoryResult:
        return AdvisoryResult(
            cache_key=key,
            protocol_version="1.0",
            decision=AdvisoryDecision.EXCLUDE,
            confidence=0.0,
            justification="test",
            generated_at="2025-01-01T00:00:00",
        )

    def test_eviction_removes_oldest(self):
        config = AdvisoryConfig(max_cache_entries=3, enable_disk_cache=False)
        cache = AdvisoryCache(config)

        a1 = self.make_advisory("k1")
        a2 = self.make_advisory("k2")
        a3 = self.make_advisory("k3")
        a4 = self.make_advisory("k4")

        cache.set(a1, stage="ic")
        cache.set(a2, stage="ic")
        cache.set(a3, stage="ic")
        assert len(cache._session_cache) == 3

        cache.set(a4, stage="ic")
        assert len(cache._session_cache) == 3
        # k1 (oldest) should be evicted
        session_key_k1 = cache._session_key("k1", "1.0", "ic")
        session_key_k4 = cache._session_key("k4", "1.0", "ic")
        assert session_key_k1 not in cache._session_cache
        assert session_key_k4 in cache._session_cache

    def test_get_bumps_lru_position(self):
        config = AdvisoryConfig(max_cache_entries=3, enable_disk_cache=False)
        cache = AdvisoryCache(config)

        a1 = self.make_advisory("k1")
        a2 = self.make_advisory("k2")
        a3 = self.make_advisory("k3")

        cache.set(a1, stage="ic")
        cache.set(a2, stage="ic")
        cache.set(a3, stage="ic")

        # Access k1 (oldest), making it most recent
        session_key_k1 = cache._session_key("k1", "1.0", "ic")
        cache.get("k1", stage="ic")

        # Now add k4; should evict k2 (now oldest), not k1
        a4 = self.make_advisory("k4")
        cache.set(a4, stage="ic")

        session_key_k2 = cache._session_key("k2", "1.0", "ic")
        assert session_key_k1 in cache._session_cache  # k1 was bumped
        assert session_key_k2 not in cache._session_cache  # k2 was evicted

    def test_no_eviction_below_limit(self):
        config = AdvisoryConfig(max_cache_entries=100, enable_disk_cache=False)
        cache = AdvisoryCache(config)
        for i in range(50):
            adv = self.make_advisory(f"k{i}")
            cache.set(adv, stage="ic")
        assert len(cache._session_cache) == 50


# ---------------------------------------------------------------------------
# 5. O(1) telemetry counters
# ---------------------------------------------------------------------------

class TestTelemetryCounters:
    """Cache must maintain O(1) hit/miss/set counters."""

    def make_advisory(self, key: str) -> AdvisoryResult:
        return AdvisoryResult(
            cache_key=key,
            protocol_version="1.0",
            decision=AdvisoryDecision.EXCLUDE,
            confidence=0.0,
            justification="test",
            generated_at="2025-01-01T00:00:00",
        )

    def test_session_hits_increment_on_get(self):
        config = AdvisoryConfig(enable_disk_cache=False)
        cache = AdvisoryCache(config)
        adv = self.make_advisory("k1")
        cache.set(adv, stage="ic")

        assert cache._session_hits == 0
        cache.get("k1", stage="ic")
        assert cache._session_hits == 1
        cache.get("k1", stage="ic")
        assert cache._session_hits == 2

    def test_session_misses_increment_on_miss(self):
        config = AdvisoryConfig(enable_disk_cache=False)
        cache = AdvisoryCache(config)
        cache.get("nonexistent", stage="ic")
        assert cache._session_misses == 1

    def test_session_sets_increment_on_set(self):
        config = AdvisoryConfig(enable_disk_cache=False)
        cache = AdvisoryCache(config)
        adv = self.make_advisory("k1")
        cache.set(adv, stage="ic")
        assert cache._session_sets == 1
        cache.set(adv, stage="ic")
        assert cache._session_sets == 2

    def test_get_cache_stats_includes_counters(self):
        config = AdvisoryConfig(enable_disk_cache=False)
        cache = AdvisoryCache(config)
        adv = self.make_advisory("k1")
        cache.set(adv, stage="ic")
        cache.get("k1", stage="ic")
        cache.get("nonexistent", stage="ic")

        stats = cache.get_cache_stats()
        assert stats["session_hits"] == 1
        assert stats["session_misses"] == 1
        assert stats["session_sets"] == 1


# ---------------------------------------------------------------------------
# 6. Queue crash recovery — stale PROCESSING requeued to PENDING
# ---------------------------------------------------------------------------

class TestQueueCrashRecovery:
    """Stale PROCESSING items must be requeued to PENDING on load."""

    def test_requeue_stale_processing_items(self):
        config = AdvisoryConfig(enable_queue_state=False)
        queue = AdvisoryQueue(config, stage="ic")
        queue._state = QueueState(
            total=2, pending=0, processing=2, completed=0, failed=0,
            items=[
                QueueItem(
                    cache_key="k1", protocol_version="1.0", article_id="a1",
                    stage="ic", status=AdvisoryStatus.PROCESSING,
                    priority=0, started_at="2025-01-01T00:00:00",
                ),
                QueueItem(
                    cache_key="k2", protocol_version="1.0", article_id="a2",
                    stage="ic", status=AdvisoryStatus.PROCESSING,
                    priority=1, started_at="2025-01-01T00:00:00",
                ),
            ],
        )

        # Simulate _load_state recovery path
        queue._requeue_stale_processing(queue._state)

        assert queue.state.pending == 2
        assert queue.state.processing == 0
        for item in queue.state.items:
            assert item.status == AdvisoryStatus.PENDING
            assert item.started_at is None

    def test_completed_items_not_affected(self):
        config = AdvisoryConfig(enable_queue_state=False)
        queue = AdvisoryQueue(config, stage="ic")
        queue._state = QueueState(
            total=1, pending=0, processing=0, completed=1, failed=0,
            items=[
                QueueItem(
                    cache_key="k1", protocol_version="1.0", article_id="a1",
                    stage="ic", status=AdvisoryStatus.COMPLETED, priority=0,
                ),
            ],
        )

        queue._requeue_stale_processing(queue._state)

        assert queue.state.completed == 1
        assert queue.state.processing == 0
        assert queue.state.pending == 0

    def test_requeue_handles_empty_items(self):
        config = AdvisoryConfig(enable_queue_state=False)
        queue = AdvisoryQueue(config, stage="ic")
        queue._state = QueueState()

        queue._requeue_stale_processing(queue._state)

        assert queue.state.pending == 0
        assert queue.state.processing == 0
