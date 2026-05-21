"""APOLLO Architecture Governance — DAG Enforcement.

Verifies the canonical dependency hierarchy for the deterministic session core:

Layer 0 — Zero-dependency leaves:
    SessionState, SessionAuditService, WorkflowStateService

Layer 1 — Primitive services (depend only on Layer 0):
    NavigationService, SessionQueryService, SessionPersistenceService,
    SessionIngestionService, SessionDecisionService

Layer 2 — Orchestration service (depends only on Layer 1 primitives):
    SessionOrchestrationService

Layer 3 — Façade (depends on all lower layers):
    ScreeningSession
"""

import pytest

from src.core.architectural_fitness import (
    assert_source_lacks,
    assert_source_has,
    assert_module_ast_lacks_imports,
    get_source,
    resolve_source_path,
)
from src.core.workflow_state_service import WorkflowStateService
from src.core.session_state import SessionState
from src.core.session_audit_service import SessionAuditService
from src.core.session_navigation import NavigationService
from src.core.session_query_service import SessionQueryService
from src.core.session_persistence_service import SessionPersistenceService
from src.core.session_ingestion_service import SessionIngestionService
from src.core.session_decision_service import SessionDecisionService
from src.core.session_orchestration_service import SessionOrchestrationService
from src.core.screening_session import ScreeningSession


# ---------------------------------------------------------------------------
# Layer 0: Zero-dependency leaves
# ---------------------------------------------------------------------------

class TestWorkflowStateServiceGovernance:

    def test_no_session_service_imports(self):
        """WorkflowStateService must not import any session service."""
        assert_module_ast_lacks_imports(
            resolve_source_path(__file__, "src", "core", "workflow_state_service.py"),
            ["src.core"],
            "workflow_state_service.py",
        )

    def test_no_ui_or_advisory(self):
        """WorkflowStateService must not import UI/advisory."""
        source = get_source(WorkflowStateService)
        assert_source_lacks(
            source,
            ["streamlit", "src.ui", "src.advisory"],
            "WorkflowStateService",
        )


class TestSessionAuditServiceGovernance:

    def test_no_session_service_imports(self):
        """SessionAuditService must not import any session service."""
        source = get_source(SessionAuditService)
        assert_source_lacks(
            source,
            [
                "NavigationService", "SessionQueryService",
                "SessionPersistenceService", "SessionIngestionService",
                "SessionDecisionService", "SessionOrchestrationService",
                "workflow_state_service",
            ],
            "SessionAuditService",
        )

    def test_no_ui_or_advisory(self):
        source = get_source(SessionAuditService)
        assert_source_lacks(
            source,
            ["streamlit", "src.ui", "src.advisory"],
            "SessionAuditService",
        )


class TestSessionStateGovernance:

    def test_no_service_imports(self):
        """SessionState must not import any service class."""
        source = get_source(SessionState)
        assert_source_lacks(
            source,
            [
                "NavigationService", "SessionQueryService",
                "SessionPersistenceService", "SessionIngestionService",
                "SessionAuditService", "SessionDecisionService",
                "SessionOrchestrationService", "WorkflowStateService",
                "ScreeningSession",
            ],
            "SessionState",
        )


# ---------------------------------------------------------------------------
# Layer 1: Primitive services
# ---------------------------------------------------------------------------

class TestNavigationServiceGovernance:

    def test_no_orchestration_or_facade_imports(self):
        assert_module_ast_lacks_imports(
            resolve_source_path(__file__, "src", "core", "session_navigation.py"),
            ["src.core.session_orchestration", "src.core.screening_session",
             "src.core.session_decision"],
            "session_navigation.py",
        )


class TestSessionQueryServiceGovernance:

    def test_no_orchestration_or_facade_imports(self):
        assert_module_ast_lacks_imports(
            resolve_source_path(__file__, "src", "core", "session_query_service.py"),
            ["src.core.session_orchestration", "src.core.screening_session",
             "src.core.session_decision"],
            "session_query_service.py",
        )


class TestSessionPersistenceServiceGovernance:

    def test_no_orchestration_or_facade_imports(self):
        assert_module_ast_lacks_imports(
            resolve_source_path(__file__, "src", "core", "session_persistence_service.py"),
            ["src.core.session_orchestration", "src.core.screening_session",
             "src.core.session_decision", "src.core.session_query",
             "src.core.session_navigation", "src.core.session_ingestion",
             "src.core.session_audit"],
            "session_persistence_service.py",
        )


class TestSessionIngestionServiceGovernance:

    def test_no_orchestration_or_facade_imports(self):
        """SessionIngestionService imports ArticleReview dataclass
        from screening_session, but must not import the session facade or
        orchestration."""
        assert_module_ast_lacks_imports(
            resolve_source_path(__file__, "src", "core", "session_ingestion_service.py"),
            ["src.core.session_orchestration",
             "src.core.session_decision", "src.core.session_query",
             "src.core.session_navigation", "src.core.session_persistence",
             "src.core.session_audit", "src.core.workflow_state"],
            "session_ingestion_service.py",
        )


class TestSessionDecisionServiceGovernance:

    def test_no_orchestration_or_facade_imports(self):
        assert_module_ast_lacks_imports(
            resolve_source_path(__file__, "src", "core", "session_decision_service.py"),
            ["src.core.session_orchestration", "src.core.screening_session",
             "src.core.session_query", "src.core.session_navigation",
             "src.core.session_persistence", "src.core.session_ingestion",
             "src.core.workflow_state"],
            "session_decision_service.py",
        )


# ---------------------------------------------------------------------------
# Layer 2: Orchestration service
# ---------------------------------------------------------------------------

class TestSessionOrchestrationServiceGovernance:

    def test_imports_only_navigation_and_decision(self):
        """SessionOrchestrationService depends only on NavigationService
        and SessionDecisionService."""
        source = resolve_source_path(
            __file__, "src", "core", "session_orchestration_service.py"
        ).read_text(encoding="utf-8")
        assert_source_has(
            source,
            [
                "from src.core.session_navigation import NavigationService",
                "from src.core.session_decision_service import SessionDecisionService",
            ],
            "SessionOrchestrationService",
        )
        assert_module_ast_lacks_imports(
            resolve_source_path(
                __file__, "src", "core", "session_orchestration_service.py"
            ),
            ["src.core.session_query", "src.core.session_persistence",
             "src.core.session_ingestion", "src.core.session_audit",
             "src.core.workflow_state", "src.core.screening_session",
             "src.core.session_state"],
            "session_orchestration_service.py",
        )


# ---------------------------------------------------------------------------
# Layer 3: Façade
# ---------------------------------------------------------------------------

class TestScreeningSessionGovernance:

    def test_no_streamlit_ui_advisory(self):
        """ScreeningSession must not import UI or advisory layers."""
        source = get_source(ScreeningSession)
        assert_source_lacks(
            source,
            ["streamlit", "src.ui", "src.advisory"],
            "ScreeningSession",
        )

    def test_imports_all_core_services(self):
        """ScreeningSession must reference every core service for delegation."""
        source = get_source(ScreeningSession)
        assert_source_has(
            source,
            [
                "NavigationService",
                "SessionQueryService",
                "SessionPersistenceService",
                "SessionIngestionService",
                "SessionAuditService",
                "SessionOrchestrationService",
                "SessionState",
            ],
            "ScreeningSession",
        )

    def test_session_decision_accessible_via_orchestration(self):
        """SessionDecisionService is reachable through orchestration, not directly."""
        source = get_source(ScreeningSession)
        assert "SessionDecisionService" not in source


# ---------------------------------------------------------------------------
# Cross-cutting: No circular dependencies
# ---------------------------------------------------------------------------

class TestNoCircularDependencies:

    def test_session_state_imports_nothing(self):
        """SessionState is the foundational leaf."""
        assert_module_ast_lacks_imports(
            resolve_source_path(__file__, "src", "core", "session_state.py"),
            ["src.core"],
            "session_state.py",
        )

    def test_workflow_state_imports_no_services(self):
        assert_module_ast_lacks_imports(
            resolve_source_path(__file__, "src", "core", "workflow_state_service.py"),
            ["src.core.session_navigation", "src.core.session_query",
             "src.core.session_persistence", "src.core.session_ingestion",
             "src.core.session_audit", "src.core.session_decision",
             "src.core.session_orchestration", "src.core.screening_session",
             "src.core.session_state"],
            "workflow_state_service.py",
        )

    def test_audit_service_imports_no_services(self):
        assert_module_ast_lacks_imports(
            resolve_source_path(__file__, "src", "core", "session_audit_service.py"),
            ["src.core"],
            "session_audit_service.py",
        )
