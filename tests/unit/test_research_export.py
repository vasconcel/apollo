"""Tests for research_export.py."""
import json
import csv
import io
import os
import pytest

from src.advisory.research_export import (
    export_calibration_runs_csv,
    export_advisories_csv,
    export_calibration_json,
    export_ec_ic_summary_json,
    export_drift_report_json,
    export_quality_metrics_json,
    export_full_calibration_export,
    export_advisories_csv_string,
    ExportError,
)


class TestCsvExports:
    def test_export_calibration_runs_csv(self, tmp_path):
        runs = [{
            "calibration_id": "cal_001",
            "sample_size": 10,
            "protocol_version": "1.0",
            "created_at": "2024-01-01",
            "ec": {"mean_confidence": 0.8, "acceptance_rate": 0.5, "total": 10},
            "ic": {"mean_confidence": 0.7, "acceptance_rate": 0.4, "total": 10},
            "diagnostics": {"overlap_rate": 0.6, "escalation_rate": 0.1, "low_grounding_rate": 0.05},
            "duration_seconds": 120,
        }]
        out = str(tmp_path / "runs.csv")
        path = export_calibration_runs_csv(runs, output_path=out)
        assert os.path.exists(path)
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 1
            assert rows[0]["calibration_id"] == "cal_001"
            assert rows[0]["ec_mean_confidence"] == "0.8"

    def test_export_advisories_csv(self, tmp_path):
        advisories = [{
            "cache_key": "abc123",
            "protocol_version": "1.0",
            "decision": "INCLUDE",
            "confidence": 0.85,
            "grounding_strength": 0.7,
            "hallucination_risk_score": 0.1,
            "triggered_criteria": ["c1", "c2"],
        }]
        out = str(tmp_path / "adv.csv")
        path = export_advisories_csv(advisories, output_path=out)
        assert os.path.exists(path)
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 1
            assert rows[0]["triggered_criteria_count"] == "2"

    def test_export_empty_raises(self, tmp_path):
        with pytest.raises(ExportError):
            export_calibration_runs_csv([], output_path=str(tmp_path / "empty.csv"))

    def test_export_advisories_csv_string(self):
        advisories = [{"cache_key": "k1", "decision": "INCLUDE", "confidence": 0.9}]
        result = export_advisories_csv_string(advisories)
        assert "INCLUDE" in result
        assert "cache_key" in result  # header


class TestJsonExports:
    def test_export_calibration_json(self, tmp_path):
        report = {"calibration_id": "cal_001", "summary": {"score": 0.8}}
        out = str(tmp_path / "cal.json")
        path = export_calibration_json(report, output_path=out)
        assert os.path.exists(path)
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        assert data["_export_version"] == "1.0.0"
        assert data["calibration"]["calibration_id"] == "cal_001"

    def test_export_ec_ic_summary_json(self, tmp_path):
        ec = [{"cache_key": "k1", "decision": "INCLUDE", "confidence": 0.9}]
        ic = [{"cache_key": "k2", "decision": "EXCLUDE", "confidence": 0.8}]
        out = str(tmp_path / "summary.json")
        path = export_ec_ic_summary_json(ec, ic, output_path=out)
        assert os.path.exists(path)
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        assert data["summary"]["ec"]["count"] == 1
        assert data["summary"]["ic"]["count"] == 1

    def test_export_drift_report_json(self, tmp_path):
        drift = {"composite_drift_score": 0.12, "drift_type": "mild drift"}
        out = str(tmp_path / "drift.json")
        path = export_drift_report_json(drift, calibration_ids={"baseline": "b1", "candidate": "c1"}, output_path=out)
        assert os.path.exists(path)
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        assert data["drift"]["composite_drift_score"] == 0.12
        assert data["calibration_ids"]["baseline"] == "b1"

    def test_export_quality_metrics_json(self, tmp_path):
        quality = {"composite_score": 0.85, "components": {}}
        out = str(tmp_path / "quality.json")
        path = export_quality_metrics_json(quality, output_path=out)
        assert os.path.exists(path)
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        assert data["quality"]["composite_score"] == 0.85

    def test_export_full_calibration_export(self, tmp_path):
        report = {"calibration_id": "full_001"}
        ec = [{"cache_key": "k1", "decision": "INCLUDE", "confidence": 0.9}]
        ic = [{"cache_key": "k2", "decision": "EXCLUDE", "confidence": 0.8}]
        drift = {"composite_drift_score": 0.05}
        quality = {"composite_score": 0.9}
        out = str(tmp_path / "full.json")
        path = export_full_calibration_export(
            report, ec, ic,
            drift_report=drift, quality_scores=quality,
            output_path=out,
        )
        assert os.path.exists(path)
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        assert data["type"] == "full_calibration_export"
        assert "drift" in data
        assert "quality" in data
        assert "advisories" in data
