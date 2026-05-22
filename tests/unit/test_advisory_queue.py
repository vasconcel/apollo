"""
Tests for AdvisoryQueue public iteration interface.

Ensures:
- pending_items property returns the correct subset
- No direct access to internal queue storage in UI layer
- Backward compatibility with get_pending()
"""
from src.advisory.advisory_queue import AdvisoryQueue
from src.advisory.advisory_models import (
    QueueItem, QueueState, AdvisoryStatus, AdvisoryConfig
)


class TestAdvisoryQueueIteration:
    """AdvisoryQueue must expose a public iteration interface."""

    def test_pending_items_returns_pending_subset(self):
        config = AdvisoryConfig(enable_queue_state=False)
        queue = AdvisoryQueue(config, stage="ic")
        items = [
            QueueItem(
                cache_key="k1", protocol_version="1.0",
                article_id="a1", stage="ic",
                status=AdvisoryStatus.PENDING, priority=0,
            ),
            QueueItem(
                cache_key="k2", protocol_version="1.0",
                article_id="a2", stage="ic",
                status=AdvisoryStatus.COMPLETED, priority=1,
            ),
            QueueItem(
                cache_key="k3", protocol_version="1.0",
                article_id="a3", stage="ic",
                status=AdvisoryStatus.PENDING, priority=2,
            ),
        ]
        queue._state = QueueState(
            total=3, pending=2, processing=0, completed=1, failed=0,
            items=items,
        )

        pending = queue.pending_items
        assert len(pending) == 2
        assert all(item.status == AdvisoryStatus.PENDING for item in pending)

    def test_pending_items_matches_get_pending(self):
        config = AdvisoryConfig(enable_queue_state=False)
        queue = AdvisoryQueue(config, stage="ic")
        items = [
            QueueItem(
                cache_key="k1", protocol_version="1.0",
                article_id="a1", stage="ic",
                status=AdvisoryStatus.PENDING, priority=0,
            ),
        ]
        queue._state = QueueState(
            total=1, pending=1, processing=0, completed=0, failed=0,
            items=items,
        )

        assert queue.pending_items == queue.get_pending()

    def test_empty_queue_returns_empty_list(self):
        config = AdvisoryConfig(enable_queue_state=False)
        queue = AdvisoryQueue(config, stage="ic")
        queue._state = QueueState()

        assert queue.pending_items == []
