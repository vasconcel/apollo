"""
APOLLO Mutation Operators — Deterministic Invariant Surface Probes

Each operator represents exactly ONE plausible deterministic regression class.
Mutations are runtime-only (monkeypatching), reversible, and locally contained.

Usage:
    with SerializationFieldOmission(session).apply():
        # session.to_dict() now omits a field
        ...

Anti-gamification:
    - No optimization for mutation count or detection rate
    - Equivalent mutations are valid and expected
    - Failure to detect means the invariant is robust, not that the test failed
"""

import hashlib
import json
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

from src.core.session_persistence_service import CHECKSUM_FIELDS, SessionPersistenceService
from src.core.session_audit_service import SessionAuditService
from src.core.workflow_state_service import WorkflowStateService
from src.core.session_navigation import NavigationService
from src.core.session_query_service import SessionQueryService


# ---------------------------------------------------------------------------
# Mutation base — reversible monkeypatching context manager
# ---------------------------------------------------------------------------

@contextmanager
def _patch(module, name, replacement):
    """Reversible monkeypatch context manager.

    Saves original, applies replacement, yields, restores original.
    Guarantees restoration even if the body raises.
    """
    original = getattr(module, name, None)
    setattr(module, name, replacement)
    try:
        yield
    finally:
        if original is not None:
            setattr(module, name, original)
        else:
            delattr(module, name)


# ---------------------------------------------------------------------------
# 1. Serialization Drift Mutation
# ---------------------------------------------------------------------------

class SerializationFieldOmission:
    """Omits a deterministic field from the serialization dict.

    Invariant target: to_dict() output must include all deterministic fields.
    Regression class: Accidental field removal during refactoring.
    Detection mechanism: Checksum mismatch on roundtrip.
    """

    def __init__(self, session, omitted_field: str = "ec_completed"):
        self.session = session
        self.omitted_field = omitted_field

    @contextmanager
    def apply(self):
        """Apply field omission mutation to compute_checksum()."""
        omitted = self.omitted_field
        original_checksum = self.session.compute_checksum
        original_to_dict = self.session._to_dict_full

        def mutated():
            d = original_to_dict()
            d.pop(omitted, None)
            return SessionPersistenceService.compute_checksum(d)

        self.session.compute_checksum = mutated
        try:
            yield
        finally:
            self.session.compute_checksum = original_checksum


# ---------------------------------------------------------------------------
# 2. Checksum Boundary Mutation
# ---------------------------------------------------------------------------

class ChecksumFieldAddition:
    """Adds a non-deterministic field to the checksum input set.

    Invariant target: CHECKSUM_FIELDS must include only deterministic fields.
    Regression class: Accidentally adding last_saved or timestamp to checksum.
    Detection mechanism: Checksum instability across loads.
    """

    def __init__(self, extra_field: str = "qc_completed"):
        self.extra_field = extra_field
        self._original_fields = list(CHECKSUM_FIELDS)

    @contextmanager
    def apply(self):
        from src.core import session_persistence_service as sps

        original = sps.CHECKSUM_FIELDS
        mutated = list(original) + [self.extra_field]

        sps.CHECKSUM_FIELDS = mutated
        try:
            yield
        finally:
            sps.CHECKSUM_FIELDS = original


class ChecksumSortKeysRemoval:
    """Removes sort_keys=True from checksum serialization.

    Invariant target: Checksum must use deterministic sort_keys serialization.
    Regression class: Accidental removal of sort_keys parameter.
    Detection mechanism: Checksum mismatch across environments.
    """

    @contextmanager
    def apply(self):
        from src.core import session_persistence_service as sps
        original = sps.SessionPersistenceService.compute_checksum

        def mutated(full_data):
            data_for_check = {
                k: full_data.get(k)
                for k in sps.CHECKSUM_FIELDS if k in full_data
            }
            canonical_json = json.dumps(
                data_for_check, sort_keys=False, ensure_ascii=False,
            )
            return hashlib.sha256(canonical_json.encode()).hexdigest()

        sps.SessionPersistenceService.compute_checksum = staticmethod(mutated)
        try:
            yield
        finally:
            sps.SessionPersistenceService.compute_checksum = original


# ---------------------------------------------------------------------------
# 3. Workflow Transition Mutation
# ---------------------------------------------------------------------------

class WorkflowStageReordering:
    """Reverses the EC → IC stage order.

    Invariant target: STAGE_ORDER must be ["ec", "ic", "qc", "complete"].
    Regression class: Accidental stage reordering during refactoring.
    Detection mechanism: can_transition_to_stage() detects illegal transitions.
    """

    @contextmanager
    def apply(self):
        original_order = list(WorkflowStateService.STAGE_ORDER)
        mutated = ["ic", "ec", "qc", "complete"]

        WorkflowStateService.STAGE_ORDER = mutated
        try:
            yield
        finally:
            WorkflowStateService.STAGE_ORDER = original_order


class WorkflowTransitionBlocked:
    """Blocks EC → IC transition (always returns False).

    Invariant target: Legal transitions must be allowed.
    Regression class: Accidental blocking of transitions.
    Detection mechanism: Transition validation failures.
    """

    @contextmanager
    def apply(self):
        original = WorkflowStateService.can_transition_to_stage

        def mutated(current_stage, target_stage):
            if current_stage == "ec" and target_stage == "ic":
                return False
            return original(current_stage, target_stage)

        WorkflowStateService.can_transition_to_stage = staticmethod(mutated)
        try:
            yield
        finally:
            WorkflowStateService.can_transition_to_stage = original


# ---------------------------------------------------------------------------
# 4. Navigation Mutation
# ---------------------------------------------------------------------------

class NavigationOffByOne:
    """Adds +1 offset to advance() return value.

    Invariant target: advance() must return correct next index.
    Regression class: Off-by-one error during index manipulation refactoring.
    Detection mechanism: Navigation parity comparison across runs.
    """

    @contextmanager
    def apply(self):
        original = NavigationService.advance

        def mutated(articles, current_index, stage, skip=False):
            idx = original(articles, current_index, stage, skip)
            return min(idx + 1, len(articles))

        NavigationService.advance = staticmethod(mutated)
        try:
            yield
        finally:
            NavigationService.advance = original


class NavigationSkipInversion:
    """Inverts skip logic: advance(skip=True) stops instead of advancing.

    Invariant target: skip=True must advance unconditionally.
    Regression class: Skip flag logic inversion.
    Detection mechanism: Navigation behavior divergence.
    """

    @contextmanager
    def apply(self):
        original = NavigationService.advance

        def mutated(articles, current_index, stage, skip=False):
            if skip:
                return current_index
            return original(articles, current_index, stage, False)

        NavigationService.advance = staticmethod(mutated)
        try:
            yield
        finally:
            NavigationService.advance = original


# ---------------------------------------------------------------------------
# 5. Audit Chain Mutation
# ---------------------------------------------------------------------------

class AuditHashBroken:
    """Breaks hash chaining by using a fixed previous_hash.

    Invariant target: Each audit event must chain to the previous event's hash.
    Regression class: Hash chain linking logic broken during refactoring.
    Detection mechanism: verify_chain() detects chain break.
    """

    @contextmanager
    def apply(self):
        original = SessionAuditService.append_event

        def mutated(audit_chain, researcher_id, article, decision, notes, stage):
            previous_hash = "FIXED_BROKEN_HASH" if audit_chain else "GENESIS"
            import uuid
            from datetime import datetime
            event_payload = {
                "event_id": str(uuid.uuid4()),
                "timestamp": datetime.now().isoformat(),
                "article_id": article.article_id,
                "reviewer_id": researcher_id,
                "stage": stage,
                "decision": decision,
                "notes": notes,
            }
            payload_json = json.dumps(
                event_payload, sort_keys=True, ensure_ascii=False
            )
            current_hash = hashlib.sha256(
                (payload_json + previous_hash).encode()
            ).hexdigest()
            return {
                **event_payload,
                "previous_hash": previous_hash,
                "current_hash": current_hash,
            }

        SessionAuditService.append_event = staticmethod(mutated)
        try:
            yield
        finally:
            SessionAuditService.append_event = original


class AuditVerificationWeakened:
    """Weakens verify_chain to always return True.

    Invariant target: verify_chain must detect audit chain corruption.
    Regression class: Tamper detection accidentally disabled.
    Detection mechanism: Corrupted fixtures no longer detected.
    """

    @contextmanager
    def apply(self):
        original = SessionAuditService.verify_chain

        def mutated(audit_chain):
            return True, []

        SessionAuditService.verify_chain = staticmethod(mutated)
        try:
            yield
        finally:
            SessionAuditService.verify_chain = original


# ---------------------------------------------------------------------------
# 6. Query Semantic Mutation
# ---------------------------------------------------------------------------

class QueryDiscussionArticlesOmission:
    """Omits discussion articles from get_discussion_articles.

    Invariant target: All articles needing discussion must be returned.
    Regression class: Filter predicate accidentally excludes discussion.
    Detection mechanism: Discussion count mismatches.
    """

    @contextmanager
    def apply(self):
        original = SessionQueryService.get_discussion_articles

        def mutated(articles):
            return []

        SessionQueryService.get_discussion_articles = staticmethod(mutated)
        try:
            yield
        finally:
            SessionQueryService.get_discussion_articles = original


class QueryWlGlInversion:
    """Swaps WL and GL classification.

    Invariant target: get_wl_articles and get_gl_articles must classify correctly.
    Regression class: Literature type classification logic inverted.
    Detection mechanism: WL/GL count parity mismatches.
    """

    @contextmanager
    def apply(self):
        original_wl = SessionQueryService.get_wl_articles
        original_gl = SessionQueryService.get_gl_articles

        SessionQueryService.get_wl_articles = original_gl
        SessionQueryService.get_gl_articles = original_wl
        try:
            yield
        finally:
            SessionQueryService.get_wl_articles = original_wl
            SessionQueryService.get_gl_articles = original_gl


# ---------------------------------------------------------------------------
# 7. Replay Parity Mutation
# ---------------------------------------------------------------------------

class ReplayChecksumAlwaysSame:
    """Makes compute_checksum return a constant value.

    Invariant target: Checksum must reflect actual session content.
    Regression class: Checksum computation accidentally disconnected from data.
    Detection mechanism: Different sessions produce same checksum.
    """

    def __init__(self, session, constant: str = "aa" * 32):
        self.session = session
        self.constant = constant

    @contextmanager
    def apply(self):
        original = self.session.compute_checksum

        def mutated():
            return self.constant

        self.session.compute_checksum = mutated
        try:
            yield
        finally:
            self.session.compute_checksum = original


class ReplaySerializationCacheStale:
    """Returns stale (cached) serialization that differs from current state.

    Invariant target: _to_dict_full must reflect current session state.
    Regression class: Stale cache returned instead of fresh serialization.
    Detection mechanism: Save/load roundtrip produces field mismatches.
    """

    def __init__(self, session, stale_field: str = "stage", stale_value: str = "complete"):
        self.session = session
        self.stale_field = stale_field
        self.stale_value = stale_value

    @contextmanager
    def apply(self):
        original = self.session._to_dict_full
        stale_val = self.stale_value
        stale_key = self.stale_field

        def mutated():
            d = original()
            d[stale_key] = stale_val
            return d

        self.session._to_dict_full = mutated
        try:
            yield
        finally:
            self.session._to_dict_full = original


# ---------------------------------------------------------------------------
# Operator registry
# ---------------------------------------------------------------------------

OPERATOR_REGISTRY = {
    "serialization_field_omission": SerializationFieldOmission,
    "checksum_field_addition": ChecksumFieldAddition,
    "checksum_sort_keys_removal": ChecksumSortKeysRemoval,
    "workflow_stage_reordering": WorkflowStageReordering,
    "workflow_transition_blocked": WorkflowTransitionBlocked,
    "navigation_off_by_one": NavigationOffByOne,
    "navigation_skip_inversion": NavigationSkipInversion,
    "audit_hash_broken": AuditHashBroken,
    "audit_verification_weakened": AuditVerificationWeakened,
    "query_discussion_omission": QueryDiscussionArticlesOmission,
    "query_wl_gl_inversion": QueryWlGlInversion,
    "replay_checksum_always_same": ReplayChecksumAlwaysSame,
    "replay_serialization_cache_stale": ReplaySerializationCacheStale,
}
