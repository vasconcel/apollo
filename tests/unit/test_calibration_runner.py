"""
Tests for calibration runner and report generation.
"""
from src.advisory.calibration_runner import (
    _select_calibration_sample,
    _count_triggered_criteria,
    _count_never_triggered,
    _count_always_triggered,
    _compute_criteria_overlap,
    generate_calibration_report,
)
from src.advisory.advisory_models import AdvisoryConfig


def make_advisory_dict(decision="INCLUDE", confidence=0.8,
                       triggered_criteria=None, grounding_strength=0.9,
                       hallucination_risk_score=0.1):
    return {
        "cache_key": "test_key",
        "decision": decision,
        "confidence": confidence,
        "triggered_criteria": triggered_criteria or [],
        "criterion_evaluations": [],
        "hallucination_risk_score": hallucination_risk_score,
        "grounding_strength": grounding_strength,
    }


class TestSelectCalibrationSample:
    def test_selects_first_n(self):
        articles = [1, 2, 3, 4, 5]
        assert _select_calibration_sample(articles, 3) == [1, 2, 3]

    def test_handles_smaller_sample(self):
        articles = [1, 2]
        assert _select_calibration_sample(articles, 10) == [1, 2]

    def test_empty_articles(self):
        assert _select_calibration_sample([], 5) == []


class TestCountTriggeredCriteria:
    def test_counts_correctly(self):
        advisories = [
            make_advisory_dict(triggered_criteria=["A", "B"]),
            make_advisory_dict(triggered_criteria=["A", "C"]),
            make_advisory_dict(triggered_criteria=["B"]),
        ]
        counts = _count_triggered_criteria(advisories)
        assert counts == {"A": 2, "B": 2, "C": 1}

    def test_empty_advisories(self):
        assert _count_triggered_criteria([]) == {}


class TestCountNeverTriggered:
    def test_identifies_never_triggered(self):
        never = _count_never_triggered(["A", "B", "C"], {"A": 3, "C": 1})
        assert never == ["B"]

    def test_all_triggered(self):
        never = _count_never_triggered(["A", "B"], {"A": 1, "B": 2})
        assert never == []


class TestCountAlwaysTriggered:
    def test_identifies_always_triggered(self):
        always = _count_always_triggered(3, {"A": 3, "B": 2})
        assert always == ["A"]

    def test_none_always(self):
        always = _count_always_triggered(3, {"A": 2, "B": 1})
        assert always == []


class TestComputeCriteriaOverlap:
    def test_detects_overlap(self):
        ec = [
            make_advisory_dict(triggered_criteria=["A", "B"]),
            make_advisory_dict(triggered_criteria=["C"]),
        ]
        ic = [
            make_advisory_dict(triggered_criteria=["B", "D"]),
            make_advisory_dict(triggered_criteria=["E"]),
        ]
        result = _compute_criteria_overlap(ec, ic)
        assert result["ec_ic_overlap_count"] == 1
        assert result["ec_ic_overlap_rate"] == 0.5

    def test_no_overlap(self):
        ec = [make_advisory_dict(triggered_criteria=["A"])]
        ic = [make_advisory_dict(triggered_criteria=["B"])]
        result = _compute_criteria_overlap(ec, ic)
        assert result["ec_ic_overlap_count"] == 0


class TestGenerateCalibrationReport:
    def test_basic_report(self):
        ec = [make_advisory_dict(decision="INCLUDE") for _ in range(3)]
        ec += [make_advisory_dict(decision="EXCLUDE")]
        ic = [make_advisory_dict(decision="INCLUDE") for _ in range(2)]
        ic += [make_advisory_dict(decision="EXCLUDE") for _ in range(2)]

        config = AdvisoryConfig(calibration_sample_size=4)
        report = generate_calibration_report(
            sample_size=4,
            ec_advisories=ec,
            ic_advisories=ic,
            config=config,
        )

        assert report["sample_size"] == 4
        assert report["total_processed"] == 4
        assert report["ec"]["accepts"] == 3
        assert report["ec"]["rejects"] == 1
        assert report["ic"]["accepts"] == 2
        assert report["ic"]["rejects"] == 2
        assert "recommendation" in report
        assert "recommendation_label" in report

    def test_empty_advisories(self):
        config = AdvisoryConfig(calibration_sample_size=0)
        report = generate_calibration_report(0, [], [], config)
        assert report["sample_size"] == 0
        assert "recommendation" in report
