"""
Tests for advisory reliability estimation, escalation, thresholds, and metrics.

Pure function tests — no external dependencies, no infrastructure.
"""
import time
import pytest

from src.advisory.advisory_models import AdvisoryResult, CriterionEvaluation, AdvisoryDecision, RiskClassification
from src.advisory.advisory_reliability import (
    compute_advisory_reliability,
    compute_reliability_components,
    compute_batch_reliability,
    check_escalation,
    ThresholdCalibrator,
    OperationalMetrics,
    get_threshold_calibrator,
    get_operational_metrics,
    reset_reliability_globals,
)


def _make_advisory(**overrides) -> AdvisoryResult:
    """Helper to create AdvisoryResult with defaults."""
    defaults = {
        "cache_key": "test_001",
        "protocol_version": "1.0",
        "decision": AdvisoryDecision.INCLUDE,
        "confidence": 0.85,
        "grounding_strength": 0.8,
        "hallucination_risk_score": 0.1,
        "parser_confidence": 0.8,
        "evidence_span": 3,
        "unsupported_claims_detected": False,
        "grounding_evidence": ["evidence1", "evidence2"],
        "criterion_evaluations": [
            CriterionEvaluation("c1", "Criterion 1", True, "evidence1", 0.9),
            CriterionEvaluation("c2", "Criterion 2", False, "evidence2", 0.8),
        ],
        "triggered_criteria": ["c1"],
        "non_triggered_criteria": ["c2"],
        "risk_classification": RiskClassification.LOW_RISK,
    }
    defaults.update(overrides)
    return AdvisoryResult(**defaults)


class TestReliabilityScoring:
    def test_high_reliability_advisory(self):
        """A well-grounded, confident, low-risk advisory should score near 1.0."""
        adv = _make_advisory()
        score = compute_advisory_reliability(adv)
        assert 0.7 <= score <= 1.0, f"Expected high reliability, got {score}"

    def test_low_reliability_advisory(self):
        """Uncertain, high-risk, unsupported advisory should score low."""
        adv = _make_advisory(
            decision=AdvisoryDecision.UNCERTAIN,
            confidence=0.9,
            grounding_strength=0.1,
            hallucination_risk_score=0.9,
            unsupported_claims_detected=True,
            evidence_span=0,
            risk_classification=RiskClassification.CRITICAL_REVIEW,
        )
        score = compute_advisory_reliability(adv)
        assert 0.0 <= score <= 0.5, f"Expected low reliability, got {score}"

    def test_overconfidence_penalty(self):
        """High confidence on UNCERTAIN decision should be penalized."""
        adv = _make_advisory(decision=AdvisoryDecision.UNCERTAIN, confidence=0.95)
        score = compute_advisory_reliability(adv)
        # Overconfidence penalty should reduce score
        assert score < 0.7, f"Overconfidence should reduce score, got {score}"

    def test_weak_grounding_penalty(self):
        """High confidence with low grounding should be penalized."""
        adv = _make_advisory(confidence=0.95, grounding_strength=0.05)
        score = compute_advisory_reliability(adv)
        assert score < 0.9, f"Weak grounding should reduce score, got {score}"

    def test_override_rate_reduces_score(self):
        """Higher override rate should reduce reliability score."""
        adv = _make_advisory()
        score_low_override = compute_advisory_reliability(adv, override_rate=0.0)
        score_high_override = compute_advisory_reliability(adv, override_rate=0.5)
        assert score_high_override < score_low_override, (
            f"Override rate should reduce score: {score_high_override} >= {score_low_override}"
        )

    def test_components_breakdown(self):
        """Component breakdown should match score and be explainable."""
        adv = _make_advisory()
        components = compute_reliability_components(adv)
        assert "reliability_score" in components
        assert "confidence_reliability" in components
        assert "grounding_reliability" in components
        assert "hallucination_reliability" in components
        assert "criterion_reliability" in components
        assert "historical_reliability" in components
        assert "uncertainty_penalty" in components
        # Composite should be weighted sum of components
        assert 0.0 <= components["reliability_score"] <= 1.0

    def test_deterministic(self):
        """Same inputs must produce same output."""
        adv = _make_advisory()
        s1 = compute_advisory_reliability(adv, override_rate=0.1)
        s2 = compute_advisory_reliability(adv, override_rate=0.1)
        assert s1 == s2

    def test_batch_reliability(self):
        """Batch computation should return aggregate stats."""
        advisories = [_make_advisory(decision=d) for d in [AdvisoryDecision.INCLUDE, AdvisoryDecision.UNCERTAIN, AdvisoryDecision.EXCLUDE]]
        result = compute_batch_reliability(advisories)
        assert result["total_count"] == 3
        assert result["max_reliability"] >= result["min_reliability"]
        assert 0 <= result["mean_reliability"] <= 1
        assert result["reliability_distribution"]["0.0-0.2"] >= 0


class TestEscalationRules:
    def test_no_escalation_for_reliable(self):
        """Highly reliable advisory should not escalate."""
        adv = _make_advisory()
        result = check_escalation(adv, reliability_score=0.9)
        assert not result["escalate"]
        assert not result["critical"]
        assert len(result["reasons"]) == 0

    def test_escalation_on_low_reliability(self):
        """Low reliability should trigger escalation."""
        adv = _make_advisory()
        result = check_escalation(adv, reliability_score=0.3, reliability_threshold=0.5)
        assert result["escalate"]
        assert any("reliability_low" in r for r in result["reasons"])

    def test_escalation_on_critical_reliability(self):
        """Very low reliability should trigger critical escalation."""
        adv = _make_advisory()
        result = check_escalation(adv, reliability_score=0.2, critical_threshold=0.3)
        assert result["escalate"]
        assert result["critical"]
        assert any("reliability_critical" in r for r in result["reasons"])

    def test_escalation_on_uncertain(self):
        """UNCERTAIN decision should trigger escalation."""
        adv = _make_advisory(decision=AdvisoryDecision.UNCERTAIN)
        result = check_escalation(adv, reliability_score=0.8)
        assert result["escalate"]
        assert any("decision_uncertain" in r for r in result["reasons"])

    def test_escalation_on_weak_grounding(self):
        """Weak grounding should trigger escalation."""
        adv = _make_advisory(grounding_strength=0.1)
        result = check_escalation(adv, reliability_score=0.8)
        assert result["escalate"]
        assert any("weak_grounding" in r for r in result["reasons"])

    def test_escalation_on_high_hallucination(self):
        """High hallucination risk should trigger escalation."""
        adv = _make_advisory(hallucination_risk_score=0.85)
        result = check_escalation(adv, reliability_score=0.8)
        assert result["escalate"]
        assert result["critical"]
        assert any("high_hallucination_risk" in r for r in result["reasons"])

    def test_escalation_on_high_override_rate(self):
        """High historical override rate should trigger escalation."""
        adv = _make_advisory()
        result = check_escalation(adv, reliability_score=0.8, override_rate=0.5)
        assert result["escalate"]
        assert any("high_override_rate" in r for r in result["reasons"])

    def test_escalation_conflicting_criteria(self):
        """Conflicting criteria evaluations should trigger escalation."""
        evaluations = [
            CriterionEvaluation("c1", "Criterion 1", True, "evidence1", 0.9),
            CriterionEvaluation("c1", "Criterion 1", False, "evidence2", 0.8),
        ]
        adv = _make_advisory(criterion_evaluations=evaluations)
        result = check_escalation(adv, reliability_score=0.8)
        assert result["escalate"]
        assert any("conflicting_criteria" in r for r in result["reasons"])

    def test_multiple_escalation_reasons(self):
        """Multiple issues should produce multiple reasons."""
        adv = _make_advisory(
            decision=AdvisoryDecision.UNCERTAIN,
            grounding_strength=0.1,
            hallucination_risk_score=0.85,
        )
        result = check_escalation(adv, reliability_score=0.3)
        assert result["escalate"]
        assert len(result["reasons"]) >= 3


class TestThresholdCalibrator:
    def test_default_override_rate(self):
        """Empty calibrator should return 0 override rate."""
        cal = ThresholdCalibrator()
        assert cal.get_override_rate("ec") == 0.0
        assert cal.get_override_rate("ic") == 0.0

    def test_records_overrides(self):
        """Overrides should be recorded and queryable."""
        cal = ThresholdCalibrator()
        cal.record_override("ec", True)
        cal.record_override("ec", False)
        assert cal.get_override_rate("ec") == 0.5

    def test_stage_isolation(self):
        """EC and IC should have independent override tracking."""
        cal = ThresholdCalibrator()
        cal.record_override("ec", True)
        cal.record_override("ec", True)
        cal.record_override("ic", False)
        assert cal.get_override_rate("ec") == 1.0
        assert cal.get_override_rate("ic") == 0.0

    def test_threshold_tight_with_high_overrides(self):
        """High override rate → tighter threshold (higher score required)."""
        cal = ThresholdCalibrator()
        for _ in range(10):
            cal.record_override("ec", True)
        high_override_threshold = cal.get_threshold("ec", base_threshold=0.5)
        # With 100% overrides, threshold should be > 0.5
        assert high_override_threshold > 0.5

    def test_threshold_loose_with_low_overrides(self):
        """Low override rate → looser threshold (lower score accepted)."""
        cal = ThresholdCalibrator()
        for _ in range(10):
            cal.record_override("ec", False)
        low_override_threshold = cal.get_threshold("ec", base_threshold=0.5)
        # With 0% overrides, threshold should be < 0.5
        assert low_override_threshold < 0.5

    def test_threshold_bounded(self):
        """Threshold should stay within [0.1, 0.9]."""
        cal = ThresholdCalibrator()
        for _ in range(100):
            cal.record_override("ec", True)
        t = cal.get_threshold("ec", base_threshold=0.5)
        assert 0.1 <= t <= 0.9

    def test_state_snapshot(self):
        """get_state should return descriptive dict."""
        cal = ThresholdCalibrator()
        cal.record_override("ec", True)
        cal.record_override("ec", False)
        state = cal.get_state("ec")
        assert state["stage"] == "ec"
        assert state["total_advisories"] == 2
        assert state["override_count"] == 1
        assert state["adaptive_threshold"] > 0


class TestOperationalMetrics:
    def test_empty_metrics(self):
        """New metrics instance should return zeros."""
        m = OperationalMetrics()
        stats = m.get_stats()
        assert stats["throughput_items_per_sec"] == 0.0
        assert stats["latency_avg_ms"] == 0.0
        assert stats["escalation_rate"] == 0.0
        assert stats["human_agreement_rate"] == 0.0

    def test_records_throughput(self):
        """Processed records should produce throughput > 0."""
        m = OperationalMetrics()
        for _ in range(5):
            m.record_processed(latency_ms=100)
            time.sleep(0.01)
        assert m.get_throughput() > 0

    def test_records_latency(self):
        m = OperationalMetrics()
        m.record_processed(latency_ms=150)
        m.record_processed(latency_ms=250)
        assert 190 <= m.get_avg_latency_ms() <= 210

    def test_escalation_rate(self):
        m = OperationalMetrics()
        m.record_escalation(True)
        m.record_escalation(True)
        m.record_escalation(False)
        rate = m.get_escalation_rate()
        assert abs(rate - 2 / 3) < 0.001, f"Expected ~0.6667, got {rate}"

    def test_agreement_rate(self):
        m = OperationalMetrics()
        m.record_agreement(True)
        m.record_agreement(True)
        m.record_agreement(False)
        rate = m.get_agreement_rate()
        assert abs(rate - 2 / 3) < 0.001, f"Expected ~0.6667, got {rate}"

    def test_estimated_precision(self):
        """Precision = agreement_rate * (1 - escalation_rate)."""
        m = OperationalMetrics()
        m.record_agreement(True)
        m.record_agreement(True)
        m.record_agreement(False)
        m.record_escalation(False)
        m.record_escalation(True)
        m.record_escalation(False)
        expected = (2 / 3) * (1 - 1 / 3)
        precision = m.get_estimated_precision()
        assert abs(precision - expected) < 0.01, f"Expected ~{expected:.4f}, got {precision}"

    def test_queue_depth(self):
        m = OperationalMetrics()
        m.record_queue_depth(5)
        m.record_queue_depth(15)
        assert m.get_avg_queue_depth() == 10.0

    def test_reset(self):
        m = OperationalMetrics()
        m.record_processed(latency_ms=100)
        m.reset()
        assert m.get_avg_latency_ms() == 0.0

    def test_total_processed_count(self):
        m = OperationalMetrics()
        m.record_processed(latency_ms=50)
        m.record_processed(latency_ms=50)
        assert m.get_stats()["total_processed"] == 2


class TestReliabilityGlobals:
    def setup_method(self):
        reset_reliability_globals()

    def test_get_threshold_calibrator_singleton(self):
        c1 = get_threshold_calibrator()
        c2 = get_threshold_calibrator()
        assert c1 is c2

    def test_get_operational_metrics_singleton(self):
        m1 = get_operational_metrics()
        m2 = get_operational_metrics()
        assert m1 is m2

    def test_reset_globals(self):
        c1 = get_threshold_calibrator()
        m1 = get_operational_metrics()
        reset_reliability_globals()
        c2 = get_threshold_calibrator()
        m2 = get_operational_metrics()
        assert c1 is not c2
        assert m1 is not m2
