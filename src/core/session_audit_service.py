"""
APOLLO Session Audit Service

Stateless audit-chain service for ScreeningSession.
Handles audit event appending, hash chaining, tamper verification,
and event retrieval. Pure functions — no side effects on session state.
"""

import hashlib
import json
import uuid
from datetime import datetime
from typing import Dict, List, Tuple


class SessionAuditService:
    """Stateless audit-chain service for ScreeningSession.

    All methods are @staticmethod — no instance state, no persistence,
    no navigation, no query, no ingestion logic.
    """

    @staticmethod
    def append_event(
        audit_chain: List[Dict],
        researcher_id: str,
        article,
        decision: str,
        notes: str,
        stage: str,
    ) -> Dict:
        """Append a new audit event and return it.

        Args:
            audit_chain: Current audit chain (list of event dicts).
            researcher_id: ID of the researcher making the decision.
            article: ArticleReview object being decided.
            decision: Decision string (include/exclude/skip/needs_discussion).
            notes: Free-text notes.
            stage: Screening stage (ec/ic).

        Returns:
            New audit event dict (caller appends to chain).
        """
        previous_hash = audit_chain[-1]["current_hash"] if audit_chain else "GENESIS"

        event_payload = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "article_id": article.article_id,
            "reviewer_id": researcher_id,
            "stage": stage,
            "decision": decision,
            "notes": notes,
        }

        payload_json = json.dumps(event_payload, sort_keys=True, ensure_ascii=False)
        current_hash = hashlib.sha256(
            (payload_json + previous_hash).encode()
        ).hexdigest()

        return {
            **event_payload,
            "previous_hash": previous_hash,
            "current_hash": current_hash,
        }

    @staticmethod
    def verify_chain(audit_chain: List[Dict]) -> Tuple[bool, List[str]]:
        """Verify audit chain integrity.

        Args:
            audit_chain: List of audit event dicts.

        Returns:
            Tuple of (is_valid: bool, errors: list)
        """
        if not audit_chain:
            return True, []

        errors = []
        expected_previous = "GENESIS"

        for i, event in enumerate(audit_chain):
            if event.get("previous_hash") != expected_previous:
                errors.append(
                    f"Event {i}: Chain broken at {event.get('event_id', 'UNKNOWN')}"
                )

            payload = {
                k: v
                for k, v in event.items()
                if k not in ("previous_hash", "current_hash")
            }
            payload_json = json.dumps(payload, sort_keys=True, ensure_ascii=False)
            computed_hash = hashlib.sha256(
                (payload_json + event.get("previous_hash", "")).encode()
            ).hexdigest()

            if computed_hash != event.get("current_hash"):
                errors.append(
                    f"Event {i}: Hash mismatch for {event.get('event_id', 'UNKNOWN')}"
                )

            expected_previous = event.get("current_hash", "")

        return len(errors) == 0, errors

    @staticmethod
    def detect_tampering(audit_chain: List[Dict]) -> Tuple[bool, List[str]]:
        """Detect tampering in audit chain.

        Args:
            audit_chain: List of audit event dicts.

        Returns:
            Tuple of (is_clean: bool, tampered_event_ids: list)
        """
        is_valid, errors = SessionAuditService.verify_chain(audit_chain)

        if is_valid:
            return True, []

        tampered = []
        for error in errors:
            if "Hash mismatch" in error:
                event_id = (
                    error.split("for ")[-1] if "for " in error else "UNKNOWN"
                )
                tampered.append(event_id)

        return False, tampered

    @staticmethod
    def get_events(audit_chain: List[Dict]) -> List[Dict]:
        """Get all audit events in order.

        Args:
            audit_chain: List of audit event dicts.

        Returns:
            Copy of the audit chain.
        """
        return list(audit_chain)
