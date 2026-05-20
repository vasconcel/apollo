"""
APOLLO Tests - Session Query Service Extraction

Verifies that filtering/query logic was correctly extracted from
ScreeningSession into SessionQueryService with full behavioral parity.

Architectural boundaries tested:
- SessionQueryService contains no Streamlit or UI imports
- SessionQueryService contains no advisory imports
- SessionQueryService contains no persistence logic
- Delegation preserves all public query/filter semantics
- Serialization format is unchanged
- Methods are stateless and deterministic
- No mutation of input article collections
"""

import ast
import inspect
from pathlib import Path

import pytest

from src.core.screening_session import (
    ScreeningSession, ArticleReview, SessionStage, ReviewDecision,
)
from src.core.session_query_service import SessionQueryService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mixed_articles():
    """Article collection with varied metadata and decisions for filtering."""
    wl_include = ArticleReview(
        article_id='1', title='A', abstract='abs1',
        metadata={'literature_type': 'WL'},
    )
    wl_include.ec_stage = 'include'
    wl_include.ic_stage = 'include'

    wl_exclude = ArticleReview(
        article_id='2', title='B', abstract='abs2',
        metadata={'literature_type': 'WL'},
    )
    wl_exclude.ec_stage = 'exclude'

    wl_skip = ArticleReview(
        article_id='3', title='C', abstract='abs3',
        metadata={'literature_type': 'WL'},
    )
    wl_skip.ec_stage = 'skip'

    wl_discuss = ArticleReview(
        article_id='4', title='D', abstract='abs4',
        metadata={'literature_type': 'WL'},
    )
    wl_discuss.ec_stage = 'needs_discussion'

    wl_pending = ArticleReview(
        article_id='5', title='E', abstract='abs5',
        metadata={'literature_type': 'WL'},
    )

    gl_include = ArticleReview(
        article_id='6', title='F', abstract='abs6',
        metadata={'literature_type': 'GL'},
    )
    gl_include.ec_stage = 'include'

    gl_pending = ArticleReview(
        article_id='7', title='G', abstract='abs7',
        metadata={'literature_type': 'GL'},
    )

    return [
        wl_include, wl_exclude, wl_skip, wl_discuss, wl_pending,
        gl_include, gl_pending,
    ]


@pytest.fixture
def query_session(mixed_articles):
    session = ScreeningSession(
        session_id='test_query',
        created_at='2025-01-01T00:00:00',
        articles=mixed_articles,
        current_index=0,
        total_count=len(mixed_articles),
        ec_completed=3,
        ic_completed=1,
        included_count=2,
        excluded_count=1,
        skip_count=1,
        discussion_count=1,
    )
    return session


# ---------------------------------------------------------------------------
# SessionQueryService — stateless unit tests
# ---------------------------------------------------------------------------

class TestSessionQueryService:
    """SessionQueryService operates on (articles, counters) explicitly."""

    def test_get_discussion_articles(self, mixed_articles):
        result = SessionQueryService.get_discussion_articles(mixed_articles)
        assert len(result) == 1
        assert result[0].article_id == '4'

    def test_get_skipped_articles(self, mixed_articles):
        result = SessionQueryService.get_skipped_articles(mixed_articles, 'ec')
        assert len(result) == 1
        assert result[0].article_id == '3'

    def test_get_skipped_articles_no_skips(self):
        articles = [
            ArticleReview(
                article_id='1', title='A', abstract='a',
                metadata={'literature_type': 'WL'},
            ),
        ]
        articles[0].ec_stage = 'include'
        result = SessionQueryService.get_skipped_articles(articles, 'ec')
        assert len(result) == 0

    def test_get_ec_included_articles(self, mixed_articles):
        result = SessionQueryService.get_ec_included_articles(mixed_articles)
        assert len(result) == 2
        ids = {a.article_id for a in result}
        expected_ids = {'1', '6'}
        assert ids == expected_ids, f"Expected {expected_ids}, got {ids}"

    def test_get_ic_included_articles(self, mixed_articles):
        result = SessionQueryService.get_ic_included_articles(mixed_articles)
        # Article '1' has ec_stage='include' AND ic_stage='include'
        assert len(result) == 1
        assert result[0].article_id == '1'

    def test_get_wl_articles(self, mixed_articles):
        result = SessionQueryService.get_wl_articles(mixed_articles)
        assert len(result) == 5
        for a in result:
            assert a.get_literature_type() == 'WL'

    def test_get_gl_articles(self, mixed_articles):
        result = SessionQueryService.get_gl_articles(mixed_articles)
        assert len(result) == 2
        for a in result:
            assert a.get_literature_type() == 'GL'

    def test_get_wl_articles_empty(self):
        assert SessionQueryService.get_wl_articles([]) == []

    def test_get_gl_articles_empty(self):
        assert SessionQueryService.get_gl_articles([]) == []

    def test_filter_articles_by_literature_type(self, mixed_articles):
        result = SessionQueryService.filter_articles(
            mixed_articles, 'ec', literature_type='WL',
        )
        assert len(result) == 5
        for a in result:
            assert a.get_literature_type() == 'WL'

    def test_filter_articles_by_decision(self, mixed_articles):
        result = SessionQueryService.filter_articles(
            mixed_articles, 'ec', stage_decision='include',
        )
        assert len(result) == 2

    def test_filter_articles_by_both(self, mixed_articles):
        result = SessionQueryService.filter_articles(
            mixed_articles, 'ec',
            literature_type='WL', stage_decision='include',
        )
        assert len(result) == 1

    def test_filter_articles_no_filters(self, mixed_articles):
        result = SessionQueryService.filter_articles(mixed_articles, 'ec')
        assert len(result) == len(mixed_articles)

    def test_get_pending_for_stage_ec(self, mixed_articles):
        pending = SessionQueryService.get_pending_for_stage(
            mixed_articles, 'ec', ec_completed=3, ic_completed=0, skip_count=1,
        )
        # total=7, ec_completed=3, skip_count=1 => 7-3-1=3
        assert pending == 3

    def test_get_pending_for_stage_ic(self, mixed_articles):
        pending = SessionQueryService.get_pending_for_stage(
            mixed_articles, 'ic', ec_completed=3, ic_completed=1, skip_count=0,
        )
        # ec_included = 2 (articles '1' and '6')
        # ic_completed=1, skip_count=0 => 2-1-0=1
        assert pending == 1

    def test_get_wl_progress(self, mixed_articles):
        progress = SessionQueryService.get_wl_progress(mixed_articles)
        assert progress['total'] == 5
        # Only include/exclude/skip count as completed (not needs_discussion)
        assert progress['completed'] == 3
        assert progress['included'] == 1   # only article '1'
        assert progress['excluded'] == 1   # article '2'
        assert progress['progress_pct'] == 60  # 3/5 = 60%

    def test_get_gl_progress(self, mixed_articles):
        progress = SessionQueryService.get_gl_progress(mixed_articles)
        assert progress['total'] == 2
        assert progress['included'] == 1  # only article '6'
        assert progress['excluded'] == 0
        assert progress['progress_pct'] == 50  # 1/2 = 50%

    def test_get_progress(self, mixed_articles):
        progress = SessionQueryService.get_progress(
            mixed_articles,
            current_index=0, total_count=7, stage='ec',
            ec_completed=3, ic_completed=1,
            included_count=2, excluded_count=1,
            skip_count=1, discussion_count=1,
        )
        assert progress['current'] == 1
        assert progress['total'] == 7
        assert progress['stage'] == 'ec'
        assert progress['ec_completed'] == 3
        assert progress['ic_completed'] == 1
        assert progress['included'] == 2
        assert progress['excluded'] == 1
        assert progress['skipped'] == 1
        assert progress['discussion'] == 1

    def test_stage_field(self):
        assert SessionQueryService._stage_field('ec') == 'ec_stage'
        assert SessionQueryService._stage_field('ic') == 'ic_stage'
        assert SessionQueryService._stage_field('qc') == ''


# ---------------------------------------------------------------------------
# ScreeningSession delegation — behavioral parity
# ---------------------------------------------------------------------------

class TestScreeningSessionQueryDelegation:
    """ScreeningSession delegates query/filter to SessionQueryService."""

    def test_get_discussion_articles(self, query_session):
        result = query_session.get_discussion_articles()
        assert len(result) == 1
        assert result[0].article_id == '4'

    def test_get_skipped_articles(self, query_session):
        result = query_session.get_skipped_articles()
        assert len(result) == 1
        assert result[0].article_id == '3'

    def test_get_ec_included_articles(self, query_session):
        result = query_session.get_ec_included_articles()
        assert len(result) == 2

    def test_get_ec_included_articles(self, query_session):
        result = query_session.get_ec_included_articles()
        assert len(result) == 2

    def test_get_wl_articles(self, query_session):
        result = query_session.get_wl_articles()
        assert len(result) == 5

    def test_get_gl_articles(self, query_session):
        result = query_session.get_gl_articles()
        assert len(result) == 2

    def test_filter_articles_by_wl(self, query_session):
        result = query_session.filter_articles(literature_type='WL')
        assert len(result) == 5

    def test_filter_articles_by_decision(self, query_session):
        result = query_session.filter_articles(stage_decision='include')
        assert len(result) == 2

    def test_get_wl_progress(self, query_session):
        progress = query_session.get_wl_progress()
        assert progress['total'] == 5
        assert progress['progress_pct'] == 60

    def test_get_gl_progress(self, query_session):
        progress = query_session.get_gl_progress()
        assert progress['total'] == 2
        assert progress['progress_pct'] == 50

    def test_get_pending_for_stage_ec(self, query_session):
        pending = query_session.get_pending_for_stage('ec')
        # total=7, ec_completed=3, skip=1 => 3 pending
        assert pending == 3

    def test_get_progress(self, query_session):
        progress = query_session.get_progress()
        assert progress['current'] == 1
        assert progress['total'] == 7
        assert progress['stage'] == 'ec'
        assert progress['ec_completed'] == 3


# ---------------------------------------------------------------------------
# Statelessness and determinism
# ---------------------------------------------------------------------------

class TestSessionQueryDeterminism:
    """All query methods are deterministic — identical inputs → identical outputs."""

    def test_get_ec_included_deterministic(self, mixed_articles):
        r1 = SessionQueryService.get_ec_included_articles(mixed_articles)
        r2 = SessionQueryService.get_ec_included_articles(mixed_articles)
        assert [a.article_id for a in r1] == [a.article_id for a in r2]

    def test_get_wl_progress_deterministic(self, mixed_articles):
        p1 = SessionQueryService.get_wl_progress(mixed_articles)
        p2 = SessionQueryService.get_wl_progress(mixed_articles)
        assert p1 == p2

    def test_get_progress_deterministic(self, mixed_articles):
        args = (mixed_articles, 0, 7, 'ec', 3, 1, 2, 1, 1, 1)
        p1 = SessionQueryService.get_progress(*args)
        p2 = SessionQueryService.get_progress(*args)
        assert p1 == p2

    def test_filter_articles_deterministic(self, mixed_articles):
        r1 = SessionQueryService.filter_articles(
            mixed_articles, 'ec', literature_type='WL', stage_decision='include',
        )
        r2 = SessionQueryService.filter_articles(
            mixed_articles, 'ec', literature_type='WL', stage_decision='include',
        )
        assert [a.article_id for a in r1] == [a.article_id for a in r2]

    def test_no_mutation_of_inputs(self, mixed_articles):
        """Query methods must not mutate input article collections."""
        original_ids = [a.article_id for a in mixed_articles]
        _ = SessionQueryService.get_ec_included_articles(mixed_articles)
        _ = SessionQueryService.get_wl_progress(mixed_articles)
        _ = SessionQueryService.filter_articles(
            mixed_articles, 'ec', literature_type='WL',
        )
        assert [a.article_id for a in mixed_articles] == original_ids

    def test_session_checksum_stability(self, query_session):
        c1 = query_session.compute_checksum()
        c2 = query_session.compute_checksum()
        assert c1 == c2

    def test_multiple_service_instances_identical(self, mixed_articles):
        s1 = SessionQueryService()
        s2 = SessionQueryService()
        r1 = s1.get_ec_included_articles(mixed_articles)
        r2 = s2.get_ec_included_articles(mixed_articles)
        assert [a.article_id for a in r1] == [a.article_id for a in r2]


# ---------------------------------------------------------------------------
# Architectural boundary — SessionQueryService has restricted dependencies
# ---------------------------------------------------------------------------

class TestSessionQueryArchitecturalBoundary:
    """SessionQueryService must not import from UI, advisory, or export layers."""

    IMPORT_BLACKLIST = [
        'src.ui', 'streamlit', 'src.advisory', 'src.core.export',
    ]

    def test_no_forbidden_imports_in_source(self):
        """Source-level check for forbidden imports."""
        source = inspect.getsource(SessionQueryService)
        for banned in self.IMPORT_BLACKLIST:
            assert banned not in source, (
                f"SessionQueryService must not reference '{banned}'"
            )

    def test_module_ast_no_import_from_ui(self):
        """AST-level check: session_query_service.py has no forbidden imports."""
        qs_path = (
            Path(__file__).parent.parent
            / 'src' / 'core' / 'session_query_service.py'
        )
        tree = ast.parse(qs_path.read_text(encoding='utf-8'))

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ''
                for banned in self.IMPORT_BLACKLIST:
                    assert not module.startswith(banned), (
                        f"session_query_service.py must not import '{module}'"
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    for banned in self.IMPORT_BLACKLIST:
                        assert not alias.name.startswith(banned), (
                            f"session_query_service.py must not import "
                            f"'{alias.name}'"
                        )

    def test_no_persistence_in_source(self):
        """No persistence-related code in query service."""
        qs_path = (
            Path(__file__).parent.parent
            / 'src' / 'core' / 'session_query_service.py'
        )
        source = qs_path.read_text(encoding='utf-8')
        persistence_hints = ['json.dump', 'json.load', '.save(', '.load(',
                             'open(']
        for hint in persistence_hints:
            assert hint not in source, (
                f"SessionQueryService must not contain '{hint}'"
            )

    def test_screening_session_delegates_to_query_service(self):
        """ScreeningSession query methods should call SessionQueryService."""
        query_methods = [
            'get_discussion_articles',
            'get_skipped_articles',
            'get_ec_included_articles',
            'get_ic_included_articles',
            'get_wl_articles',
            'get_gl_articles',
            'filter_articles',
            'get_wl_progress',
            'get_gl_progress',
            'get_pending_for_stage',
            'get_progress',
        ]
        for method_name in query_methods:
            method = getattr(ScreeningSession, method_name)
            source = inspect.getsource(method)
            assert 'SessionQueryService.' in source, (
                f"{method_name} should delegate to SessionQueryService"
            )


# ---------------------------------------------------------------------------
# Serialization preservation
# ---------------------------------------------------------------------------

class TestSessionQuerySerialization:
    """Serialization format unchanged after query extraction."""

    def test_serialized_fields_unchanged(self, query_session):
        d = query_session._to_dict()
        expected = {
            'session_id', 'created_at', 'protocol_version', 'stage',
            'current_index', 'total_count', 'ec_completed', 'ic_completed',
            'included_count', 'excluded_count', 'skip_count',
            'discussion_count', 'researcher_id', 'last_saved', 'articles',
        }
        for field in expected:
            assert field in d, f'Missing serialized field: {field}'

    def test_no_service_leak_in_to_dict(self, query_session):
        d = query_session._to_dict()
        assert 'SessionQueryService' not in str(d.keys())

    def test_no_service_leak_in_to_dict_full(self, query_session):
        d = query_session._to_dict_full()
        assert 'SessionQueryService' not in str(d.keys())

    def test_session_hash_stable(self, query_session):
        import hashlib, json
        data = query_session._to_dict()
        h1 = hashlib.sha256(
            json.dumps(data, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()[:16]
        h2 = hashlib.sha256(
            json.dumps(data, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()[:16]
        assert h1 == h2


# ---------------------------------------------------------------------------
# Verification — pre-existing caller compatibility
# ---------------------------------------------------------------------------

class TestExistingCallerCompatibility:
    """Methods that existing callers rely on still produce identical output."""

    def test_get_wl_articles_export_view_pattern(self, query_session):
        """Pattern used in export_view.py: len(session.get_wl_articles())"""
        wl_count = len(query_session.get_wl_articles())
        assert wl_count == 5

    def test_get_gl_articles_export_engine_pattern(self, query_session):
        """Pattern used in export_engine.py: gl_articles = session.get_gl_articles()"""
        gl_articles = query_session.get_gl_articles()
        assert len(gl_articles) == 2

    def test_get_ec_included_ic_view_pattern(self, query_session):
        """Pattern used in ic_screening_view.py"""
        ec_included = query_session.get_ec_included_articles()
        assert len(ec_included) == 2

    def test_get_wl_progress_ec_view_pattern(self, query_session):
        """Pattern used in ec_screening_view.py: progress dict access"""
        wl_progress = query_session.get_wl_progress()
        assert wl_progress['total'] >= 0
        assert 'progress_pct' in wl_progress

    def test_get_gl_progress_ic_view_pattern(self, query_session):
        """Pattern used in ic_screening_view.py: progress dict access"""
        gl_progress = query_session.get_gl_progress()
        assert gl_progress['total'] >= 0
        assert 'progress_pct' in gl_progress
