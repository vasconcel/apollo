"""Tests for advisory_quality_score.py."""
import pytest

from src.advisory.advisory_quality_score import (
    compute_confidence_calibration_score,
    compute_grounding_quality_score,
    compute_criterion_consistency_score,
    compute_hallucination_risk_score,
    compute_override_rate_score,
    compute_quality_score,
    DEFAULT_WEIGHTS,
)


def _make_advisory(decision="INCLUDE", confidence=0.8, grounding=0.7,
                   hallucination=0.1, risk_class="LOW_RISK",
                   triggered_criteria=None):
    return {
        "decision": decision,
        "confidence": confidence,
        "grounding_strength": grounding,
        "hallucination_risk_score": hallucination,
        "risk_classification": risk_class,
        "triggered_criteria": triggered_criteria or ["c1"],
    }


class TestConfidenceCalibration:
    def test_perfect_calibration(self):
        advs = [_make_advisory(decision="INCLUDE", confidence=0.85)]
        score = compute_confidence_calibration_score(advs)
        assert score > 0.9

    def test_overconfident_uncertain(self):
        advs = [_make_advisory(decision="UNCERTAIN", confidence=0.9)]
        score = compute_confidence_calibration_score(advs)
        assert score < 0.8

    def test_underconfident_include(self):
        advs = [_make_advisory(decision="INCLUDE", confidence=0.2)]
        score = compute_confidence_calibration_score(advs)
        assert score < 0.8

    def test_empty_list(self):
        assert compute_confidence_calibration_score([]) == 1.0

    def test_mixed_advisories(self):
        advs = [
            _make_advisory(decision="INCLUDE", confidence=0.85),
            _make_advisory(decision="EXCLUDE", confidence=0.90),
            _make_advisory(decision="UNCERTAIN", confidence=0.95),
        ]
        score = compute_confidence_calibration_score(advs)
        assert 0.0 < score < 1.0


class TestGroundingQuality:
    def test_high_grounding(self):
        advs = [_make_advisory(grounding=0.9)]
        assert compute_grounding_quality_score(advs) == 0.9

    def test_mixed_grounding(self):
        advs = [
            _make_advisory(grounding=0.8),
            _make_advisory(grounding=0.4),
        ]
        assert compute_grounding_quality_score(advs) == 0.6

    def test_empty(self):
        assert compute_grounding_quality_score([]) == 1.0


class TestCriterionConsistency:
    def test_all_criteria_varied(self):
        advs = [_make_advisory(triggered_criteria=["c1"]),
                _make_advisory(triggered_criteria=["c2"])]
        score = compute_criterion_consistency_score(advs)
        assert score == 1.0

    def test_always_triggered_criterion(self):
        advs = [_make_advisory(triggered_criteria=["c1"])
                for _ in range(20)]
        score = compute_criterion_consistency_score(advs)
        assert score < 1.0

    def test_empty_list(self):
        assert compute_criterion_consistency_score([]) == 1.0


class TestQualityScore:
    def test_composite_score_high(self):
        advs = [
            _make_advisory(decision="INCLUDE", confidence=0.85, grounding=0.8),
            _make_advisory(decision="EXCLUDE", confidence=0.90, grounding=0.85),
        ]
        result = compute_quality_score(advs)
        assert 0.0 <= result["composite_score"] <= 1.0
        assert result["total_advisories"] == 2
        assert "components" in result
        assert "weights_used" in result

    def test_composite_score_low(self):
        advs = [
            _make_advisory(decision="UNCERTAIN", confidence=0.95,
                           grounding=0.1, hallucination=0.9),
            _make_advisory(decision="INSUFFICIENT_EVIDENCE", confidence=0.0,
                           grounding=0.0, hallucination=0.8),
        ]
        result = compute_quality_score(advs)
        assert result["composite_score"] < 0.5

    def test_custom_weights(self):
        advs = [_make_advisory()]
        weights = {"confidence_calibration": 1.0, "grounding_strength": 0.0,
                   "criterion_consistency": 0.0, "hallucination_risk": 0.0,
                   "override_rate": 0.0}
        result = compute_quality_score(advs, weights)
        assert result["weights_used"]["confidence_calibration"] == 1.0

    def test_deterministic(self):
        advs = [_make_advisory(decision="INCLUDE", confidence=0.8)]
        r1 = compute_quality_score(advs)
        r2 = compute_quality_score(advs)
        assert r1["composite_score"] == r2["composite_score"]

    def test_empty_advisories(self):
        result = compute_quality_score([])
        assert result["composite_score"] == 1.0
        assert result["total_advisories"] == 0
