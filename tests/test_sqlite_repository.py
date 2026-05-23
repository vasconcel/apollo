import json

import pytest

from src.domain.enums import ScreeningStatus
from src.domain.models import ScreeningDecision


@pytest.fixture
def repo():
    from src.infrastructure.repositories.sqlite_repository import (
        SQLiteScreeningDecisionRepository,
    )

    return SQLiteScreeningDecisionRepository(db_path=":memory:")


class TestSQLiteScreeningDecisionRepository:
    def test_save_and_get_decision(self, repo):
        decision = ScreeningDecision(
            paper_id="p1",
            status=ScreeningStatus.INCLUDED,
            confidence_score=0.95,
            rationale="Good paper.",
            applied_criteria_codes=["IC1", "IC2"],
        )
        repo.save_decision(decision)
        retrieved = repo.get_decision("p1")

        assert retrieved is not None
        assert retrieved.paper_id == "p1"
        assert retrieved.status is ScreeningStatus.INCLUDED
        assert retrieved.confidence_score == 0.95
        assert retrieved.rationale == "Good paper."
        assert retrieved.applied_criteria_codes == ["IC1", "IC2"]

    def test_get_decision_not_found_returns_none(self, repo):
        retrieved = repo.get_decision("nonexistent")
        assert retrieved is None

    def test_get_all_decisions(self, repo):
        decisions = [
            ScreeningDecision(
                paper_id="p1",
                status=ScreeningStatus.INCLUDED,
                confidence_score=0.9,
                rationale="A",
                applied_criteria_codes=["IC1"],
            ),
            ScreeningDecision(
                paper_id="p2",
                status=ScreeningStatus.EXCLUDED,
                confidence_score=0.8,
                rationale="B",
                applied_criteria_codes=["EC1"],
            ),
            ScreeningDecision(
                paper_id="p3",
                status=ScreeningStatus.NEEDS_REVIEW,
                confidence_score=0.5,
                rationale="C",
                applied_criteria_codes=[],
            ),
        ]
        for d in decisions:
            repo.save_decision(d)

        all_d = repo.get_all_decisions()
        assert len(all_d) == 3
        assert all_d[0].paper_id == "p1"
        assert all_d[1].paper_id == "p2"
        assert all_d[2].paper_id == "p3"

    def test_overwrite_existing_decision(self, repo):
        d1 = ScreeningDecision(
            paper_id="p1",
            status=ScreeningStatus.INCLUDED,
            confidence_score=0.9,
            rationale="First pass",
            applied_criteria_codes=["IC1"],
        )
        repo.save_decision(d1)

        d2 = ScreeningDecision(
            paper_id="p1",
            status=ScreeningStatus.EXCLUDED,
            confidence_score=1.0,
            rationale="Second pass — excluded",
            applied_criteria_codes=["EC1"],
        )
        repo.save_decision(d2)

        retrieved = repo.get_decision("p1")
        assert retrieved.status is ScreeningStatus.EXCLUDED
        assert retrieved.confidence_score == 1.0
        assert retrieved.rationale == "Second pass — excluded"
        assert retrieved.applied_criteria_codes == ["EC1"]
        assert len(repo.get_all_decisions()) == 1

    def test_empty_database_returns_empty_list(self, repo):
        assert repo.get_all_decisions() == []

    def test_roundtrip_json_codes_with_special_chars(self, repo):
        decision = ScreeningDecision(
            paper_id="p-special",
            status=ScreeningStatus.INCLUDED,
            confidence_score=0.7,
            rationale="Has 'quotes' and \"double quotes\"",
            applied_criteria_codes=["IC-1", "EC-2"],
        )
        repo.save_decision(decision)
        retrieved = repo.get_decision("p-special")

        assert retrieved.rationale == decision.rationale
        assert retrieved.applied_criteria_codes == ["IC-1", "EC-2"]

    def test_decision_with_empty_codes(self, repo):
        decision = ScreeningDecision(
            paper_id="p-empty-codes",
            status=ScreeningStatus.NEEDS_REVIEW,
            confidence_score=0.0,
            rationale="No codes",
            applied_criteria_codes=[],
        )
        repo.save_decision(decision)
        retrieved = repo.get_decision("p-empty-codes")

        assert retrieved.applied_criteria_codes == []

    @pytest.mark.parametrize("status", list(ScreeningStatus))
    def test_all_status_values_survive_roundtrip(self, repo, status):
        decision = ScreeningDecision(
            paper_id=f"p-{status.value}",
            status=status,
            confidence_score=0.5,
            rationale=f"Test {status.value}",
            applied_criteria_codes=["IC1"],
        )
        repo.save_decision(decision)
        retrieved = repo.get_decision(f"p-{status.value}")

        assert retrieved.status is status
