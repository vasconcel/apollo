"""
APOLLO Tests — SessionState Model Extraction

Verifies that SessionState is a lightweight deterministic state container
with no orchestration logic, no forbidden imports, and backward-compatible
field access through ScreeningSession delegation.
"""

import ast
from pathlib import Path

import pytest

from src.core.session_state import SessionState
from src.core.screening_session import ScreeningSession


# ---------------------------------------------------------------------------
# SessionState — pure dataclass tests
# ---------------------------------------------------------------------------

class TestSessionState:

    def test_construct_with_required_fields(self):
        state = SessionState(session_id="s1", created_at="2024-01-01")
        assert state.session_id == "s1"
        assert state.created_at == "2024-01-01"
        assert state.protocol_version == "1.0"
        assert state.stage == "ec"

    def test_construct_with_all_fields(self):
        state = SessionState(
            session_id="s1", created_at="2024-01-01", protocol_version="2.0",
            stage="ic", current_index=5, total_count=100,
            ec_completed=10, ic_completed=5, qc_completed=0,
            included_count=8, excluded_count=2, skip_count=3,
            discussion_count=1, researcher_id="res_2", last_saved="now",
            schema_version="2.0", autosave_enabled=True,
        )
        assert state.stage == "ic"
        assert state.current_index == 5
        assert state.included_count == 8

    def test_default_collections(self):
        state = SessionState(session_id="s1", created_at="2024-01-01")
        assert state.articles == []
        assert state.audit_chain == []
        assert state.snapshots == []
        assert state.dynamic_protocol is None

    def test_field_order_matches_serialization(self):
        from dataclasses import fields
        fnames = [f.name for f in fields(SessionState)]
        assert fnames[0] == "session_id"
        assert fnames[1] == "created_at"
        assert fnames[2] == "protocol_version"
        assert fnames[3] == "stage"
        assert fnames[4] == "articles"
        assert "audit_chain" in fnames
        assert "snapshots" in fnames


# ---------------------------------------------------------------------------
# ScreeningSession — backward-compatible field access via SessionState
# ---------------------------------------------------------------------------

class TestScreeningSessionStateDelegation:

    def test_construct_delegates_to_state(self):
        session = ScreeningSession(
            session_id="s1", created_at="2024-01-01", stage="ic",
        )
        assert session.state.session_id == "s1"
        assert session.state.stage == "ic"

    def test_backward_compatible_field_read(self):
        session = ScreeningSession(
            session_id="s1", created_at="2024-01-01",
            current_index=7, total_count=42,
        )
        assert session.session_id == "s1"
        assert session.current_index == 7
        assert session.total_count == 42

    def test_backward_compatible_field_write(self):
        session = ScreeningSession(
            session_id="s1", created_at="2024-01-01",
        )
        session.stage = "ic"
        assert session.state.stage == "ic"
        assert session.stage == "ic"

    def test_backward_compatible_audit_chain(self):
        session = ScreeningSession(
            session_id="s1", created_at="2024-01-01",
        )
        assert session._audit_chain == []
        session._audit_chain = [{"event": "test"}]
        assert session.state.audit_chain == [{"event": "test"}]
        assert session._audit_chain == [{"event": "test"}]

    def test_backward_compatible_snapshots(self):
        session = ScreeningSession(
            session_id="s1", created_at="2024-01-01",
        )
        assert session._snapshots == []
        session._snapshots.append("snap1")
        assert session.state.snapshots == ["snap1"]

    def test_backward_compatible_articles(self):
        session = ScreeningSession(
            session_id="s1", created_at="2024-01-01",
        )
        from src.core.screening_session import ArticleReview
        article = ArticleReview(
            article_id="a1", title="Test", abstract="", metadata={},
        )
        session.articles = [article]
        assert session.state.articles == [article]
        assert session.articles == [article]

    def test_backward_compatible_dynamic_protocol(self):
        session = ScreeningSession(
            session_id="s1", created_at="2024-01-01",
        )
        session.dynamic_protocol = {"key": "value"}
        assert session.state.dynamic_protocol == {"key": "value"}
        assert session.dynamic_protocol == {"key": "value"}

    def test_constructor_with_positional_args(self):
        session = ScreeningSession("dummy", "2024-01-01", "1.0")
        assert session.session_id == "dummy"
        assert session.created_at == "2024-01-01"
        assert session.protocol_version == "1.0"
        assert session.state.stage == "ec"

    def test_constructor_with_positional_partial(self):
        session = ScreeningSession("dummy", "2024-01-01")
        assert session.session_id == "dummy"
        assert session.created_at == "2024-01-01"

    def test_state_isolation(self):
        s1 = ScreeningSession("s1", "2024-01-01")
        s2 = ScreeningSession("s2", "2024-01-02")
        s1.stage = "ic"
        assert s2.stage == "ec"
        assert s1.state.stage == "ic"

    def test_repr_no_error(self):
        session = ScreeningSession("s1", "2024-01-01")
        r = repr(session)
        assert "ScreeningSession" in r


# ---------------------------------------------------------------------------
# Determinism — same state produces identical behavior
# ---------------------------------------------------------------------------

class TestSessionStateDeterminism:

    def test_same_construction_identical(self):
        s1 = ScreeningSession("s1", "2024-01-01", stage="ic", current_index=3)
        s2 = ScreeningSession("s1", "2024-01-01", stage="ic", current_index=3)
        assert s1.state == s2.state

    def test_field_access_deterministic(self):
        session = ScreeningSession("s1", "2024-01-01")
        assert session.stage == session.state.stage
        assert session.stage == session.state.stage  # second read same

    def test_mutation_through_state(self):
        session = ScreeningSession("s1", "2024-01-01")
        session.state.current_index = 10
        assert session.current_index == 10


# ---------------------------------------------------------------------------
# Architectural boundary — no forbidden dependencies
# ---------------------------------------------------------------------------

class TestSessionStateArchitecturalBoundary:

    IMPORT_BLACKLIST = [
        "src.ui", "streamlit", "src.advisory", "SessionPersistenceService",
        "NavigationService", "SessionQueryService", "SessionAuditService",
        "SessionIngestionService", "SessionDecisionService", "WorkflowStateService",
        "screening_session", "ArticleReview",
    ]

    def test_no_forbidden_imports_in_session_state(self):
        svc_path = (
            Path(__file__).parent.parent
            / "src" / "core" / "session_state.py"
        )
        source = svc_path.read_text(encoding="utf-8")
        for banned in self.IMPORT_BLACKLIST:
            assert banned not in source, (
                f"SessionState must not reference '{banned}'"
            )

    def test_module_ast_no_forbidden_imports(self):
        svc_path = (
            Path(__file__).parent.parent
            / "src" / "core" / "session_state.py"
        )
        tree = ast.parse(svc_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for banned in self.IMPORT_BLACKLIST:
                    if banned.startswith("src."):
                        assert not module.startswith(banned), (
                            f"Forbidden import '{module}' in SessionState"
                        )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    for banned in self.IMPORT_BLACKLIST:
                        if not banned.startswith("src."):
                            assert alias.name != banned, (
                                f"Forbidden import '{alias.name}'"
                            )

    def test_session_state_is_dataclass(self):
        from dataclasses import is_dataclass
        assert is_dataclass(SessionState)

    def test_session_state_no_methods(self):
        import inspect
        methods = [
            m for m in inspect.getmembers(SessionState, predicate=inspect.isfunction)
            if not m[0].startswith("__")
        ]
        assert len(methods) == 0, f"SessionState has unexpected methods: {methods}"

    def test_session_state_class_has_no_imports(self):
        source = Path(__file__).parent.parent / "src" / "core" / "session_state.py"
        content = source.read_text(encoding="utf-8")
        assert "import streamlit" not in content
        assert "from streamlit" not in content
        assert "import src.ui" not in content
        assert "from src.ui" not in content
        assert "import src.advisory" not in content
        assert "from src.advisory" not in content
