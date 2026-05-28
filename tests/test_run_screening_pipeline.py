from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_mock import MockerFixture

from src.domain.enums import CriterionType, ScreeningStatus, SourceType
from src.domain.models import Criterion, Paper, ScreeningDecision


@pytest.fixture
def papers():
    return [
        Paper(id="p1", title="Paper A", source_type=SourceType.WL, publication_year=2023),
        Paper(id="p2", title="Paper B", source_type=SourceType.WL, publication_year=2023),
        Paper(id="p3", title="Paper C", source_type=SourceType.WL, publication_year=2023),
    ]


@pytest.fixture
def criteria():
    return [
        Criterion(
            id="c-ec4",
            type=CriterionType.EXCLUSION,
            code="EC4",
            description="Before 2015",
        ),
    ]


@pytest.fixture
def mock_paper_repo(papers):
    repo = MagicMock()
    repo.get_all_papers.return_value = papers
    return repo


@pytest.fixture
def mock_decision_repo():
    repo = MagicMock()
    repo.get_few_shot_examples.return_value = []
    return repo


@pytest.fixture
def mock_screen_use_case():
    use_case = MagicMock()
    use_case.execute = AsyncMock()
    return use_case


class TestRunScreeningPipeline:
    @pytest.mark.asyncio
    async def test_processes_all_papers(
        self, papers, criteria, mock_paper_repo, mock_decision_repo, mock_screen_use_case
    ):
        from src.use_cases.run_screening_pipeline import RunScreeningPipelineUseCase

        mock_decision_repo.get_decision.return_value = None
        mock_screen_use_case.execute.side_effect = [
            ScreeningDecision(
                paper_id=p.id,
                status=ScreeningStatus.INCLUDED,
                confidence_score=0.9,
                rationale="OK",
                applied_criteria_codes=["IC1"],
            )
            for p in papers
        ]

        use_case = RunScreeningPipelineUseCase(
            paper_repository=mock_paper_repo,
            decision_repository=mock_decision_repo,
            screen_paper_use_case=mock_screen_use_case,
            criteria=criteria,
        )
        processed = await use_case.execute()

        assert processed == 3
        assert mock_screen_use_case.execute.call_count == 3
        assert mock_decision_repo.save_decision.call_count == 3

    @pytest.mark.asyncio
    async def test_skips_papers_with_existing_decisions(
        self, papers, criteria, mock_paper_repo, mock_decision_repo, mock_screen_use_case
    ):
        from src.use_cases.run_screening_pipeline import RunScreeningPipelineUseCase

        def get_decision_side_effect(paper_id):
            if paper_id == "p1":
                return ScreeningDecision(
                    paper_id="p1",
                    status=ScreeningStatus.INCLUDED,
                    confidence_score=0.9,
                    rationale="Already done",
                    applied_criteria_codes=["IC1"],
                )
            return None

        mock_decision_repo.get_decision.side_effect = get_decision_side_effect
        mock_screen_use_case.execute.side_effect = [
            ScreeningDecision(
                paper_id=p.id,
                status=ScreeningStatus.INCLUDED,
                confidence_score=0.9,
                rationale="OK",
                applied_criteria_codes=["IC1"],
            )
            for p in papers[1:]
        ]

        use_case = RunScreeningPipelineUseCase(
            paper_repository=mock_paper_repo,
            decision_repository=mock_decision_repo,
            screen_paper_use_case=mock_screen_use_case,
            criteria=criteria,
        )
        processed = await use_case.execute()

        assert processed == 2
        assert mock_screen_use_case.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_saves_decision_immediately_after_screening(
        self, papers, criteria, mock_paper_repo, mock_decision_repo, mock_screen_use_case
    ):
        from src.use_cases.run_screening_pipeline import RunScreeningPipelineUseCase

        mock_decision_repo.get_decision.return_value = None

        decisions_iter = iter(
            ScreeningDecision(
                paper_id=p.id,
                status=ScreeningStatus.INCLUDED,
                confidence_score=0.9,
                rationale=f"Result for {p.id}",
                applied_criteria_codes=["IC1"],
            )
            for p in papers
        )
        mock_screen_use_case.execute.side_effect = lambda paper, criteria, **kwargs: next(decisions_iter)

        use_case = RunScreeningPipelineUseCase(
            paper_repository=mock_paper_repo,
            decision_repository=mock_decision_repo,
            screen_paper_use_case=mock_screen_use_case,
            criteria=criteria,
        )
        await use_case.execute()

        assert mock_decision_repo.save_decision.call_count == 3
        for i, p in enumerate(papers):
            saved = mock_decision_repo.save_decision.call_args_list[i][0][0]
            assert saved.paper_id == p.id

    @pytest.mark.asyncio
    async def test_keyboard_interrupt_graceful(
        self, papers, criteria, mock_paper_repo, mock_decision_repo, mock_screen_use_case
    ):
        from src.use_cases.run_screening_pipeline import RunScreeningPipelineUseCase

        mock_decision_repo.get_decision.return_value = None

        call_count = 0

        async def side_effect(paper, criteria, **_):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise KeyboardInterrupt()
            return ScreeningDecision(
                paper_id=paper.id,
                status=ScreeningStatus.INCLUDED,
                confidence_score=0.9,
                rationale="OK",
                applied_criteria_codes=["IC1"],
            )

        mock_screen_use_case.execute.side_effect = side_effect

        use_case = RunScreeningPipelineUseCase(
            paper_repository=mock_paper_repo,
            decision_repository=mock_decision_repo,
            screen_paper_use_case=mock_screen_use_case,
            criteria=criteria,
        )
        processed = await use_case.execute()

        assert processed == 1
        assert mock_decision_repo.save_decision.call_count == 1

    @pytest.mark.asyncio
    async def test_empty_paper_list(
        self, criteria, mock_paper_repo, mock_decision_repo, mock_screen_use_case
    ):
        from src.use_cases.run_screening_pipeline import RunScreeningPipelineUseCase

        mock_paper_repo.get_all_papers.return_value = []

        use_case = RunScreeningPipelineUseCase(
            paper_repository=mock_paper_repo,
            decision_repository=mock_decision_repo,
            screen_paper_use_case=mock_screen_use_case,
            criteria=criteria,
        )
        processed = await use_case.execute()

        assert processed == 0
        mock_screen_use_case.execute.assert_not_called()
        mock_decision_repo.save_decision.assert_not_called()

    @pytest.mark.asyncio
    async def test_all_papers_already_screened(
        self, papers, criteria, mock_paper_repo, mock_decision_repo, mock_screen_use_case
    ):
        from src.use_cases.run_screening_pipeline import RunScreeningPipelineUseCase

        mock_decision_repo.get_decision.return_value = ScreeningDecision(
            paper_id="any",
            status=ScreeningStatus.INCLUDED,
            confidence_score=0.9,
            rationale="Done",
            applied_criteria_codes=["IC1"],
        )

        use_case = RunScreeningPipelineUseCase(
            paper_repository=mock_paper_repo,
            decision_repository=mock_decision_repo,
            screen_paper_use_case=mock_screen_use_case,
            criteria=criteria,
        )
        processed = await use_case.execute()

        assert processed == 0
        mock_screen_use_case.execute.assert_not_called()
        mock_decision_repo.save_decision.assert_not_called()
