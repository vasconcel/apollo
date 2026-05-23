"""
Calibration Comparison Engine for APOLLO.

Compares two calibration artifacts and produces a structured
delta report. Supports comparisons:

  - protocol v1 vs v2 (same dataset)
  - same protocol across different datasets
  - same dataset across protocol revisions

Pure deterministic analysis. No side effects, no mutations.
"""
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field


@dataclass
class ComparisonDelta:
    """A single metric delta between two calibration runs."""
    metric: str
    baseline_value: Any
    candidate_value: Any
    delta: float
    direction: str  # "improved", "regressed", "neutral"
    significance: str  # "low", "medium", "high"


def _safe_float(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _delta_direction(
    baseline: float,
    candidate: float,
    higher_is_better: bool,
    tolerance: float = 0.02,
) -> str:
    if abs(candidate - baseline) <= tolerance:
        return "neutral"
    if candidate > baseline:
        return "improved" if higher_is_better else "regressed"
    return "regressed" if higher_is_better else "improved"


def _significance_from_delta(delta_abs: float) -> str:
    if delta_abs >= 0.3:
        return "high"
    if delta_abs >= 0.1:
        return "medium"
    return "low"


def _compare_summary(
    baseline: Dict,
    candidate: Dict,
    stage_key: str,
    higher_is_better: bool = True,
) -> List[ComparisonDelta]:
    """Compare summary sections (ec_summary or ic_summary)."""
    deltas = []
    b = baseline.get(stage_key, {})
    c = candidate.get(stage_key, {})

    metrics = [
        ("mean_confidence", True),
        ("accepts", True),
        ("rejects", False),
        ("ambiguous", False),
        ("low_grounding", False),
        ("high_ambiguity", False),
    ]

    for metric, hib in metrics:
        bv = _safe_float(b.get(metric, 0))
        cv = _safe_float(c.get(metric, 0))
        delta = cv - bv
        dir_ = _delta_direction(bv, cv, hib if higher_is_better else hib)
        sig = _significance_from_delta(abs(delta))
        metric_key = f"{stage_key}.{metric}"
        deltas.append(ComparisonDelta(
            metric=metric_key,
            baseline_value=bv,
            candidate_value=cv,
            delta=round(delta, 4),
            direction=dir_,
            significance=sig,
        ))

    return deltas


def _compare_criteria(
    baseline: Dict,
    candidate: Dict,
) -> List[ComparisonDelta]:
    """Compare criteria activation distributions."""
    deltas = []
    b_criteria = baseline.get("criteria", {})
    c_criteria = candidate.get("criteria", {})

    overlap_b = baseline.get("overlap", {})
    overlap_c = candidate.get("overlap", {})

    overlap_rate_b = _safe_float(overlap_b.get("ec_ic_overlap_rate", 0))
    overlap_rate_c = _safe_float(overlap_c.get("ec_ic_overlap_rate", 0))
    overlap_delta = overlap_rate_c - overlap_rate_b

    deltas.append(ComparisonDelta(
        metric="overlap.ec_ic_overlap_rate",
        baseline_value=overlap_rate_b,
        candidate_value=overlap_rate_c,
        delta=round(overlap_delta, 4),
        direction=_delta_direction(overlap_rate_b, overlap_rate_c, False),
        significance=_significance_from_delta(abs(overlap_delta)),
    ))

    overlap_count_b = _safe_float(overlap_b.get("ec_ic_overlap_count", 0))
    overlap_count_c = _safe_float(overlap_c.get("ec_ic_overlap_count", 0))
    overlap_count_delta = overlap_count_c - overlap_count_b

    deltas.append(ComparisonDelta(
        metric="overlap.ec_ic_overlap_count",
        baseline_value=overlap_count_b,
        candidate_value=overlap_count_c,
        delta=round(overlap_count_delta, 4),
        direction=_delta_direction(overlap_count_b, overlap_count_c, False),
        significance=_significance_from_delta(abs(overlap_count_delta)),
    ))

    return deltas


def _compare_runtime(
    baseline: Dict,
    candidate: Dict,
) -> List[ComparisonDelta]:
    """Compare runtime metadata between runs."""
    deltas = []
    b_runtime = baseline.get("runtime_metadata", {})
    c_runtime = candidate.get("runtime_metadata", {})

    b_dur = _safe_float(b_runtime.get("duration_seconds", 0))
    c_dur = _safe_float(c_runtime.get("duration_seconds", 0))
    dur_delta = c_dur - b_dur

    deltas.append(ComparisonDelta(
        metric="runtime.duration_seconds",
        baseline_value=b_dur,
        candidate_value=c_dur,
        delta=round(dur_delta, 2),
        direction=_delta_direction(b_dur, c_dur, False, tolerance=5.0),
        significance=_significance_from_delta(abs(dur_delta) / max(b_dur, 1)),
    ))

    b_sample = _safe_float(baseline.get("sample_size", 0))
    c_sample = _safe_float(candidate.get("sample_size", 0))

    deltas.append(ComparisonDelta(
        metric="sample_size",
        baseline_value=b_sample,
        candidate_value=c_sample,
        delta=c_sample - b_sample,
        direction="neutral",
        significance="low",
    ))

    return deltas


def compare_calibrations(
    baseline: Dict,
    candidate: Dict,
) -> Dict:
    """Compare two calibration artifacts.

    Args:
        baseline: The earlier/reference calibration artifact dict.
        candidate: The later/new calibration artifact dict.

    Returns:
        Structured comparison report.
    """
    deltas = []

    deltas.extend(_compare_summary(baseline, candidate, "ec_summary", higher_is_better=True))
    deltas.extend(_compare_summary(baseline, candidate, "ic_summary", higher_is_better=True))
    deltas.extend(_compare_criteria(baseline, candidate))
    deltas.extend(_compare_runtime(baseline, candidate))

    improvements = [d for d in deltas if d.direction == "improved"]
    regressions = [d for d in deltas if d.direction == "regressed"]
    unchanged = [d for d in deltas if d.direction == "neutral"]

    high_count = sum(1 for d in regressions if d.significance == "high")
    medium_count = sum(1 for d in regressions if d.significance == "medium")
    improvement_count = sum(1 for d in improvements if d.significance in ("high", "medium"))

    if high_count > 0:
        overall = "regressed"
    elif improvement_count > medium_count:
        overall = "improved"
    elif improvement_count == 0 and medium_count == 0 and high_count == 0:
        overall = "neutral"
    else:
        overall = "regressed"

    bl_name = baseline.get("calibration_id", "baseline")
    cand_name = candidate.get("calibration_id", "candidate")

    return {
        "baseline_calibration_id": bl_name,
        "candidate_calibration_id": cand_name,
        "baseline_created_at": baseline.get("created_at", ""),
        "candidate_created_at": candidate.get("created_at", ""),
        "improvements": [
            {
                "metric": d.metric,
                "baseline_value": d.baseline_value,
                "candidate_value": d.candidate_value,
                "delta": d.delta,
                "significance": d.significance,
            }
            for d in improvements
        ],
        "regressions": [
            {
                "metric": d.metric,
                "baseline_value": d.baseline_value,
                "candidate_value": d.candidate_value,
                "delta": d.delta,
                "significance": d.significance,
            }
            for d in regressions
        ],
        "unchanged": [
            {
                "metric": d.metric,
                "baseline_value": d.baseline_value,
                "candidate_value": d.candidate_value,
            }
            for d in unchanged
        ],
        "summary": {
            "overall_direction": overall,
            "total_deltas": len(deltas),
            "improvement_count": len(improvements),
            "regression_count": len(regressions),
            "unchanged_count": len(unchanged),
        },
    }
