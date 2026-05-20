"""
APOLLO Session Query Service

Stateless query/filter service for screening sessions.
Operates purely on article lists and explicit counter values.
Contains no Streamlit, advisory, persistence, or audit logic.

Every method accepts articles + parameters explicitly — no session objects.
"""

from typing import Dict, List, Optional, Any

from src.core.logging_config import get_logger
from src.core.workflow_state_service import WorkflowStateService

logger = get_logger("session_query")


class SessionQueryService:
    """Stateless query and filtering service for ArticleReview collections.

    All methods are @staticmethod — no instance state, no side effects,
    no persistence, no session coupling.
    """

    @staticmethod
    def get_discussion_articles(
        articles: List[Any],
    ) -> List[Any]:
        """Get all articles needing discussion at any stage."""
        return [a for a in articles if a.is_discussion_needed]

    @staticmethod
    def get_skipped_articles(
        articles: List[Any], stage: str
    ) -> List[Any]:
        """Get all articles skipped at the given stage."""
        stage_field = SessionQueryService._stage_field(stage)
        return [a for a in articles if getattr(a, stage_field, "") == "skip"]

    @staticmethod
    def get_ec_included_articles(
        articles: List[Any],
    ) -> List[Any]:
        """Get articles that passed EC stage."""
        return [a for a in articles if a.is_ec_included]

    @staticmethod
    def get_ic_included_articles(
        articles: List[Any],
    ) -> List[Any]:
        """Get articles that passed IC stage (requires EC pass first)."""
        return [a for a in articles if a.is_ic_included]

    @staticmethod
    def get_wl_articles(articles: List[Any]) -> List[Any]:
        """Get White Literature articles only."""
        return [
            a for a in articles
            if a.get_literature_type() == "WL"
            or a.metadata.get("source_sheet", "").lower()
            in ["white literature", "wl"]
        ]

    @staticmethod
    def get_gl_articles(articles: List[Any]) -> List[Any]:
        """Get Grey Literature articles only."""
        return [
            a for a in articles
            if a.get_literature_type() == "GL"
            or a.metadata.get("source_sheet", "").lower()
            in ["grey literature", "gl"]
        ]

    @staticmethod
    def filter_articles(
        articles: List[Any],
        stage: str,
        literature_type: Optional[str] = None,
        stage_decision: Optional[str] = None,
    ) -> List[Any]:
        """Filter articles by literature type and/or stage decision."""
        filtered = articles

        if literature_type:
            if literature_type == "WL":
                filtered = SessionQueryService.get_wl_articles(articles)
            elif literature_type == "GL":
                filtered = SessionQueryService.get_gl_articles(articles)

        if stage_decision:
            stage_field = SessionQueryService._stage_field(stage)
            filtered = [
                a for a in filtered
                if getattr(a, stage_field, "") == stage_decision
            ]

        return filtered

    @staticmethod
    def get_pending_for_stage(
        articles: List[Any],
        stage: str,
        ec_completed: int,
        ic_completed: int,
        skip_count: int,
    ) -> int:
        """Get count of pending (undecided) articles for stage."""
        if stage == "ec":
            return len(articles) - ec_completed - skip_count
        elif stage == "ic":
            ec_included = SessionQueryService.get_ec_included_articles(articles)
            return len(ec_included) - ic_completed - skip_count
        return 0

    @staticmethod
    def get_wl_progress(articles: List[Any]) -> Dict[str, Any]:
        """Get WL-specific progress statistics."""
        wl_articles = SessionQueryService.get_wl_articles(articles)
        wl_total = len(wl_articles)
        wl_completed = sum(
            1 for a in wl_articles
            if a.ec_stage in ["include", "exclude", "skip"]
        )
        wl_included = sum(1 for a in wl_articles if a.ec_stage == "include")
        wl_excluded = sum(1 for a in wl_articles if a.ec_stage == "exclude")

        return {
            "total": wl_total,
            "completed": wl_completed,
            "pending": wl_total - wl_completed,
            "included": wl_included,
            "excluded": wl_excluded,
            "progress_pct": int(
                (wl_completed / wl_total * 100) if wl_total > 0 else 0
            ),
        }

    @staticmethod
    def get_gl_progress(articles: List[Any]) -> Dict[str, Any]:
        """Get GL-specific progress statistics."""
        gl_articles = SessionQueryService.get_gl_articles(articles)
        gl_total = len(gl_articles)
        gl_completed = sum(
            1 for a in gl_articles
            if a.ec_stage in ["include", "exclude", "skip"]
        )
        gl_included = sum(1 for a in gl_articles if a.ec_stage == "include")
        gl_excluded = sum(1 for a in gl_articles if a.ec_stage == "exclude")

        return {
            "total": gl_total,
            "completed": gl_completed,
            "pending": gl_total - gl_completed,
            "included": gl_included,
            "excluded": gl_excluded,
            "progress_pct": int(
                (gl_completed / gl_total * 100) if gl_total > 0 else 0
            ),
        }

    @staticmethod
    def get_progress(
        articles: List[Any],
        current_index: int,
        total_count: int,
        stage: str,
        ec_completed: int,
        ic_completed: int,
        included_count: int,
        excluded_count: int,
        skip_count: int,
        discussion_count: int,
    ) -> Dict[str, Any]:
        """Get progress statistics."""
        return {
            "current": current_index + 1,
            "total": total_count,
            "stage": stage,
            "ec_completed": ec_completed,
            "ic_completed": ic_completed,
            "ec_pending": SessionQueryService.get_pending_for_stage(
                articles, "ec", ec_completed, ic_completed, skip_count
            ),
            "ic_pending": SessionQueryService.get_pending_for_stage(
                articles, "ic", ec_completed, ic_completed, skip_count
            ),
            "included": included_count,
            "excluded": excluded_count,
            "skipped": skip_count,
            "discussion": discussion_count,
        }

    @staticmethod
    def _stage_field(stage: str) -> str:
        """Get stage field name, delegated to canonical WorkflowStateService."""
        return WorkflowStateService.stage_field(stage)
