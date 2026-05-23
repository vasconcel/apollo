from src.domain.interfaces import PaperRepository
from src.domain.models import Paper


class ImportPapersUseCase:
    def __init__(self, repository: PaperRepository) -> None:
        if repository is None:
            raise TypeError("repository must not be None")
        self._repository = repository

    def execute(self) -> list[Paper]:
        return self._repository.get_all_papers()
