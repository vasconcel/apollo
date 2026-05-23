"""Tests for ground_truth_comparator.py."""
import pytest

from src.advisory.ground_truth_comparator import (
    compute_confusion_matrix,
    compute_per_criterion_accuracy,
    compute_ground_truth_summary,
)


class TestConfusionMatrix:
    def test_perfect_match(self):
        advisory = ["INCLUDE", "EXCLUDE", "SKIP", "INCLUDE"]
        truth = ["INCLUDE", "EXCLUDE", "SKIP", "INCLUDE"]
        result = compute_confusion_matrix(advisory, truth)
        assert result["count"] == 4
        metrics = result["derived_metrics"]["macro_avg"]
        assert metrics["precision"] == 1.0
        assert metrics["recall"] == 1.0
        assert metrics["f1"] == 1.0

    def test_partial_match(self):
        advisory = ["INCLUDE", "INCLUDE", "EXCLUDE"]
        truth = ["INCLUDE", "EXCLUDE", "INCLUDE"]
        result = compute_confusion_matrix(advisory, truth)
        metrics = result["derived_metrics"]["macro_avg"]
        assert 0.0 < metrics["f1"] < 1.0

    def test_complete_mismatch(self):
        advisory = ["INCLUDE", "INCLUDE"]
        truth = ["EXCLUDE", "EXCLUDE"]
        result = compute_confusion_matrix(advisory, truth)
        metrics = result["derived_metrics"]
        assert metrics["per_label"]["INCLUDE"]["precision"] == 0.0
        assert metrics["per_label"]["EXCLUDE"]["recall"] == 0.0

    def test_empty_input(self):
        result = compute_confusion_matrix([], [])
        assert result["count"] == 0
        assert result["derived_metrics"]["macro_avg"]["f1"] == 0.0

    def test_normalized_decisions(self):
        """Verify UNCERTAIN-like decisions are normalized correctly."""
        advisory = ["INSUFFICIENT_EVIDENCE"]
        truth = ["UNCERTAIN"]
        result = compute_confusion_matrix(advisory, truth)
        metrics = result["derived_metrics"]
        assert metrics["per_label"]["UNCERTAIN"]["f1"] == 1.0


class TestPerCriterionAccuracy:
    def test_perfect_criterion_match(self):
        advisory = [{"criterion_id": "c1", "satisfied": True},
                    {"criterion_id": "c2", "satisfied": False}]
        truth = [{"criterion_id": "c1", "satisfied": True},
                 {"criterion_id": "c2", "satisfied": False}]
        result = compute_per_criterion_accuracy(advisory, truth)
        assert result["accuracy"] == 1.0
        assert result["correct"] == 2

    def test_partial_criterion_match(self):
        advisory = [{"criterion_id": "c1", "satisfied": True},
                    {"criterion_id": "c2", "satisfied": True}]
        truth = [{"criterion_id": "c1", "satisfied": True},
                 {"criterion_id": "c2", "satisfied": False}]
        result = compute_per_criterion_accuracy(advisory, truth)
        assert result["accuracy"] == 0.5

    def test_missing_ground_truth(self):
        advisory = [{"criterion_id": "c1", "satisfied": True},
                    {"criterion_id": "c2", "satisfied": False}]
        truth = [{"criterion_id": "c1", "satisfied": True}]
        result = compute_per_criterion_accuracy(advisory, truth)
        assert result["accuracy"] == 1.0
        assert result["missing_ground_truth"] == 1


class TestGroundTruthSummary:
    def test_full_summary(self):
        result = compute_ground_truth_summary(
            advisory_decisions=["INCLUDE", "EXCLUDE"],
            ground_truth_decisions=["INCLUDE", "EXCLUDE"],
            advisory_criteria=[{"criterion_id": "c1", "satisfied": True}],
            ground_truth_criteria=[{"criterion_id": "c1", "satisfied": True}],
        )
        assert "confusion_matrix" in result
        assert "derived_metrics" in result
        assert "criterion_accuracy" in result

    def test_decisions_only(self):
        result = compute_ground_truth_summary(
            advisory_decisions=["INCLUDE"],
            ground_truth_decisions=["INCLUDE"],
        )
        assert "confusion_matrix" in result
        assert "criterion_accuracy" not in result
