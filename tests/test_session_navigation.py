"""
APOLLO Tests - Session Navigation Extraction

Verifies that navigation logic was correctly extracted from ScreeningSession
into NavigationService with full behavioral parity.

Architectural boundaries tested:
- NavigationService contains no Streamlit or UI imports
- NavigationService contains no advisory imports
- NavigationService contains no persistence logic
- Delegation preserves all public navigation semantics
- Serialization format is unchanged
"""

import pytest

from src.core.architectural_fitness import (
    assert_source_lacks,
    assert_module_ast_lacks_imports,
    get_source,
    resolve_source_path,
)

from src.core.screening_session import (
    ScreeningSession, ArticleReview, SessionStage,
)
from src.core.session_navigation import NavigationService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def three_articles():
    return [
        ArticleReview(article_id='1', title='A', abstract='abs1',
                      metadata={'literature_type': 'WL'}),
        ArticleReview(article_id='2', title='B', abstract='abs2',
                      metadata={'literature_type': 'WL'}),
        ArticleReview(article_id='3', title='C', abstract='abs3',
                      metadata={'literature_type': 'WL'}),
    ]


@pytest.fixture
def empty_session(three_articles):
    session = ScreeningSession(
        session_id='test_nav',
        created_at='2025-01-01T00:00:00',
        articles=three_articles,
        current_index=0,
        total_count=3,
    )
    return session


# ---------------------------------------------------------------------------
# NavigationService — stateless unit tests
# ---------------------------------------------------------------------------

class TestNavigationService:
    """NavigationService operates on (articles, index) explicitly."""

    def test_get_current_article_valid(self, three_articles):
        assert NavigationService.get_current_article(three_articles, 0).title == 'A'
        assert NavigationService.get_current_article(three_articles, 2).title == 'C'

    def test_get_current_article_out_of_bounds(self, three_articles):
        assert NavigationService.get_current_article(three_articles, 5) is None
        assert NavigationService.get_current_article(three_articles, -1) is None

    def test_get_current_article_empty(self):
        assert NavigationService.get_current_article([], 0) is None

    def test_is_valid_index(self, three_articles):
        assert NavigationService.is_valid_index(three_articles, 0) is True
        assert NavigationService.is_valid_index(three_articles, 2) is True
        assert NavigationService.is_valid_index(three_articles, 3) is False
        assert NavigationService.is_valid_index(three_articles, -1) is False
        assert NavigationService.is_valid_index([], 0) is False

    def test_clamp_index(self):
        assert NavigationService.clamp_index(5, 10) == 5
        assert NavigationService.clamp_index(15, 10) == 9
        assert NavigationService.clamp_index(-1, 10) == 0
        assert NavigationService.clamp_index(0, 0) == 0
        assert NavigationService.clamp_index(5, 0) == 0

    def test_next_index(self):
        assert NavigationService.next_index(0, 10) == 1
        assert NavigationService.next_index(9, 10) == 9
        assert NavigationService.next_index(0, 0) == 0

    def test_previous_index(self):
        assert NavigationService.previous_index(1) == 0
        assert NavigationService.previous_index(0) == 0
        assert NavigationService.previous_index(5) == 4

    def test_advance_no_skip_stays_at_undecided(self, three_articles):
        """With no decisions recorded, advance should stay at current index."""
        result = NavigationService.advance(three_articles, 0, 'ec')
        assert result == 0

    def test_advance_past_decided(self, three_articles):
        """Advance past articles that have decisions."""
        three_articles[0].ec_stage = 'include'
        three_articles[1].ec_stage = 'exclude'
        result = NavigationService.advance(three_articles, 0, 'ec')
        assert result == 2

    def test_advance_skip_mode(self, three_articles):
        """Skip=True unconditionally advances by 1."""
        result = NavigationService.advance(three_articles, 0, 'ec', skip=True)
        assert result == 1

    def test_advance_past_end(self, three_articles):
        """Advance past total articles count."""
        three_articles[0].ec_stage = 'include'
        three_articles[1].ec_stage = 'exclude'
        three_articles[2].ec_stage = 'include'
        result = NavigationService.advance(three_articles, 0, 'ec')
        assert result == 3

    def test_skip_unreviewable_skips(self, three_articles):
        """Article that can't proceed to IC from EC should be skipped."""
        three_articles[0].ec_stage = 'exclude'
        result = NavigationService.skip_unreviewable(three_articles, 0, 'ic')
        assert result == 1

    def test_skip_unreviewable_no_skip_needed(self, three_articles):
        """Article that passed EC can proceed to IC."""
        three_articles[0].ec_stage = 'include'
        result = NavigationService.skip_unreviewable(three_articles, 0, 'ic')
        assert result == 0

    def test_can_review_current_at_stage_true(self, three_articles):
        assert NavigationService.can_review_current_at_stage(
            three_articles, 0, 'ec'
        ) is True

    def test_can_review_current_at_stage_false_oob(self, three_articles):
        assert NavigationService.can_review_current_at_stage(
            three_articles, 5, 'ec'
        ) is False

    def test_is_complete(self):
        assert NavigationService.is_complete(10, 10, 'ec') is True
        assert NavigationService.is_complete(5, 10, 'ec') is False
        assert NavigationService.is_complete(0, 10, 'complete') is True

    def test_stage_field(self):
        assert NavigationService._stage_field('ec') == 'ec_stage'
        assert NavigationService._stage_field('ic') == 'ic_stage'
        assert NavigationService._stage_field('qc') == ''


# ---------------------------------------------------------------------------
# ScreeningSession delegation — behavioral parity
# ---------------------------------------------------------------------------

class TestScreeningSessionNavigationDelegation:
    """ScreeningSession delegates navigation to NavigationService."""

    def test_get_current_article(self, empty_session):
        a = empty_session.get_current_article()
        assert a is not None
        assert a.title == 'A'

    def test_get_current_article_past_end(self, empty_session):
        empty_session.current_index = 5
        assert empty_session.get_current_article() is None

    def test_can_review_current_at_stage(self, empty_session):
        assert empty_session.can_review_current_at_stage('ec') is True

    def test_advance_no_decisions(self, empty_session):
        empty_session.advance()
        assert empty_session.current_index == 0

    def test_advance_after_decisions(self, empty_session):
        empty_session.record_decision('include')
        empty_session.advance()
        assert empty_session.current_index == 1

    def test_advance_skip(self, empty_session):
        empty_session.advance(skip=True)
        assert empty_session.current_index == 1

    def test_advance_traverses_all(self, empty_session):
        empty_session.record_decision('include')
        empty_session.advance()
        empty_session.record_decision('exclude')
        empty_session.advance()
        empty_session.record_decision('include')
        empty_session.advance()
        assert empty_session.current_index >= empty_session.total_count
        assert empty_session.is_complete() is True

    def test_skip_unreviewable_noop(self, empty_session):
        result = empty_session.skip_unreviewable()
        assert result is False
        assert empty_session.current_index == 0

    def test_skip_unreviewable_skips_excluded_in_ic(self, empty_session):
        empty_session.current_index = 0
        empty_session.record_decision('exclude')
        # Move to IC stage
        empty_session.stage = SessionStage.IC.value
        empty_session.current_index = 0
        result = empty_session.skip_unreviewable()
        assert result is True
        assert empty_session.current_index == 1

    def test_is_complete_false(self, empty_session):
        assert empty_session.is_complete() is False

    def test_is_complete_true(self, empty_session):
        empty_session.current_index = empty_session.total_count
        assert empty_session.is_complete() is True


# ---------------------------------------------------------------------------
# Navigation identity — same inputs produce same outputs
# ---------------------------------------------------------------------------

class TestNavigationDeterminism:
    """Navigation is deterministic — identical inputs → identical outputs."""

    def test_advance_deterministic(self, three_articles):
        three_articles[0].ec_stage = 'include'
        three_articles[1].ec_stage = 'exclude'

        result1 = NavigationService.advance(three_articles, 0, 'ec')
        result2 = NavigationService.advance(three_articles, 0, 'ec')
        assert result1 == result2

    def test_session_navigation_checksum_stable(self, empty_session):
        checksum1 = empty_session.compute_checksum()
        empty_session.advance(skip=True)
        checksum2 = empty_session.compute_checksum()
        # navigation state change should change checksum (current_index changed)
        assert checksum1 != checksum2

        # Same state should produce same checksum
        checksum3 = empty_session.compute_checksum()
        assert checksum2 == checksum3


# ---------------------------------------------------------------------------
# Architectural boundary — NavigationService has restricted dependencies
# ---------------------------------------------------------------------------

class TestNavigationArchitecturalBoundary:
    """NavigationService must not import from UI, advisory, or export layers."""

    IMPORT_BLACKLIST = [
        'src.ui', 'streamlit', 'src.advisory', 'src.core.export',
    ]

    def test_no_ui_imports(self):
        """NavigationService should not import from UI layer."""
        assert_source_lacks(
            get_source(NavigationService),
            self.IMPORT_BLACKLIST,
            "NavigationService",
        )

    def test_module_ast_no_import_from_ui(self):
        """AST-level check: session_navigation.py has no UI/advisory imports."""
        assert_module_ast_lacks_imports(
            resolve_source_path(__file__, 'src', 'core', 'session_navigation.py'),
            self.IMPORT_BLACKLIST,
            "session_navigation.py",
        )

    def test_screening_session_delegates_to_navigation(self):
        """ScreeningSession should call NavigationService for navigation."""
        assert 'NavigationService.get_current_article' in get_source(
            ScreeningSession.get_current_article
        )
        assert 'NavigationService.advance' in get_source(ScreeningSession.advance)
        assert 'NavigationService.skip_unreviewable' in get_source(
            ScreeningSession.skip_unreviewable
        )
        assert 'NavigationService.is_complete' in get_source(
            ScreeningSession.is_complete
        )


# ---------------------------------------------------------------------------
# Serialization preservation
# ---------------------------------------------------------------------------

class TestNavigationSerialization:
    """Serialization format unchanged after navigation extraction."""

    SERIALIZED_FIELDS = {
        'session_id', 'created_at', 'protocol_version', 'stage',
        'current_index', 'total_count', 'ec_completed', 'ic_completed',
        'included_count', 'excluded_count', 'skip_count',
        'discussion_count', 'researcher_id', 'last_saved', 'articles',
    }

    def test_no_navigation_leak_in_to_dict(self, empty_session):
        d = empty_session._to_dict()
        assert 'current_index' in d
        assert NavigationService.__name__ not in str(d.keys())

    def test_no_navigation_leak_in_to_dict_full(self, empty_session):
        d = empty_session._to_dict_full()
        assert 'current_index' in d
        assert NavigationService.__name__ not in str(d.keys())

    def test_no_navigation_leak_in_checksum_input(self, empty_session):
        checksum = empty_session.compute_checksum()
        assert isinstance(checksum, str)
        assert len(checksum) == 64

    def test_serialized_fields_unchanged(self, empty_session):
        d = empty_session._to_dict()
        for field in self.SERIALIZED_FIELDS:
            assert field in d, f'Missing serialized field: {field}'
