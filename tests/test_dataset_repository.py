import pandas as pd
import pytest

from src.domain.enums import SourceType
from src.domain.models import Paper


@pytest.fixture
def csv_fixture(tmp_path):
    """Creates a minimal CSV fixture mirroring the real dataset columns."""
    rows = [
        {
            "Global_ID": 1,
            "Title": "Paper One",
            "URL": "https://example.com/1",
            "Abstract": "Abstract of paper one.",
            "Year": 2023.0,
            "Provenance_Trace": "wl:ACM Digital Library",
            "Authors": "Author A",
            "DOI": "10.1234/one",
        },
        {
            "Global_ID": 2,
            "Title": "Paper Two",
            "URL": "",
            "Abstract": "",
            "Year": float("nan"),
            "Provenance_Trace": "gl:Google Scholar",
            "Authors": "Author B",
            "DOI": "10.1234/two",
        },
        {
            "Global_ID": 3,
            "Title": "Paper Three",
            "URL": "https://example.com/3",
            "Abstract": "Abstract three.",
            "Year": 2021.0,
            "Provenance_Trace": "wl:IEEE Xplore",
            "Authors": "Author C",
            "DOI": "",
        },
    ]
    path = tmp_path / "fixture.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


@pytest.fixture
def empty_csv(tmp_path):
    path = tmp_path / "empty.csv"
    pd.DataFrame(columns=[
        "Global_ID", "Title", "URL", "Abstract", "Year",
        "Provenance_Trace", "Authors", "DOI",
    ]).to_csv(path, index=False)
    return path


# ── DatasetPaperRepository tests ─────────────────────────────────────────


class TestDatasetPaperRepository:
    def test_returns_list_of_paper_entities(self, csv_fixture):
        from src.infrastructure.repositories.dataset_repository import (
            DatasetPaperRepository,
        )

        repo = DatasetPaperRepository(csv_fixture)
        papers = repo.get_all_papers()

        assert isinstance(papers, list)
        assert len(papers) == 3
        assert all(isinstance(p, Paper) for p in papers)

    def test_column_mapping(self, csv_fixture):
        from src.infrastructure.repositories.dataset_repository import (
            DatasetPaperRepository,
        )

        repo = DatasetPaperRepository(csv_fixture)
        papers = repo.get_all_papers()

        p1 = papers[0]
        assert p1.id == "1"
        assert p1.title == "Paper One"
        assert p1.url == "https://example.com/1"
        assert p1.abstract == "Abstract of paper one."
        assert p1.publication_year == 2023
        assert p1.source_type is SourceType.WL

        p2 = papers[1]
        assert p2.id == "2"
        assert p2.title == "Paper Two"
        assert p2.source_type is SourceType.GL

    def test_handles_nan_url_as_none(self, csv_fixture):
        from src.infrastructure.repositories.dataset_repository import (
            DatasetPaperRepository,
        )

        repo = DatasetPaperRepository(csv_fixture)
        papers = repo.get_all_papers()

        p1 = papers[0]
        assert p1.url == "https://example.com/1"

        p2 = papers[1]
        assert p2.url is None

    def test_handles_nan_abstract_as_none(self, csv_fixture):
        from src.infrastructure.repositories.dataset_repository import (
            DatasetPaperRepository,
        )

        repo = DatasetPaperRepository(csv_fixture)
        papers = repo.get_all_papers()

        p1 = papers[0]
        assert p1.abstract == "Abstract of paper one."

        p2 = papers[1]
        assert p2.abstract is None

    def test_handles_nan_year_as_none(self, csv_fixture):
        from src.infrastructure.repositories.dataset_repository import (
            DatasetPaperRepository,
        )

        repo = DatasetPaperRepository(csv_fixture)
        papers = repo.get_all_papers()

        p1 = papers[0]
        assert p1.publication_year == 2023

        p2 = papers[1]
        assert p2.publication_year is None

    def test_source_type_from_wl_provenance(self, csv_fixture):
        from src.infrastructure.repositories.dataset_repository import (
            DatasetPaperRepository,
        )

        repo = DatasetPaperRepository(csv_fixture)
        papers = repo.get_all_papers()

        assert papers[0].source_type is SourceType.WL
        assert papers[2].source_type is SourceType.WL

    def test_source_type_from_gl_provenance(self, csv_fixture):
        from src.infrastructure.repositories.dataset_repository import (
            DatasetPaperRepository,
        )

        repo = DatasetPaperRepository(csv_fixture)
        papers = repo.get_all_papers()

        assert papers[1].source_type is SourceType.GL

    def test_metadata_contains_unrecognized_columns(self, csv_fixture):
        from src.infrastructure.repositories.dataset_repository import (
            DatasetPaperRepository,
        )

        repo = DatasetPaperRepository(csv_fixture)
        papers = repo.get_all_papers()

        p1 = papers[0]
        assert "Authors" in p1.metadata
        assert p1.metadata["Authors"] == "Author A"
        assert "DOI" in p1.metadata
        assert p1.metadata["DOI"] == "10.1234/one"

    def test_metadata_does_not_contain_mapped_columns(self, csv_fixture):
        from src.infrastructure.repositories.dataset_repository import (
            DatasetPaperRepository,
        )

        repo = DatasetPaperRepository(csv_fixture)
        papers = repo.get_all_papers()

        p1 = papers[0]
        assert "Global_ID" not in p1.metadata
        assert "Title" not in p1.metadata
        assert "URL" not in p1.metadata
        assert "Abstract" not in p1.metadata
        assert "Year" not in p1.metadata
        assert "Provenance_Trace" not in p1.metadata

    def test_returns_empty_list_for_empty_csv(self, empty_csv):
        from src.infrastructure.repositories.dataset_repository import (
            DatasetPaperRepository,
        )

        repo = DatasetPaperRepository(empty_csv)
        papers = repo.get_all_papers()

        assert papers == []

    def test_file_not_found_raises(self):
        from src.infrastructure.repositories.dataset_repository import (
            DatasetPaperRepository,
        )

        repo = DatasetPaperRepository("nonexistent.csv")

        with pytest.raises(FileNotFoundError):
            repo.get_all_papers()

    def test_nan_in_metadata_is_converted_to_none(self, csv_fixture):
        from src.infrastructure.repositories.dataset_repository import (
            DatasetPaperRepository,
        )

        repo = DatasetPaperRepository(csv_fixture)
        papers = repo.get_all_papers()

        p3 = papers[2]
        assert p3.metadata["DOI"] is None


class TestDatasetPaperRepositoryRealFile:
    """Integration-style tests using the real dataset in the project root."""

    def test_reads_real_xlsx_without_error(self):
        from src.infrastructure.repositories.dataset_repository import (
            DatasetPaperRepository,
        )

        repo = DatasetPaperRepository("ATLAS_Initial_Search_20260511_224108.xlsx")
        papers = repo.get_all_papers()

        assert len(papers) == 1994
        assert all(isinstance(p, Paper) for p in papers)

    def test_real_xlsx_all_source_types_are_wl(self):
        from src.infrastructure.repositories.dataset_repository import (
            DatasetPaperRepository,
        )

        repo = DatasetPaperRepository("ATLAS_Initial_Search_20260511_224108.xlsx")
        papers = repo.get_all_papers()

        assert all(p.source_type is SourceType.WL for p in papers)
