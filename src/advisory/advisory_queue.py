"""
Advisory queue management for APOLLO.

This module provides:
- Queue construction from articles
- Progress tracking
- Duplicate prevention
- State persistence

The queue is processed by the worker pipeline, NOT by UI.
"""

import os
import json
import hashlib
from pathlib import Path
from typing import List, Optional, Dict, Set
from datetime import datetime

from .advisory_models import (
    QueueItem,
    QueueState,
    AdvisoryStatus,
    AdvisoryConfig
)
from .advisory_cache import get_advisory_cache, has_advisory


class AdvisoryQueue:
    """
    Advisory queue manager.
    
    Responsibilities:
    - Build queue from articles
    - Track progress
    - Prevent duplicate work
    - Persist queue state
    """
    
    def __init__(self, config: Optional[AdvisoryConfig] = None, stage: str = "ic"):
        self.config = config or AdvisoryConfig()
        self._stage = stage
        self._queue_path = Path(f"data/cache/queue_state_{stage}.json")

        self._state: Optional[QueueState] = None

        print(f"[QUEUE INIT] Stage: {stage} | Path: {self._queue_path}")

        if self.config.enable_queue_state:
            self._queue_path.parent.mkdir(parents=True, exist_ok=True)
    
    @property
    def state(self) -> QueueState:
        """Get current queue state (lazy load)."""
        if self._state is None:
            self._state = self._load_state()
        return self._state
    
    def build_from_articles(
        self,
        articles: List,
        protocol_version: str = "1.0",
        stage: str = "ic",
        skip_existing: bool = True
    ) -> QueueState:
        """
        Build queue from article list.

        Args:
            articles: List of article objects
            protocol_version: Protocol version to use
            stage: Advisory stage (ec or ic) - MUST be valid
            skip_existing: Skip articles with existing advisories

        Returns:
            QueueState with populated items

        Raises:
            ValueError: If stage is not explicitly "ec", "ic", or "qc"
        """
        if stage not in ("ec", "ic", "qc"):
            raise ValueError(f"Invalid stage: {stage}. Must be 'ec', 'ic', or 'qc'.")

        print(f"[QUEUE BUILD] Stage: {stage}")

        existing_keys = set()
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
                priority=idx
            )
            items.append(item)
        
        self._state = QueueState(
            total=len(articles),
            pending=len(items),
            processing=0,
            completed=0,
            failed=0,
            items=items
        )
        
        if self.config.enable_queue_state:
            self._save_state()
        
        return self.state
    
    def get_pending(self) -> List[QueueItem]:
        """Get all pending queue items."""
        return [
            item for item in self.state.items
            if item.status == AdvisoryStatus.PENDING
        ]
    
    def get_next(self) -> Optional[QueueItem]:
        """Get next pending item (FIFO)."""
        pending = self.get_pending()
        if not pending:
            return None

        pending.sort(key=lambda x: (x.priority, x.created_at))
        item = pending[0]

        print(f"[QUEUE POP] QueueStage: {self._stage} | ItemStage: {item.stage}")

        if item.stage != self._stage:
            print(f"[QUEUE DATA-PLANE VIOLATION] Queue stage={self._stage} != Item stage={item.stage}")
            raise RuntimeError(f"Queue contains invalid stage item: queue stage={self._stage}, item stage={item.stage}")

        return item
    
    def mark_processing(self, item: QueueItem) -> None:
        """Mark item as processing."""
        item.status = AdvisoryStatus.PROCESSING
        item.started_at = datetime.utcnow().isoformat()
        
        self.state.processing += 1
        self.state.pending -= 1
        
        self._save_state()
    
    def mark_completed(self, item: QueueItem) -> None:
        """Mark item as completed."""
        item.status = AdvisoryStatus.COMPLETED
        item.completed_at = datetime.utcnow().isoformat()
        
        self.state.completed += 1
        self.state.processing -= 1
        
        self._save_state()
    
    def mark_failed(self, item: QueueItem, error: str) -> None:
        """Mark item as failed."""
        item.status = AdvisoryStatus.FAILED
        item.completed_at = datetime.utcnow().isoformat()
        item.last_error = error
        
        self.state.failed += 1
        self.state.processing -= 1
        
        self._save_state()
    
    def retry(self, item: QueueItem) -> bool:
        """
        Retry a failed item.
        
        Returns:
            True if retry scheduled, False if max retries exceeded
        """
        if item.retry_count >= self.config.max_retries:
            return False
        
        item.status = AdvisoryStatus.PENDING
        item.retry_count += 1
        item.started_at = None
        item.completed_at = None
        
        self.state.pending += 1
        self.state.failed -= 1
        
        self._save_state()
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
            "status_summary": self.state.status_summary
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
    
    def _load_state(self) -> QueueState:
        """Load queue state from disk."""
        if not self._queue_path.exists():
            return QueueState()
        
        try:
            with open(self._queue_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return QueueState.from_dict(data)
        except Exception as e:
            print(f"Warning: Failed to load queue state: {e}")
            return QueueState()
    
    def _save_state(self) -> None:
        """Save queue state to disk."""
        self.state.last_updated = datetime.utcnow().isoformat()
        
        try:
            with open(self._queue_path, 'w', encoding='utf-8') as f:
                json.dump(self.state.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Warning: Failed to save queue state: {e}")
    
    def clear(self) -> None:
        """Clear queue state."""
        self._state = QueueState()
        if self._queue_path.exists():
            self._queue_path.unlink()


_global_queue_ec: Optional[AdvisoryQueue] = None
_global_queue_ic: Optional[AdvisoryQueue] = None
_global_queue_qc: Optional[AdvisoryQueue] = None


def lookup_queue(stage: str = "ic") -> Optional[AdvisoryQueue]:
    """
    PURE READ-ONLY queue lookup - NEVER creates runtime.

    Args:
        stage: Advisory stage

    Returns:
        Existing queue instance or None if not initialized

    Raises:
        ValueError: If stage is invalid
    """
    if stage not in ("ec", "ic", "qc"):
        raise ValueError(f"Invalid stage: {stage}. Must be 'ec', 'ic', or 'qc'.")

    print(f"[LOOKUP QUEUE] Stage: {stage}")

    global _global_queue_ec, _global_queue_ic, _global_queue_qc

    if stage.lower() == "ec":
        if _global_queue_ec is None:
            print(f"[LOOKUP QUEUE] Stage: ec | MISSING")
            return None
        print(f"[LOOKUP QUEUE] Stage: ec | FOUND")
        return _global_queue_ec
    elif stage.lower() == "ic":
        if _global_queue_ic is None:
            print(f"[LOOKUP QUEUE] Stage: ic | MISSING")
            return None
        print(f"[LOOKUP QUEUE] Stage: ic | FOUND")
        return _global_queue_ic
    else:
        if _global_queue_qc is None:
            print(f"[LOOKUP QUEUE] Stage: qc | MISSING")
            return None
        print(f"[LOOKUP QUEUE] Stage: qc | FOUND")
        return _global_queue_qc


def get_advisory_queue(config: Optional[AdvisoryConfig] = None, stage: str = "ic") -> AdvisoryQueue:
    """
    Get stage-scoped advisory queue instance - CREATES if absent.

    Args:
        config: Optional configuration
        stage: Advisory stage - MUST be "ec", "ic", or "qc"

    Returns:
        AdvisoryQueue instance for the specified stage

    Raises:
        ValueError: If stage is not explicitly "ec", "ic", or "qc"
    """
    if stage not in ("ec", "ic", "qc"):
        raise ValueError(f"Invalid stage: {stage}. Must be 'ec', 'ic', or 'qc'.")

    print(f"[QUEUE FACTORY] Requested Stage: {stage}")

    global _global_queue_ec, _global_queue_ic, _global_queue_qc

    stage_lower = stage.lower()
    if stage_lower == "ec":
        if _global_queue_ec is None:
            print(f"[QUEUE CREATE] Stage: ec")
            _global_queue_ec = AdvisoryQueue(config, stage="ec")
        else:
            print(f"[QUEUE REUSE] Stage: ec")
        return _global_queue_ec
    elif stage_lower == "ic":
        if _global_queue_ic is None:
            print(f"[QUEUE CREATE] Stage: ic")
            _global_queue_ic = AdvisoryQueue(config, stage="ic")
        else:
            print(f"[QUEUE REUSE] Stage: ic")
        return _global_queue_ic
    else:
        if _global_queue_qc is None:
            print(f"[QUEUE CREATE] Stage: qc")
            _global_queue_qc = AdvisoryQueue(config, stage="qc")
        else:
            print(f"[QUEUE REUSE] Stage: qc")
        return _global_queue_qc


def reset_queue_for_stage(stage: str = "ic"):
    """Reset queue for specific stage - clears memory and disk state."""
    global _global_queue_ec, _global_queue_ic, _global_queue_qc
    stage_lower = stage.lower()
    if stage_lower == "ec":
        _global_queue_ec = None
        print(f"[QUEUE RESET] Stage: ec (memory released)")
    elif stage_lower == "ic":
        _global_queue_ic = None
        print(f"[QUEUE RESET] Stage: ic (memory released)")
    else:
        _global_queue_qc = None
        print(f"[QUEUE RESET] Stage: qc (memory released)")

    queue_path = Path(f"data/cache/advisory_queue_{stage_lower}.json")
    if queue_path.exists():
        queue_path.unlink()
        print(f"[QUEUE RESET] Stage: {stage} (disk cleared)")


def clear_queue_items(stage: str = "ic"):
    """Clear all items from queue for specific stage (keeps queue object)."""
    queue = get_advisory_queue(stage=stage)
    if hasattr(queue, '_state'):
        queue._state = queue._state.__class__()
        print(f"[QUEUE CLEAR] Stage: {stage} (items cleared, state reset)")


def build_queue(
    articles: List,
    protocol_version: str = "1.0",
    stage: str = "ic",
    skip_existing: bool = True
) -> QueueState:
    """Build advisory queue from articles."""
    if stage not in ("ec", "ic", "qc"):
        raise ValueError(f"Invalid stage: {stage}. Must be 'ec', 'ic', or 'qc'.")
    queue = get_advisory_queue(stage=stage)
    print(f"[QUEUE BUILD] Built for stage: {stage}")
    return queue.build_from_articles(articles, protocol_version, stage, skip_existing)


def get_queue_stats(stage: str = "ic") -> Dict:
    """
    Get queue statistics for specific stage.
    READ-ONLY - uses lookup to never create runtime.
    """
    if stage not in ("ec", "ic", "qc"):
        raise ValueError(f"Invalid stage: {stage}. Must be 'ec', 'ic', or 'qc'.")
    print(f"[QUEUE STATS] Lookup for stage: {stage}")
    queue = lookup_queue(stage=stage)
    if queue is None:
        print(f"[QUEUE STATS] Stage: {stage} | NOT INITIALIZED")
        return {"total": 0, "pending": 0, "processing": 0, "completed": 0, "failed": 0}
    return queue.get_stats()


def reset_failed_advisories(stage: str = "ic") -> int:
    """Reset failed items for retry."""
    if stage not in ("ec", "ic", "qc"):
        raise ValueError(f"Invalid stage: {stage}. Must be 'ec', 'ic', or 'qc'.")
    print(f"[QUEUE RESET FAILED] For stage: {stage}")
    queue = get_advisory_queue(stage=stage)
    return queue.reset_failed()