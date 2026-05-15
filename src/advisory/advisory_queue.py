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
    
    def __init__(self, config: Optional[AdvisoryConfig] = None):
        self.config = config or AdvisoryConfig()
        self._queue_path = Path(self.config.queue_state_path)
        
        self._state: Optional[QueueState] = None
        
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
        skip_existing: bool = True
    ) -> QueueState:
        """
        Build queue from article list.
        
        Args:
            articles: List of article objects
            protocol_version: Protocol version to use
            skip_existing: Skip articles with existing advisories
            
        Returns:
            QueueState with populated items
        """
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
        return pending[0]
    
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


_global_queue: Optional[AdvisoryQueue] = None


def get_advisory_queue(config: Optional[AdvisoryConfig] = None) -> AdvisoryQueue:
    """Get global advisory queue instance."""
    global _global_queue
    if _global_queue is None:
        _global_queue = AdvisoryQueue(config)
    return _global_queue


def build_queue(
    articles: List,
    protocol_version: str = "1.0",
    skip_existing: bool = True
) -> QueueState:
    """Build advisory queue from articles."""
    queue = get_advisory_queue()
    return queue.build_from_articles(articles, protocol_version, skip_existing)


def get_queue_stats() -> Dict:
    """Get queue statistics."""
    queue = get_advisory_queue()
    return queue.get_stats()


def reset_failed_advisories() -> int:
    """Reset failed items for retry."""
    queue = get_advisory_queue()
    return queue.reset_failed()