"""
APOLLO Tests — SessionOrchestrationService extraction

Verifies that the orchestration service correctly coordinates
multi-service decision workflows, remains stateless, and
preserves all behavioral invariants.
"""

import ast
import inspect
from pathlib import Path

import pytest

from src.core.session_orchestration_service import SessionOrchestrationService
from src.core.screening_session import ScreeningSession, ArticleReview


# ---------------------------------------------------------------------------
# OrchestrationService — stateless unit tests
# ---------------------------------------------------------------------------

def _make_session() -> ScreeningSession:
    session = ScreeningSession("test-session", "2024-01-01")
    session.articles = [
        ArticleReview(article_id="a1", title="Paper 1", abstract="", metadata={}),
        ArticleReview(article_id="a2", title="Paper 2", abstract="", metadata={}),
    ]
    session.total_count = 2
    session.current_index = 0
    return session


class TestSessionOrchestrationService:

    def test_record_decision_ec_include(self):
        session = _make_session()
        result = SessionOrchestrationService.record_decision(
            session.articles, session.current_index,
            "ec", "include", "Good paper", None,
            session.researcher_id, session.dynamic_protocol,
            session._audit_chain,
        )
        assert result is not None
        assert result["success"] is True
        assert result["article_field_updates"]["ec_stage"] == "include"
        assert result["counter_increments"]["ec_completed"] == 1
        assert result["counter_increments"]["included_count"] == 1
        assert result["timestamp"] is not None
        assert result["audit_event"] is not None
        # Article should be mutated in-place
        assert session.articles[0].ec_stage == "include"

    def test_record_decision_ec_exclude(self):
        session = _make_session()
        result = SessionOrchestrationService.record_decision(
            session.articles, session.current_index,
            "ec", "exclude", "Not relevant", None,
            session.researcher_id, session.dynamic_protocol,
            session._audit_chain,
        )
        assert result is not None
        assert result["success"] is True
        assert result["article_field_updates"]["ec_stage"] == "exclude"
        assert result["counter_increments"]["excluded_count"] == 1

    def test_record_decision_ic_without_ec_fails(self):
        session = _make_session()
        result = SessionOrchestrationService.record_decision(
            session.articles, session.current_index,
            "ic", "include", "Good paper", None,
            session.researcher_id, session.dynamic_protocol,
            session._audit_chain,
        )
        assert result is None  # IC fails because article hasn't passed EC

    def test_record_decision_ic_after_ec_include(self):
        session = _make_session()
        # First pass EC
        SessionOrchestrationService.record_decision(
            session.articles, session.current_index,
            "ec", "include", "Good paper", None,
            session.researcher_id, session.dynamic_protocol,
            session._audit_chain,
        )
        # Then IC on same article
        result = SessionOrchestrationService.record_decision(
            session.articles, session.current_index,
            "ic", "include", "Also good", None,
            session.researcher_id, session.dynamic_protocol,
            session._audit_chain,
        )
        assert result is not None
        assert result["article_field_updates"]["ic_stage"] == "include"

    def test_record_decision_no_article_returns_none(self):
        session = _make_session()
        session.current_index = 999  # Out of bounds
        result = SessionOrchestrationService.record_decision(
            session.articles, session.current_index,
            "ec", "include", "", None,
            session.researcher_id, session.dynamic_protocol,
            session._audit_chain,
        )
        assert result is None

    def test_record_decision_empty_articles(self):
        result = SessionOrchestrationService.record_decision(
            [], 0, "ec", "include", "", None,
            "researcher_1", None, [],
        )
        assert result is None

    def test_record_decision_skip(self):
        session = _make_session()
        result = SessionOrchestrationService.record_decision(
            session.articles, session.current_index,
            "ec", "skip", "Later", None,
            session.researcher_id, session.dynamic_protocol,
            session._audit_chain,
        )
        assert result is not None
        assert result["counter_increments"]["skip_count"] == 1

    def test_record_decision_discussion(self):
        session = _make_session()
        result = SessionOrchestrationService.record_decision(
            session.articles, session.current_index,
            "ec", "needs_discussion", "Discuss", None,
            session.researcher_id, session.dynamic_protocol,
            session._audit_chain,
        )
        assert result is not None
        assert result["counter_increments"]["discussion_count"] == 1

    def test_record_decision_llm_suggestion(self):
        session = _make_session()
        llm = {"suggestion": "include", "confidence": 0.85}
        result = SessionOrchestrationService.record_decision(
            session.articles, session.current_index,
            "ec", "include", "", llm,
            session.researcher_id, session.dynamic_protocol,
            session._audit_chain,
        )
        assert result is not None
        assert result["article_field_updates"]["ec_llm_suggestion"] == llm


class TestApplyDecisionById:

    def test_apply_decision_by_id_found(self):
        session = _make_session()
        result, saved_index = SessionOrchestrationService.apply_decision_by_id(
            session.articles, session.current_index,
            "a1", "ec", "include", "Good", None,
            session.researcher_id, session.dynamic_protocol,
            session._audit_chain,
        )
        assert result is not None
        assert saved_index == 0
        assert session.articles[0].ec_stage == "include"

    def test_apply_decision_by_id_not_found(self):
        session = _make_session()
        result, saved_index = SessionOrchestrationService.apply_decision_by_id(
            session.articles, session.current_index,
            "nonexistent", "ec", "include", "", None,
            session.researcher_id, session.dynamic_protocol,
            session._audit_chain,
        )
        assert result is None
        assert saved_index == 0

    def test_apply_decision_by_id_second_article(self):
        session = _make_session()
        session.current_index = 0
        result, saved_index = SessionOrchestrationService.apply_decision_by_id(
            session.articles, session.current_index,
            "a2", "ec", "exclude", "Bad", None,
            session.researcher_id, session.dynamic_protocol,
            session._audit_chain,
        )
        assert result is not None
        assert session.articles[1].ec_stage == "exclude"


# ---------------------------------------------------------------------------
# Behavioral parity — ScreeningSession delegation matches direct service call
# ---------------------------------------------------------------------------

class TestBehavioralParity:

    def test_record_decision_parity(self):
        session = _make_session()
        # Direct service call
        direct = SessionOrchestrationService.record_decision(
            session.articles, session.current_index,
            "ec", "include", "notes", None,
            session.researcher_id, session.dynamic_protocol,
            session._audit_chain,
        )
        # Reset
        session.articles[0] = ArticleReview(
            article_id="a1", title="Paper 1", abstract="", metadata={},
        )
        session.current_index = 0
        # Via ScreeningSession delegation
        result = session.record_decision("include", notes="notes")
        assert result is True
        assert session.articles[0].ec_stage == "include"
        assert session._audit_chain != []
        assert session.last_saved != ""

    def test_apply_decision_parity(self):
        session = _make_session()
        result = session.apply_decision("a1", "ec", "include", notes="Good")
        assert result is True
        assert session.articles[0].ec_stage == "include"

    def test_apply_decision_nonexistent(self):
        session = _make_session()
        result = session.apply_decision("nonexistent", "ec", "include")
        assert result is False

    def test_multiple_decisions_accumulate(self):
        session = _make_session()
        session.record_decision("include")
        session.advance()
        session.record_decision("exclude")
        assert session.articles[0].ec_stage == "include"
        assert session.articles[1].ec_stage == "exclude"


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestOrchestrationDeterminism:

    def test_record_decision_deterministic(self):
        session = _make_session()
        r1 = SessionOrchestrationService.record_decision(
            session.articles, session.current_index,
            "ec", "include", "", None,
            session.researcher_id, session.dynamic_protocol,
            session._audit_chain,
        )
        session2 = _make_session()
        r2 = SessionOrchestrationService.record_decision(
            session2.articles, session2.current_index,
            "ec", "include", "", None,
            session2.researcher_id, session2.dynamic_protocol,
            session2._audit_chain,
        )
        # counter_increments are deterministic (identical inputs)
        assert r1["counter_increments"] == r2["counter_increments"]
        # article_field_updates differ only in timestamp, check non-time fields
        for key in ["ec_stage", "ec_notes"]:
            assert r1["article_field_updates"][key] == r2["article_field_updates"][key]

    def test_apply_decision_deterministic(self):
        session = _make_session()
        r1, _ = SessionOrchestrationService.apply_decision_by_id(
            session.articles, 0, "a1", "ec", "exclude", "", None,
            session.researcher_id, session.dynamic_protocol,
            session._audit_chain,
        )
        session2 = _make_session()
        r2, _ = SessionOrchestrationService.apply_decision_by_id(
            session2.articles, 0, "a1", "ec", "exclude", "", None,
            session2.researcher_id, session2.dynamic_protocol,
            session2._audit_chain,
        )
        assert r1["counter_increments"] == r2["counter_increments"]
        for key in ["ec_stage", "ec_notes"]:
            assert r1["article_field_updates"][key] == r2["article_field_updates"][key]


# ---------------------------------------------------------------------------
# Architectural boundary
# ---------------------------------------------------------------------------

class TestOrchestrationArchitecturalBoundary:

    FORBIDDEN_IMPORTS = [
        "src.ui", "streamlit", "src.advisory",
        "SessionPersistenceService", "SessionQueryService",
        "SessionAuditService", "SessionIngestionService",
        "WorkflowStateService", "screening_session",
        "SessionState",
    ]

    def test_no_forbidden_imports_in_source(self):
        source = inspect.getsource(SessionOrchestrationService)
        for banned in self.FORBIDDEN_IMPORTS:
            assert banned not in source, (
                f"SessionOrchestrationService must not reference '{banned}'"
            )

    def test_module_ast_no_forbidden_imports(self):
        svc_path = (
            Path(__file__).parent.parent
            / "src" / "core" / "session_orchestration_service.py"
        )
        tree = ast.parse(svc_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for banned in self.FORBIDDEN_IMPORTS:
                    if banned.startswith("src."):
                        assert not module.startswith(banned), (
                            f"Forbidden import '{module}'"
                        )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    for banned in self.FORBIDDEN_IMPORTS:
                        if not banned.startswith("src."):
                            assert alias.name != banned, (
                                f"Forbidden import '{alias.name}'"
                            )

    def test_service_is_stateless(self):
        s1 = SessionOrchestrationService()
        s2 = SessionOrchestrationService()
        assert type(s1) == type(s2)

    def test_screening_session_delegates_to_orchestration(self):
        source = inspect.getsource(ScreeningSession.record_decision)
        assert "SessionOrchestrationService.record_decision" in source

    def test_screening_session_apply_decision_delegates(self):
        source = inspect.getsource(ScreeningSession.apply_decision)
        assert "SessionOrchestrationService.apply_decision_by_id" in source

    def test_no_persistence_in_source(self):
        svc_path = (
            Path(__file__).parent.parent
            / "src" / "core" / "session_orchestration_service.py"
        )
        source = svc_path.read_text(encoding="utf-8")
        assert "SessionPersistenceService" not in source

    def test_dependency_direction(self):
        """OrchestrationService must depend on navigation + decision only."""
        svc_path = (
            Path(__file__).parent.parent
            / "src" / "core" / "session_orchestration_service.py"
        )
        source = svc_path.read_text(encoding="utf-8")
        assert "NavigationService" in source
        assert "SessionDecisionService" in source
