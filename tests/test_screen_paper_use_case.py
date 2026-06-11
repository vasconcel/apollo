from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_mock import MockerFixture

from src.domain.enums import CriterionType, ScreeningStatus, SourceType
from src.domain.models import Criterion, Paper, ScreeningDecision


@pytest.fixture
def paper() -> Paper:
    return Paper(
        id="p1",
        title="A Valid Paper",
        source_type=SourceType.WL,
        publication_year=2023,
    )


@pytest.fixture
def criteria() -> list[Criterion]:
    return [
        Criterion(
            id="c-ec4",
            type=CriterionType.EXCLUSION,
            code="EC4",
            description="Before 2015",
        ),
    ]


class TestScreenPaperUseCase:
    @pytest.mark.asyncio
    async def test_heuristic_decision_returned_immediately(self, paper, criteria, mocker: MockerFixture):
        from src.use_cases.heuristic_screening import HeuristicScreeningUseCase
        from src.use_cases.screen_paper import ScreenPaperUseCase

        heuristic_decision = ScreeningDecision(
            paper_id=paper.id,
            status=ScreeningStatus.EXCLUDED,
            confidence_score=1.0,
            rationale="Excluded by EC4: year before 2015.",
            applied_criteria_codes=["EC4"],
        )

        mock_heuristic = MagicMock(spec=HeuristicScreeningUseCase)
        mock_heuristic.execute.return_value = heuristic_decision

        mock_llm = MagicMock()
        mock_llm.screen_paper = AsyncMock()

        use_case = ScreenPaperUseCase(
            heuristic_use_case=mock_heuristic,
            llm_service=mock_llm,
        )
        decision = await use_case.execute(paper=paper, criteria=criteria)

        assert decision is heuristic_decision
        mock_heuristic.execute.assert_called_once_with(paper=paper, criteria=criteria)
        mock_llm.screen_paper.assert_not_called()

    @pytest.mark.asyncio
    async def test_heuristic_passes_llm_is_called(self, paper, criteria, mocker: MockerFixture):
        from src.use_cases.heuristic_screening import HeuristicScreeningUseCase
        from src.use_cases.screen_paper import ScreenPaperUseCase

        llm_decision = ScreeningDecision(
            paper_id=paper.id,
            status=ScreeningStatus.INCLUDED,
            confidence_score=0.85,
            rationale="Meets criteria.",
            applied_criteria_codes=["IC1"],
        )

        mock_heuristic = MagicMock(spec=HeuristicScreeningUseCase)
        mock_heuristic.execute.return_value = None

        mock_llm = MagicMock()
        mock_llm.screen_paper = AsyncMock(return_value=llm_decision)

        use_case = ScreenPaperUseCase(
            heuristic_use_case=mock_heuristic,
            llm_service=mock_llm,
        )
        decision = await use_case.execute(paper=paper, criteria=criteria)

        assert decision is llm_decision
        mock_heuristic.execute.assert_called_once()
        mock_llm.screen_paper.assert_called_once_with(
            paper=paper,
            criteria=criteria,
            few_shot_examples=None,
            cooldown_callback=None,
        )
