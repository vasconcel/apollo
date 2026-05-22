"""
Advisory queue management for APOLLO.

This module provides:
- Queue construction from articles
- Progress tracking
- Duplicate prevention
- Crash-safe state persistence via write-ahead log (WAL)
- Thread-safe operations via RLock
- Atomic snapshot writes

The queue is processed by the worker pipeline, NOT by UI.

CRASH SAFETY:
- Every mutation is written to an append-only WAL before any state change
- Snapshots are written atomically (temp file + fsync + os.replace)
- On init, the WAL is replayed to reconstruct canonical state
- A corrupted snapshot is recovered from the WAL alone
"""

import os
import json
import threading
import tempfile
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime

from .advisory_models import (
    QueueItem,
    QueueState,
    AdvisoryStatus,
    AdvisoryConfig,
)
from .advisory_cache import get_advisory_cache


class AdvisoryQueue:
    """
    Advisory queue manager with WAL-backed crash safety.

    Responsibilities:
    - Build queue from articles
    - Track progress
    - Prevent duplicate work
    - Persist queue state (WAL + atomic snapshots)
    """

    def __init__(self, config: Optional[AdvisoryConfig] = None, stage: str = "ic"):
        self.config = config or AdvisoryConfig()
        self._stage = stage
        self._queue_path = Path(f"data/cache/queue_state_{stage}.json")
        self._wal_path = Path(f"data/cache/queue_ops_{stage}.jsonl")

        self._lock = threading.RLock()
        self._state: Optional[QueueState] = None

        self._wal_seq: int = 0

        print(f"[QUEUE INIT] Stage: {stage} | Snapshot: {self._queue_path} | WAL: {self._wal_path}")

        if self.config.enable_queue_state:
            self._queue_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # WAL (Write-Ahead Log)
    # ------------------------------------------------------------------

    def _append_wal(self, op_record: dict):
        """Append one operation to WAL and fsync."""
        self._wal_seq += 1
        op_record['seq'] = self._wal_seq
        op_record['timestamp'] = datetime.utcnow().isoformat()
        self._wal_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._wal_path, 'a', encoding='utf-8') as f:
            line = json.dumps(op_record, ensure_ascii=False) + '\n'
            f.write(line)
            f.flush()
            os.fsync(f.fileno())

    def _apply_wal_op(self, state: QueueState, op: dict):
        """Apply a single WAL operation to an in-memory QueueState."""
        op_type = op.get('op')
        cache_key = op.get('cache_key', '')

        if op_type == 'enqueue':
            item = QueueItem(
                cache_key=cache_key,
                protocol_version=op.get('protocol_version', '1.0'),
                article_id=op.get('article_id', cache_key),
                stage=op.get('stage', self._stage),
                status=AdvisoryStatus.PENDING,
                priority=op.get('priority', 0),
                title=op.get('title', ''),
                abstract=op.get('abstract', ''),
            )
            state.items.append(item)
            state.pending += 1
            state.total += 1

        elif op_type == 'mark_processing':
            for item in state.items:
                if item.cache_key == cache_key:
                    item.status = AdvisoryStatus.PROCESSING
                    item.started_at = op.get('timestamp')
                    state.pending -= 1
                    state.processing += 1
                    break

        elif op_type == 'mark_completed':
            for item in state.items:
                if item.cache_key == cache_key:
                    item.status = AdvisoryStatus.COMPLETED
                    item.completed_at = op.get('timestamp')
                    state.processing -= 1
                    state.completed += 1
                    break

        elif op_type == 'mark_failed':
            for item in state.items:
                if item.cache_key == cache_key:
                    item.status = AdvisoryStatus.FAILED
                    item.completed_at = op.get('timestamp')
                    item.last_error = op.get('error', '')
                    state.processing -= 1
                    state.failed += 1
                    break

        elif op_type == 'retry':
            for item in state.items:
                if item.cache_key == cache_key:
                    item.status = AdvisoryStatus.PENDING
                    item.retry_count += 1
                    item.started_at = None
                    item.completed_at = None
                    state.failed -= 1
                    state.pending += 1
                    break

        elif op_type == 'reset':
            state.total = 0
            state.pending = 0
            state.processing = 0
            state.completed = 0
            state.failed = 0
            state.items.clear()

    def _replay_wal(self, state: QueueState, after_seq: int = 0):
        """Replay WAL operations into state, skipping seq <= after_seq."""
        if not self._wal_path.exists():
            return
        try:
            with open(self._wal_path, 'r', encoding='utf-8') as f:
                for line in f:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    try:
                        op = json.loads(stripped)
                    except json.JSONDecodeError:
                        print(f"[QUEUE WAL] Skipping malformed line: {stripped[:80]}")
                        continue
                    op_seq = op.get('seq', 0)
                    if op_seq <= after_seq:
                        continue
                    self._wal_seq = max(self._wal_seq, op_seq)
                    self._apply_wal_op(state, op)
        except FileNotFoundError:
            pass

    # ------------------------------------------------------------------
    # State persistence (snapshot + WAL replay)
    # ------------------------------------------------------------------

    def _load_state(self) -> QueueState:
        """
        Load queue state from snapshot + WAL replay.

        Strategy:
        1. Load snapshot (if valid) for baseline state + last_wal_seq
        2. Replay WAL operations with seq > snapshot's last_wal_seq
        3. If snapshot is corrupted, recover from WAL alone
        4. If WAL is missing, fall back to snapshot (backward compat)
        """
        state = QueueState()
        snapshot_seq = 0

        if self._queue_path.exists():
            try:
                with open(self._queue_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                state = QueueState.from_dict(data)
                snapshot_seq = state.last_wal_seq
            except Exception as e:
                print(f"[QUEUE REPLAY] Snapshot corrupted ({e}), recovering from WAL")
                state = QueueState()
                snapshot_seq = 0

        self._replay_wal(state, after_seq=snapshot_seq)

        # Requene any PROCESSING items orphaned by crash/stop
        self._requeue_stale_processing(state)
        return state

    def _requeue_stale_processing(self, state: QueueState):
        """Return PROCESSING items back to PENDING (orphaned after crash/stop)."""
        for item in state.items:
            if item.status == AdvisoryStatus.PROCESSING:
                item.status = AdvisoryStatus.PENDING
                item.started_at = None
                state.processing -= 1
                state.pending += 1

    def _save_state(self):
        """Write snapshot atomically (temp file + fsync + os.replace)."""
        self.state.last_updated = datetime.utcnow().isoformat()
        self.state.last_wal_seq = self._wal_seq

        try:
            tmp = tempfile.NamedTemporaryFile(
                dir=str(self._queue_path.parent),
                suffix='.tmp',
                delete=False,
                mode='w',
                encoding='utf-8',
            )
            try:
                json.dump(self.state.to_dict(), tmp, indent=2, ensure_ascii=False)
                tmp.flush()
                os.fsync(tmp.fileno())
                tmp.close()
                os.replace(tmp.name, str(self._queue_path))
            except Exception:
                try:
                    os.unlink(tmp.name)
                except OSError:
                    pass
                raise
        except Exception as e:
            print(f"Warning: Failed to save queue state: {e}")

    # ------------------------------------------------------------------
    # Public API — all synchronized via RLock
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        """Return total number of items in queue."""
        state = self.state
        return state.pending + state.processing + state.completed

    @property
    def state(self) -> QueueState:
        """Get current queue state (lazy load, thread-safe)."""
        if self._state is None:
            with self._lock:
                if self._state is None:
                    self._state = self._load_state()
        return self._state

    def build_from_articles(
        self,
        articles: List,
        protocol_version: str = "1.0",
        stage: str = "ic",
        skip_existing: bool = True,
    ) -> QueueState:
        """
        Build queue from article list.

        Args:
            articles: List of article objects
            protocol_version: Protocol version to use
            stage: Advisory stage (ec, ic, or qc)
            skip_existing: Skip articles with existing advisories

        Returns:
            QueueState with populated items
        """
        if stage not in ("ec", "ic", "qc"):
            raise ValueError(f"Invalid stage: {stage}. Must be 'ec', 'ic', or 'qc'.")

        print(f"[QUEUE BUILD] Stage: {stage}")

        existing_keys: set = set()
        if skip_existing:
            cache = get_advisory_cache()
            existing_keys = set(cache.list_cached(protocol_version))

        items: List[QueueItem] = []
        for idx, article in enumerate(articles):
            if hasattr(article, 'article_id'):
                article_id = article.article_id
            elif hasattr(article, 'get'):
                article_id = article.get("article_id", f"idx_{idx}")
            else:
                article_id = f"idx_{idx}"

            if hasattr(article, 'title'):
                title = article.title
            elif hasattr(article, 'get'):
                title = article.get("title", "")
            else:
                title = ""

            if hasattr(article, 'abstract'):
                abstract = article.abstract
            elif hasattr(article, 'get'):
                abstract = article.get("abstract", "")
            else:
                abstract = ""

            if not title and not abstract:
                continue

            cache_key = get_advisory_cache().compute_cache_key(
                title, abstract, protocol_version
            )
            if skip_existing and cache_key in existing_keys:
                continue

            item = QueueItem(
                cache_key=cache_key,
                protocol_version=protocol_version,
                article_id=article_id,
                stage=stage,
                status=AdvisoryStatus.PENDING,
                priority=idx,
                title=title,
                abstract=abstract,
            )
            items.append(item)

        with self._lock:
            self._state = QueueState(
                total=len(articles),
                pending=len(items),
                processing=0,
                completed=0,
                failed=0,
                items=items,
            )

            for item in items:
                self._append_wal({
                    "op": "enqueue",
                    "cache_key": item.cache_key,
                    "protocol_version": item.protocol_version,
                    "article_id": item.article_id,
                    "stage": item.stage,
                    "priority": item.priority,
                    "title": item.title,
                    "abstract": item.abstract,
                })

            if self.config.enable_queue_state:
                self._save_state()

        return self.state

    def get_pending(self) -> List[QueueItem]:
        """Get all pending queue items."""
        with self._lock:
            return [
                item for item in self.state.items
                if item.status == AdvisoryStatus.PENDING
            ]

    def get_next(self) -> Optional[QueueItem]:
        """Get next pending item (FIFO) without marking it."""
        with self._lock:
            pending = self.get_pending()
            if not pending:
                return None
            pending.sort(key=lambda x: (x.priority, x.created_at))
            item = pending[0]
            if item.stage != self._stage:
                raise RuntimeError(
                    f"Queue contains invalid stage item: "
                    f"queue stage={self._stage}, item stage={item.stage}"
                )
            return item

    def acquire_next(self) -> Optional[QueueItem]:
        """
        Atomically get next pending item AND mark it as PROCESSING.

        This is the thread-safe "pop" operation for the worker.
        Prevents double-booking when multiple threads call get_next.
        """
        with self._lock:
            item = self.get_next()
            if item is None:
                return None
            self._mark_processing(item)
            return item

    def mark_processing(self, item: QueueItem) -> None:
        """Mark item as processing (idempotent)."""
        with self._lock:
            self._mark_processing(item)

    def _mark_processing(self, item: QueueItem) -> None:
        """Internal: mark processing (caller must hold _lock)."""
        if item.status == AdvisoryStatus.PROCESSING:
            return
        item.status = AdvisoryStatus.PROCESSING
        item.started_at = datetime.utcnow().isoformat()
        self.state.processing += 1
        self.state.pending -= 1
        self._append_wal({
            "op": "mark_processing",
            "cache_key": item.cache_key,
        })

    def mark_completed(self, item: QueueItem) -> None:
        """Mark item as completed (idempotent)."""
        with self._lock:
            if item.status == AdvisoryStatus.COMPLETED:
                return
            item.status = AdvisoryStatus.COMPLETED
            item.completed_at = datetime.utcnow().isoformat()
            self.state.completed += 1
            self.state.processing -= 1
            self._append_wal({
                "op": "mark_completed",
                "cache_key": item.cache_key,
            })

    def mark_failed(self, item: QueueItem, error: str) -> None:
        """Mark item as failed (idempotent)."""
        with self._lock:
            if item.status == AdvisoryStatus.FAILED:
                return
            item.status = AdvisoryStatus.FAILED
            item.completed_at = datetime.utcnow().isoformat()
            item.last_error = error
            self.state.failed += 1
            self.state.processing -= 1
            self._append_wal({
                "op": "mark_failed",
                "cache_key": item.cache_key,
                "error": error,
            })

    def retry(self, item: QueueItem) -> bool:
        """Retry a failed item."""
        with self._lock:
            if item.retry_count >= self.config.max_retries:
                return False
            item.status = AdvisoryStatus.PENDING
            item.retry_count += 1
            item.started_at = None
            item.completed_at = None
            self.state.pending += 1
            self.state.failed -= 1
            self._append_wal({
                "op": "retry",
                "cache_key": item.cache_key,
            })
            return True

    def reset_failed(self) -> int:
        """Reset all failed items for retry."""
        count = 0
        for item in self.state.items:
            if item.status == AdvisoryStatus.FAILED:
                if self.retry(item):
                    count += 1
        return count

    def get_stats(self) -> Dict:
        """Get queue statistics."""
        return {
            "total": self.state.total,
            "pending": self.state.pending,
            "processing": self.state.processing,
            "completed": self.state.completed,
            "failed": self.state.failed,
            "completion_rate": self.state.completion_rate,
            "status_summary": self.state.status_summary,
        }

    def get_item(self, cache_key: str) -> Optional[QueueItem]:
        """Get specific item by cache key."""
        for item in self.state.items:
            if item.cache_key == cache_key:
                return item
        return None

    def is_queued(self, cache_key: str) -> bool:
        """Check if item is in queue."""
        return self.get_item(cache_key) is not None

    def is_completed(self, cache_key: str) -> bool:
        """Check if item is completed."""
        item = self.get_item(cache_key)
        return item is not None and item.status == AdvisoryStatus.COMPLETED

    def clear(self) -> None:
        """Clear queue state, WAL, and snapshot."""
        with self._lock:
            self._state = QueueState()
            self._wal_seq = 0
            for p in [self._queue_path, self._wal_path]:
                if p.exists():
                    p.unlink()
            # Clean up any stale temp files
            for p in self._queue_path.parent.glob(f"queue_state_{self._stage}.json*.tmp"):
                try:
                    p.unlink()
                except OSError:
                    pass

    @property
    def pending_items(self) -> List[QueueItem]:
        """Get all pending queue items (property alias)."""
        return self.get_pending()


# ---------------------------------------------------------------------------
# Global singleton access
# ---------------------------------------------------------------------------

_global_queue_ec: Optional[AdvisoryQueue] = None
_global_queue_ic: Optional[AdvisoryQueue] = None
_global_queue_qc: Optional[AdvisoryQueue] = None


def lookup_queue(stage: str = "ic") -> Optional[AdvisoryQueue]:
    """
    PURE READ-ONLY queue lookup - NEVER creates runtime.
    """
    if stage not in ("ec", "ic", "qc"):
        raise ValueError(f"Invalid stage: {stage}. Must be 'ec', 'ic', or 'qc'.")
    global _global_queue_ec, _global_queue_ic, _global_queue_qc
    if stage.lower() == "ec":
        return _global_queue_ec
    elif stage.lower() == "ic":
        return _global_queue_ic
    else:
        return _global_queue_qc


def get_advisory_queue(config: Optional[AdvisoryConfig] = None, stage: str = "ic") -> AdvisoryQueue:
    """
    Get stage-scoped advisory queue instance - CREATES if absent.
    """
    if stage not in ("ec", "ic", "qc"):
        raise ValueError(f"Invalid stage: {stage}. Must be 'ec', 'ic', or 'qc'.")
    global _global_queue_ec, _global_queue_ic, _global_queue_qc
    stage_lower = stage.lower()
    if stage_lower == "ec":
        if _global_queue_ec is None:
            _global_queue_ec = AdvisoryQueue(config, stage="ec")
        return _global_queue_ec
    elif stage_lower == "ic":
        if _global_queue_ic is None:
            _global_queue_ic = AdvisoryQueue(config, stage="ic")
        return _global_queue_ic
    else:
        if _global_queue_qc is None:
            _global_queue_qc = AdvisoryQueue(config, stage="qc")
        return _global_queue_qc


def reset_queue_for_stage(stage: str = "ic"):
    """
    Reset queue for specific stage - clears memory, snapshot, and WAL.
    """
    global _global_queue_ec, _global_queue_ic, _global_queue_qc
    stage_lower = stage.lower()
    if stage_lower == "ec":
        _global_queue_ec = None
    elif stage_lower == "ic":
        _global_queue_ic = None
    else:
        _global_queue_qc = None
    print(f"[QUEUE RESET] Stage: {stage} (memory released)")

    # Clear snapshot
    snapshot_path = Path(f"data/cache/queue_state_{stage_lower}.json")
    if snapshot_path.exists():
        snapshot_path.unlink()
        print(f"[QUEUE RESET] Stage: {stage} (snapshot cleared)")

    # Clear WAL
    wal_path = Path(f"data/cache/queue_ops_{stage_lower}.jsonl")
    if wal_path.exists():
        wal_path.unlink()
        print(f"[QUEUE RESET] Stage: {stage} (WAL cleared)")

    # Clear any temp snapshot files
    for p in Path("data/cache").glob(f"queue_state_{stage_lower}.json*.tmp"):
        try:
            p.unlink()
        except OSError:
            pass


def clear_queue_items(stage: str = "ic"):
    """Clear all items from queue for specific stage (keeps queue object)."""
    queue = get_advisory_queue(stage=stage)
    with queue._lock:
        queue._state = QueueState()
        queue._wal_seq = 0
        print(f"[QUEUE CLEAR] Stage: {stage} (items cleared)")


def build_queue(
    articles: List,
    protocol_version: str = "1.0",
    stage: str = "ic",
    skip_existing: bool = True,
) -> QueueState:
    """Build advisory queue from articles."""
    if stage not in ("ec", "ic", "qc"):
        raise ValueError(f"Invalid stage: {stage}. Must be 'ec', 'ic', or 'qc'.")
    queue = get_advisory_queue(stage=stage)
    return queue.build_from_articles(articles, protocol_version, stage, skip_existing)


def get_queue_stats(stage: str = "ic") -> Dict:
    """Get queue statistics for specific stage (READ-ONLY)."""
    if stage not in ("ec", "ic", "qc"):
        raise ValueError(f"Invalid stage: {stage}. Must be 'ec', 'ic', or 'qc'.")
    queue = lookup_queue(stage=stage)
    if queue is None:
        return {"total": 0, "pending": 0, "processing": 0, "completed": 0, "failed": 0}
    return queue.get_stats()


def reset_failed_advisories(stage: str = "ic") -> int:
    """Reset failed items for retry."""
    if stage not in ("ec", "ic", "qc"):
        raise ValueError(f"Invalid stage: {stage}. Must be 'ec', 'ic', or 'qc'.")
    queue = get_advisory_queue(stage=stage)
    return queue.reset_failed()
