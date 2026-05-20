"""
APOLLO Session Decision Service

Stateless decision orchestration service for ScreeningSession.
Handles reviewer decision application, stage enforcement, and
coordination of audit events and protocol snapshots.
"""

from datetime import datetime
from typing import Dict, List, Optional


class SessionDecisionService:
    """Stateless decision orchestration for ScreeningSession.

    All methods are @staticmethod — no instance state, no persistence,
    no navigation, no query, no ingestion logic.
    """

    @staticmethod
    def apply_review_decision(
        article,
        stage: str,
        decision: str,
        notes: str,
        llm_suggestion: Optional[Dict],
        researcher_id: str,
        dynamic_protocol: Optional[Dict],
        audit_chain: List[Dict],
    ) -> Dict:
        """Apply a reviewer decision and return all resulting effects.

        Pure computation — caller applies the returned effects to session state.

        Args:
            article: ArticleReview to apply decision to.
            stage: Current screening stage ("ec" or "ic").
            decision: Decision string (include/exclude/skip/needs_discussion).
            notes: Free-text notes.
            llm_suggestion: Optional LLM advisory snapshot.
            researcher_id: ID of the researcher.
            dynamic_protocol: Protocol dict (None if not loaded).
            audit_chain: Current audit chain list.

        Returns:
            Dict with keys:
                success (bool)
                timestamp (str)
                article_field_updates (dict) — fields to set on article
                counter_increments (dict) — counter -> delta
                audit_event (dict or None) — event to append to chain
                protocol_snapshot (dict or None) — snapshot to append
        """
        if not article:
            return {"success": False}

        if stage == "ic" and not article.can_proceed_to_stage("ic"):
            return {"success": False}

        timestamp = datetime.now().isoformat()
        article_field_updates: Dict[str, object] = {}
        counter_increments: Dict[str, int] = {}

        if stage == "ec":
            article_field_updates["ec_stage"] = decision
            article_field_updates["ec_notes"] = notes
            article_field_updates["ec_timestamp"] = timestamp
            if llm_suggestion:
                article_field_updates["ec_llm_suggestion"] = llm_suggestion
            counter_increments["ec_completed"] = counter_increments.get("ec_completed", 0) + 1

        elif stage == "ic":
            article_field_updates["ic_stage"] = decision
            article_field_updates["ic_notes"] = notes
            article_field_updates["ic_timestamp"] = timestamp
            if llm_suggestion:
                article_field_updates["ic_llm_suggestion"] = llm_suggestion
            counter_increments["ic_completed"] = counter_increments.get("ic_completed", 0) + 1

        decision_counter_map = {
            "include": "included_count",
            "exclude": "excluded_count",
            "skip": "skip_count",
            "needs_discussion": "discussion_count",
        }
        if decision in decision_counter_map:
            counter = decision_counter_map[decision]
            counter_increments[counter] = counter_increments.get(counter, 0) + 1

        from src.core.session_audit_service import SessionAuditService

        audit_event = SessionAuditService.append_event(
            audit_chain, researcher_id, article, decision, notes, stage,
        )

        protocol_snapshot = None
        if dynamic_protocol:
            from src.core.dynamic_protocol import DynamicProtocol

            protocol = DynamicProtocol.from_dict(dynamic_protocol)
            snapshot = protocol.create_snapshot(stage)
            protocol_snapshot = snapshot.to_dict()

        return {
            "success": True,
            "timestamp": timestamp,
            "article_field_updates": article_field_updates,
            "counter_increments": counter_increments,
            "audit_event": audit_event,
            "protocol_snapshot": protocol_snapshot,
        }
