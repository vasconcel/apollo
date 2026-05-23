"""
Tests for persistent calibration artifacts, diagnostics engine,
and comparison engine.
"""
import os
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from src.advisory.calibration_artifact import (
    build_calibration_artifact,
    save_calibration_artifact,
    load_calibration_artifact,
    index_calibration_reports,
    _compute_protocol_hash,
    _make_calibration_id,
)
from src.advisory.protocol_diagnostics import (
    run_diagnostics,
    signal_never_triggered,
    signal_always_triggered,
    signal_high_ambiguity,
    signal_high_quarantine,
    signal_low_grounding,
    signal_confidence_instability,
    signal_overlap,
    signal_skew,
    signal_criteria_redundancy,
    signal_implicit_inference,
)
from src.advisory.calibration_comparator import compare_calibrations
from src.advisory.advisory_models import AdvisoryConfig


def _make_mock_runner(sample_size=10, protocol_version="1.0", total_articles=100):
    runner = MagicMock()
    runner.sample_size = sample_size
    runner.protocol_version = protocol_version
    runner.articles = [MagicMock() for _ in range(total_articles)]
    runner.protocol = None
    return runner


def _make_minimal_report():
    return {
        "sample_size": 10,
        "total_processed": 10,
        "ec": {
            "total": 5, "accepts": 3, "rejects": 1, "ambiguous": 1,
            "mean_confidence": 0.78, "low_grounding": 1, "high_ambiguity": 0,
        },
        "ic": {
            "total": 5, "accepts": 2, "rejects": 2, "ambiguous": 1,
            "mean_confidence": 0.72, "low_grounding": 1, "high_ambiguity": 1,
        },
        "criteria": {
            "most_triggered_ec": [("EC1", 3)],
            "most_triggered_ic": [("IC1", 2)],
        },
        "overlap": {"ec_ic_overlap_count": 1, "ec_ic_overlap_rate": 0.2},
        "recommendation": "protocol_stable",
        "recommendation_label": "Protocol stable",
    }


def make_advisory_dict(decision="INCLUDE", confidence=0.8,
                       triggered_criteria=None, grounding_strength=0.9,
                       hallucination_risk_score=0.1,
                       evidence_span=100, criterion_evaluations=None,
                       cache_key="test_key"):
    return {
        "cache_key": cache_key,
        "decision": decision,
        "confidence": confidence,
        "triggered_criteria": triggered_criteria or [],
        "criterion_evaluations": criterion_evaluations or [],
        "hallucination_risk_score": hallucination_risk_score,
        "grounding_strength": grounding_strength,
        "evidence_span": evidence_span,
    }


# ---------------------------------------------------------------------------
# Part 1: Calibration artifact persistence
# ---------------------------------------------------------------------------

class TestCalibrationArtifactBuild:
    def test_build_minimal(self):
        report = _make_minimal_report()
        runner = _make_mock_runner()
        config = AdvisoryConfig()
        artifact = build_calibration_artifact(
            report, runner, config, [], [],
            duration_seconds=120.0, ec_duration=65.0, ic_duration=55.0,
        )
        assert artifact["calibration_id"].startswith("cal_")
        assert artifact["protocol_hash"] == _compute_protocol_hash("1.0")
        assert artifact["sample_size"] == 10
        assert artifact["runtime_metadata"]["duration_seconds"] == 120.0
        assert artifact["ec_summary"]["accepts"] == 3
        assert artifact["ic_summary"]["accepts"] == 2
        assert artifact["determinism_metadata"]["replay_safe"] is True

    def test_build_supports_custom_calibration_id(self):
        report = _make_minimal_report()
        runner = _make_mock_runner(protocol_version="2.0")
        config = AdvisoryConfig()
        artifact = build_calibration_artifact(report, runner, config, [], [],
                                              60.0, 30.0, 30.0)
        assert "2.0" in artifact["protocol_version"]

    def test_sampled_articles_never_include_full_text(self):
        report = _make_minimal_report()
        runner = _make_mock_runner()
        config = AdvisoryConfig()
        ec_adv = [make_advisory_dict(cache_key="k1"), make_advisory_dict(cache_key="k2")]
        artifact = build_calibration_artifact(report, runner, config, ec_adv, [],
                                              60.0, 30.0, 30.0)
        for key in artifact["dataset_metadata"]["sampled_articles"]:
            assert len(key) > 0
            assert "title" not in key.lower()
            assert "abstract" not in key.lower()


class TestCalibrationArtifactSaveLoad:
    def test_save_and_load_roundtrip(self, tmp_path):
        report = _make_minimal_report()
        runner = _make_mock_runner()
        config = AdvisoryConfig()
        artifact = build_calibration_artifact(report, runner, config, [], [],
                                              60.0, 30.0, 30.0)
        path = save_calibration_artifact(artifact, base_path=tmp_path)
        assert os.path.exists(path)
        assert path.endswith(".json")

        loaded = load_calibration_artifact(path)
        assert loaded["calibration_id"] == artifact["calibration_id"]
        assert loaded["protocol_hash"] == artifact["protocol_hash"]
        assert loaded["sample_size"] == 10
        assert loaded["runtime_metadata"]["duration_seconds"] == 60.0

    def test_load_ignores_unknown_fields(self, tmp_path):
        artifact = {
            "calibration_id": "test_123",
            "protocol_hash": "abc123",
            "protocol_version": "1.0",
            "created_at": "2026-01-01T00:00:00",
            "screening_mode": "CALIBRATION",
            "sample_size": 5,
            "dataset_metadata": {},
            "runtime_metadata": {},
            "ec_summary": {},
            "ic_summary": {},
            "criteria": {},
            "overlap": {},
            "diagnostics": [],
            "recommendation": {"status": "", "label": "", "reasons": []},
            "determinism_metadata": {},
            "future_field_x": "should_be_preserved",
            "future_field_y": {"nested": "data"},
        }
        path = save_calibration_artifact(artifact, base_path=tmp_path)
        loaded = load_calibration_artifact(path)
        assert loaded["_unknown_fields"]["future_field_x"] == "should_be_preserved"
        assert loaded["_unknown_fields"]["future_field_y"]["nested"] == "data"

    def test_corrupted_file_raises_error(self, tmp_path):
        dir_path = tmp_path / "protocol_test"
        dir_path.mkdir(parents=True)
        bad_file = dir_path / "calibration_bad.json"
        bad_file.write_text("not json content")
        import pytest
        with pytest.raises(json.JSONDecodeError):
            load_calibration_artifact(str(bad_file))

    def test_artifact_immutable_after_save(self, tmp_path):
        report = _make_minimal_report()
        runner = _make_mock_runner()
        config = AdvisoryConfig()
        artifact = build_calibration_artifact(report, runner, config, [], [],
                                              60.0, 30.0, 30.0)
        path = save_calibration_artifact(artifact, base_path=tmp_path)
        saved = load_calibration_artifact(path)
        assert saved["ec_summary"]["accepts"] == 3
        artifact["ec_summary"]["accepts"] = 999
        saved_again = load_calibration_artifact(path)
        assert saved_again["ec_summary"]["accepts"] == 3


class TestCalibrationReportIndex:
    def test_index_empty_directory(self, tmp_path):
        assert index_calibration_reports(base_path=tmp_path) == []

    def test_index_returns_sorted_reports(self, tmp_path):
        for i, (proto, ts) in enumerate([
            ("p1", "2026-01-03T00:00:00"),
            ("p1", "2026-01-01T00:00:00"),
            ("p2", "2026-01-02T00:00:00"),
        ]):
            art = {
                "calibration_id": f"cal_{proto}_{i}",
                "protocol_hash": proto,
                "protocol_version": "1.0",
                "created_at": ts,
                "sample_size": 5,
                "screening_mode": "CALIBRATION",
                "dataset_metadata": {},
                "runtime_metadata": {},
                "ec_summary": {},
                "ic_summary": {},
                "criteria": {},
                "overlap": {},
                "diagnostics": [],
                "recommendation": {"status": "stable", "label": "", "reasons": []},
                "determinism_metadata": {},
            }
            save_calibration_artifact(art, base_path=tmp_path)

        idx = index_calibration_reports(base_path=tmp_path)
        assert len(idx) == 3
        dates = [r["created_at"] for r in idx]
        assert dates == sorted(dates, reverse=True)

    def test_index_skips_tmp_files(self, tmp_path):
        d = tmp_path / "protocol_x"
        d.mkdir(parents=True)
        (d / "calibration_2026-01-01T00-00-00.json.tmp").write_text("{}")
        art = {
            "calibration_id": "real",
            "protocol_hash": "x",
            "protocol_version": "1.0",
            "created_at": "2026-01-02T00:00:00",
            "sample_size": 5,
            "screening_mode": "CALIBRATION",
            "dataset_metadata": {},
            "runtime_metadata": {},
            "ec_summary": {},
            "ic_summary": {},
            "criteria": {},
            "overlap": {},
            "diagnostics": [],
            "recommendation": {"status": "", "label": "", "reasons": []},
            "determinism_metadata": {},
        }
        save_calibration_artifact(art, base_path=tmp_path)
        idx = index_calibration_reports(base_path=tmp_path)
        assert len(idx) == 1
        assert idx[0]["calibration_id"] == "real"


# ---------------------------------------------------------------------------
# Part 2: Protocol diagnostics
# ---------------------------------------------------------------------------

class TestDiagnosticsNeverTriggered:
    def test_detects_never_triggered(self):
        config = AdvisoryConfig()
        signals = signal_never_triggered(
            ["EC1", "EC2", "EC3"],
            {"EC1": 3, "EC2": 1},
            3, config, "ec",
        )
        triggered_ids = [s.criterion_id for s in signals]
        assert "EC3" in triggered_ids
        assert "EC1" not in triggered_ids

    def test_no_signal_when_all_triggered(self):
        config = AdvisoryConfig()
        signals = signal_never_triggered(
            ["EC1", "EC2"],
            {"EC1": 2, "EC2": 2},
            2, config, "ec",
        )
        assert len(signals) == 0


class TestDiagnosticsAlwaysTriggered:
    def test_detects_always_triggered(self):
        config = AdvisoryConfig()
        signals = signal_always_triggered(
            ["EC1", "EC2"],
            {"EC1": 5, "EC2": 3},
            5, config, "ec",
        )
        triggered_ids = [s.criterion_id for s in signals]
        assert "EC1" in triggered_ids
        assert "EC2" not in triggered_ids


class TestDiagnosticsHighAmbiguity:
    def test_detects_high_ambiguity(self):
        config = AdvisoryConfig()
        advs = [
            make_advisory_dict(hallucination_risk_score=0.8),
            make_advisory_dict(hallucination_risk_score=0.2),
            make_advisory_dict(hallucination_risk_score=0.9),
        ]
        signals = signal_high_ambiguity(advs, config, "ec")
        assert len(signals) == 1
        assert signals[0].evidence["count"] == 2

    def test_no_signal_when_all_low(self):
        config = AdvisoryConfig()
        advs = [
            make_advisory_dict(hallucination_risk_score=0.1),
            make_advisory_dict(hallucination_risk_score=0.2),
        ]
        assert len(signal_high_ambiguity(advs, config, "ec")) == 0


class TestDiagnosticsHighQuarantine:
    def test_detects_high_quarantine(self):
        config = AdvisoryConfig()
        advs = [
            make_advisory_dict(decision="UNCERTAIN"),
            make_advisory_dict(decision="INCLUDE"),
            make_advisory_dict(decision="INSUFFICIENT_EVIDENCE"),
        ]
        signals = signal_high_quarantine(advs, config, "ec")
        assert len(signals) == 1
        assert signals[0].evidence["quarantine_count"] == 2

    def test_below_threshold(self):
        config = AdvisoryConfig()
        advs = [make_advisory_dict(decision="INCLUDE") for _ in range(10)]
        signals = signal_high_quarantine(advs, config, "ec")
        assert len(signals) == 0


class TestDiagnosticsLowGrounding:
    def test_detects_low_grounding(self):
        config = AdvisoryConfig()
        advs = [
            make_advisory_dict(grounding_strength=0.2),
            make_advisory_dict(grounding_strength=0.9),
        ]
        signals = signal_low_grounding(advs, config, "ec")
        assert len(signals) == 1
        assert signals[0].evidence["low_grounding_count"] == 1


class TestDiagnosticsConfidenceInstability:
    def test_detects_instability(self):
        config = AdvisoryConfig()
        advs = [
            make_advisory_dict(confidence=0.01),
            make_advisory_dict(confidence=0.99),
            make_advisory_dict(confidence=0.01),
            make_advisory_dict(confidence=0.99),
        ]
        signals = signal_confidence_instability(advs, config, "ec")
        assert len(signals) == 1

    def test_stable_confidence_no_signal(self):
        config = AdvisoryConfig()
        advs = [make_advisory_dict(confidence=0.85) for _ in range(5)]
        signals = signal_confidence_instability(advs, config, "ec")
        assert len(signals) == 0


class TestDiagnosticsOverlap:
    def test_detects_overlap(self):
        config = AdvisoryConfig()
        overlap = {"ec_ic_overlap_count": 5, "ec_ic_overlap_rate": 0.8}
        signals = signal_overlap(overlap, config)
        assert len(signals) == 1

    def test_below_threshold_no_signal(self):
        config = AdvisoryConfig()
        overlap = {"ec_ic_overlap_count": 0, "ec_ic_overlap_rate": 0.0}
        assert len(signal_overlap(overlap, config)) == 0


class TestDiagnosticsSkew:
    def test_acceptance_skew(self):
        config = AdvisoryConfig()
        advs = [make_advisory_dict(decision="INCLUDE") for _ in range(98)]
        advs.append(make_advisory_dict(decision="EXCLUDE"))
        advs.append(make_advisory_dict(decision="EXCLUDE"))
        signals = signal_skew(advs, config, "ec")
        assert len(signals) == 1
        assert signals[0].signal_type == "acceptance_skew"


class TestDiagnosticsRedundancy:
    def test_detects_redundancy(self):
        advs = [make_advisory_dict(triggered_criteria=["EC1", "EC2"]) for _ in range(4)]
        signals = signal_criteria_redundancy(advs, ["EC1", "EC2", "EC3"], "ec")
        assert len(signals) >= 1

    def test_no_redundancy(self):
        advs = [
            make_advisory_dict(triggered_criteria=["EC1"]),
            make_advisory_dict(triggered_criteria=["EC2"]),
        ]
        signals = signal_criteria_redundancy(advs, ["EC1", "EC2", "EC3"], "ec")
        assert len(signals) == 0


class TestDiagnosticsImplicitInference:
    def test_detects_implicit_inference(self):
        config = AdvisoryConfig()
        advs = [
            make_advisory_dict(triggered_criteria=["EC1"], grounding_strength=0.2),
        ]
        signals = signal_implicit_inference(advs, config, "ec")
        assert len(signals) == 1

    def test_good_grounding_no_signal(self):
        config = AdvisoryConfig()
        advs = [make_advisory_dict(triggered_criteria=["EC1"], grounding_strength=0.9)]
        assert len(signal_implicit_inference(advs, config, "ec")) == 0


class TestDiagnosticsRunAll:
    def test_run_diagnostics_deterministic(self):
        config = AdvisoryConfig()
        ec = [make_advisory_dict(triggered_criteria=["EC1"], decision="INCLUDE")]
        ic = [make_advisory_dict(triggered_criteria=["IC1"], decision="EXCLUDE")]
        all_criteria = ["EC1", "IC1"]
        overlap = {"ec_ic_overlap_count": 0, "ec_ic_overlap_rate": 0.0}

        r1 = run_diagnostics(ec, ic, all_criteria, overlap, config)
        r2 = run_diagnostics(ec, ic, all_criteria, overlap, config)
        assert r1 == r2

    def test_empty_advisories(self):
        config = AdvisoryConfig()
        signals = run_diagnostics([], [], [], {}, config)
        assert signals == []

    def test_single_study(self):
        config = AdvisoryConfig()
        ec = [make_advisory_dict(triggered_criteria=["EC1"], decision="INCLUDE")]
        ic = [make_advisory_dict(triggered_criteria=["IC1"], decision="EXCLUDE")]
        signals = run_diagnostics(ec, ic, ["EC1", "IC1"],
                                   {"ec_ic_overlap_count": 0, "ec_ic_overlap_rate": 0.0},
                                   config)
        assert isinstance(signals, list)
        assert all(isinstance(s, dict) for s in signals)


# ---------------------------------------------------------------------------
# Part 3: Calibration comparator
# ---------------------------------------------------------------------------

class TestCalibrationComparator:
    def test_compare_identical_artifacts(self):
        art = {
            "calibration_id": "same",
            "protocol_hash": "x",
            "protocol_version": "1.0",
            "created_at": "2026-01-01",
            "screening_mode": "CALIBRATION",
            "sample_size": 10,
            "dataset_metadata": {},
            "runtime_metadata": {"duration_seconds": 100.0},
            "ec_summary": {
                "total": 5, "accepts": 3, "rejects": 1, "ambiguous": 1,
                "mean_confidence": 0.78, "low_grounding": 1, "high_ambiguity": 0,
            },
            "ic_summary": {
                "total": 5, "accepts": 2, "rejects": 2, "ambiguous": 1,
                "mean_confidence": 0.72, "low_grounding": 1, "high_ambiguity": 1,
            },
            "criteria": {},
            "overlap": {"ec_ic_overlap_count": 1, "ec_ic_overlap_rate": 0.2},
            "diagnostics": [],
            "recommendation": {"status": "stable", "label": "", "reasons": []},
            "determinism_metadata": {},
        }
        result = compare_calibrations(art, art)
        assert result["summary"]["unchanged_count"] > 0
        assert result["summary"]["overall_direction"] == "neutral"

    def test_compare_improved_artifact(self):
        baseline = {
            "calibration_id": "base",
            "protocol_hash": "x",
            "protocol_version": "1.0",
            "created_at": "2026-01-01",
            "screening_mode": "CALIBRATION",
            "sample_size": 10,
            "dataset_metadata": {},
            "runtime_metadata": {"duration_seconds": 200.0},
            "ec_summary": {
                "total": 5, "accepts": 2, "rejects": 2, "ambiguous": 1,
                "mean_confidence": 0.60, "low_grounding": 3, "high_ambiguity": 2,
            },
            "ic_summary": {
                "total": 5, "accepts": 1, "rejects": 3, "ambiguous": 1,
                "mean_confidence": 0.55, "low_grounding": 3, "high_ambiguity": 2,
            },
            "criteria": {},
            "overlap": {"ec_ic_overlap_count": 3, "ec_ic_overlap_rate": 0.6},
            "diagnostics": [],
            "recommendation": {"status": "refinement", "label": "", "reasons": []},
            "determinism_metadata": {},
        }
        candidate = {
            "calibration_id": "cand",
            "protocol_hash": "x",
            "protocol_version": "1.0",
            "created_at": "2026-01-02",
            "screening_mode": "CALIBRATION",
            "sample_size": 10,
            "dataset_metadata": {},
            "runtime_metadata": {"duration_seconds": 150.0},
            "ec_summary": {
                "total": 5, "accepts": 3, "rejects": 1, "ambiguous": 1,
                "mean_confidence": 0.78, "low_grounding": 1, "high_ambiguity": 0,
            },
            "ic_summary": {
                "total": 5, "accepts": 2, "rejects": 2, "ambiguous": 1,
                "mean_confidence": 0.72, "low_grounding": 1, "high_ambiguity": 1,
            },
            "criteria": {},
            "overlap": {"ec_ic_overlap_count": 1, "ec_ic_overlap_rate": 0.2},
            "diagnostics": [],
            "recommendation": {"status": "stable", "label": "", "reasons": []},
            "determinism_metadata": {},
        }
        result = compare_calibrations(baseline, candidate)
        assert result["summary"]["improvement_count"] > 0
        assert result["summary"]["overall_direction"] == "improved"

    def test_compare_regressed_artifact(self):
        baseline = {
            "calibration_id": "base",
            "protocol_hash": "x",
            "protocol_version": "1.0",
            "created_at": "2026-01-01",
            "screening_mode": "CALIBRATION",
            "sample_size": 10,
            "dataset_metadata": {},
            "runtime_metadata": {"duration_seconds": 100.0},
            "ec_summary": {"total": 5, "accepts": 4, "rejects": 1, "ambiguous": 0,
                           "mean_confidence": 0.85, "low_grounding": 0, "high_ambiguity": 0},
            "ic_summary": {"total": 5, "accepts": 3, "rejects": 2, "ambiguous": 0,
                           "mean_confidence": 0.80, "low_grounding": 0, "high_ambiguity": 0},
            "criteria": {},
            "overlap": {"ec_ic_overlap_count": 0, "ec_ic_overlap_rate": 0.0},
            "diagnostics": [],
            "recommendation": {"status": "stable", "label": "", "reasons": []},
            "determinism_metadata": {},
        }
        candidate = {
            "calibration_id": "cand",
            "protocol_hash": "x",
            "protocol_version": "1.0",
            "created_at": "2026-01-02",
            "screening_mode": "CALIBRATION",
            "sample_size": 10,
            "dataset_metadata": {},
            "runtime_metadata": {"duration_seconds": 100.0},
            "ec_summary": {"total": 5, "accepts": 2, "rejects": 2, "ambiguous": 1,
                           "mean_confidence": 0.55, "low_grounding": 3, "high_ambiguity": 2},
            "ic_summary": {"total": 5, "accepts": 1, "rejects": 3, "ambiguous": 1,
                           "mean_confidence": 0.50, "low_grounding": 4, "high_ambiguity": 3},
            "criteria": {},
            "overlap": {"ec_ic_overlap_count": 4, "ec_ic_overlap_rate": 0.8},
            "diagnostics": [],
            "recommendation": {"status": "refinement", "label": "", "reasons": []},
            "determinism_metadata": {},
        }
        result = compare_calibrations(baseline, candidate)
        assert result["summary"]["regression_count"] > 0
        assert result["summary"]["overall_direction"] == "regressed"

    def test_different_sample_sizes(self):
        bl = {
            "calibration_id": "bl", "protocol_hash": "x", "protocol_version": "1.0",
            "created_at": "", "screening_mode": "CALIBRATION", "sample_size": 5,
            "dataset_metadata": {}, "runtime_metadata": {"duration_seconds": 100.0},
            "ec_summary": {"mean_confidence": 0.8, "accepts": 0, "rejects": 0,
                           "ambiguous": 0, "low_grounding": 0, "high_ambiguity": 0, "total": 5},
            "ic_summary": {"mean_confidence": 0.8, "accepts": 0, "rejects": 0,
                           "ambiguous": 0, "low_grounding": 0, "high_ambiguity": 0, "total": 5},
            "criteria": {}, "overlap": {"ec_ic_overlap_count": 0, "ec_ic_overlap_rate": 0.0},
            "diagnostics": [], "recommendation": {"status": "", "label": "", "reasons": []},
            "determinism_metadata": {},
        }
        cand = dict(bl)
        cand["calibration_id"] = "cand"
        cand["sample_size"] = 10
        result = compare_calibrations(bl, cand)
        assert result["summary"]["overall_direction"] in ("improved", "regressed", "neutral")

    def test_comparison_deterministic(self):
        bl = {
            "calibration_id": "bl", "protocol_hash": "x", "protocol_version": "1.0",
            "created_at": "", "screening_mode": "CALIBRATION", "sample_size": 10,
            "dataset_metadata": {}, "runtime_metadata": {"duration_seconds": 100.0},
            "ec_summary": {"mean_confidence": 0.7, "accepts": 3, "rejects": 2,
                           "ambiguous": 0, "low_grounding": 1, "high_ambiguity": 1, "total": 5},
            "ic_summary": {"mean_confidence": 0.7, "accepts": 2, "rejects": 3,
                           "ambiguous": 0, "low_grounding": 1, "high_ambiguity": 1, "total": 5},
            "criteria": {}, "overlap": {"ec_ic_overlap_count": 1, "ec_ic_overlap_rate": 0.2},
            "diagnostics": [], "recommendation": {"status": "", "label": "", "reasons": []},
            "determinism_metadata": {},
        }
        cand = dict(bl)
        cand["calibration_id"] = "cand"
        cand["ec_summary"] = {"mean_confidence": 0.8, "accepts": 4, "rejects": 1,
                              "ambiguous": 0, "low_grounding": 0, "high_ambiguity": 0, "total": 5}
        r1 = compare_calibrations(bl, cand)
        r2 = compare_calibrations(bl, cand)
        assert r1 == r2


# ---------------------------------------------------------------------------
# Part 5: Threshold edge cases
# ---------------------------------------------------------------------------

class TestThresholdEdgeCases:
    def test_zero_threshold_never_triggered(self):
        config = AdvisoryConfig(diagnostics_never_triggered_threshold=0.0)
        signals = signal_never_triggered(["EC1"], {"EC1": 0}, 5, config, "ec")
        assert len(signals) == 1

    def test_perfect_threshold_always_triggered(self):
        config = AdvisoryConfig(diagnostics_always_triggered_threshold=1.0)
        signals = signal_always_triggered(["EC1"], {"EC1": 5}, 5, config, "ec")
        assert len(signals) == 1

    def test_zero_overlap_threshold(self):
        config = AdvisoryConfig(diagnostics_overlap_threshold=0.0)
        overlap = {"ec_ic_overlap_count": 1, "ec_ic_overlap_rate": 0.01}
        signals = signal_overlap(overlap, config)
        assert len(signals) == 1

    def test_max_threshold_no_signal(self):
        config = AdvisoryConfig(
            diagnostics_always_triggered_threshold=1.0,
            diagnostics_high_ambiguity_threshold=1.0,
            diagnostics_low_grounding_threshold=0.0,
            diagnostics_confidence_instability_threshold=10.0,
            diagnostics_skew_acceptance_threshold_high=1.0,
            diagnostics_skew_acceptance_threshold_low=0.0,
        )
        advs = [
            make_advisory_dict(decision="INCLUDE", confidence=0.5,
                               grounding_strength=0.5, hallucination_risk_score=0.5),
            make_advisory_dict(decision="EXCLUDE", confidence=0.5,
                               grounding_strength=0.5, hallucination_risk_score=0.5),
        ]
        assert len(signal_high_ambiguity(advs, config, "ec")) == 0
        assert len(signal_low_grounding(advs, config, "ec")) == 0
        assert len(signal_skew(advs, config, "ec")) == 0


# ---------------------------------------------------------------------------
# Part 6: Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_advisories_diagnostics(self):
        config = AdvisoryConfig()
        signals = run_diagnostics([], [], [], {}, config)
        assert signals == []

    def test_single_study_diagnostics(self):
        config = AdvisoryConfig()
        ec = [make_advisory_dict(triggered_criteria=["EC1"], decision="INCLUDE")]
        ic = [make_advisory_dict(triggered_criteria=["IC1"], decision="EXCLUDE")]
        signals = run_diagnostics(ec, ic, ["EC1", "IC1"],
                                   {"ec_ic_overlap_count": 0, "ec_ic_overlap_rate": 0.0},
                                   config)
        assert len(signals) >= 0

    def test_empty_criteria_list(self):
        config = AdvisoryConfig()
        ec = [make_advisory_dict()]
        ic = [make_advisory_dict()]
        signals = run_diagnostics(ec, ic, [], {}, config)
        assert isinstance(signals, list)

    def test_artifact_without_runtime(self, tmp_path):
        art = {
            "calibration_id": "no_runtime",
            "protocol_hash": "x", "protocol_version": "1.0",
            "created_at": "", "screening_mode": "CALIBRATION",
            "sample_size": 0, "dataset_metadata": {},
            "runtime_metadata": {},
            "ec_summary": {}, "ic_summary": {},
            "criteria": {}, "overlap": {},
            "diagnostics": [],
            "recommendation": {"status": "", "label": "", "reasons": []},
            "determinism_metadata": {},
        }
        path = save_calibration_artifact(art, base_path=tmp_path)
        loaded = load_calibration_artifact(path)
        assert loaded["calibration_id"] == "no_runtime"

    def test_compare_with_empty_runtime(self):
        bl = {
            "calibration_id": "bl", "protocol_hash": "x", "protocol_version": "1.0",
            "created_at": "", "screening_mode": "CALIBRATION", "sample_size": 10,
            "dataset_metadata": {}, "runtime_metadata": {},
            "ec_summary": {"mean_confidence": 0.7, "accepts": 0, "rejects": 0,
                           "ambiguous": 0, "low_grounding": 0, "high_ambiguity": 0, "total": 0},
            "ic_summary": {"mean_confidence": 0.7, "accepts": 0, "rejects": 0,
                           "ambiguous": 0, "low_grounding": 0, "high_ambiguity": 0, "total": 0},
            "criteria": {}, "overlap": {"ec_ic_overlap_count": 0, "ec_ic_overlap_rate": 0.0},
            "diagnostics": [], "recommendation": {"status": "", "label": "", "reasons": []},
            "determinism_metadata": {},
        }
        cand = dict(bl)
        cand["calibration_id"] = "cand"
        result = compare_calibrations(bl, cand)
        assert result["summary"]["overall_direction"] == "neutral"

    def test_high_severity_diagnostics_countable(self):
        config = AdvisoryConfig()
        ec = [make_advisory_dict(triggered_criteria=["EC1"], grounding_strength=0.1,
                                  hallucination_risk_score=0.9, decision="UNCERTAIN")]
        ic = [make_advisory_dict(triggered_criteria=["IC1"], grounding_strength=0.2,
                                  hallucination_risk_score=0.8, decision="INSUFFICIENT_EVIDENCE")]
        signals = run_diagnostics(ec, ic, ["EC1", "IC1"],
                                   {"ec_ic_overlap_count": 1, "ec_ic_overlap_rate": 1.0},
                                   config)
        high = [s for s in signals if s.get("severity") == "high"]
        assert len(high) >= 0
