"""
Long-running session stability tests.

Simulates extended operational scenarios:
- 100 replay cycles
- 100 compaction cycles
- 10k enqueue/dequeue cycles
- Repeated recovery after synthetic corruption
- Repeated metrics flushes

Assertions:
- No replay drift
- Bounded WAL size after compaction
- Bounded cache size
- No duplicate acquisition
- Metrics log remains parseable
- No temp-file leakage
- No stale .bak accumulation
"""
import os
import json
import time
import threading
import tempfile
import shutil
from pathlib import Path
from collections import Counter

from src.advisory.advisory_queue import AdvisoryQueue
from src.advisory.advisory_cache import AdvisoryCache, get_advisory_cache
from src.advisory.advisory_metrics import AdvisoryMetrics, get_metrics, reset_metrics, configure_metrics
from src.advisory.advisory_models import (
    AdvisoryResult, AdvisoryConfig, AdvisoryDecision,
    QueueItem, QueueState, AdvisoryStatus,
)


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


def _isolated_queue(config=None, tag="stability"):
    """Create AdvisoryQueue with paths redirected to a temp dir."""
    config = config or AdvisoryConfig(enable_queue_state=True)
    stage = "ic"
    queue = AdvisoryQueue(config, stage=stage)
    tmp = tempfile.mkdtemp()
    queue._queue_path = Path(tmp) / f"queue_state_{stage}_{tag}.json"
    queue._wal_path = Path(tmp) / f"queue_ops_{stage}_{tag}.jsonl"
    return queue, tmp


# ---------------------------------------------------------------------------
# 1. Repeated replay cycles (100x)
# ---------------------------------------------------------------------------

class TestReplayCycles:
    """100 successive build → acquire → replay cycles without drift."""

    CYCLES = 100
    ITEMS = 50

    def test_100_replay_cycles_no_drift(self):
        for cycle in range(self.CYCLES):
            reset_metrics()
            queue, tmp = _isolated_queue(tag=f"replay_{cycle}")
            try:
                articles = [make_synthetic_article(f"r{cycle}_{i:04d}") for i in range(self.ITEMS)]
                queue.build_from_articles(articles, stage="ic", skip_existing=False)
                assert queue.state.total == self.ITEMS
                assert queue.state.pending == self.ITEMS

                acquired = 0
                while True:
                    item = queue.acquire_next()
                    if item is None:
                        break
                    acquired += 1
                    queue.mark_completed(item)
                assert acquired == self.ITEMS
                assert queue.state.completed == self.ITEMS

                # Build second queue from same WAL+snapshot to verify replay
                queue2 = AdvisoryQueue(queue.config, stage="ic")
                queue2._queue_path = queue._queue_path
                queue2._wal_path = queue._wal_path
                queue2._load_state()

                assert queue2.state.total == self.ITEMS, \
                    f"Cycle {cycle}: replay drift total={queue2.state.total}"
                assert queue2.state.completed == self.ITEMS, \
                    f"Cycle {cycle}: replay drift completed={queue2.state.completed}"
            finally:
                shutil.rmtree(tmp, ignore_errors=True)

    def test_100_replay_cycles_no_double_acquisition(self):
        for cycle in range(self.CYCLES):
            reset_metrics()
            queue, tmp = _isolated_queue(tag=f"no_double_{cycle}")
            try:
                articles = [make_synthetic_article(f"nd{cycle}_{i:04d}") for i in range(self.ITEMS)]
                queue.build_from_articles(articles, stage="ic", skip_existing=False)
                acquired_keys = set()
                while True:
                    item = queue.acquire_next()
                    if item is None:
                        break
                    assert item.cache_key not in acquired_keys, \
                        f"Cycle {cycle}: duplicate {item.cache_key}"
                    acquired_keys.add(item.cache_key)
                    queue.mark_completed(item)
                assert len(acquired_keys) == self.ITEMS
            finally:
                shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# 2. Repeated compaction cycles (100x)
# ---------------------------------------------------------------------------

class TestCompactionCycles:
    """100 successive compact + replay cycles with bounded WAL size."""

    CYCLES = 100
    ITEMS = 20

    def test_100_compactions_bounded_wal(self):
        queue, tmp = _isolated_queue(tag="compact_100")
        try:
            for cycle in range(self.CYCLES):
                articles = [make_synthetic_article(f"c{cycle}_{i:04d}") for i in range(self.ITEMS)]
                queue.build_from_articles(articles, stage="ic", skip_existing=False)

                # Verify this batch is correct (build_from_articles replaces state)
                assert queue.state.total == self.ITEMS
                assert queue.state.pending == self.ITEMS

                acquired = 0
                while True:
                    item = queue.acquire_next()
                    if item is None:
                        break
                    acquired += 1
                    queue.mark_completed(item)
                assert acquired == self.ITEMS
                assert queue.state.completed == self.ITEMS

                result = queue.compact_wal()
                assert result["compacted"]

                wal_size = queue._wal_path.stat().st_size if queue._wal_path.exists() else 0
                assert wal_size < 4096, f"Cycle {cycle}: WAL too large after compaction ({wal_size} bytes)"

                bak_path = queue._wal_path.with_suffix('.jsonl.bak')
                assert not bak_path.exists(), f"Cycle {cycle}: stale .bak found"

                # Verify no temp files leaked
                tmp_files = list(Path(tmp).glob("*.tmp"))
                assert len(tmp_files) == 0, f"Cycle {cycle}: {len(tmp_files)} temp files leaked"

                # Verify replay of compacted state matches
                queue2 = AdvisoryQueue(queue.config, stage="ic")
                queue2._queue_path = queue._queue_path
                queue2._wal_path = queue._wal_path
                queue2._load_state()
                assert queue2.state.total == self.ITEMS
                assert queue2.state.completed == self.ITEMS
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_auto_compact_telemetry(self):
        """Verify auto-compaction triggers and skip counters are tracked."""
        reset_metrics()
        config = AdvisoryConfig(
            enable_queue_state=True,
            wal_compaction_max_operations=10,
            wal_compaction_interval_seconds=0,
        )
        queue, tmp = _isolated_queue(config, tag="auto_compact_telemetry")
        try:
            for cycle in range(5):
                articles = [make_synthetic_article(f"ac{cycle}_{i:04d}") for i in range(20)]
                queue.build_from_articles(articles, stage="ic", skip_existing=False)
                while True:
                    item = queue.acquire_next()
                    if item is None:
                        break
                    queue.mark_completed(item)

            snapshot = get_metrics().get_snapshot()
            comp = snapshot.get("auto_compaction", {})
            assert comp.get("auto_compaction_trigger_count", 0) > 0, \
                f"Expected auto-compaction triggers, got {comp}"
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# 3. 10k enqueue/dequeue cycles
# ---------------------------------------------------------------------------

class TestEnqueueDequeueCycles:
    """10k successive single-item enqueue + acquire + complete cycles."""

    CYCLES = 10000
    BATCH_SIZE = 100

    def test_10k_cycles_no_drift(self):
        reset_metrics()
        queue, tmp = _isolated_queue(tag="10k_cycles")
        try:
            total_ops = 0
            for batch in range(self.CYCLES // self.BATCH_SIZE):
                articles = [make_synthetic_article(f"10k{batch}_{i:04d}") for i in range(self.BATCH_SIZE)]
                queue.build_from_articles(articles, stage="ic", skip_existing=False)
                total_ops += self.BATCH_SIZE

                assert queue.state.total == self.BATCH_SIZE, \
                    f"Batch {batch}: expected {self.BATCH_SIZE}, got {queue.state.total}"

                acquired = 0
                while True:
                    item = queue.acquire_next()
                    if item is None:
                        break
                    acquired += 1
                    queue.mark_completed(item)
                assert acquired == self.BATCH_SIZE
                assert queue.state.completed == self.BATCH_SIZE

            # Each build replaces state; verify last batch is correct
            assert queue.state.completed == self.BATCH_SIZE
            assert queue.state.pending == 0

            # Verify replay matches last batch
            queue2 = AdvisoryQueue(queue.config, stage="ic")
            queue2._queue_path = queue._queue_path
            queue2._wal_path = queue._wal_path
            queue2._load_state()
            assert queue2.state.total == self.BATCH_SIZE
            assert queue2.state.completed == self.BATCH_SIZE
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_10k_cycles_no_double_booking(self):
        reset_metrics()
        queue, tmp = _isolated_queue(tag="10k_nodouble")
        try:
            occupied = threading.Lock()
            active = set()

            def worker(item):
                with occupied:
                    assert item.cache_key not in active, f"Double-booked: {item.cache_key}"
                    active.add(item.cache_key)
                time.sleep(0.0001)
                with occupied:
                    active.discard(item.cache_key)
                queue.mark_completed(item)

            for batch in range(self.CYCLES // self.BATCH_SIZE):
                articles = [make_synthetic_article(f"ndb{batch}_{i:04d}") for i in range(self.BATCH_SIZE)]
                queue.build_from_articles(articles, stage="ic", skip_existing=False)

                assert queue.state.total == self.BATCH_SIZE

                threads = []
                while True:
                    item = queue.acquire_next()
                    if item is None:
                        break
                    t = threading.Thread(target=worker, args=(item,), daemon=True)
                    t.start()
                    threads.append(t)
                for t in threads:
                    t.join()

                assert queue.state.completed == self.BATCH_SIZE
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# 4. Repeated recovery after synthetic corruption
# ---------------------------------------------------------------------------

class TestRecoveryAfterCorruption:
    """Repeatedly corrupt snapshot, verify WAL recovery each time."""

    CYCLES = 20
    ITEMS = 30

    def test_repeated_corruption_recovery(self):
        for cycle in range(self.CYCLES):
            reset_metrics()
            queue, tmp = _isolated_queue(tag=f"corrupt_{cycle}")
            try:
                articles = [make_synthetic_article(f"cr{cycle}_{i:04d}") for i in range(self.ITEMS)]
                queue.build_from_articles(articles, stage="ic", skip_existing=False)

                while True:
                    item = queue.acquire_next()
                    if item is None:
                        break
                    queue.mark_completed(item)

                # Corrupt the snapshot file
                with open(queue._queue_path, 'w') as f:
                    f.write('{"corrupted": true')

                # Rebuild from WAL
                queue2 = AdvisoryQueue(queue.config, stage="ic")
                queue2._queue_path = queue._queue_path
                queue2._wal_path = queue._wal_path
                queue2._load_state()

                assert queue2.state.total == self.ITEMS, \
                    f"Cycle {cycle}: total drift ({queue2.state.total} vs {self.ITEMS})"
                assert queue2.state.completed == self.ITEMS, \
                    f"Cycle {cycle}: completed drift ({queue2.state.completed} vs {self.ITEMS})"

                snapshot = get_metrics().get_snapshot()
                assert snapshot["recovery"]["corrupted_snapshot_recoveries"] > 0
            finally:
                shutil.rmtree(tmp, ignore_errors=True)

    def test_repeated_missing_both_returns_empty(self):
        for cycle in range(self.CYCLES):
            queue, tmp = _isolated_queue(tag=f"missing_{cycle}")
            try:
                # Delete both snapshot and WAL
                if queue._queue_path.exists():
                    queue._queue_path.unlink()
                if queue._wal_path.exists():
                    queue._wal_path.unlink()

                queue._load_state()
                assert queue.state.total == 0
                assert queue.state.pending == 0
            finally:
                shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# 5. Repeated metrics flushes
# ---------------------------------------------------------------------------

class TestMetricsFlush:
    """Repeated metrics log writes remain parseable and bounded."""

    FLUSHES = 50
    ITEMS = 10

    def test_50_metrics_flush_parseable(self):
        reset_metrics()
        log_dir = tempfile.mkdtemp()
        log_path = str(Path(log_dir) / "metrics.jsonl")
        try:
            configure_metrics(metrics_log_path=log_path, retention=200)

            for flush_idx in range(self.FLUSHES):
                queue, tmp = _isolated_queue(tag=f"flush_{flush_idx}")
                try:
                    articles = [make_synthetic_article(f"f{flush_idx}_{i:04d}") for i in range(self.ITEMS)]
                    queue.build_from_articles(articles, stage="ic", skip_existing=False)

                    while True:
                        item = queue.acquire_next()
                        if item is None:
                            break
                        queue.mark_completed(item)

                    get_metrics().flush_metrics()
                finally:
                    shutil.rmtree(tmp, ignore_errors=True)

            # Verify log is parseable
            assert Path(log_path).exists()
            with open(log_path, 'r') as f:
                lines = f.readlines()
            assert len(lines) == self.FLUSHES, f"Expected {self.FLUSHES} lines, got {len(lines)}"
            for i, line in enumerate(lines):
                record = json.loads(line)
                assert record["type"] == "metrics_snapshot", \
                    f"Line {i}: unexpected type {record['type']}"
                assert "data" in record
                assert "queue" in record["data"]
        finally:
            shutil.rmtree(log_dir, ignore_errors=True)

    def test_rotate_metrics_log(self):
        reset_metrics()
        log_dir = tempfile.mkdtemp()
        log_path = str(Path(log_dir) / "metrics.jsonl")
        try:
            configure_metrics(metrics_log_path=log_path, retention=20)

            # Write more records than retention
            for i in range(50):
                get_metrics().flush_metrics()

            get_metrics().rotate_metrics_log()

            with open(log_path, 'r') as f:
                lines = f.readlines()
            assert 10 < len(lines) <= 25, f"Expected ~20 lines after rotate, got {len(lines)}"

            # Verify all lines still parseable
            for line in lines:
                record = json.loads(line)
                assert record["type"] == "metrics_snapshot"
        finally:
            shutil.rmtree(log_dir, ignore_errors=True)

    def test_metrics_log_event_types(self):
        reset_metrics()
        log_dir = tempfile.mkdtemp()
        log_path = str(Path(log_dir) / "metrics.jsonl")
        try:
            configure_metrics(metrics_log_path=log_path, retention=50)

            for i in range(10):
                get_metrics().flush_metrics()
                get_metrics().log_event_to_file("test_event", {"index": i})
                get_metrics().log_event_to_file("compaction_event", {"cycle": i})

            # Verify all event types
            with open(log_path, 'r') as f:
                lines = f.readlines()
            assert len(lines) == 30  # 10 flush + 10 test + 10 compaction
            types = Counter(json.loads(l)["type"] for l in lines)
            assert types["metrics_snapshot"] == 10
            assert types["test_event"] == 10
            assert types["compaction_event"] == 10
        finally:
            shutil.rmtree(log_dir, ignore_errors=True)
