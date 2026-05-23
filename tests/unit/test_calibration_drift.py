"""Tests for calibration_drift.py."""
import pytest

from src.advisory.calibration_drift import (
    jensen_shannon_divergence,
    detect_decision_drift,
    detect_confidence_drift,
    detect_criteria_drift,
    detect_drift,
)


class TestJensenShannonDivergence:
    def test_identical_distributions(self):
        p = [0.5, 0.5]
        q = [0.5, 0.5]
        assert jensen_shannon_divergence(p, q) == 0.0

    def test_completely_different(self):
        p = [1.0, 0.0]
        q = [0.0, 1.0]
        js = jensen_shannon_divergence(p, q)
        assert 0.9 < js <= 1.0

    def test_partial_overlap(self):
        p = [0.8, 0.2]
        q = [0.3, 0.7]
        js = jensen_shannon_divergence(p, q)
        assert 0.0 < js < 1.0

    def test_empty_input(self):
        assert jensen_shannon_divergence([], []) == 0.0
        assert jensen_shannon_divergence([1.0], []) == 0.0

    def test_different_lengths(self):
        assert jensen_shannon_divergence([0.5, 0.5], [1.0]) == 1.0


class TestDetectDecisionDrift:
    def test_identical_decisions(self):
        baseline = {"INCLUDE": 50, "EXCLUDE": 50}
        current = {"INCLUDE": 50, "EXCLUDE": 50}
        result = detect_decision_drift(baseline, current)
        assert result["drift_score"] == 0.0
        assert result["drift_type"] == "stable"

    def test_mild_drift(self):
        baseline = {"INCLUDE": 80, "EXCLUDE": 20}
        current = {"INCLUDE": 70, "EXCLUDE": 30}
        result = detect_decision_drift(baseline, current)
        assert 0.0 < result["drift_score"] < 0.15

    def test_structural_drift(self):
        baseline = {"INCLUDE": 90, "EXCLUDE": 10}
        current = {"INCLUDE": 10, "EXCLUDE": 90}
        result = detect_decision_drift(baseline, current)
        assert result["drift_score"] >= 0.15

    def test_different_label_sets(self):
        baseline = {"INCLUDE": 50, "EXCLUDE": 50}
        current = {"INCLUDE": 30, "UNCERTAIN": 40, "EXCLUDE": 30}
        result = detect_decision_drift(baseline, current)
        assert "UNCERTAIN" in result["labels"]


class TestDetectConfidenceDrift:
    def test_identical_confidences(self):
        baseline = [0.5, 0.6, 0.7]
        current = [0.5, 0.6, 0.7]
        result = detect_confidence_drift(baseline, current)
        assert result["drift_score"] >= 0.0

    def test_different_confidences(self):
        baseline = [0.1, 0.2, 0.3]
        current = [0.8, 0.9, 0.95]
        result = detect_confidence_drift(baseline, current)
        assert result["drift_score"] > 0.0

    def test_empty_baseline(self):
        result = detect_confidence_drift([], [0.5, 0.6])
        assert result["drift_score"] == 0.0


class TestDetectCriteriaDrift:
    def test_identical_criteria(self):
        baseline = {"c1": 0.5, "c2": 0.5}
        current = {"c1": 0.5, "c2": 0.5}
        result = detect_criteria_drift(baseline, current)
        assert result["drift_score"] == 0.0

    def test_new_criteria_appear(self):
        baseline = {"c1": 0.8, "c2": 0.2}
        current = {"c1": 0.4, "c2": 0.2, "c3": 0.4}
        result = detect_criteria_drift(baseline, current)
        assert result["active_criteria_changes"]["newly_active_count"] == 1


class TestDetectDrift:
    def test_full_drift_detection(self):
        baseline = {
            "decision_counts": {"INCLUDE": 60, "EXCLUDE": 40},
            "confidences": [0.5, 0.6, 0.7],
            "criteria_frequencies": {"c1": 0.8, "c2": 0.2},
        }
        current = {
            "decision_counts": {"INCLUDE": 30, "EXCLUDE": 70},
            "confidences": [0.3, 0.4, 0.5],
            "criteria_frequencies": {"c1": 0.5, "c2": 0.3, "c3": 0.2},
        }
        result = detect_drift(baseline, current)
        assert "composite_drift_score" in result
        assert "composite_drift_type" in result
        assert "decision_drift" in result
        assert "confidence_drift" in result
        assert "criteria_drift" in result
        assert result["composite_drift_score"] > 0.0
