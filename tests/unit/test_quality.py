"""
Unit Tests for src/core/quality.py - Quality Assessment Logic.
"""
import pytest
from src.core.quality import QualityEngine


class TestQualityEngine:
    """Test Quality Engine threshold and scoring logic."""

    def test_threshold_pass(self):
        """Score >= 2.0 should result in include."""
        scores = {"Q1": 1.0, "Q2": 0.5, "Q3": 0.5, "Q4": 0.0}
        engine = QualityEngine()
        result = engine.evaluate(scores)
        assert result["decision"] == "include"
        assert result["total_score"] == 2.0

    def test_threshold_fail(self):
        """Score < 2.0 should result in exclude."""
        scores = {"Q1": 0.5, "Q2": 0.5, "Q3": 0.0, "Q4": 0.0}
        engine = QualityEngine()
        result = engine.evaluate(scores)
        assert result["decision"] == "exclude"

    def test_custom_threshold(self):
        """Custom threshold should be respected."""
        scores = {"Q1": 1.0, "Q2": 0.5}
        engine = QualityEngine(threshold=1.5)
        result = engine.evaluate(scores)
        assert result["decision"] == "include"
        assert result["total_score"] == 1.5

    def test_zero_score(self):
        """Zero score should result in exclude."""
        scores = {"Q1": 0.0, "Q2": 0.0, "Q3": 0.0, "Q4": 0.0}
        engine = QualityEngine()
        result = engine.evaluate(scores)
        assert result["decision"] == "exclude"

    def test_maximum_score(self):
        """Maximum score (4.0) should result in include."""
        scores = {"Q1": 1.0, "Q2": 1.0, "Q3": 1.0, "Q4": 1.0}
        engine = QualityEngine()
        result = engine.evaluate(scores)
        assert result["decision"] == "include"
        assert result["total_score"] == 4.0

    def test_boundary_exactly_2(self):
        """Score exactly at threshold should result in include."""
        scores = {"Q1": 1.0, "Q2": 1.0, "Q3": 0.0, "Q4": 0.0}
        engine = QualityEngine(threshold=2.0)
        result = engine.evaluate(scores)
        assert result["decision"] == "include"

    def test_boundary_just_below_2(self):
        """Score just below threshold should result in exclude."""
        scores = {"Q1": 0.5, "Q2": 0.5, "Q3": 0.5, "Q4": 0.4}  # Total = 1.9
        engine = QualityEngine(threshold=2.0)
        result = engine.evaluate(scores)
        assert result["decision"] == "exclude"


class TestDualAssessment:
    """Test dual reviewer assessment logic."""

    def test_insufficient_assessments(self):
        """Less than 2 assessments should return insufficient."""
        engine = QualityEngine()
        result = engine.validate_dual_assessment([{"decision": "include"}])
        assert result == "insufficient"

    def test_consensus(self):
        """Same decisions should return consensus."""
        engine = QualityEngine()
        result = engine.validate_dual_assessment([
            {"decision": "include"},
            {"decision": "include"}
        ])
        assert result == "consensus"

    def test_conflict(self):
        """Different decisions should return conflict."""
        engine = QualityEngine()
        result = engine.validate_dual_assessment([
            {"decision": "include"},
            {"decision": "exclude"}
        ])
        assert result == "conflict"