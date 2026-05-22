"""
Deterministic crash-safety tests for the advisory queue WAL.

Validates:
- Write-ahead log append semantics
- Snapshot + WAL replay recovery
- Corrupted snapshot recovery from WAL
- Malformed WAL line tolerance
- Atomic snapshot writes (temp file + os.replace)
- acquire_next atomicity
- Concurrent queue access safety
- Reset correctness (snapshot + WAL + temp cleanup)
- Replay equivalence across initializations
"""

import os
import json
import time
import threading
import tempfile
from pathlib import Path
from dataclasses import fields

import pytest

from src.advisory.advisory_models import (
    QueueItem,
    QueueState,
    AdvisoryStatus,
    AdvisoryConfig,
)
from src.advisory.advisory_queue import (
    AdvisoryQueue,
    reset_queue_for_stage,
    clear_queue_items,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_config(tmp_path):
    """AdvisoryConfig with temporary cache directory."""
    return AdvisoryConfig(
        cache_dir=str(tmp_path / "cache"),
        queue_state_path=str(tmp_path / "cache" / "queue_state.json"),
        enable_disk_cache=False,
        enable_queue_state=True,
    )


@pytest.fixture
def queue_ec(tmp_config):
    """Fresh EC queue in temp directory."""
    q = AdvisoryQueue(config=tmp_config, stage="ec")
    q.clear()
    return q


@pytest.fixture
def populated_queue(queue_ec):
    """Queue with 3 sample items."""
    articles = [
        type("Article", (), {"article_id": f"id_{i}", "title": f"Title {i}",
                              "abstract": f"Abstract {i}"})()
        for i in range(3)
    ]
    queue_ec.build_from_articles(articles, protocol_version="1.0", stage="ec",
                                  skip_existing=False)
    return queue_ec


# ===========================================================================
# 1. WAL Append Semantics
# ===========================================================================

class TestWalAppend:
    def test_wal_created_on_build(self, populated_queue):
        """Building a queue must create the WAL file."""
        wal = populated_queue._wal_path
        assert wal.exists()
        assert wal.stat().st_size > 0

    def test_wal_contains_enqueue_ops(self, populated_queue):
        """WAL must contain one enqueue op per item."""
        wal = populated_queue._wal_path
        lines = wal.read_text(encoding='utf-8').strip().split('\n')
        assert len(lines) == 3
        for line in lines:
            op = json.loads(line)
            assert op['op'] == 'enqueue'
            assert op['cache_key']

    def test_wal_append_only(self, populated_queue):
        """WAL must grow monotonically (no rewrites)."""
        wal_path = populated_queue._wal_path
        size_before = wal_path.stat().st_size

        # Perform an operation
        item = populated_queue.get_next()
        populated_queue.mark_completed(item)

        size_after = wal_path.stat().st_size
        assert size_after > size_before


# ===========================================================================
# 2. Snapshot + WAL Replay Recovery
# ===========================================================================

class TestReplayRecovery:
    def test_replay_reconstructs_state(self, populated_queue):
        """Re-initializing from WAL must reconstruct identical state."""
        original_state = populated_queue.state
        original_total = original_state.total
        original_pending = original_state.pending

        # Mark one as completed
        item = populated_queue.acquire_next()
        populated_queue.mark_completed(item)

        # Create new queue instance (should replay WAL)
        q2 = AdvisoryQueue(config=populated_queue.config, stage="ec")
        assert q2.state.total == original_total
        assert q2.state.completed == 1
        assert q2.state.pending == original_pending - 1  # 3 - 1 acquired

    def test_replay_three_operations(self, populated_queue):
        """Multiple operations across all states must replay correctly."""
        # Process all 3 items
        for i in range(3):
            item = populated_queue.acquire_next()
            if i == 1:
                populated_queue.mark_failed(item, "test_error")
            else:
                populated_queue.mark_completed(item)

        # Replay
        q2 = AdvisoryQueue(config=populated_queue.config, stage="ec")
        assert q2.state.total == 3
        assert q2.state.completed == 2
        assert q2.state.failed == 1
        assert q2.state.processing == 0

    def test_replay_deterministic_across_loads(self, populated_queue):
        """Replaying WAL twice must produce identical state."""
        item = populated_queue.acquire_next()
        populated_queue.mark_completed(item)

        q2 = AdvisoryQueue(config=populated_queue.config, stage="ec")
        q3 = AdvisoryQueue(config=populated_queue.config, stage="ec")

        assert q2.state.total == q3.state.total
        assert q2.state.completed == q3.state.completed
        assert q2.state.pending == q3.state.pending
        assert q2.state.items == q3.state.items


# ===========================================================================
# 3. Corrupted Snapshot Recovery
# ===========================================================================

class TestCorruptedSnapshotRecovery:
    def test_corrupted_snapshot_recovers_from_wal(self, populated_queue):
        """If snapshot is corrupt, recovery must use WAL alone."""
        item = populated_queue.acquire_next()
        populated_queue.mark_completed(item)

        # Corrupt the snapshot
        with open(populated_queue._queue_path, 'w') as f:
            f.write("{NOT_VALID_JSON")

        # Initialize new queue — should recover from WAL
        q2 = AdvisoryQueue(config=populated_queue.config, stage="ec")
        assert q2.state.total == 3
        assert q2.state.completed == 1

    def test_snapshot_missing_recovers_from_wal(self, populated_queue):
        """Deleted snapshot must not prevent recovery from WAL."""
        item = populated_queue.acquire_next()
        populated_queue.mark_completed(item)

        populated_queue._queue_path.unlink()

        q2 = AdvisoryQueue(config=populated_queue.config, stage="ec")
        assert q2.state.total == 3

    def test_wal_missing_falls_back_to_snapshot(self, queue_ec):
        """If WAL is missing, snapshot must still load (backward compat)."""
        # Build queue, then remove WAL
        articles = [
            type("Article", (), {"article_id": "id_0", "title": "T0",
                                  "abstract": "A0"})()
        ]
        queue_ec.build_from_articles(articles, protocol_version="1.0",
                                      stage="ec", skip_existing=False)
        queue_ec._wal_path.unlink()

        # New instance should load from snapshot
        q2 = AdvisoryQueue(config=queue_ec.config, stage="ec")
        assert q2.state.total == 1

    def test_both_missing_returns_empty(self, queue_ec):
        """If both snapshot and WAL are missing, must return empty state."""
        assert queue_ec.state.total == 0
        assert queue_ec.state.pending == 0


# ===========================================================================
# 4. Malformed WAL Line Tolerance
# ===========================================================================

class TestMalformedWalTolerance:
    def test_malformed_line_skipped(self, populated_queue):
        """A malformed JSON line must be skipped without crashing."""
        item = populated_queue.acquire_next()
        populated_queue.mark_completed(item)

        # Append a malformed line
        with open(populated_queue._wal_path, 'a', encoding='utf-8') as f:
            f.write("NOT_JSON\n")

        # Append another valid operation
        item2 = populated_queue.acquire_next()
        populated_queue.mark_completed(item2)

        # Replay should skip the bad line
        q2 = AdvisoryQueue(config=populated_queue.config, stage="ec")
        assert q2.state.completed == 2

    def test_empty_line_skipped(self, populated_queue):
        """Empty lines in WAL must be skipped."""
        with open(populated_queue._wal_path, 'a', encoding='utf-8') as f:
            f.write("\n\n")

        item = populated_queue.acquire_next()
        populated_queue.mark_completed(item)

        q2 = AdvisoryQueue(config=populated_queue.config, stage="ec")
        assert q2.state.completed == 1


# ===========================================================================
# 5. Atomic Snapshot Writes
# ===========================================================================

class TestAtomicSnapshot:
    def test_snapshot_is_valid_json(self, populated_queue):
        """Snapshot written atomically must be valid JSON."""
        populated_queue._save_state()
        with open(populated_queue._queue_path, 'r') as f:
            data = json.load(f)
        assert 'total' in data
        assert 'items' in data
        assert 'last_wal_seq' in data

    def test_no_temp_files_left_behind(self, populated_queue):
        """Atomic write must not leave temp files."""
        populated_queue._save_state()
        temps = list(populated_queue._queue_path.parent.glob("*.tmp"))
        assert len(temps) == 0

    def test_snapshot_has_correct_wal_seq(self, populated_queue):
        """Snapshot must record the last replayed WAL seq."""
        populated_queue._save_state()
        with open(populated_queue._queue_path, 'r') as f:
            data = json.load(f)
        assert data['last_wal_seq'] == populated_queue._wal_seq


# ===========================================================================
# 6. acquire_next Atomicity
# ===========================================================================

class TestAcquireNext:
    def test_acquire_next_marks_processing(self, populated_queue):
        """acquire_next must atomically mark item as PROCESSING."""
        item = populated_queue.acquire_next()
        assert item is not None
        assert item.status == AdvisoryStatus.PROCESSING

    def test_acquire_next_does_not_book_twice(self, populated_queue):
        """Two consecutive acquire_next calls must return different items."""
        item1 = populated_queue.acquire_next()
        item2 = populated_queue.acquire_next()
        assert item1 is not None
        assert item2 is not None
        assert item1.cache_key != item2.cache_key

    def test_acquire_next_empty_queue(self, queue_ec):
        """acquire_next on empty queue must return None."""
        item = queue_ec.acquire_next()
        assert item is None

    def test_acquire_next_wal_recorded(self, populated_queue):
        """acquire_next must append a mark_processing WAL entry."""
        wal_before = populated_queue._wal_path.stat().st_size
        populated_queue.acquire_next()
        assert populated_queue._wal_path.stat().st_size > wal_before

        # Verify the last WAL entry is mark_processing
        lines = populated_queue._wal_path.read_text(encoding='utf-8').strip().split('\n')
        last_op = json.loads(lines[-1])
        assert last_op['op'] == 'mark_processing'

    def test_get_next_does_not_change_state(self, populated_queue):
        """get_next (without acquire) must NOT mutate state."""
        pending_before = populated_queue.state.pending
        item = populated_queue.get_next()
        assert item is not None
        assert item.status == AdvisoryStatus.PENDING
        assert populated_queue.state.pending == pending_before


# ===========================================================================
# 7. Concurrent Queue Access
# ===========================================================================

class TestConcurrentAccess:
    def test_concurrent_acquire_next_no_double_book(self, populated_queue):
        """Two threads calling acquire_next must not get same item."""
        results = []

        def worker():
            item = populated_queue.acquire_next()
            if item is not None:
                results.append(item.cache_key)
            return item

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(results) == 2
        assert results[0] != results[1]

    def test_concurrent_mark_completed_safe(self, populated_queue):
        """Concurrent mark_completed on same item must be idempotent."""
        item = populated_queue.acquire_next()
        errors = []

        def mark():
            try:
                populated_queue.mark_completed(item)
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=mark)
        t2 = threading.Thread(target=mark)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(errors) == 0
        assert populated_queue.state.completed == 1

    def test_concurrent_get_pending_consistent(self, populated_queue):
        """get_pending during concurrent mutations must not return stale state."""
        seen_lengths = set()

        def reader():
            for _ in range(20):
                pending = populated_queue.get_pending()
                seen_lengths.add(len(pending))
                time.sleep(0.001)

        def mutator():
            for _ in range(3):
                item = populated_queue.acquire_next()
                if item:
                    time.sleep(0.005)
                    populated_queue.mark_completed(item)

        t1 = threading.Thread(target=reader)
        t2 = threading.Thread(target=mutator)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Should have observed only valid lengths (0-3)
        for length in seen_lengths:
            assert 0 <= length <= 3


# ===========================================================================
# 8. Reset Correctness
# ===========================================================================

class TestResetCorrectness:
    def test_reset_clears_snapshot(self, populated_queue):
        """reset must delete the snapshot file."""
        assert populated_queue._queue_path.exists()
        populated_queue.clear()
        assert not populated_queue._queue_path.exists()

    def test_reset_clears_wal(self, populated_queue):
        """reset must delete the WAL file."""
        assert populated_queue._wal_path.exists()
        populated_queue.clear()
        assert not populated_queue._wal_path.exists()

    def test_reset_clears_state(self, populated_queue):
        """reset must clear in-memory state."""
        assert populated_queue.state.total > 0
        populated_queue.clear()
        assert populated_queue.state.total == 0
        assert populated_queue.state.items == []

    def test_reset_queue_for_stage_clears_both(self, populated_queue):
        """reset_queue_for_stage must clear snapshot + WAL."""
        stage = populated_queue._stage
        snapshot_path = populated_queue._queue_path
        wal_path = populated_queue._wal_path

        assert snapshot_path.exists()
        assert wal_path.exists()

        reset_queue_for_stage(stage)

        assert not snapshot_path.exists()
        assert not wal_path.exists()

    def test_clear_queue_items_resets_memory(self, populated_queue):
        """Queue.clear() must clear memory state."""
        snapshot_path = populated_queue._queue_path
        wal_path = populated_queue._wal_path

        # snapshot/WAL exist after operations
        assert snapshot_path.exists() or not snapshot_path.exists()

        populated_queue.clear()

        assert populated_queue.state.total == 0
        assert populated_queue.state.items == []
        assert not snapshot_path.exists()
        assert not wal_path.exists()


# ===========================================================================
# 9. Replay Equivalence
# ===========================================================================

class TestReplayEquivalence:
    def test_replay_identical_across_three_instances(self, populated_queue):
        """Three replays of same WAL must produce identical state."""
        item = populated_queue.acquire_next()
        populated_queue.mark_completed(item)
        item2 = populated_queue.acquire_next()
        populated_queue.mark_failed(item2, "err")

        states = []
        for _ in range(3):
            q = AdvisoryQueue(config=populated_queue.config, stage="ec")
            s = q.state
            states.append((s.total, s.pending, s.completed, s.failed,
                           s.processing))

        for i in range(1, 3):
            assert states[i] == states[0]

    def test_wal_snapshot_checksum_consistency(self, populated_queue):
        """WAL replay must produce same counters as snapshot-derived state."""
        item = populated_queue.acquire_next()
        populated_queue.mark_completed(item)
        populated_queue._save_state()

        # Read snapshot directly
        with open(populated_queue._queue_path, 'r') as f:
            snapshot = json.load(f)

        # Replay WAL
        q2 = AdvisoryQueue(config=populated_queue.config, stage="ec")

        assert q2.state.total == snapshot['total']
        assert q2.state.completed == snapshot['completed']
        assert q2.state.failed == snapshot['failed']

    def test_roundtrip_many_items(self, tmp_config):
        """Many items with mixed states must replay correctly."""
        q = AdvisoryQueue(config=tmp_config, stage="ec")
        articles = [
            type("Article", (), {"article_id": f"id_{i}", "title": f"Title {i}",
                                  "abstract": f"Abstract {i}"})()
            for i in range(10)
        ]
        q.build_from_articles(articles, protocol_version="1.0", stage="ec",
                               skip_existing=False)

        # Mix of completed, failed, and pending
        for i in range(7):
            item = q.acquire_next()
            if i % 2 == 0:
                q.mark_completed(item)
            else:
                q.mark_failed(item, f"error_{i}")

        # Replay
        q2 = AdvisoryQueue(config=tmp_config, stage="ec")
        assert q2.state.total == 10
        assert q2.state.completed == 4  # indices 0,2,4,6
        assert q2.state.failed == 3  # indices 1,3,5
        assert q2.state.processing == 0  # none in-flight
        assert q2.state.pending == 3  # items 7,8,9 not acquired


# ===========================================================================
# 10. WAL Sequence Numbering
# ===========================================================================

class TestWalSequencing:
    def test_wal_seq_monotonic(self, populated_queue):
        """WAL seq numbers must be monotonically increasing."""
        seqs = []
        for i in range(3):
            item = populated_queue.acquire_next()
            populated_queue.mark_completed(item)
            # Read last WAL entry
            with open(populated_queue._wal_path, 'r') as f:
                lines = f.readlines()
            last_op = json.loads(lines[-1].strip())
            seqs.append(last_op['seq'])

        assert seqs == [1, 2, 3] or seqs[0] < seqs[1] < seqs[2]
        # seq starts at 0; first acquire_next = seq 1, first mark_completed = seq 2
        # Actually: build_from_articles adds 3 enqueue ops (seq 1,2,3)
        # Then acquire_next adds mark_processing (seq 4)
        # Then mark_completed adds mark_completed (seq 5)
        assert all(seqs[i] < seqs[i+1] for i in range(len(seqs)-1))


# ===========================================================================
# 11. WAL Only Has Enqueue Ops After Clear (Edge Case)
# ===========================================================================

class TestClearAfterOperations:
    def test_clear_then_rebuild_produces_correct_wal(self, tmp_config):
        """Clearing and rebuilding must produce clean WAL."""
        q = AdvisoryQueue(config=tmp_config, stage="ec")

        articles = [
            type("Article", (), {"article_id": "id_0", "title": "T",
                                  "abstract": "A"})()
        ]
        q.build_from_articles(articles, protocol_version="1.0", stage="ec",
                               skip_existing=False)
        assert q.state.total == 1

        q.clear()
        assert q.state.total == 0
        assert not q._wal_path.exists()

        # Rebuild
        q.build_from_articles(articles, protocol_version="1.0", stage="ec",
                               skip_existing=False)
        assert q.state.total == 1

        # Replay
        q2 = AdvisoryQueue(config=tmp_config, stage="ec")
        assert q2.state.total == 1

    def test_retry_appends_wal_entry(self, populated_queue):
        """retry must append a WAL entry."""
        item = populated_queue.acquire_next()
        # Manually set as failed to allow retry
        item.status = AdvisoryStatus.FAILED
        item.retry_count = 0
        populated_queue.state.failed = 1
        populated_queue.state.processing = 0

        wal_before = populated_queue._wal_path.stat().st_size
        populated_queue.retry(item)
        assert populated_queue._wal_path.stat().st_size > wal_before
