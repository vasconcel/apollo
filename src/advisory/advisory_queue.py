"""
Advisory queue management for APOLLO.

This module provides:
- Queue construction from articles
- Progress tracking
- Duplicate prevention
- Crash-safe state persistence via write-ahead log (WAL)
- Thread-safe operations via RLock
- Atomic snapshot writes
- WAL compaction with crash-safe rotation
- Recovery telemetry

The queue is processed by the worker pipeline, NOT by UI.

CRASH SAFETY:
- Every mutation is written to an append-only WAL before any state change
- Snapshots are written atomically (temp file + fsync + os.replace)
- On init, the WAL is replayed to reconstruct canonical state
- A corrupted snapshot is recovered from the WAL alone
- WAL compaction atomically rotates the WAL; crash during rotation
  leaves the snapshot valid + bak file recoverable
"""

import os
import json
import time
import threading
import tempfile
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime, timezone

from .advisory_models import (
    QueueItem,
    QueueState,
    AdvisoryStatus,
    AdvisoryConfig,
)
from .advisory_cache import get_advisory_cache
from .advisory_metrics import get_metrics, _RecoveryEvent
from .telemetry_bus import get_telemetry_bus


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
        base_dir = Path(self.config.queue_state_path).parent if self.config.queue_state_path != "data/cache/queue_state.json" else Path("data/cache")
        self._queue_path = base_dir / f"queue_state_{stage}.json"
        self._wal_path = base_dir / f"queue_ops_{stage}.jsonl"

        self._lock = threading.RLock()
        self._state: Optional[QueueState] = None

        self._wal_seq: int = 0
        self._acquire_timestamp: float = 0.0

        # Auto-compaction state
        self._compact_pending: bool = False
        self._compact_pending_reason: str = ""
        self._last_compact_time: float = 0.0

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
        op_record['timestamp'] = datetime.now(timezone.utc).isoformat()
        self._wal_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._wal_path, 'a', encoding='utf-8') as f:
            line = json.dumps(op_record, ensure_ascii=False) + '\n'
            f.write(line)
            f.flush()
            os.fsync(f.fileno())
        self._check_and_schedule_compact()

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
                    item.retry_after = None
                    state.failed -= 1
                    state.pending += 1
                    break

        elif op_type == 'schedule_retry':
            for item in state.items:
                if item.cache_key == cache_key:
                    item.retry_after = op.get('retry_after')
                    item.retry_reason = op.get('retry_reason', 'transient')
                    break

        elif op_type == 'quarantine':
            for item in state.items:
                if item.cache_key == cache_key:
                    item.is_quarantined = True
                    item.retry_after = None
                    item.retry_reason = "quarantined"
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
        metrics = get_metrics()
        try:
            with open(self._wal_path, 'r', encoding='utf-8') as f:
                for line in f:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    try:
                        op = json.loads(stripped)
                    except json.JSONDecodeError:
                        metrics.malformed_wal_entries += 1
                        metrics.record_recovery_event(_RecoveryEvent(
                            event_type="malformed_wal_skipped",
                            stage=self._stage,
                            outcome="skipped",
                            detail=stripped[:80],
                        ))
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
        replay_start = time.time()
        state = QueueState()
        snapshot_seq = 0
        metrics = get_metrics()

        if self._queue_path.exists():
            try:
                with open(self._queue_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                state = QueueState.from_dict(data)
                snapshot_seq = state.last_wal_seq
                metrics.record_recovery_event(_RecoveryEvent(
                    event_type="snapshot_loaded",
                    stage=self._stage,
                    operation_count=len(state.items),
                    outcome="ok",
                    detail=f"snapshot_seq={snapshot_seq}",
                ))
            except Exception as e:
                print(f"[QUEUE REPLAY] Snapshot corrupted ({e}), recovering from WAL")
                metrics.corrupted_snapshot_recoveries += 1
                metrics.record_recovery_event(_RecoveryEvent(
                    event_type="corrupted_snapshot_detected",
                    stage=self._stage,
                    outcome="recovered_from_wal",
                    detail=str(e),
                ))
                state = QueueState()
                snapshot_seq = 0

        play_count_before = len(state.items) if state.items else 0
        self._replay_wal(state, after_seq=snapshot_seq)
        play_count_after = len(state.items) if state.items else 0
        replayed_ops = max(0, play_count_after - play_count_before)
        state.replay_operation_count += replayed_ops

        replay_duration = (time.time() - replay_start) * 1000
        metrics.record_replay(replay_duration, replayed_ops)

        # Requeue any PROCESSING items orphaned by crash/stop
        stale_count = self._requeue_stale_processing(state)
        if stale_count:
            metrics.stale_processing_requeues += stale_count
            metrics.record_recovery_event(_RecoveryEvent(
                event_type="stale_processing_requeued",
                stage=self._stage,
                operation_count=stale_count,
                outcome="ok",
                detail=f"requeued {stale_count} processing items to pending",
            ))

        return state

    def _requeue_stale_processing(self, state: QueueState) -> int:
        """Return PROCESSING items back to PENDING (orphaned after crash/stop). Returns count."""
        count = 0
        for item in state.items:
            if item.status == AdvisoryStatus.PROCESSING:
                item.status = AdvisoryStatus.PENDING
                item.started_at = None
                state.processing -= 1
                state.pending += 1
                count += 1
        return count

    def _save_state(self):
        """Write snapshot atomically (temp file + fsync + os.replace)."""
        now = datetime.now(timezone.utc).isoformat()
        self.state.last_updated = now
        self.state.last_wal_seq = self._wal_seq
        self.state.snapshot_created_at = now
        self.state.snapshot_item_counts = {
            "pending": self.state.pending,
            "processing": self.state.processing,
            "completed": self.state.completed,
            "failed": self.state.failed,
        }

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
    # WAL Compaction
    # ------------------------------------------------------------------

    def compact_wal(self) -> Dict:
        """
        Compact WAL by atomically writing snapshot and rotating the log.

        Crash-safe strategy:
        1. Write snapshot atomically (temp file + fsync + os.replace)
        2. fsync the parent directory
        3. Rotate old WAL -> .bak
        4. Create new empty WAL
        5. Delete .bak only after success

        Crash recovery scenarios:
        - Crash BEFORE step 3: snapshot is valid, WAL is intact
          -> replay from snapshot + WAL (normal path)
        - Crash AFTER step 3 (rename) but BEFORE step 5 (delete .bak):
          -> .bak exists; replay from snapshot + .bak (recoverable)
        - Crash AFTER step 5: snapshot + empty WAL
          -> replay from snapshot only
        """
        start = time.time()

        with self._lock:
            if self._state is None:
                return {"compacted": False, "reason": "no_state", "wal_seq": 0}

            prev_wal_seq = self._wal_seq

            # Increment compaction count BEFORE save so snapshot includes it
            self.state.wal_compaction_count += 1

            # Step 1: write snapshot atomically
            self._save_state()

            # Step 2: fsync parent directory (best-effort on Windows)
            try:
                fd = os.open(str(self._queue_path.parent), os.O_RDONLY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
            except OSError:
                pass

            # Step 3: rotate old WAL -> .bak
            bak_path = self._wal_path.with_suffix('.jsonl.bak')
            if self._wal_path.exists():
                os.replace(str(self._wal_path), str(bak_path))

            # Step 4: create new empty WAL
            self._wal_seq = 0
            self._wal_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._wal_path, 'w', encoding='utf-8') as f:
                f.write('')
                f.flush()
                os.fsync(f.fileno())

            # Step 5: delete .bak on success
            try:
                if bak_path.exists():
                    bak_path.unlink()
            except OSError:
                pass

            duration_ms = (time.time() - start) * 1000
            get_metrics().record_recovery_event(_RecoveryEvent(
                event_type="wal_compacted",
                stage=self._stage,
                duration_ms=duration_ms,
                operation_count=prev_wal_seq,
                outcome="ok",
            ))

            print(f"[QUEUE COMPACT] Stage: {self._stage} | "
                  f"Previous WAL seq: {prev_wal_seq} | "
                  f"Duration: {duration_ms:.1f}ms")

            self._last_compact_time = time.time()

            return {
                "compacted": True,
                "wal_seq_before": prev_wal_seq,
                "wal_seq_after": 0,
                "compaction_count": self.state.wal_compaction_count,
                "duration_ms": round(duration_ms, 2),
            }

    # ------------------------------------------------------------------
    # Auto-Compaction
    # ------------------------------------------------------------------

    def _check_and_schedule_compact(self):
        """Check WAL compaction thresholds (must be called with _lock held).

        Sets _compact_pending flag if any threshold is exceeded and the
        minimum interval has elapsed since the last compaction.
        """
        now = time.time()

        if now - self._last_compact_time < self.config.wal_compaction_interval_seconds:
            return

        reasons = []

        if self._wal_seq >= self.config.wal_compaction_max_operations:
            reasons.append(f"ops>{self.config.wal_compaction_max_operations}")

        if self._wal_path.exists():
            try:
                size_mb = self._wal_path.stat().st_size / (1024 * 1024)
                if size_mb >= self.config.wal_compaction_max_size_mb:
                    reasons.append(f"size>{size_mb:.1f}MB")
            except OSError:
                pass

        if reasons:
            self._compact_pending = True
            self._compact_pending_reason = "; ".join(reasons)

    def _run_pending_compact(self):
        """Execute pending auto-compaction if thresholds exceeded.

        Must be called OUTSIDE the mutation lock. Uses a non-blocking
        lock acquire to skip if another thread is already compacting.
        """
        if not self._compact_pending:
            return

        reason = self._compact_pending_reason
        self._compact_pending = False
        self._compact_pending_reason = ""

        if not self._lock.acquire(blocking=False):
            get_metrics().auto_compaction_skipped_lock += 1
            get_metrics().record_recovery_event(_RecoveryEvent(
                event_type="compaction_skipped",
                stage=self._stage,
                outcome="lock_held",
                detail=f"auto:{reason}",
            ))
            return

        try:
            result = self.compact_wal()
            get_metrics().auto_compaction_trigger_count += 1
            get_metrics().record_recovery_event(_RecoveryEvent(
                event_type="auto_compaction",
                stage=self._stage,
                outcome="ok",
                detail=f"triggered_by:{reason}",
            ))
            print(f"[AUTO COMPACT] Stage: {self._stage} | Reason: {reason} | "
                  f"WAL seq before: {result.get('wal_seq_before', '?')}")
        finally:
            self._lock.release()

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

            # Batch-write all WAL ops with a single fsync for performance
            # (individual _append_wal ops still fsync per call for crash safety)
            op_records = []
            for item in items:
                self._wal_seq += 1
                op_records.append({
                    "seq": self._wal_seq,
                    "op": "enqueue",
                    "cache_key": item.cache_key,
                    "protocol_version": item.protocol_version,
                    "article_id": item.article_id,
                    "stage": item.stage,
                    "priority": item.priority,
                    "title": item.title,
                    "abstract": item.abstract,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

            if op_records:
                self._wal_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self._wal_path, 'a', encoding='utf-8') as f:
                    for op in op_records:
                        f.write(json.dumps(op, ensure_ascii=False) + '\n')
                    f.flush()
                    os.fsync(f.fileno())

            if self.config.enable_queue_state:
                self._save_state()

            self._check_and_schedule_compact()

        try:
            get_telemetry_bus().record_queue_depth(stage, len(items))
        except Exception:
            pass

        self._run_pending_compact()
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
                try:
                    get_telemetry_bus().record_queue_depth(self._stage, 0)
                except Exception:
                    pass
                self._run_pending_compact()
                return None
            self._mark_processing(item)
            self._acquire_timestamp = time.time()
            metrics = get_metrics()
            metrics.queue_pending_count = self.state.pending
            metrics.queue_processing_count = self.state.processing
            metrics.queue_completed_count = self.state.completed
            metrics.queue_failed_count = self.state.failed
            try:
                get_telemetry_bus().record_queue_depth(self._stage, self.state.pending)
            except Exception:
                pass
            self._run_pending_compact()
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
        item.started_at = datetime.now(timezone.utc).isoformat()
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
            item.completed_at = datetime.now(timezone.utc).isoformat()
            self.state.completed += 1
            self.state.processing -= 1
            self._append_wal({
                "op": "mark_completed",
                "cache_key": item.cache_key,
            })
            metrics = get_metrics()
            metrics.queue_completed_count = self.state.completed
            metrics.queue_processing_count = self.state.processing

        try:
            bus = get_telemetry_bus()
            if self._acquire_timestamp > 0:
                bus.record_processing_time(self._stage, time.time() - self._acquire_timestamp)
            self._acquire_timestamp = 0.0
            bus.record_queue_depth(self._stage, self.state.pending)
        except Exception:
            pass
        self._run_pending_compact()

    def mark_failed(self, item: QueueItem, error: str) -> None:
        """Mark item as failed (idempotent)."""
        with self._lock:
            if item.status == AdvisoryStatus.FAILED:
                return
            item.status = AdvisoryStatus.FAILED
            item.completed_at = datetime.now(timezone.utc).isoformat()
            item.last_error = error
            self.state.failed += 1
            self.state.processing -= 1
            self._append_wal({
                "op": "mark_failed",
                "cache_key": item.cache_key,
                "error": error,
            })
            metrics = get_metrics()
            metrics.queue_failed_count = self.state.failed
            metrics.queue_processing_count = self.state.processing

        try:
            bus = get_telemetry_bus()
            if self._acquire_timestamp > 0:
                bus.record_processing_time(self._stage, time.time() - self._acquire_timestamp)
            self._acquire_timestamp = 0.0
            bus.record_queue_depth(self._stage, self.state.pending)
        except Exception:
            pass
        self._run_pending_compact()

    def retry(self, item: QueueItem) -> bool:
        """Retry a failed item (immediate)."""
        with self._lock:
            if item.retry_count >= self.config.max_retries:
                return False
            if item.is_quarantined:
                return False
            item.status = AdvisoryStatus.PENDING
            item.retry_count += 1
            item.started_at = None
            item.completed_at = None
            item.retry_after = None
            self.state.pending += 1
            self.state.failed -= 1
            self._append_wal({
                "op": "retry",
                "cache_key": item.cache_key,
            })
            get_metrics().queue_retry_count += 1
            return True

        self._run_pending_compact()

    def schedule_retry(self, item: QueueItem, backoff_seconds: float = 60.0) -> bool:
        """Schedule a failed item for delayed retry.

        Sets retry_after to current time + backoff_seconds.
        Only transient failures are eligible for scheduled retry.
        Terminal failures are quarantined immediately.

        Returns True if scheduled, False if max retries exceeded or quarantined.
        """
        from .transient_failures import classify_failure
        failure_class = classify_failure(item.last_error)

        if failure_class == "terminal":
            try:
                get_telemetry_bus().record_requeue_event(self._stage, "terminal")
            except Exception:
                pass
            return self._quarantine_item(item)

        if item.retry_count >= self.config.max_retries:
            try:
                get_telemetry_bus().record_requeue_event(self._stage, "max_retries")
            except Exception:
                pass
            return self._quarantine_item(item)

        with self._lock:
            if item.is_quarantined:
                return False
            from datetime import datetime, timezone, timedelta
            item.retry_after = (
                datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds)
            ).isoformat()
            item.retry_reason = failure_class
            self._append_wal({
                "op": "schedule_retry",
                "cache_key": item.cache_key,
                "retry_after": item.retry_after,
                "retry_reason": failure_class,
            })
            get_metrics().queue_retry_count += 1
            try:
                get_telemetry_bus().record_requeue_event(self._stage, failure_class)
            except Exception:
                pass
            return True

    def _quarantine_item(self, item: QueueItem) -> bool:
        """Permanently quarantine an item (max retries exceeded or terminal)."""
        with self._lock:
            if item.is_quarantined:
                return False
            item.is_quarantined = True
            item.retry_after = None
            item.retry_reason = "quarantined"
            self._append_wal({
                "op": "quarantine",
                "cache_key": item.cache_key,
            })
            get_metrics().log_event_to_file("item_quarantined", {
                "cache_key": item.cache_key[:16],
                "stage": self._stage,
                "retry_count": item.retry_count,
                "last_error": (item.last_error or "")[:100],
            })
            return True

    def get_retryable_items(self) -> list:
        """Get items that are eligible for scheduled retry (retry_after <= now).

        Returns list of (QueueItem, backoff_seconds) for items whose
        retry_after has passed. Items without retry_after set are not included.
        """
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        retryable = []
        for item in self.state.items:
            if item.is_quarantined:
                continue
            if item.retry_after is None:
                continue
            try:
                retry_time = datetime.fromisoformat(item.retry_after)
                if retry_time.tzinfo is None:
                    retry_time = retry_time.replace(tzinfo=timezone.utc)
                if retry_time <= now:
                    retryable.append(item)
            except (ValueError, TypeError):
                continue
        return retryable

    def process_retryable_items(self, max_items: int = 10) -> int:
        """Process all retryable items (move from FAILED to PENDING).

        Returns count of items retried.
        """
        count = 0
        for item in self.get_retryable_items():
            if count >= max_items:
                break
            if self.retry(item):
                count += 1
        return count

    def reset_failed(self) -> int:
        """Reset all failed items for immediate retry (skips quarantined)."""
        count = 0
        for item in self.state.items:
            if item.status == AdvisoryStatus.FAILED and not item.is_quarantined:
                if self.retry(item):
                    count += 1
        return count

    def get_stats(self) -> Dict:
        """Get queue statistics including checkpoint metadata."""
        s = self.state
        quarantined = sum(1 for it in self.state.items if it.is_quarantined)
        return {
            "total": s.total,
            "pending": s.pending,
            "processing": s.processing,
            "completed": s.completed,
            "failed": s.failed,
            "quarantined": quarantined,
            "completion_rate": s.completion_rate,
            "status_summary": s.status_summary,
            "last_wal_seq": s.last_wal_seq,
            "wal_compaction_count": s.wal_compaction_count,
            "replay_operation_count": s.replay_operation_count,
            "snapshot_created_at": s.snapshot_created_at,
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
            for p in [self._queue_path, self._wal_path, self._wal_path.with_suffix('.jsonl.bak')]:
                if p.exists():
                    p.unlink()
            # Clean up any stale temp files
            for p in self._queue_path.parent.glob(f"queue_state_{self._stage}.json*.tmp"):
                try:
                    p.unlink()
                except OSError:
                    pass
        try:
            get_telemetry_bus().record_queue_depth(self._stage, 0)
        except Exception:
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


def _can_reset_queue(stage: str) -> bool:
    """Check if it is safe to reset a queue.

    Returns False if the stage has an active orchestrator worker.
    Uses lazy import to avoid circular dependency.
    """
    try:
        from .advisory_orchestrator import lookup_orchestrator as _lo
        orch = _lo(stage)
    except Exception:
        return True
    if orch is not None:
        if orch._worker_thread is not None and orch._worker_thread.is_alive():
            print(f"[QUEUE RESET GUARD] Stage: {stage} | Worker thread alive — reset blocked")
            return False
    return True


def reset_queue_for_stage(stage: str = "ic", force: bool = False):
    """
    Reset queue for specific stage - clears memory, snapshot, and WAL.
    First checks if a global queue instance exists (for custom paths),
    then falls back to default paths.

    Args:
        stage: Advisory stage
        force: If True, skip safety check (for calibration runner).

    Raises:
        RuntimeError: If stage has active worker and force=False
    """
    if not force and not _can_reset_queue(stage):
        raise RuntimeError(
            f"Cannot reset queue for stage {stage}: worker is still active. "
            f"Stop the worker or use force=True."
        )

    global _global_queue_ec, _global_queue_ic, _global_queue_qc
    stage_lower = stage.lower()

    target_snapshot = None
    target_wal = None

    if stage_lower == "ec":
        if _global_queue_ec is not None:
            target_snapshot = _global_queue_ec._queue_path
            target_wal = _global_queue_ec._wal_path
        _global_queue_ec = None
    elif stage_lower == "ic":
        if _global_queue_ic is not None:
            target_snapshot = _global_queue_ic._queue_path
            target_wal = _global_queue_ic._wal_path
        _global_queue_ic = None
    else:
        if _global_queue_qc is not None:
            target_snapshot = _global_queue_qc._queue_path
            target_wal = _global_queue_qc._wal_path
        _global_queue_qc = None

    print(f"[QUEUE RESET] Stage: {stage} (memory released)")

    # Use queue instance paths if available, otherwise fall back to defaults
    snapshot_path = target_snapshot if target_snapshot else Path(f"data/cache/queue_state_{stage_lower}.json")
    if snapshot_path.exists():
        snapshot_path.unlink()
        print(f"[QUEUE RESET] Stage: {stage} (snapshot cleared)")

    wal_path = target_wal if target_wal else Path(f"data/cache/queue_ops_{stage_lower}.jsonl")
    if wal_path.exists():
        wal_path.unlink()
        print(f"[QUEUE RESET] Stage: {stage} (WAL cleared)")

    wal_bak = wal_path.with_suffix('.jsonl.bak')
    if wal_bak.exists():
        wal_bak.unlink()
        print(f"[QUEUE RESET] Stage: {stage} (WAL backup cleared)")

    # Clear any temp snapshot files
    base = snapshot_path.parent
    for p in base.glob(f"queue_state_{stage_lower}.json*.tmp"):
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
