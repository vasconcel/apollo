from abc import ABC, abstractmethod

from src.domain.models import Paper


class PaperRepository(ABC):
    @abstractmethod
    def get_all_papers(self) -> list[Paper]:
        """Retrieve all papers from the data source."""
