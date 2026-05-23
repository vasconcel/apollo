"""
Research Export Pipeline for APOLLO.

Exports calibration runs, summaries, drift reports, and quality metrics
as reproducible, schema-stable, versioned artifacts.

Supported formats:
  - CSV (tabular data: calibration runs, per-article decisions)
  - JSON (structured data: summaries, drift reports, quality metrics, full exports)

All exports are deterministic given the same input data.
"""
import csv
import json
import os
import io
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone


EXPORT_VERSION = "1.0.0"
EXPORT_DIR = Path("data/exports")


class ExportError(Exception):
    """Raised when an export operation fails."""


def _export_dir(subdir: str = "") -> Path:
    path = EXPORT_DIR / subdir
    path.mkdir(parents=True, exist_ok=True)
    return path


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_filename(base: str, ext: str, session_id: str = "") -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    if session_id:
        return f"{base}_{session_id}_{ts}.{ext}"
    return f"{base}_{ts}.{ext}"


# ---------------------------------------------------------------------------
# CSV exports
# ---------------------------------------------------------------------------

def export_calibration_runs_csv(
    runs: List[Dict],
    output_path: Optional[str] = None,
) -> str:
    """Export calibration runs as CSV.

    Each row represents one calibration run with summary metrics.

    Args:
        runs: List of calibration report dicts
        output_path: Optional file path (auto-generated if omitted)

    Returns:
        Path to exported CSV file.
    """
    if not runs:
        raise ExportError("No calibration runs to export")

    fieldnames = [
        "calibration_id", "session_id", "protocol_version",
        "sample_size", "created_at",
        "ec_mean_confidence", "ec_acceptance_rate", "ec_total",
        "ic_mean_confidence", "ic_acceptance_rate", "ic_total",
        "ec_ic_overlap_rate",
        "escalation_rate", "low_grounding_rate",
        "duration_seconds",
    ]

    path = output_path or str(_export_dir("csv") / _make_filename("calibration_runs", "csv"))
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for run in runs:
            ec = run.get("ec", {})
            ic = run.get("ic", {})
            diagnostics = run.get("diagnostics", {})
            writer.writerow({
                "calibration_id": run.get("calibration_id", ""),
                "session_id": run.get("session_id", ""),
                "protocol_version": run.get("protocol_version", "1.0"),
                "sample_size": run.get("sample_size", 0),
                "created_at": run.get("created_at", ""),
                "ec_mean_confidence": ec.get("mean_confidence", 0.0),
                "ec_acceptance_rate": ec.get("acceptance_rate", 0.0),
                "ec_total": ec.get("total", 0),
                "ic_mean_confidence": ic.get("mean_confidence", 0.0),
                "ic_acceptance_rate": ic.get("acceptance_rate", 0.0),
                "ic_total": ic.get("total", 0),
                "ec_ic_overlap_rate": diagnostics.get("overlap_rate", 0.0),
                "escalation_rate": diagnostics.get("escalation_rate", 0.0),
                "low_grounding_rate": diagnostics.get("low_grounding_rate", 0.0),
                "duration_seconds": run.get("duration_seconds", 0),
            })
    return path


def export_advisories_csv(
    advisories: List[Dict],
    output_path: Optional[str] = None,
) -> str:
    """Export per-article advisories as CSV.

    Each row represents one advisory decision for one article.

    Args:
        advisories: List of advisory dicts (from AdvisoryResult.to_dict())
        output_path: Optional file path

    Returns:
        Path to exported CSV file.
    """
    if not advisories:
        raise ExportError("No advisories to export")

    fieldnames = [
        "cache_key", "protocol_version", "stage",
        "decision", "confidence",
        "grounding_strength", "hallucination_risk_score",
        "risk_classification", "validation_queue",
        "requires_validation", "generated_at",
        "prefilter_applied", "prefilter_reason", "model_used",
        "triggered_criteria_count",
    ]

    path = output_path or str(_export_dir("csv") / _make_filename("advisories", "csv"))
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for adv in advisories:
            triggered = adv.get("triggered_criteria", [])
            writer.writerow({
                "cache_key": adv.get("cache_key", ""),
                "protocol_version": adv.get("protocol_version", "1.0"),
                "stage": adv.get("stage", ""),
                "decision": str(adv.get("decision", "")),
                "confidence": adv.get("confidence", 0.0),
                "grounding_strength": adv.get("grounding_strength", 0.0),
                "hallucination_risk_score": adv.get("hallucination_risk_score", 0.0),
                "risk_classification": str(adv.get("risk_classification", "")),
                "validation_queue": str(adv.get("validation_queue", "")),
                "requires_validation": adv.get("requires_validation", False),
                "generated_at": adv.get("generated_at", ""),
                "prefilter_applied": adv.get("prefilter_applied", False),
                "prefilter_reason": adv.get("prefilter_reason", ""),
                "model_used": adv.get("model_used", ""),
                "triggered_criteria_count": len(triggered),
            })
    return path


# ---------------------------------------------------------------------------
# JSON exports
# ---------------------------------------------------------------------------

def export_calibration_json(
    calibration_report: Dict,
    output_path: Optional[str] = None,
) -> str:
    """Export a single calibration report as JSON.

    Args:
        calibration_report: Full calibration report dict
        output_path: Optional file path

    Returns:
        Path to exported JSON file.
    """
    export = {
        "_export_version": EXPORT_VERSION,
        "_exported_at": _timestamp(),
        "calibration": calibration_report,
    }
    path = output_path or str(_export_dir("json") / _make_filename("calibration", "json"))
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(export, f, ensure_ascii=False, indent=2)
    return path


def export_ec_ic_summary_json(
    ec_advisories: List[Dict],
    ic_advisories: List[Dict],
    output_path: Optional[str] = None,
) -> str:
    """Export EC and IC advisory summaries as JSON.

    Args:
        ec_advisories: List of EC advisory dicts
        ic_advisories: List of IC advisory dicts
        output_path: Optional file path

    Returns:
        Path to exported JSON file.
    """
    from src.advisory.advisory_quality import compute_all_diagnostics

    ec_diag = compute_all_diagnostics(ec_advisories) if ec_advisories else {}
    ic_diag = compute_all_diagnostics(ic_advisories) if ic_advisories else {}

    export = {
        "_export_version": EXPORT_VERSION,
        "_exported_at": _timestamp(),
        "summary": {
            "ec": {
                "count": len(ec_advisories),
                "diagnostics": ec_diag,
            },
            "ic": {
                "count": len(ic_advisories),
                "diagnostics": ic_diag,
            },
        },
        "advisories": {
            "ec": [{"cache_key": a.get("cache_key", ""), "decision": str(a.get("decision", "")), "confidence": a.get("confidence", 0.0)} for a in ec_advisories],
            "ic": [{"cache_key": a.get("cache_key", ""), "decision": str(a.get("decision", "")), "confidence": a.get("confidence", 0.0)} for a in ic_advisories],
        },
    }
    path = output_path or str(_export_dir("json") / _make_filename("ec_ic_summary", "json"))
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(export, f, ensure_ascii=False, indent=2)
    return path


def export_drift_report_json(
    drift_report: Dict,
    calibration_ids: Optional[Dict[str, str]] = None,
    output_path: Optional[str] = None,
) -> str:
    """Export drift detection report as JSON.

    Args:
        drift_report: Output from calibration_drift.detect_drift()
        calibration_ids: Optional dict with baseline/candidate calibration IDs
        output_path: Optional file path

    Returns:
        Path to exported JSON file.
    """
    export = {
        "_export_version": EXPORT_VERSION,
        "_exported_at": _timestamp(),
        "drift": drift_report,
        "calibration_ids": calibration_ids or {},
    }
    path = output_path or str(_export_dir("json") / _make_filename("drift_report", "json"))
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(export, f, ensure_ascii=False, indent=2)
    return path


def export_quality_metrics_json(
    quality_scores: Dict,
    output_path: Optional[str] = None,
) -> str:
    """Export advisory quality scores as JSON.

    Args:
        quality_scores: Output from advisory_quality_score.compute_quality_score()
        output_path: Optional file path

    Returns:
        Path to exported JSON file.
    """
    export = {
        "_export_version": EXPORT_VERSION,
        "_exported_at": _timestamp(),
        "quality": quality_scores,
    }
    path = output_path or str(_export_dir("json") / _make_filename("quality_metrics", "json"))
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(export, f, ensure_ascii=False, indent=2)
    return path


def export_full_calibration_export(
    calibration_report: Dict,
    ec_advisories: List[Dict],
    ic_advisories: List[Dict],
    drift_report: Optional[Dict] = None,
    quality_scores: Optional[Dict] = None,
    ground_truth: Optional[Dict] = None,
    output_path: Optional[str] = None,
) -> str:
    """Export a complete calibration run as a single JSON file.

    Combines calibration report, EC/IC advisories, drift report,
    quality scores, and ground truth comparison (if available).

    Args:
        calibration_report: Full calibration report dict
        ec_advisories: List of EC advisory dicts
        ic_advisories: List of IC advisory dicts
        drift_report: Optional drift detection report
        quality_scores: Optional quality scores
        ground_truth: Optional ground truth comparison
        output_path: Optional file path

    Returns:
        Path to exported JSON file.
    """
    from src.advisory.advisory_quality import compute_all_diagnostics

    ec_diag = compute_all_diagnostics(ec_advisories) if ec_advisories else {}
    ic_diag = compute_all_diagnostics(ic_advisories) if ic_advisories else {}

    export: Dict[str, Any] = {
        "_export_version": EXPORT_VERSION,
        "_exported_at": _timestamp(),
        "type": "full_calibration_export",
        "calibration_report": calibration_report,
        "diagnostics": {
            "ec": ec_diag,
            "ic": ic_diag,
        },
        "advisories": {
            "ec": ec_advisories,
            "ic": ic_advisories,
        },
    }
    if drift_report:
        export["drift"] = drift_report
    if quality_scores:
        export["quality"] = quality_scores
    if ground_truth:
        export["ground_truth"] = ground_truth

    path = output_path or str(_export_dir("json") / _make_filename("full_calibration_export", "json"))
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(export, f, ensure_ascii=False, indent=2)
    return path


# ---------------------------------------------------------------------------
# In-memory export (for UI download buttons)
# ---------------------------------------------------------------------------

def export_advisories_csv_string(advisories: List[Dict]) -> str:
    """Export advisories as CSV string (for Streamlit download_button)."""
    output = io.StringIO()
    if not advisories:
        return ""
    fieldnames = [
        "cache_key", "protocol_version", "stage",
        "decision", "confidence", "grounding_strength",
        "hallucination_risk_score", "triggered_criteria_count",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for adv in advisories:
        writer.writerow({
            "cache_key": adv.get("cache_key", ""),
            "protocol_version": adv.get("protocol_version", "1.0"),
            "stage": adv.get("stage", ""),
            "decision": str(adv.get("decision", "")),
            "confidence": adv.get("confidence", 0.0),
            "grounding_strength": adv.get("grounding_strength", 0.0),
            "hallucination_risk_score": adv.get("hallucination_risk_score", 0.0),
            "triggered_criteria_count": len(adv.get("triggered_criteria", [])),
        })
    return output.getvalue()
