import pytest
from uuid import UUID
from pydantic import ValidationError

from src.domain.enums import SourceType, CriterionType, ScreeningStatus
from src.domain.models import Paper, Criterion, ScreeningDecision


# ── Enums ──────────────────────────────────────────────────────────────────


class TestSourceType:
    def test_has_wl_and_gl_values(self):
        assert SourceType.WL.value == "WL"
        assert SourceType.GL.value == "GL"

    def test_from_string(self):
        assert SourceType("WL") is SourceType.WL
        assert SourceType("GL") is SourceType.GL

    def test_unknown_value_raises(self):
        with pytest.raises(ValueError):
            SourceType("INVALID")


class TestCriterionType:
    def test_has_inclusion_and_exclusion(self):
        assert CriterionType.INCLUSION.value == "INCLUSION"
        assert CriterionType.EXCLUSION.value == "EXCLUSION"


class TestScreeningStatus:
    def test_has_expected_values(self):
        assert ScreeningStatus.INCLUDED.value == "INCLUDED"
        assert ScreeningStatus.EXCLUDED.value == "EXCLUDED"
        assert ScreeningStatus.NEEDS_REVIEW.value == "NEEDS_REVIEW"


# ── Paper ──────────────────────────────────────────────────────────────────


class TestPaperCreation:
    def test_create_with_all_fields(self):
        paper = Paper(
            id="123e4567-e89b-12d3-a456-426614174000",
            title="Systematic Review Methods",
            url="https://example.com/paper",
            abstract="This paper discusses SLR methods.",
            source_type=SourceType.WL,
            publication_year=2023,
            metadata={"doi": "10.1234/test", "authors": 3},
        )
        assert paper.id == "123e4567-e89b-12d3-a456-426614174000"
        assert paper.title == "Systematic Review Methods"
        assert paper.url == "https://example.com/paper"
        assert paper.abstract == "This paper discusses SLR methods."
        assert paper.source_type is SourceType.WL
        assert paper.publication_year == 2023
        assert paper.metadata == {"doi": "10.1234/test", "authors": 3}

    def test_create_minimal(self):
        paper = Paper(
            id="abc-123",
            title="Minimal Paper",
            source_type=SourceType.GL,
        )
        assert paper.id == "abc-123"
        assert paper.title == "Minimal Paper"
        assert paper.source_type is SourceType.GL
        assert paper.url is None
        assert paper.abstract is None
        assert paper.publication_year is None
        assert paper.metadata == {}

    def test_create_with_uuid_id(self):
        uuid_val = UUID("123e4567-e89b-12d3-a456-426614174000")
        paper = Paper(
            id=uuid_val,
            title="UUID Paper",
            source_type=SourceType.WL,
        )
        assert paper.id == "123e4567-e89b-12d3-a456-426614174000"

    def test_title_cannot_be_empty(self):
        with pytest.raises(ValidationError):
            Paper(id="p1", title="", source_type=SourceType.WL)

    def test_metadata_defaults_to_empty_dict(self):
        paper = Paper(id="p1", title="Test", source_type=SourceType.GL)
        assert paper.metadata == {}

    def test_invalid_source_type_raises(self):
        with pytest.raises(ValidationError):
            Paper(id="p1", title="Test", source_type="INVALID")


class TestPaperImmutability:
    def test_fields_are_immutable_by_default(self):
        paper = Paper(id="p1", title="Test", source_type=SourceType.WL)
        with pytest.raises(ValidationError):
            paper.title = "New Title"


# ── Criterion ──────────────────────────────────────────────────────────────


class TestCriterionCreation:
    def test_create_inclusion_criterion(self):
        criterion = Criterion(
            id="c1",
            type=CriterionType.INCLUSION,
            code="IC1",
            description="Peer-reviewed studies only",
        )
        assert criterion.id == "c1"
        assert criterion.type is CriterionType.INCLUSION
        assert criterion.code == "IC1"
        assert criterion.description == "Peer-reviewed studies only"

    def test_create_exclusion_criterion(self):
        criterion = Criterion(
            id="c2",
            type=CriterionType.EXCLUSION,
            code="EC1",
            description="Studies before 2010",
        )
        assert criterion.type is CriterionType.EXCLUSION
        assert criterion.code == "EC1"

    def test_description_cannot_be_empty(self):
        with pytest.raises(ValidationError):
            Criterion(
                id="c3",
                type=CriterionType.INCLUSION,
                code="IC2",
                description="",
            )

    def test_code_cannot_be_empty(self):
        with pytest.raises(ValidationError):
            Criterion(
                id="c4",
                type=CriterionType.EXCLUSION,
                code="",
                description="Some description",
            )


# ── ScreeningDecision ─────────────────────────────────────────────────────


class TestScreeningDecisionCreation:
    def test_create_included_decision(self):
        decision = ScreeningDecision(
            paper_id="p1",
            status=ScreeningStatus.INCLUDED,
            confidence_score=0.95,
            rationale="Meets all inclusion criteria.",
            applied_criteria_codes=["IC1", "IC2"],
        )
        assert decision.paper_id == "p1"
        assert decision.status is ScreeningStatus.INCLUDED
        assert decision.confidence_score == 0.95
        assert decision.rationale == "Meets all inclusion criteria."
        assert decision.applied_criteria_codes == ["IC1", "IC2"]

    def test_create_excluded_decision(self):
        decision = ScreeningDecision(
            paper_id="p2",
            status=ScreeningStatus.EXCLUDED,
            confidence_score=0.0,
            rationale="Fails EC1.",
            applied_criteria_codes=["EC1"],
        )
        assert decision.status is ScreeningStatus.EXCLUDED

    def test_create_needs_review_decision(self):
        decision = ScreeningDecision(
            paper_id="p3",
            status=ScreeningStatus.NEEDS_REVIEW,
            confidence_score=0.5,
            rationale="Ambiguous abstract.",
            applied_criteria_codes=[],
        )
        assert decision.status is ScreeningStatus.NEEDS_REVIEW

    def test_empty_rationale_allowed(self):
        decision = ScreeningDecision(
            paper_id="p4",
            status=ScreeningStatus.INCLUDED,
            confidence_score=1.0,
            rationale="",
            applied_criteria_codes=["IC1"],
        )
        assert decision.rationale == ""

    def test_empty_criteria_codes_allowed(self):
        decision = ScreeningDecision(
            paper_id="p5",
            status=ScreeningStatus.NEEDS_REVIEW,
            confidence_score=0.3,
            rationale="Uncertain",
            applied_criteria_codes=[],
        )
        assert decision.applied_criteria_codes == []


class TestConfidenceScoreValidation:
    def test_confidence_at_min_boundary(self):
        decision = ScreeningDecision(
            paper_id="p1",
            status=ScreeningStatus.INCLUDED,
            confidence_score=0.0,
            rationale="",
            applied_criteria_codes=[],
        )
        assert decision.confidence_score == 0.0

    def test_confidence_at_max_boundary(self):
        decision = ScreeningDecision(
            paper_id="p2",
            status=ScreeningStatus.INCLUDED,
            confidence_score=1.0,
            rationale="",
            applied_criteria_codes=[],
        )
        assert decision.confidence_score == 1.0

    def test_confidence_below_zero_raises(self):
        with pytest.raises(ValidationError):
            ScreeningDecision(
                paper_id="p3",
                status=ScreeningStatus.INCLUDED,
                confidence_score=-0.1,
                rationale="",
                applied_criteria_codes=[],
            )

    def test_confidence_above_one_raises(self):
        with pytest.raises(ValidationError):
            ScreeningDecision(
                paper_id="p4",
                status=ScreeningStatus.INCLUDED,
                confidence_score=1.1,
                rationale="",
                applied_criteria_codes=[],
            )
