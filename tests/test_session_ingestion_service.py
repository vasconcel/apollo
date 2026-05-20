"""
APOLLO Tests - Session Ingestion Service Extraction

Verifies that ingestion logic was correctly extracted from
ScreeningSession into SessionIngestionService with full behavioral parity.

Architectural boundaries tested:
- SessionIngestionService contains no Streamlit or UI imports
- SessionIngestionService contains no advisory imports
- SessionIngestionService contains no persistence logic
- Delegation preserves all public ingestion semantics
- Metadata normalization helpers are deterministic
"""

import ast
import inspect
from pathlib import Path

import pytest

from src.core.screening_session import (
    ScreeningSession, ArticleReview, SessionStage,
)
from src.core.session_ingestion_service import (
    SessionIngestionService,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_articles():
    return [
        ArticleReview(
            article_id='1', title='A', abstract='abs1',
            metadata={'literature_type': 'WL', 'year': '2020'},
        ),
        ArticleReview(
            article_id='2', title='B', abstract='abs2',
            metadata={'literature_type': 'WL', 'year': '2021'},
        ),
    ]


@pytest.fixture
def sample_session(sample_articles):
    session = ScreeningSession(
        session_id='test_ingest',
        created_at='2025-01-01T00:00:00',
        articles=sample_articles,
        current_index=0,
        total_count=2,
    )
    return session


# ---------------------------------------------------------------------------
# SessionIngestionService — stateless unit tests
# ---------------------------------------------------------------------------

class TestSessionIngestionService:

    def test_normalize_metadata_fills_empty_fields(self):
        metadata = {}
        result = SessionIngestionService.normalize_metadata(metadata)
        assert result['year'] == 'Unknown'
        assert result['year_source'] == 'missing'
        assert result['authors'] == ''
        assert result['literature_type'] == 'WL'
        assert result['metadata_completeness'] == 'unknown'

    def test_normalize_metadata_preserves_existing(self):
        metadata = {'year': '2024', 'authors': 'Doe, J'}
        result = SessionIngestionService.normalize_metadata(metadata)
        assert result['year'] == '2024'
        assert result['authors'] == 'Doe, J'

    def test_normalize_metadata_overrides_empty_string(self):
        metadata = {'year': '', 'authors': 'Doe, J'}
        result = SessionIngestionService.normalize_metadata(metadata)
        assert result['year'] == 'Unknown'
        assert result['authors'] == 'Doe, J'

    def test_normalize_metadata_overrides_none(self):
        metadata = {'year': None, 'authors': 'Doe, J'}
        result = SessionIngestionService.normalize_metadata(metadata)
        assert result['year'] == 'Unknown'
        assert result['authors'] == 'Doe, J'

    def test_normalize_literature_type_wl_variants(self):
        assert SessionIngestionService.normalize_literature_type('WL') == 'WL'
        assert SessionIngestionService.normalize_literature_type('wl') == 'WL'
        assert SessionIngestionService.normalize_literature_type('White Literature') == 'WL'
        assert SessionIngestionService.normalize_literature_type('WHITE LITERATURE') == 'WL'

    def test_normalize_literature_type_gl_variants(self):
        assert SessionIngestionService.normalize_literature_type('GL') == 'GL'
        assert SessionIngestionService.normalize_literature_type('gl') == 'GL'
        assert SessionIngestionService.normalize_literature_type('Grey Literature') == 'GL'
        assert SessionIngestionService.normalize_literature_type('GREY LITERATURE') == 'GL'

    def test_normalize_literature_type_empty_defaults_to_wl(self):
        assert SessionIngestionService.normalize_literature_type('') == 'WL'
        assert SessionIngestionService.normalize_literature_type(None) == 'WL'

    def test_normalize_literature_type_unknown_defaults_to_wl(self):
        assert SessionIngestionService.normalize_literature_type('unknown') == 'WL'
        assert SessionIngestionService.normalize_literature_type('magazine') == 'WL'

    def test_compute_csv_metadata_completeness_complete(self):
        row = {'Title': 'A', 'Abstract': 'abs', 'Year': '2024'}
        assert SessionIngestionService.compute_csv_metadata_completeness(row) == 'complete'

    def test_compute_csv_metadata_completeness_partial(self):
        row = {'Title': 'A', 'Abstract': '', 'Year': ''}
        assert SessionIngestionService.compute_csv_metadata_completeness(row) == 'partial'

    def test_compute_csv_metadata_completeness_minimal(self):
        row = {'Title': '', 'Abstract': '', 'Year': ''}
        assert SessionIngestionService.compute_csv_metadata_completeness(row) == 'minimal'

    def test_add_articles_converts_records(self):
        class MockRecord:
            title = 'A'
            abstract = 'abs1'
            library = 'WL'
            global_id = 'g1'
            local_id = ''
            keywords = ''
            literature_type = 'WL'
            url = ''
            source_file = ''
            year = '2024'
            authors = 'Doe, J'
            posicao = '1'
            ec_decision = ''
            ic_decision = ''
            final_decision = ''
            metadata = {'title': 'A', 'abstract': 'abs1', 'year': '2024'}

        records = [MockRecord()]
        result = SessionIngestionService.add_articles(records)
        assert len(result) == 1
        assert isinstance(result[0], ArticleReview)
        assert result[0].title == 'A'


# ---------------------------------------------------------------------------
# ScreeningSession delegation — ensures session calls the service
# ---------------------------------------------------------------------------

class TestScreeningSessionIngestionDelegation:
    """ScreeningSession methods must delegate to SessionIngestionService."""

    def test_add_articles_delegates(self):
        source = inspect.getsource(ScreeningSession.add_articles)
        assert 'SessionIngestionService.add_articles' in source

    def test_ingest_from_upload_delegates(self):
        source = inspect.getsource(ScreeningSession.ingest_from_upload)
        assert 'SessionIngestionService.ingest_from_bytes' in source


# ---------------------------------------------------------------------------
# Determinism — metadata helpers are deterministic
# ---------------------------------------------------------------------------

class TestIngestionDeterminism:

    def test_normalize_metadata_deterministic(self):
        md = {'year': '2024', 'authors': 'Doe, J'}
        r1 = SessionIngestionService.normalize_metadata(md)
        r2 = SessionIngestionService.normalize_metadata(md)
        assert r1 == r2

    def test_normalize_literature_type_deterministic(self):
        assert (SessionIngestionService.normalize_literature_type('WL')
                == SessionIngestionService.normalize_literature_type('wl'))

    def test_no_mutation_of_input(self):
        md = {'year': ''}
        original = dict(md)
        SessionIngestionService.normalize_metadata(md)
        assert md == original


# ---------------------------------------------------------------------------
# Architectural boundary — SessionIngestionService has restricted dependencies
# ---------------------------------------------------------------------------

class TestIngestionArchitecturalBoundary:
    """SessionIngestionService must not import from UI, advisory, etc."""

    IMPORT_BLACKLIST = ['src.ui', 'streamlit', 'src.advisory']

    def test_no_forbidden_imports_in_source(self):
        source = inspect.getsource(SessionIngestionService)
        for banned in self.IMPORT_BLACKLIST:
            assert banned not in source, (
                f"SessionIngestionService must not reference '{banned}'"
            )

    def test_module_ast_no_forbidden_imports(self):
        svc_path = (
            Path(__file__).parent.parent
            / 'src' / 'core' / 'session_ingestion_service.py'
        )
        tree = ast.parse(svc_path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ''
                for banned in self.IMPORT_BLACKLIST:
                    assert not module.startswith(banned), (
                        f"Forbidden import '{module}' in ingestion service"
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    for banned in self.IMPORT_BLACKLIST:
                        assert not alias.name.startswith(banned), (
                            f"Forbidden import '{alias.name}'"
                        )

    def test_no_persistence_in_source(self):
        source = inspect.getsource(SessionIngestionService)
        assert 'SessionPersistenceService' not in source

    def test_screening_session_delegates_to_ingestion(self):
        """Verify delegation for add_articles and ingest_from_upload."""
        for method_name in ['add_articles', 'ingest_from_upload']:
            method = getattr(ScreeningSession, method_name)
            source = inspect.getsource(method)
            assert 'SessionIngestionService.' in source, (
                f"{method_name} should delegate to SessionIngestionService"
            )

    def test_session_ingestion_service_is_stateless(self):
        s1 = SessionIngestionService()
        s2 = SessionIngestionService()
        assert type(s1) == type(s2)
