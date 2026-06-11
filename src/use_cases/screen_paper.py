from collections.abc import Callable
from typing import Optional

from src.domain.interfaces import LLMService
from src.domain.models import Criterion, Paper, ScreeningDecision
from src.use_cases.heuristic_screening import HeuristicScreeningUseCase


class ScreenPaperUseCase:
    def __init__(
        self,
        heuristic_use_case: HeuristicScreeningUseCase,
        llm_service: LLMService,
        cooldown_callback: Callable[[float], None] | None = None,
    ) -> None:
        self._heuristic = heuristic_use_case
        self._llm = llm_service
        self._cooldown_callback = cooldown_callback

    async def execute(
        self,
        paper: Paper,
        criteria: list[Criterion],
        few_shot_examples: Optional[list[dict]] = None,
    ) -> ScreeningDecision:
        decision = self._heuristic.execute(paper=paper, criteria=criteria)
        if decision is not None:
            return decision
        return await self._llm.screen_paper(
            paper=paper,
            criteria=criteria,
            few_shot_examples=few_shot_examples,
            cooldown_callback=self._cooldown_callback,
        )
