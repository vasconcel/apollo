from abc import ABC, abstractmethod

from typing import Optional

from src.domain.models import Criterion, Paper, ScreeningDecision


class PaperRepository(ABC):
    @abstractmethod
    def get_all_papers(self) -> list[Paper]:
        """Retrieve all papers from the data source."""


class LLMService(ABC):
    @abstractmethod
    async def screen_paper(
        self,
        paper: Paper,
        criteria: list[Criterion],
    ) -> ScreeningDecision:
        """Evaluate a paper against criteria using an LLM and return a decision."""


class ScreeningDecisionRepository(ABC):
    @abstractmethod
    def save_decision(self, decision: ScreeningDecision) -> None:
        """Persist a screening decision (insert or update)."""

    @abstractmethod
    def get_decision(self, paper_id: str) -> Optional[ScreeningDecision]:
        """Retrieve a decision by paper_id, or None if not found."""

    @abstractmethod
    def get_all_decisions(self) -> list[ScreeningDecision]:
        """Retrieve all persisted screening decisions."""

    @abstractmethod
    def get_human_decision_map(self) -> dict[str, str]:
        """Return a dict mapping paper_id to human audit verdict ("YES"/"NO")."""

    @abstractmethod
    def save_bulk_audit(self, paper_ids: list[str], human_decision: str) -> None:
        """Save the same human audit verdict for multiple papers in a single transaction."""
