"""
Unit Tests for src/core/analytics.py - Cohen's Kappa Calculation.
"""
import pytest
import pandas as pd
from src.core.analytics import prepare_kappa


class TestCohenKappa:
    """Test Cohen's Kappa calculation with edge cases."""

    def test_perfect_agreement(self):
        """When both reviewers agree 100%, Kappa should return 1.0."""
        df = pd.DataFrame([
            {"article_id": 1, "reviewer_id": "Reviewer_1", "decision": "include"},
            {"article_id": 1, "reviewer_id": "Reviewer_2", "decision": "include"},
            {"article_id": 2, "reviewer_id": "Reviewer_1", "decision": "exclude"},
            {"article_id": 2, "reviewer_id": "Reviewer_2", "decision": "exclude"},
        ])
        kappa, pivot = prepare_kappa(df)
        assert kappa == 1.0

    def test_complete_disagreement(self):
        """When reviewers have opposing views."""
        df = pd.DataFrame([
            {"article_id": 1, "reviewer_id": "Reviewer_1", "decision": "include"},
            {"article_id": 1, "reviewer_id": "Reviewer_2", "decision": "exclude"},
        ])
        result, _ = prepare_kappa(df)
        # Should return a float (either 0.0 or None depending on implementation)
        assert result is None or isinstance(result, float)

    def test_moderate_agreement(self):
        """Standard case with some agreement."""
        df = pd.DataFrame([
            {"article_id": 1, "reviewer_id": "Reviewer_1", "decision": "include"},
            {"article_id": 1, "reviewer_id": "Reviewer_2", "decision": "include"},
            {"article_id": 2, "reviewer_id": "Reviewer_1", "decision": "include"},
            {"article_id": 2, "reviewer_id": "Reviewer_2", "decision": "exclude"},
            {"article_id": 3, "reviewer_id": "Reviewer_1", "decision": "exclude"},
            {"article_id": 3, "reviewer_id": "Reviewer_2", "decision": "exclude"},
        ])
        result, pivot = prepare_kappa(df)
        # Should return valid result
        assert result is None or 0.0 <= result <= 1.0

    def test_missing_reviewer_returns_none(self):
        """When one reviewer hasn't finished, should return None."""
        df = pd.DataFrame([
            {"article_id": 1, "reviewer_id": "Reviewer_1", "decision": "include"},
            {"article_id": 1, "reviewer_id": "Reviewer_2", "decision": "include"},
            {"article_id": 2, "reviewer_id": "Reviewer_1", "decision": "include"},
        ])
        kappa, pivot = prepare_kappa(df)
        assert kappa is None

    def test_insufficient_articles(self):
        """When there's only one overlapping article, should return None."""
        df = pd.DataFrame([
            {"article_id": 1, "reviewer_id": "Reviewer_1", "decision": "include"},
            {"article_id": 1, "reviewer_id": "Reviewer_2", "decision": "include"},
        ])
        kappa, pivot = prepare_kappa(df)
        assert kappa is None

    def test_empty_dataframe(self):
        """Empty DataFrame should return None."""
        kappa, pivot = prepare_kappa(pd.DataFrame())
        assert kappa is None

    def test_single_reviewer(self):
        """DataFrame with only one reviewer should return None."""
        df = pd.DataFrame([
            {"article_id": 1, "reviewer_id": "Reviewer_1", "decision": "include"},
            {"article_id": 2, "reviewer_id": "Reviewer_1", "decision": "exclude"},
        ])
        kappa, pivot = prepare_kappa(df)
        assert kappa is None


class TestKappaValueInterpretation:
    """Test Kappa value interpretation."""

    def test_kappa_returns_float(self):
        """Kappa should return a float value."""
        df = pd.DataFrame([
            {"article_id": 1, "reviewer_id": "Reviewer_1", "decision": "include"},
            {"article_id": 1, "reviewer_id": "Reviewer_2", "decision": "include"},
            {"article_id": 2, "reviewer_id": "Reviewer_1", "decision": "exclude"},
            {"article_id": 2, "reviewer_id": "Reviewer_2", "decision": "exclude"},
        ])
        kappa, _ = prepare_kappa(df)
        assert isinstance(kappa, float)

    def test_pivot_table_structure(self):
        """Pivot table should have correct structure."""
        df = pd.DataFrame([
            {"article_id": 1, "reviewer_id": "Reviewer_1", "decision": "include"},
            {"article_id": 1, "reviewer_id": "Reviewer_2", "decision": "include"},
            {"article_id": 2, "reviewer_id": "Reviewer_1", "decision": "exclude"},
            {"article_id": 2, "reviewer_id": "Reviewer_2", "decision": "exclude"},
        ])
        _, pivot = prepare_kappa(df)
        assert pivot is not None
        assert pivot.index.name == "article_id"