from unittest.mock import MagicMock

import pytest

from src.domain.models import Paper, SourceType


@pytest.fixture
def mock_repository():
    repo = MagicMock()
    repo.get_all_papers.return_value = [
        Paper(id="1", title="Paper A", source_type=SourceType.WL),
        Paper(id="2", title="Paper B", source_type=SourceType.GL),
    ]
    return repo


class TestImportPapersUseCase:
    def test_execute_returns_papers_from_repository(self, mock_repository):
        from src.use_cases.import_papers import ImportPapersUseCase

        use_case = ImportPapersUseCase(repository=mock_repository)
        result = use_case.execute()

        assert len(result) == 2
        assert result[0].title == "Paper A"
        assert result[1].title == "Paper B"

    def test_execute_calls_repository_get_all_papers(self, mock_repository):
        from src.use_cases.import_papers import ImportPapersUseCase

        use_case = ImportPapersUseCase(repository=mock_repository)
        use_case.execute()

        mock_repository.get_all_papers.assert_called_once()

    def test_execute_returns_empty_list_when_repository_empty(self):
        from src.use_cases.import_papers import ImportPapersUseCase

        repo = MagicMock()
        repo.get_all_papers.return_value = []

        use_case = ImportPapersUseCase(repository=repo)
        result = use_case.execute()

        assert result == []

    def test_raises_when_repository_is_none(self):
        from src.use_cases.import_papers import ImportPapersUseCase

        with pytest.raises(TypeError):
            ImportPapersUseCase(repository=None)
