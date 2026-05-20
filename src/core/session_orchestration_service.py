"""
APOLLO Session Orchestration Service

Coordinates multi-service decision workflows for ScreeningSession.
Stateless — all parameters explicit, no service, UI, advisory, or
persistence imports. Pure orchestration coordination only.
"""

from typing import Dict, List, Optional, Any

from src.core.session_navigation import NavigationService
from src.core.session_decision_service import SessionDecisionService


class SessionOrchestrationService:
    """Orchestrates multi-service workflows for ScreeningSession.

    Coordinates sequencing across NavigationService and
    SessionDecisionService. Every method is @staticmethod.
    No instance state, no persistence, no UI, no advisory.
    """

    @staticmethod
    def record_decision(
        articles: List[Any],
        current_index: int,
        stage: str,
        decision: str,
        notes: str,
        llm_suggestion: Optional[Dict],
        researcher_id: str,
        dynamic_protocol: Optional[Dict],
        audit_chain: List[Dict],
    ) -> Optional[Dict]:
        """Coordinate the full decision pipeline.

        1. Resolve current article via NavigationService.
        2. Apply review decision via SessionDecisionService.
        3. Apply article-level field updates (mutates article in-place).
        4. Return combined result dict for caller to apply state-level
           side effects (counter increments, audit, timestamps).

        Returns None if the article is missing or the decision fails.
        """
        article = NavigationService.get_current_article(articles, current_index)
        if not article:
            return None

        result = SessionDecisionService.apply_review_decision(
            article, stage, decision, notes, llm_suggestion,
            researcher_id, dynamic_protocol, audit_chain,
        )

        if not result["success"]:
            return None

        for key, value in result["article_field_updates"].items():
            setattr(article, key, value)

        return result

    @staticmethod
    def apply_decision_by_id(
        articles: List[Any],
        current_index: int,
        article_id: str,
        stage: str,
        decision: str,
        notes: str,
        llm_suggestion: Optional[Dict],
        researcher_id: str,
        dynamic_protocol: Optional[Dict],
        audit_chain: List[Dict],
    ) -> tuple:
        """Apply a decision to a specific article by article_id.

        Locates the article, delegates to record_decision at that index,
        and returns (result_dict, saved_index). The caller restores
        current_index from saved_index after applying side effects.

        Returns (None, current_index) if article_id is not found.
        """
        for idx, article in enumerate(articles):
            if article.article_id == article_id:
                result = SessionOrchestrationService.record_decision(
                    articles, idx, stage, decision, notes,
                    llm_suggestion, researcher_id,
                    dynamic_protocol, audit_chain,
                )
                return result, current_index
        return None, current_index
