"""
APOLLO Tests — Workflow State Service Extraction

Verifies that workflow/state-transition semantics are correctly
centralized in WorkflowStateService.

Architectural boundaries tested:
- WorkflowStateService contains no Streamlit or UI imports
- WorkflowStateService contains no advisory imports
- WorkflowStateService contains no persistence/navigation/query/audit coupling
- Stage field mappings are deterministic
- Stage transition rules match workflow semantics
- Completion checks are consistent
"""

import pytest

from src.core.architectural_fitness import (
    assert_source_lacks,
    assert_module_ast_lacks_imports,
    assert_is_stateless,
    get_source,
    resolve_source_path,
)
from src.core.workflow_state_service import WorkflowStateService


# ---------------------------------------------------------------------------
# WorkflowStateService — stateless unit tests
# ---------------------------------------------------------------------------

class TestWorkflowStateService:

    def test_stage_field_ec(self):
        assert WorkflowStateService.stage_field("ec") == "ec_stage"

    def test_stage_field_ic(self):
        assert WorkflowStateService.stage_field("ic") == "ic_stage"

    def test_stage_field_unknown(self):
        assert WorkflowStateService.stage_field("qc") == ""
        assert WorkflowStateService.stage_field("complete") == ""
        assert WorkflowStateService.stage_field("invalid") == ""

    def test_stage_counter_ec(self):
        assert WorkflowStateService.stage_counter("ec") == "ec_completed"

    def test_stage_counter_ic(self):
        assert WorkflowStateService.stage_counter("ic") == "ic_completed"

    def test_stage_counter_unknown(self):
        assert WorkflowStateService.stage_counter("qc") == ""
        assert WorkflowStateService.stage_counter("complete") == ""

    def test_is_valid_stage(self):
        assert WorkflowStateService.is_valid_stage("ec") is True
        assert WorkflowStateService.is_valid_stage("ic") is True
        assert WorkflowStateService.is_valid_stage("qc") is True
        assert WorkflowStateService.is_valid_stage("complete") is True
        assert WorkflowStateService.is_valid_stage("invalid") is False
        assert WorkflowStateService.is_valid_stage("") is False

    def test_can_transition_to_stage_valid(self):
        assert WorkflowStateService.can_transition_to_stage("ec", "ic") is True
        assert WorkflowStateService.can_transition_to_stage("ic", "qc") is True
        assert WorkflowStateService.can_transition_to_stage("qc", "complete") is True

    def test_can_transition_to_stage_same(self):
        assert WorkflowStateService.can_transition_to_stage("ec", "ec") is True
        assert WorkflowStateService.can_transition_to_stage("ic", "ic") is True

    def test_can_transition_to_stage_invalid(self):
        assert WorkflowStateService.can_transition_to_stage("ec", "qc") is False
        assert WorkflowStateService.can_transition_to_stage("ic", "ec") is False
        assert WorkflowStateService.can_transition_to_stage("complete", "ec") is False

    def test_can_transition_to_stage_invalid_input(self):
        assert WorkflowStateService.can_transition_to_stage("", "ec") is False
        assert WorkflowStateService.can_transition_to_stage("ec", "") is False
        assert WorkflowStateService.can_transition_to_stage("invalid", "ec") is False

    def test_is_workflow_complete_true_by_stage(self):
        assert WorkflowStateService.is_workflow_complete("complete", 0, 10) is True

    def test_is_workflow_complete_true_by_index(self):
        assert WorkflowStateService.is_workflow_complete("ec", 10, 10) is True
        assert WorkflowStateService.is_workflow_complete("ec", 11, 10) is True

    def test_is_workflow_complete_false(self):
        assert WorkflowStateService.is_workflow_complete("ec", 5, 10) is False
        assert WorkflowStateService.is_workflow_complete("ic", 0, 10) is False

    def test_get_next_stage(self):
        assert WorkflowStateService.get_next_stage("ec") == "ic"
        assert WorkflowStateService.get_next_stage("ic") == "qc"
        assert WorkflowStateService.get_next_stage("qc") == "complete"

    def test_get_next_stage_final(self):
        assert WorkflowStateService.get_next_stage("complete") is None

    def test_get_next_stage_invalid(self):
        assert WorkflowStateService.get_next_stage("invalid") is None

    def test_stage_order_constant(self):
        assert WorkflowStateService.STAGE_ORDER == ["ec", "ic", "qc", "complete"]

    def test_stage_field_map_constant(self):
        assert WorkflowStateService.STAGE_FIELD_MAP == {
            "ec": "ec_stage",
            "ic": "ic_stage",
        }

    def test_stage_counter_map_constant(self):
        assert WorkflowStateService.STAGE_COUNTER_MAP == {
            "ec": "ec_completed",
            "ic": "ic_completed",
        }


# ---------------------------------------------------------------------------
# Determinism — same inputs produce same outputs
# ---------------------------------------------------------------------------

class TestWorkflowDeterminism:

    def test_stage_field_deterministic(self):
        r1 = WorkflowStateService.stage_field("ec")
        r2 = WorkflowStateService.stage_field("ec")
        assert r1 == r2

    def test_is_workflow_complete_deterministic(self):
        r1 = WorkflowStateService.is_workflow_complete("ec", 10, 10)
        r2 = WorkflowStateService.is_workflow_complete("ec", 10, 10)
        assert r1 == r2

    def test_can_transition_deterministic(self):
        r1 = WorkflowStateService.can_transition_to_stage("ec", "ic")
        r2 = WorkflowStateService.can_transition_to_stage("ec", "ic")
        assert r1 == r2


# ---------------------------------------------------------------------------
# Architectural boundary — no forbidden dependencies
# ---------------------------------------------------------------------------

class TestWorkflowArchitecturalBoundary:

    IMPORT_BLACKLIST = [
        "src.ui", "streamlit", "src.advisory",
        "SessionPersistenceService", "NavigationService",
        "SessionQueryService", "SessionAuditService",
        "SessionIngestionService", "SessionDecisionService",
    ]

    def test_no_forbidden_imports_in_source(self):
        assert_source_lacks(
            get_source(WorkflowStateService),
            self.IMPORT_BLACKLIST,
            "WorkflowStateService",
        )

    def test_module_ast_no_forbidden_imports(self):
        assert_module_ast_lacks_imports(
            resolve_source_path(__file__, "src", "core", "workflow_state_service.py"),
            self.IMPORT_BLACKLIST,
            "workflow_state_service.py",
        )

    def test_workflow_state_service_is_stateless(self):
        assert_is_stateless(WorkflowStateService)

    def test_screening_session_reaches_workflow_via_services(self):
        """ScreeningSession accesses WorkflowStateService indirectly through
        NavigationService and SessionQueryService, which delegate to it."""
        nav_source = resolve_source_path(
            __file__, "src", "core", "session_navigation.py"
        ).read_text(encoding="utf-8")
        assert "WorkflowStateService.stage_field" in nav_source
        qry_source = resolve_source_path(
            __file__, "src", "core", "session_query_service.py"
        ).read_text(encoding="utf-8")
        assert "WorkflowStateService.stage_field" in qry_source

    def test_no_persistence_in_source(self):
        source = get_source(WorkflowStateService)
        assert_source_lacks(
            source, ["SessionPersistenceService", "save", "load"],
            "WorkflowStateService",
        )


# ---------------------------------------------------------------------------
# Workflow consolidation — no duplicate stage field mappings remain
# ---------------------------------------------------------------------------

class TestWorkflowConsolidation:

    def test_navigation_service_delegates_to_workflow(self):
        from src.core.session_navigation import NavigationService
        source = resolve_source_path(
            __file__, "src", "core", "session_navigation.py"
        ).read_text(encoding="utf-8")
        assert "WorkflowStateService.stage_field(stage)" in source

    def test_session_query_service_delegates_to_workflow(self):
        from src.core.session_query_service import SessionQueryService
        source = resolve_source_path(
            __file__, "src", "core", "session_query_service.py"
        ).read_text(encoding="utf-8")
        assert "WorkflowStateService.stage_field(stage)" in source

    def test_navigation_service_no_hardcoded_stage_map(self):
        source = resolve_source_path(
            __file__, "src", "core", "session_navigation.py"
        ).read_text(encoding="utf-8")
        assert '"ec": "ec_stage"' not in source

    def test_session_query_no_hardcoded_stage_map(self):
        source = resolve_source_path(
            __file__, "src", "core", "session_query_service.py"
        ).read_text(encoding="utf-8")
        assert '"ec": "ec_stage"' not in source

    def test_only_workflow_has_stage_field_map(self):
        from pathlib import Path
        wf_source = resolve_source_path(
            __file__, "src", "core", "workflow_state_service.py"
        ).read_text(encoding="utf-8")
        assert '"ec": "ec_stage"' in wf_source
        core_dir = Path(
            resolve_source_path(__file__, "src", "core")
        )
        for py_file in core_dir.glob("*.py"):
            if py_file.name == "workflow_state_service.py":
                continue
            source = py_file.read_text(encoding="utf-8")
            if '"ec": "ec_stage"' in source:
                pytest.fail(f"Duplicate stage map found in {py_file.name}")

    def test_navigation_and_query_produce_same_stage_field(self):
        from src.core.session_navigation import NavigationService
        from src.core.session_query_service import SessionQueryService
        for stage in ["ec", "ic", "qc", "complete", "", "invalid"]:
            nav = NavigationService._stage_field(stage)
            qry = SessionQueryService._stage_field(stage)
            wf = WorkflowStateService.stage_field(stage)
            assert nav == wf, f"Mismatch NavigationService._stage_field({stage!r})"
            assert qry == wf, f"Mismatch SessionQueryService._stage_field({stage!r})"
