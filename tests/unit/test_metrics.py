"""
Unit Tests for src/core/metrics.py
"""
import pytest
from src.core.metrics import (
    calculate_confusion_matrix,
    calculate_metrics_from_confusion
)


class TestConfusionMatrix:
    """Test confusion matrix calculation."""

    def test_all_correct_predictions(self):
        """Perfect predictions should give all TP and TN."""
        human = ["include", "exclude", "include", "exclude"]
        predicted = ["include", "exclude", "include", "exclude"]
        
        matrix = calculate_confusion_matrix(human, predicted)
        
        assert matrix["TP"] == 2
        assert matrix["TN"] == 2
        assert matrix["FP"] == 0
        assert matrix["FN"] == 0

    def test_all_wrong_predictions(self):
        """All wrong predictions should give all FP and FN."""
        human = ["include", "exclude", "include", "exclude"]
        predicted = ["exclude", "include", "exclude", "include"]
        
        matrix = calculate_confusion_matrix(human, predicted)
        
        assert matrix["TP"] == 0
        assert matrix["TN"] == 0
        assert matrix["FP"] == 2
        assert matrix["FN"] == 2

    def test_mixed_predictions(self):
        """Mixed results."""
        human = ["include", "include", "exclude", "exclude"]
        predicted = ["include", "exclude", "exclude", "include"]
        
        matrix = calculate_confusion_matrix(human, predicted)
        
        assert matrix["TP"] == 1
        assert matrix["TN"] == 1
        assert matrix["FP"] == 1
        assert matrix["FN"] == 1


class TestMetricsCalculation:
    """Test precision/recall/f1 calculation."""

    def test_perfect_predictions(self):
        """100% correct predictions should give 1.0 for all metrics."""
        matrix = {"TP": 10, "FP": 0, "TN": 10, "FN": 0}
        
        metrics = calculate_metrics_from_confusion(matrix)
        
        assert metrics["precision"] == 1.0
        assert metrics["recall"] == 1.0
        assert metrics["f1"] == 1.0
        assert metrics["accuracy"] == 1.0

    def test_partial_correct(self):
        """Partial correct predictions."""
        matrix = {"TP": 5, "FP": 5, "TN": 5, "FN": 5}
        
        metrics = calculate_metrics_from_confusion(matrix)
        
        assert metrics["precision"] == 0.5
        assert metrics["recall"] == 0.5
        assert metrics["f1"] == 0.5
        assert metrics["accuracy"] == 0.5

    def test_no_positives(self):
        """No positive predictions - avoid division by zero."""
        matrix = {"TP": 0, "FP": 0, "TN": 10, "FN": 10}
        
        metrics = calculate_metrics_from_confusion(matrix)
        
        assert metrics["precision"] == 0.0
        assert metrics["recall"] == 0.0
        assert metrics["f1"] == 0.0
        assert metrics["accuracy"] == 0.5

    def test_perfect_precision_low_recall(self):
        """Perfect precision but low recall."""
        matrix = {"TP": 5, "FP": 0, "TN": 5, "FN": 10}
        
        metrics = calculate_metrics_from_confusion(matrix)
        
        assert metrics["precision"] == 1.0
        assert metrics["recall"] == 0.333
        assert 0 < metrics["f1"] < 1