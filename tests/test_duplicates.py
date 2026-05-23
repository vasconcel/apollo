from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_mock import MockerFixture

from src.domain.enums import CriterionType, ScreeningStatus, SourceType
from src.domain.models import Criterion, Paper, ScreeningDecision

# ── Helpers ────────────────────────────────────────────────────────────────


def _make_paper(pid: str, title: str) -> Paper:
    return Paper(
        id=pid,
        title=title,
        source_type=SourceType.WL,
        publication_year=2023,
    )


# ── Duplicate detection tests ─────────────────────────────────────────────


class TestDuplicateDetectionEC6:
    @pytest.fixture
    def criteria(self):
        return [
            Criterion(
                id="c-ec4",
                type=CriterionType.EXCLUSION,
                code="EC4",
                description="Before 2015",
            ),
        ]

    @pytest.mark.asyncio
    async def test_duplicate_title_excluded_with_ec6(self, criteria, mocker: MockerFixture):
        from src.use_cases.run_screening_pipeline import RunScreeningPipelineUseCase

        paper1 = _make_paper("p1", "Research on Agile Methods")
        paper2 = _make_paper("p2", "Research on Agile Methods")
        papers = [paper1, paper2]

        mock_paper_repo = MagicMock()
        mock_paper_repo.get_all_papers.return_value = papers
        mock_decision_repo = MagicMock()
        mock_decision_repo.get_decision.return_value = None

        mock_screen = MagicMock()
        mock_screen.execute = AsyncMock(return_value=ScreeningDecision(
            paper_id="p1",
            status=ScreeningStatus.INCLUDED,
            confidence_score=0.9,
            rationale="OK",
            applied_criteria_codes=["IC1"],
        ))

        use_case = RunScreeningPipelineUseCase(
            paper_repository=mock_paper_repo,
            decision_repository=mock_decision_repo,
            screen_paper_use_case=mock_screen,
            criteria=criteria,
        )
        processed = await use_case.execute()

        assert processed == 2
        mock_screen.execute.assert_called_once_with(paper=paper1, criteria=criteria)

        ec6_call = mock_decision_repo.save_decision.call_args_list[1][0][0]
        assert ec6_call.paper_id == "p2"
        assert ec6_call.status is ScreeningStatus.EXCLUDED
        assert ec6_call.confidence_score == 1.0
        assert "EC6" in ec6_call.applied_criteria_codes
        assert "duplicate" in ec6_call.rationale.lower()

    @pytest.mark.asyncio
    async def test_different_titles_not_flagged(self, criteria, mocker: MockerFixture):
        from src.use_cases.run_screening_pipeline import RunScreeningPipelineUseCase

        paper1 = _make_paper("p1", "Research on Agile")
        paper2 = _make_paper("p2", "Research on Waterfall")
        papers = [paper1, paper2]

        mock_paper_repo = MagicMock()
        mock_paper_repo.get_all_papers.return_value = papers
        mock_decision_repo = MagicMock()
        mock_decision_repo.get_decision.return_value = None
        mock_screen = MagicMock()
        mock_screen.execute = AsyncMock(return_value=ScreeningDecision(
            paper_id="x", status=ScreeningStatus.INCLUDED,
            confidence_score=0.9, rationale="OK", applied_criteria_codes=["IC1"],
        ))

        use_case = RunScreeningPipelineUseCase(
            paper_repository=mock_paper_repo,
            decision_repository=mock_decision_repo,
            screen_paper_use_case=mock_screen,
            criteria=criteria,
        )
        processed = await use_case.execute()

        assert processed == 2
        assert mock_screen.execute.call_count == 2
        # No EC6 decisions
        for call in mock_decision_repo.save_decision.call_args_list:
            assert "EC6" not in call[0][0].applied_criteria_codes

    @pytest.mark.asyncio
    async def test_case_insensitive_matching(self, criteria, mocker: MockerFixture):
        from src.use_cases.run_screening_pipeline import RunScreeningPipelineUseCase

        paper1 = _make_paper("p1", "Agile in Large Organizations")
        paper2 = _make_paper("p2", "AGILE IN LARGE ORGANIZATIONS")
        papers = [paper1, paper2]

        mock_paper_repo = MagicMock()
        mock_paper_repo.get_all_papers.return_value = papers
        mock_decision_repo = MagicMock()
        mock_decision_repo.get_decision.return_value = None
        mock_screen = MagicMock()
        mock_screen.execute = AsyncMock(return_value=ScreeningDecision(
            paper_id="x", status=ScreeningStatus.INCLUDED,
            confidence_score=0.9, rationale="OK", applied_criteria_codes=["IC1"],
        ))

        use_case = RunScreeningPipelineUseCase(
            paper_repository=mock_paper_repo,
            decision_repository=mock_decision_repo,
            screen_paper_use_case=mock_screen,
            criteria=criteria,
        )
        await use_case.execute()

        ec6_call = mock_decision_repo.save_decision.call_args_list[1][0][0]
        assert "EC6" in ec6_call.applied_criteria_codes

    @pytest.mark.asyncio
    async def test_punctuation_stripped_in_matching(self, criteria, mocker: MockerFixture):
        from src.use_cases.run_screening_pipeline import RunScreeningPipelineUseCase

        paper1 = _make_paper("p1", "What is Agile? A Study.")
        paper2 = _make_paper("p2", "What is Agile  A Study")
        papers = [paper1, paper2]

        mock_paper_repo = MagicMock()
        mock_paper_repo.get_all_papers.return_value = papers
        mock_decision_repo = MagicMock()
        mock_decision_repo.get_decision.return_value = None
        mock_screen = MagicMock()
        mock_screen.execute = AsyncMock(return_value=ScreeningDecision(
            paper_id="x", status=ScreeningStatus.INCLUDED,
            confidence_score=0.9, rationale="OK", applied_criteria_codes=["IC1"],
        ))

        use_case = RunScreeningPipelineUseCase(
            paper_repository=mock_paper_repo,
            decision_repository=mock_decision_repo,
            screen_paper_use_case=mock_screen,
            criteria=criteria,
        )
        await use_case.execute()

        ec6_call = mock_decision_repo.save_decision.call_args_list[1][0][0]
        assert "EC6" in ec6_call.applied_criteria_codes
