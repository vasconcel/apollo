import pytest

from src.domain.enums import CriterionType, ScreeningStatus, SourceType
from src.domain.models import Criterion, Paper

# ── Shared fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def ec4_criterion() -> Criterion:
    return Criterion(
        id="c-ec4",
        type=CriterionType.EXCLUSION,
        code="EC4",
        description="Exclude papers published before 2015",
    )


@pytest.fixture
def ec3_criterion() -> Criterion:
    return Criterion(
        id="c-ec3",
        type=CriterionType.EXCLUSION,
        code="EC3",
        description="Exclude poster/editorial/extended abstract/keynote/tutorial",
    )


@pytest.fixture
def ec1_criterion() -> Criterion:
    return Criterion(
        id="c-ec1",
        type=CriterionType.EXCLUSION,
        code="EC1",
        description="Exclude non-English papers",
    )


@pytest.fixture
def valid_paper() -> Paper:
    return Paper(
        id="p-valid",
        title="A Systematic Review of Agile Methods",
        source_type=SourceType.WL,
        publication_year=2020,
        metadata={"Language": "English", "Authors": "Someone"},
    )


# ── Rule A — EC4: year < 2015 ────────────────────────────────────────────


class TestRuleA_EC4_YearBefore2015:
    def test_excludes_when_year_before_2015(self, ec4_criterion):
        from src.use_cases.heuristic_screening import HeuristicScreeningUseCase

        paper = Paper(
            id="p1",
            title="Old Paper",
            source_type=SourceType.WL,
            publication_year=2014,
        )
        use_case = HeuristicScreeningUseCase()
        decision = use_case.execute(paper=paper, criteria=[ec4_criterion])

        assert decision is not None
        assert decision.status is ScreeningStatus.EXCLUDED
        assert decision.confidence_score == 1.0
        assert "EC4" in decision.applied_criteria_codes
        assert "2015" in decision.rationale

    def test_allows_when_year_is_2015(self, ec4_criterion):
        from src.use_cases.heuristic_screening import HeuristicScreeningUseCase

        paper = Paper(
            id="p2",
            title="Borderline Paper",
            source_type=SourceType.WL,
            publication_year=2015,
        )
        use_case = HeuristicScreeningUseCase()
        decision = use_case.execute(paper=paper, criteria=[ec4_criterion])

        assert decision is None

    def test_allows_when_year_is_none(self, ec4_criterion):
        from src.use_cases.heuristic_screening import HeuristicScreeningUseCase

        paper = Paper(
            id="p3",
            title="No Year Paper",
            source_type=SourceType.WL,
            publication_year=None,
        )
        use_case = HeuristicScreeningUseCase()
        decision = use_case.execute(paper=paper, criteria=[ec4_criterion])

        assert decision is None


# ── Rule B — EC3: keyword regex on title & metadata ──────────────────────


class TestRuleB_EC3_KeywordRegex:
    def test_excludes_title_with_poster(self, ec3_criterion):
        from src.use_cases.heuristic_screening import HeuristicScreeningUseCase

        paper = Paper(
            id="p1",
            title="Poster Session on AI Ethics",
            source_type=SourceType.WL,
            publication_year=2023,
        )
        use_case = HeuristicScreeningUseCase()
        decision = use_case.execute(paper=paper, criteria=[ec3_criterion])

        assert decision is not None
        assert decision.status is ScreeningStatus.EXCLUDED
        assert "EC3" in decision.applied_criteria_codes

    def test_excludes_title_with_editorial_case_insensitive(self, ec3_criterion):
        from src.use_cases.heuristic_screening import HeuristicScreeningUseCase

        paper = Paper(
            id="p2",
            title="EDITORIAL: Special Issue on SE",
            source_type=SourceType.WL,
            publication_year=2023,
        )
        use_case = HeuristicScreeningUseCase()
        decision = use_case.execute(paper=paper, criteria=[ec3_criterion])

        assert decision is not None
        assert decision.status is ScreeningStatus.EXCLUDED

    def test_excludes_title_with_extended_abstract(self, ec3_criterion):
        from src.use_cases.heuristic_screening import HeuristicScreeningUseCase

        paper = Paper(
            id="p3",
            title="Extended Abstract: New Approach",
            source_type=SourceType.WL,
            publication_year=2023,
        )
        use_case = HeuristicScreeningUseCase()
        decision = use_case.execute(paper=paper, criteria=[ec3_criterion])

        assert decision is not None
        assert decision.status is ScreeningStatus.EXCLUDED

    def test_excludes_title_with_keynote(self, ec3_criterion):
        from src.use_cases.heuristic_screening import HeuristicScreeningUseCase

        paper = Paper(
            id="p4",
            title="Keynote Talk at ICSE 2023",
            source_type=SourceType.WL,
            publication_year=2023,
        )
        use_case = HeuristicScreeningUseCase()
        decision = use_case.execute(paper=paper, criteria=[ec3_criterion])

        assert decision is not None
        assert decision.status is ScreeningStatus.EXCLUDED

    def test_excludes_title_with_tutorial(self, ec3_criterion):
        from src.use_cases.heuristic_screening import HeuristicScreeningUseCase

        paper = Paper(
            id="p5",
            title="Conference Tutorial on DevOps",
            source_type=SourceType.WL,
            publication_year=2023,
        )
        use_case = HeuristicScreeningUseCase()
        decision = use_case.execute(paper=paper, criteria=[ec3_criterion])

        assert decision is not None
        assert decision.status is ScreeningStatus.EXCLUDED

    def test_excludes_metadata_keywords_field(self, ec3_criterion):
        from src.use_cases.heuristic_screening import HeuristicScreeningUseCase

        paper = Paper(
            id="p6",
            title="Some Paper Title",
            source_type=SourceType.WL,
            publication_year=2023,
            metadata={"Keywords": "keynote speech, SE"},
        )
        use_case = HeuristicScreeningUseCase()
        decision = use_case.execute(paper=paper, criteria=[ec3_criterion])

        assert decision is not None
        assert decision.status is ScreeningStatus.EXCLUDED

    def test_allows_when_no_keyword_match(self, ec3_criterion):
        from src.use_cases.heuristic_screening import HeuristicScreeningUseCase

        paper = Paper(
            id="p7",
            title="A Real Research Paper on Agile",
            source_type=SourceType.WL,
            publication_year=2023,
            metadata={"Keywords": "agile, software engineering"},
        )
        use_case = HeuristicScreeningUseCase()
        decision = use_case.execute(paper=paper, criteria=[ec3_criterion])

        assert decision is None

    def test_word_boundary_no_false_positive(self, ec3_criterion):
        from src.use_cases.heuristic_screening import HeuristicScreeningUseCase

        paper = Paper(
            id="p8",
            title="Posterity of Software Engineering Methods",
            source_type=SourceType.WL,
            publication_year=2023,
        )
        use_case = HeuristicScreeningUseCase()
        decision = use_case.execute(paper=paper, criteria=[ec3_criterion])

        assert decision is None


# ── Rule C — EC1: language check ─────────────────────────────────────────


class TestRuleC_EC1_Language:
    def test_excludes_non_english_language(self, ec1_criterion):
        from src.use_cases.heuristic_screening import HeuristicScreeningUseCase

        paper = Paper(
            id="p1",
            title="Um Estudo sobre Métodos",
            source_type=SourceType.WL,
            publication_year=2023,
            metadata={"Language": "Portuguese"},
        )
        use_case = HeuristicScreeningUseCase()
        decision = use_case.execute(paper=paper, criteria=[ec1_criterion])

        assert decision is not None
        assert decision.status is ScreeningStatus.EXCLUDED
        assert "EC1" in decision.applied_criteria_codes

    def test_allows_english_language(self, ec1_criterion):
        from src.use_cases.heuristic_screening import HeuristicScreeningUseCase

        paper = Paper(
            id="p2",
            title="A Study on Methods",
            source_type=SourceType.WL,
            publication_year=2023,
            metadata={"Language": "English"},
        )
        use_case = HeuristicScreeningUseCase()
        decision = use_case.execute(paper=paper, criteria=[ec1_criterion])

        assert decision is None

    def test_allows_missing_language(self, ec1_criterion):
        from src.use_cases.heuristic_screening import HeuristicScreeningUseCase

        paper = Paper(
            id="p3",
            title="A Study on Methods",
            source_type=SourceType.WL,
            publication_year=2023,
            metadata={},
        )
        use_case = HeuristicScreeningUseCase()
        decision = use_case.execute(paper=paper, criteria=[ec1_criterion])

        assert decision is None

    def test_allows_language_none(self, ec1_criterion):
        from src.use_cases.heuristic_screening import HeuristicScreeningUseCase

        paper = Paper(
            id="p4",
            title="A Study on Methods",
            source_type=SourceType.WL,
            publication_year=2023,
            metadata={"Language": None},
        )
        use_case = HeuristicScreeningUseCase()
        decision = use_case.execute(paper=paper, criteria=[ec1_criterion])

        assert decision is None


# ── Multi-rule / integration ──────────────────────────────────────────────


class TestMultipleRules:
    def test_valid_paper_passes_all_rules(self, valid_paper, ec4_criterion, ec3_criterion, ec1_criterion):
        from src.use_cases.heuristic_screening import HeuristicScreeningUseCase

        use_case = HeuristicScreeningUseCase()
        decision = use_case.execute(
            paper=valid_paper,
            criteria=[ec4_criterion, ec3_criterion, ec1_criterion],
        )

        assert decision is None

    def test_returns_first_matching_rule(self, ec4_criterion, ec3_criterion):
        from src.use_cases.heuristic_screening import HeuristicScreeningUseCase

        paper = Paper(
            id="p1",
            title="Poster: Old Paper",
            source_type=SourceType.WL,
            publication_year=2010,
        )
        use_case = HeuristicScreeningUseCase()
        decision = use_case.execute(
            paper=paper,
            criteria=[ec4_criterion, ec3_criterion],
        )

        assert decision is not None
        assert "EC4" in decision.applied_criteria_codes

    def test_ignores_inclusion_criteria(self, ec4_criterion):
        from src.use_cases.heuristic_screening import HeuristicScreeningUseCase

        inclusion_criterion = Criterion(
            id="c-ic1",
            type=CriterionType.INCLUSION,
            code="IC1",
            description="Peer-reviewed",
        )
        paper = Paper(
            id="p1",
            title="A Good Paper",
            source_type=SourceType.WL,
            publication_year=2020,
        )
        use_case = HeuristicScreeningUseCase()
        decision = use_case.execute(
            paper=paper,
            criteria=[inclusion_criterion, ec4_criterion],
        )

        assert decision is None


class TestDecisionStructure:
    def test_decision_has_correct_fields(self, ec4_criterion):
        from src.use_cases.heuristic_screening import HeuristicScreeningUseCase

        paper = Paper(
            id="p-excluded",
            title="Old Paper",
            source_type=SourceType.WL,
            publication_year=2010,
        )
        use_case = HeuristicScreeningUseCase()
        decision = use_case.execute(paper=paper, criteria=[ec4_criterion])

        assert decision.paper_id == "p-excluded"
        assert decision.status is ScreeningStatus.EXCLUDED
        assert decision.confidence_score == 1.0
        assert isinstance(decision.rationale, str)
        assert len(decision.rationale) > 0
        assert decision.applied_criteria_codes == ["EC4"]


class TestEdgeCases:
    def test_empty_criteria_list(self):
        from src.use_cases.heuristic_screening import HeuristicScreeningUseCase

        paper = Paper(
            id="p1",
            title="Any Paper",
            source_type=SourceType.WL,
            publication_year=2020,
        )
        use_case = HeuristicScreeningUseCase()
        decision = use_case.execute(paper=paper, criteria=[])

        assert decision is None

    def test_unknown_criterion_code_skipped(self):
        from src.use_cases.heuristic_screening import HeuristicScreeningUseCase

        unknown = Criterion(
            id="c-unknown",
            type=CriterionType.EXCLUSION,
            code="EC99",
            description="Unknown rule",
        )
        paper = Paper(
            id="p1",
            title="A Paper",
            source_type=SourceType.WL,
            publication_year=2020,
        )
        use_case = HeuristicScreeningUseCase()
        decision = use_case.execute(paper=paper, criteria=[unknown])

        assert decision is None
