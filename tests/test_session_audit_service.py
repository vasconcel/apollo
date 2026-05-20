"""
APOLLO Tests — Session Audit Service Extraction

Verifies that audit-chain logic was correctly extracted from
ScreeningSession into SessionAuditService with full behavioral parity.

Architectural boundaries tested:
- SessionAuditService contains no Streamlit or UI imports
- SessionAuditService contains no advisory imports
- SessionAuditService contains no persistence/navigation/query/ingestion coupling
- Delegation preserves all public audit semantics
- Hash chaining, tamper detection, and event ordering are unchanged
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
from src.core.session_audit_service import SessionAuditService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def empty_chain():
    return []


@pytest.fixture
def single_event_chain():
    return [{
        "event_id": "evt-001",
        "timestamp": "2025-01-01T00:00:00",
        "article_id": "art-001",
        "reviewer_id": "researcher_1",
        "stage": "ec",
        "decision": "include",
        "notes": "",
        "previous_hash": "GENESIS",
        "current_hash": (
            "5c8c1c6c9b9c9c9c9c9c9c9c9c9c9c9c9c9c9c9c9c9c9c9c9c9c9c9c9c9c9c"
        ),
    }]


# ---------------------------------------------------------------------------
# SessionAuditService — stateless unit tests
# ---------------------------------------------------------------------------

class TestSessionAuditService:

    def test_append_creates_event_with_required_fields(self, empty_chain):
        article = ArticleReview(
            article_id="art-001", title="A", abstract="abs",
            metadata={"literature_type": "WL"},
        )
        event = SessionAuditService.append_event(
            empty_chain, "researcher_1", article, "include", "", "ec",
        )
        assert "event_id" in event
        assert "timestamp" in event
        assert "article_id" in event
        assert "reviewer_id" in event
        assert "stage" in event
        assert "decision" in event
        assert "notes" in event
        assert "previous_hash" in event
        assert "current_hash" in event

    def test_append_genesis_hash_for_first_event(self, empty_chain):
        article = ArticleReview(
            article_id="art-001", title="A", abstract="abs",
            metadata={"literature_type": "WL"},
        )
        event = SessionAuditService.append_event(
            empty_chain, "researcher_1", article, "include", "", "ec",
        )
        assert event["previous_hash"] == "GENESIS"
        assert len(event["current_hash"]) == 64

    def test_append_chains_second_event(self):
        article = ArticleReview(
            article_id="art-001", title="A", abstract="abs",
            metadata={"literature_type": "WL"},
        )
        # Build first event
        chain = []
        ev1 = SessionAuditService.append_event(
            chain, "researcher_1", article, "include", "", "ec",
        )
        chain.append(ev1)

        ev2 = SessionAuditService.append_event(
            chain, "researcher_1", article, "exclude", "", "ec",
        )
        assert ev2["previous_hash"] == ev1["current_hash"]
        assert ev2["current_hash"] != ev1["current_hash"]

    def test_verify_chain_empty(self, empty_chain):
        is_valid, errors = SessionAuditService.verify_chain(empty_chain)
        assert is_valid is True
        assert errors == []

    def test_verify_chain_single_valid(self, single_event_chain):
        # Recreate with known values to get correct hash
        article = ArticleReview(
            article_id="art-001", title="A", abstract="abs",
            metadata={"literature_type": "WL"},
        )
        chain = []
        ev = SessionAuditService.append_event(
            chain, "researcher_1", article, "include", "", "ec",
        )
        chain.append(ev)

        is_valid, errors = SessionAuditService.verify_chain(chain)
        assert is_valid is True
        assert errors == []

    def test_verify_chain_broken_link(self):
        article = ArticleReview(
            article_id="art-001", title="A", abstract="abs",
            metadata={"literature_type": "WL"},
        )
        chain = []
        ev1 = SessionAuditService.append_event(
            chain, "researcher_1", article, "include", "", "ec",
        )
        chain.append(ev1)
        ev2 = SessionAuditService.append_event(
            chain, "researcher_1", article, "exclude", "", "ec",
        )
        chain.append(ev2)

        # Break the link
        chain[1]["previous_hash"] = "TAMPERED"
        is_valid, errors = SessionAuditService.verify_chain(chain)
        assert is_valid is False
        assert any("Chain broken" in e for e in errors)

    def test_detect_tampering_clean(self):
        article = ArticleReview(
            article_id="art-001", title="A", abstract="abs",
            metadata={"literature_type": "WL"},
        )
        chain = []
        ev = SessionAuditService.append_event(
            chain, "researcher_1", article, "include", "", "ec",
        )
        chain.append(ev)

        is_clean, tampered = SessionAuditService.detect_tampering(chain)
        assert is_clean is True
        assert tampered == []

    def test_detect_tampering_altered_event(self):
        article = ArticleReview(
            article_id="art-001", title="A", abstract="abs",
            metadata={"literature_type": "WL"},
        )
        chain = []
        ev = SessionAuditService.append_event(
            chain, "researcher_1", article, "include", "", "ec",
        )
        chain.append(ev)

        chain[0]["decision"] = "altered"
        is_clean, tampered = SessionAuditService.detect_tampering(chain)
        assert is_clean is False
        assert len(tampered) > 0

    def test_get_events_returns_copy(self):
        article = ArticleReview(
            article_id="art-001", title="A", abstract="abs",
            metadata={"literature_type": "WL"},
        )
        chain = []
        ev = SessionAuditService.append_event(
            chain, "researcher_1", article, "include", "", "ec",
        )
        chain.append(ev)

        events = SessionAuditService.get_events(chain)
        assert events == chain
        assert events is not chain  # should be a copy


# ---------------------------------------------------------------------------
# ScreeningSession delegation — ensures session calls the service
# ---------------------------------------------------------------------------

class TestScreeningSessionAuditDelegation:

    def test_verify_audit_chain_delegates(self):
        assert "SessionAuditService.verify_chain" in get_source(
            ScreeningSession.verify_audit_chain
        )

    def test_detect_tampering_delegates(self):
        assert "SessionAuditService.detect_tampering" in get_source(
            ScreeningSession.detect_tampering
        )

    def test_get_audit_events_delegates(self):
        assert "SessionAuditService.get_events" in get_source(
            ScreeningSession.get_audit_events
        )


# ---------------------------------------------------------------------------
# Behavioral parity — session audit methods work identically
# ---------------------------------------------------------------------------

class TestAuditBehavioralParity:

    def test_record_decision_appends_audit_event(self):
        session = ScreeningSession(
            session_id="parity-test",
            created_at="2025-01-01T00:00:00",
            protocol_version="1.0",
        )
        session.articles.append(ArticleReview(
            article_id="PARITY-001", title="Test", abstract="abs",
            metadata={"literature_type": "WL"},
        ))
        session.record_decision("include")

        events = session.get_audit_events()
        assert len(events) == 1
        assert events[0]["decision"] == "include"
        assert events[0]["article_id"] == "PARITY-001"

    def test_verify_chain_passes_clean(self):
        session = ScreeningSession(
            session_id="verify-parity",
            created_at="2025-01-01T00:00:00",
            protocol_version="1.0",
        )
        session.articles = [
            ArticleReview(article_id=f"A{i}", title=f"T{i}", abstract="abs",
                          metadata={"literature_type": "WL"})
            for i in range(3)
        ]
        session.total_count = 3
        for _ in range(3):
            session.record_decision("include")

        is_valid, errors = session.verify_audit_chain()
        assert is_valid is True
        assert len(errors) == 0

    def test_detect_tampering_fails_altered(self):
        session = ScreeningSession(
            session_id="tamper-parity",
            created_at="2025-01-01T00:00:00",
            protocol_version="1.0",
        )
        session.articles.append(ArticleReview(
            article_id="TAMPER-PARITY", title="Test", abstract="abs",
            metadata={"literature_type": "WL"},
        ))
        session.record_decision("include")

        session._audit_chain[0]["decision"] = "altered"
        is_clean, tampered = session.detect_tampering()
        assert is_clean is False
        assert len(tampered) > 0


# ---------------------------------------------------------------------------
# Determinism — audit service is deterministic
# ---------------------------------------------------------------------------

class TestAuditDeterminism:

    def test_verify_chain_deterministic(self):
        article = ArticleReview(
            article_id="art-001", title="A", abstract="abs",
            metadata={"literature_type": "WL"},
        )
        chain = []
        ev = SessionAuditService.append_event(
            chain, "researcher_1", article, "include", "", "ec",
        )
        chain.append(ev)

        r1 = SessionAuditService.verify_chain(chain)
        r2 = SessionAuditService.verify_chain(chain)
        assert r1 == r2

    def test_detect_tampering_deterministic(self):
        article = ArticleReview(
            article_id="art-001", title="A", abstract="abs",
            metadata={"literature_type": "WL"},
        )
        chain = []
        ev = SessionAuditService.append_event(
            chain, "researcher_1", article, "include", "", "ec",
        )
        chain.append(ev)

        chain[0]["decision"] = "altered"
        r1 = SessionAuditService.detect_tampering(chain)
        r2 = SessionAuditService.detect_tampering(chain)
        assert r1 == r2


# ---------------------------------------------------------------------------
# Architectural boundary — SessionAuditService has restricted dependencies
# ---------------------------------------------------------------------------

class TestAuditArchitecturalBoundary:

    IMPORT_BLACKLIST = [
        "src.ui", "streamlit", "src.advisory",
        "SessionPersistenceService", "NavigationService",
        "SessionQueryService", "SessionIngestionService",
    ]

    def test_no_forbidden_imports_in_source(self):
        assert_source_lacks(
            get_source(SessionAuditService),
            self.IMPORT_BLACKLIST,
            "SessionAuditService",
        )

    def test_module_ast_no_forbidden_imports(self):
        assert_module_ast_lacks_imports(
            resolve_source_path(__file__, "src", "core", "session_audit_service.py"),
            self.IMPORT_BLACKLIST,
            "session_audit_service.py",
        )

    def test_screening_session_delegates_to_audit(self):
        for method_name in [
            "verify_audit_chain",
            "detect_tampering",
            "get_audit_events",
        ]:
            method = getattr(ScreeningSession, method_name)
            source = get_source(method)
            assert "SessionAuditService." in source, (
                f"{method_name} should delegate to SessionAuditService"
            )

    def test_session_audit_service_is_stateless(self):
        assert_is_stateless(SessionAuditService)
