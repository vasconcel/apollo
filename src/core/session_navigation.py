"""
APOLLO Session Navigation Service

Stateless navigation service for screening sessions.
Operates purely on article lists and index values.
Contains no Streamlit, advisory, or persistence logic.
"""

from typing import List, Optional, Any

from src.core.logging_config import get_logger

logger = get_logger("session_navigation")


class NavigationService:
    """Stateless navigation service for ScreeningSession.

    Every method takes explicit (articles, current_index, ...) parameters —
    no internal state, no side effects, no persistence.
    """

    @staticmethod
    def get_current_article(articles: List[Any], current_index: int) -> Optional[Any]:
        """Get article at current index, or None if out of bounds."""
        if 0 <= current_index < len(articles):
            return articles[current_index]
        return None

    @staticmethod
    def is_valid_index(articles: List[Any], current_index: int) -> bool:
        """Check if current index is within valid bounds."""
        return 0 <= current_index < len(articles)

    @staticmethod
    def clamp_index(current_index: int, total_count: int) -> int:
        """Clamp index to [0, total_count - 1]."""
        if total_count <= 0:
            return 0
        return max(0, min(current_index, total_count - 1))

    @staticmethod
    def next_index(current_index: int, total_count: int) -> int:
        """Get next index (bounds-safe)."""
        if total_count <= 0:
            return 0
        return min(current_index + 1, total_count - 1)

    @staticmethod
    def previous_index(current_index: int) -> int:
        """Get previous index (bounds-safe, clamped at 0)."""
        return max(current_index - 1, 0)

    @staticmethod
    def can_review_current_at_stage(
        articles: List[Any], current_index: int, stage: str
    ) -> bool:
        """Check if current article can be reviewed at the given stage."""
        article = NavigationService.get_current_article(articles, current_index)
        if not article:
            return False
        return article.can_proceed_to_stage(stage)

    @staticmethod
    def skip_unreviewable(
        articles: List[Any], current_index: int, stage: str
    ) -> int:
        """Skip articles that can't be reviewed at current stage.

        Returns the new index (current_index if no skip needed,
        current_index + 1 if current article can't proceed).
        """
        article = NavigationService.get_current_article(articles, current_index)
        if not article:
            return current_index
        if not article.can_proceed_to_stage(stage):
            return current_index + 1
        return current_index

    @staticmethod
    def advance(
        articles: List[Any], current_index: int, stage: str, skip: bool = False
    ) -> int:
        """Move to next undecided article with workflow rules.

        If skip=True, unconditionally advance by 1.
        Otherwise, advance past all decided articles at this stage.

        Returns the new index.
        """
        if skip:
            return current_index + 1

        idx = current_index
        while idx < len(articles):
            article = articles[idx]
            stage_field = NavigationService._stage_field(stage)
            decision = getattr(article, stage_field, "")
            if decision == "":
                break
            idx += 1
        return idx

    @staticmethod
    def is_complete(current_index: int, total_count: int, stage: str) -> bool:
        """Check if navigation is complete (past end or stage is 'complete')."""
        return stage == "complete" or current_index >= total_count

    @staticmethod
    def _stage_field(stage: str) -> str:
        """Get stage field name ('ec' -> 'ec_stage', 'ic' -> 'ic_stage')."""
        stage_map = {"ec": "ec_stage", "ic": "ic_stage"}
        return stage_map.get(stage, "")
