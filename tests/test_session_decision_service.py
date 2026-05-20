"""
APOLLO Tests — Session Decision Service Extraction

Verifies that decision orchestration logic was correctly extracted from
ScreeningSession into SessionDecisionService with full behavioral parity.

Architectural boundaries tested:
- SessionDecisionService contains no Streamlit or UI imports
- SessionDecisionService contains no advisory imports
- SessionDecisionService contains no persistence/navigation/query coupling
- Delegation preserves all public decision semantics
- Stage enforcement, audit coordination, and counter updates are unchanged
"""

import pytest

from src.core.architectural_fitness import (
    assert_source_lacks,
    assert_module_ast_lacks_imports,
    assert_is_stateless,
    get_source,
    resolve_source_path,
)

from src.core.screening_session import (
    ScreeningSession, ArticleReview, SessionStage,
)
from src.core.session_decision_service import SessionDecisionService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_article():
    return ArticleReview(
        article_id="art-001", title="Test Article", abstract="Abstract",
        metadata={"literature_type": "WL"},
    )


@pytest.fixture
def empty_chain():
    return []


@pytest.fixture
def session_with_article():
    session = ScreeningSession(
        session_id="test-decision",
        created_at="2025-01-01T00:00:00",
        protocol_version="1.0",
    )
    session.articles.append(ArticleReview(
        article_id="ART-001", title="Test", abstract="abs",
        metadata={"literature_type": "WL"},
    ))
    session.total_count = 1
    return session


# ---------------------------------------------------------------------------
# SessionDecisionService — stateless unit tests
# ---------------------------------------------------------------------------

class TestSessionDecisionService:

    def test_apply_review_decision_ec(self, sample_article, empty_chain):
        result = SessionDecisionService.apply_review_decision(
            sample_article, "ec", "include", "good paper", None,
            "researcher_1", None, empty_chain,
        )
        assert result["success"] is True
        assert result["timestamp"] is not None
        assert result["article_field_updates"]["ec_stage"] == "include"
        assert result["article_field_updates"]["ec_notes"] == "good paper"
        assert "ec_timestamp" in result["article_field_updates"]
        assert result["counter_increments"]["ec_completed"] == 1
        assert result["counter_increments"]["included_count"] == 1
        assert "audit_event" in result
        assert result["audit_event"]["previous_hash"] == "GENESIS"

    def test_apply_review_decision_ic(self, sample_article, empty_chain):
        sample_article.ec_stage = "include"
        result = SessionDecisionService.apply_review_decision(
            sample_article, "ic", "include", "meets criteria", None,
            "researcher_1", None, empty_chain,
        )
        assert result["success"] is True
        assert result["article_field_updates"]["ic_stage"] == "include"
        assert result["article_field_updates"]["ic_notes"] == "meets criteria"
        assert result["counter_increments"]["ic_completed"] == 1
        assert result["counter_increments"]["included_count"] == 1

    def test_apply_review_decision_ic_fails_if_not_ec_included(self, sample_article, empty_chain):
        """IC decision should fail if article wasn't EC-included."""
        result = SessionDecisionService.apply_review_decision(
            sample_article, "ic", "include", "", None,
            "researcher_1", None, empty_chain,
        )
        assert result["success"] is False

    def test_apply_review_decision_null_article(self, empty_chain):
        result = SessionDecisionService.apply_review_decision(
            None, "ec", "include", "", None,
            "researcher_1", None, empty_chain,
        )
        assert result["success"] is False

    def test_apply_review_decision_include_counter(self, sample_article, empty_chain):
        result = SessionDecisionService.apply_review_decision(
            sample_article, "ec", "include", "", None,
            "researcher_1", None, empty_chain,
        )
        assert result["counter_increments"].get("included_count") == 1

    def test_apply_review_decision_exclude_counter(self, sample_article, empty_chain):
        result = SessionDecisionService.apply_review_decision(
            sample_article, "ec", "exclude", "", None,
            "researcher_1", None, empty_chain,
        )
        assert result["counter_increments"].get("excluded_count") == 1

    def test_apply_review_decision_skip_counter(self, sample_article, empty_chain):
        result = SessionDecisionService.apply_review_decision(
            sample_article, "ec", "skip", "", None,
            "researcher_1", None, empty_chain,
        )
        assert result["counter_increments"].get("skip_count") == 1

    def test_apply_review_decision_discussion_counter(self, sample_article, empty_chain):
        result = SessionDecisionService.apply_review_decision(
            sample_article, "ec", "needs_discussion", "", None,
            "researcher_1", None, empty_chain,
        )
        assert result["counter_increments"].get("discussion_count") == 1

    def test_apply_review_decision_llm_suggestion(self, sample_article, empty_chain):
        llm = {"advisory": "include", "confidence": 0.85}
        result = SessionDecisionService.apply_review_decision(
            sample_article, "ec", "include", "", llm,
            "researcher_1", None, empty_chain,
        )
        assert result["article_field_updates"].get("ec_llm_suggestion") == llm

    def test_apply_review_decision_without_protocol(self, sample_article, empty_chain):
        result = SessionDecisionService.apply_review_decision(
            sample_article, "ec", "include", "", None,
            "researcher_1", None, empty_chain,
        )
        assert result["protocol_snapshot"] is None


# ---------------------------------------------------------------------------
# ScreeningSession delegation — ensures session calls the service
# ---------------------------------------------------------------------------

class TestScreeningSessionDecisionDelegation:

    def test_record_decision_delegates(self):
        assert "SessionOrchestrationService.record_decision" in get_source(
            ScreeningSession.record_decision
        )


# ---------------------------------------------------------------------------
# Behavioral parity — session decision methods work identically
# ---------------------------------------------------------------------------

class TestDecisionBehavioralParity:

    def test_record_decision_updates_article(self, session_with_article):
        session_with_article.record_decision("include", notes="Good paper")
        article = session_with_article.articles[0]
        assert article.ec_stage == "include"
        assert article.ec_notes == "Good paper"

    def test_record_decision_increments_counters(self, session_with_article):
        session_with_article.record_decision("include")
        assert session_with_article.ec_completed == 1
        assert session_with_article.included_count == 1

    def test_record_decision_exclude(self, session_with_article):
        session_with_article.record_decision("exclude")
        assert session_with_article.excluded_count == 1
        assert session_with_article.articles[0].ec_stage == "exclude"

    def test_record_decision_skip(self, session_with_article):
        session_with_article.record_decision("skip")
        assert session_with_article.skip_count == 1
        assert session_with_article.articles[0].ec_stage == "skip"

    def test_record_decision_needs_discussion(self, session_with_article):
        session_with_article.record_decision("needs_discussion")
        assert session_with_article.discussion_count == 1

    def test_record_decision_no_article_returns_false(self):
        session = ScreeningSession(
            session_id="empty-test", created_at="2025-01-01T00:00:00",
        )
        result = session.record_decision("include")
        assert result is False

    def test_record_decision_appends_audit_event(self, session_with_article):
        session_with_article.record_decision("include")
        assert len(session_with_article._audit_chain) == 1
        assert session_with_article._audit_chain[0]["decision"] == "include"

    def test_record_decision_updates_last_saved(self, session_with_article):
        session_with_article.last_saved = ""
        session_with_article.record_decision("include")
        assert session_with_article.last_saved != ""

    def test_apply_decision_by_id(self, session_with_article):
        session_with_article.apply_decision("ART-001", "ec", "include", notes="via apply")
        article = session_with_article.articles[0]
        assert article.ec_stage == "include"
        assert article.ec_notes == "via apply"

    def test_apply_decision_nonexistent_id(self, session_with_article):
        result = session_with_article.apply_decision("NONEXISTENT", "ec", "include")
        assert result is False

    def test_apply_decision_restores_index(self, session_with_article):
        session_with_article.record_decision("include")
        session_with_article.current_index = 0
        # Add a second article
        session_with_article.articles.append(ArticleReview(
            article_id="ART-002", title="Test2", abstract="abs2",
            metadata={"literature_type": "WL"},
        ))
        session_with_article.total_count = 2
        session_with_article.current_index = 1
        session_with_article.apply_decision("ART-001", "ec", "include")
        assert session_with_article.current_index == 1

    def test_multiple_decisions_audit_chain(self, session_with_article):
        for decision in ["include", "exclude", "include"]:
            session_with_article.record_decision(decision)
        assert len(session_with_article._audit_chain) == 3
        is_valid, errors = session_with_article.verify_audit_chain()
        assert is_valid is True


# ---------------------------------------------------------------------------
# Determinism — same inputs produce same decision results
# ---------------------------------------------------------------------------

class TestDecisionDeterminism:

    def test_apply_review_decision_deterministic(self, sample_article, empty_chain):
        r1 = SessionDecisionService.apply_review_decision(
            sample_article, "ec", "include", "notes", None,
            "researcher_1", None, empty_chain,
        )
        r2 = SessionDecisionService.apply_review_decision(
            sample_article, "ec", "include", "notes", None,
            "researcher_1", None, empty_chain,
        )
        # Timestamps and event_ids will differ by definition; compare deterministic fields
        assert r1["success"] == r2["success"]
        # article_field_updates: ec_timestamp differs, so compare excluding it
        for key in r1["article_field_updates"]:
            if key != "ec_timestamp":
                assert r1["article_field_updates"][key] == r2["article_field_updates"][key]
        assert r1["counter_increments"] == r2["counter_increments"]

    def test_multiple_decision_runs_same_counters(self, session_with_article):
        session_with_article.record_decision("include")
        ec1 = session_with_article.ec_completed
        inc1 = session_with_article.included_count

        session2 = ScreeningSession(
            session_id="test-copy", created_at="2025-01-01T00:00:00",
        )
        session2.articles.append(ArticleReview(
            article_id="ART-001", title="Test", abstract="abs",
            metadata={"literature_type": "WL"},
        ))
        session2.total_count = 1
        session2.record_decision("include")
        assert session2.ec_completed == ec1
        assert session2.included_count == inc1


# ---------------------------------------------------------------------------
# Architectural boundary — SessionDecisionService has restricted dependencies
# ---------------------------------------------------------------------------

class TestDecisionArchitecturalBoundary:

    IMPORT_BLACKLIST = [
        "src.ui", "streamlit", "src.advisory",
        "SessionPersistenceService", "NavigationService",
        "SessionQueryService", "SessionIngestionService",
    ]

    def test_no_forbidden_imports_in_source(self):
        assert_source_lacks(
            get_source(SessionDecisionService),
            self.IMPORT_BLACKLIST,
            "SessionDecisionService",
        )

    def test_module_ast_no_forbidden_imports(self):
        assert_module_ast_lacks_imports(
            resolve_source_path(__file__, "src", "core", "session_decision_service.py"),
            self.IMPORT_BLACKLIST,
            "session_decision_service.py",
        )

    def test_screening_session_delegates_to_decision(self):
        assert "SessionOrchestrationService.record_decision" in get_source(
            ScreeningSession.record_decision
        )

    def test_session_decision_service_is_stateless(self):
        assert_is_stateless(SessionDecisionService)
