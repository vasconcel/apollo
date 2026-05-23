import csv

import pytest
from pytest_mock import MockerFixture

from src.domain.enums import ScreeningStatus, SourceType
from src.domain.models import Paper, ScreeningDecision


class TestExportScreenedPapers:
    @pytest.fixture
    def mock_paper_repo(self, mocker: MockerFixture):
        repo = mocker.MagicMock()
        repo.get_all_papers.return_value = [
            Paper(
                id="1",
                title="Paper One",
                source_type=SourceType.WL,
                publication_year=2023,
                url="https://example.com/1",
                abstract="Abstract one.",
            ),
            Paper(
                id="2",
                title="Paper Two",
                source_type=SourceType.GL,
                publication_year=2022,
                url="https://example.com/2",
                abstract="Abstract two.",
            ),
        ]
        return repo

    @pytest.fixture
    def mock_decision_repo(self, mocker: MockerFixture):
        repo = mocker.MagicMock()
        repo.get_all_decisions.return_value = [
            ScreeningDecision(
                paper_id="1",
                status=ScreeningStatus.INCLUDED,
                confidence_score=0.95,
                rationale="Good paper.",
                applied_criteria_codes=["IC1", "IC2"],
            ),
            ScreeningDecision(
                paper_id="2",
                status=ScreeningStatus.EXCLUDED,
                confidence_score=1.0,
                rationale="Duplicate.",
                applied_criteria_codes=["EC6"],
            ),
        ]
        return repo

    def test_export_creates_csv_with_correct_headers(self, mock_paper_repo, mock_decision_repo, tmp_path):
        from src.use_cases.export_papers import ExportScreenedPapersUseCase

        output = tmp_path / "results.csv"
        use_case = ExportScreenedPapersUseCase(
            paper_repository=mock_paper_repo,
            decision_repository=mock_decision_repo,
        )
        use_case.execute(output_path=str(output))

        assert output.exists()
        with open(output, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            headers = next(reader)

        assert headers == [
            "Global_ID", "Title", "URL", "Abstract",
            "Source_Type", "Status", "Rationale", "Applied_Criteria",
        ]

    def test_export_contains_correct_rows(self, mock_paper_repo, mock_decision_repo, tmp_path):
        from src.use_cases.export_papers import ExportScreenedPapersUseCase

        output = tmp_path / "results.csv"
        use_case = ExportScreenedPapersUseCase(
            paper_repository=mock_paper_repo,
            decision_repository=mock_decision_repo,
        )
        use_case.execute(output_path=str(output))

        with open(output, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        assert len(rows) == 2

        row1 = rows[0]
        assert row1["Global_ID"] == "1"
        assert row1["Title"] == "Paper One"
        assert row1["URL"] == "https://example.com/1"
        assert row1["Abstract"] == "Abstract one."
        assert row1["Source_Type"] == "WL"
        assert row1["Status"] == "INCLUDED"
        assert row1["Rationale"] == "Good paper."
        assert row1["Applied_Criteria"] == "IC1; IC2"

        row2 = rows[1]
        assert row2["Global_ID"] == "2"
        assert row2["Title"] == "Paper Two"
        assert row2["Status"] == "EXCLUDED"
        assert row2["Applied_Criteria"] == "EC6"

    def test_empty_decisions_produces_csv_with_only_headers(self, mock_paper_repo, mocker: MockerFixture, tmp_path):
        from src.use_cases.export_papers import ExportScreenedPapersUseCase

        mock_decision_repo = mocker.MagicMock()
        mock_decision_repo.get_all_decisions.return_value = []

        use_case = ExportScreenedPapersUseCase(
            paper_repository=mock_paper_repo,
            decision_repository=mock_decision_repo,
        )
        output = tmp_path / "empty.csv"
        use_case.execute(output_path=str(output))

        with open(output, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))

        assert len(rows) == 1  # only headers

    def test_export_missing_paper_shows_empty_fields(self, mock_paper_repo, mock_decision_repo, mocker: MockerFixture, tmp_path):
        from src.use_cases.export_papers import ExportScreenedPapersUseCase

        mock_decision_repo.get_all_decisions.return_value = [
            ScreeningDecision(
                paper_id="999",
                status=ScreeningStatus.NEEDS_REVIEW,
                confidence_score=0.5,
                rationale="Unknown paper",
                applied_criteria_codes=[],
            ),
        ]

        use_case = ExportScreenedPapersUseCase(
            paper_repository=mock_paper_repo,
            decision_repository=mock_decision_repo,
        )
        output = tmp_path / "missing.csv"
        use_case.execute(output_path=str(output))

        with open(output, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        assert len(rows) == 1
        assert rows[0]["Global_ID"] == "999"
        assert rows[0]["Title"] == ""
