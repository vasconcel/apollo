"""
Advisory Quality Diagnostics for APOLLO.

Analytical diagnostics for evaluating advisory quality:
- Confidence distribution (histogram into buckets)
- Uncertainty distribution
- Triggered criteria frequency
- Escalation rate
- Calibration drift analysis

All functions are PURE — they accept advisory data and return results.
No side effects, no state mutation, no I/O.
"""
from typing import Dict, List, Optional, Tuple
from collections import Counter


CONFIDENCE_BUCKETS = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]


def compute_confidence_histogram(advisories: List[Dict]) -> Dict:
    """Compute confidence score histogram.

    Args:
        advisories: List of advisory dicts with 'confidence' key.

    Returns:
        Dict mapping bucket label -> count.
    """
    histogram: Dict[str, int] = {}
    for i in range(len(CONFIDENCE_BUCKETS) - 1):
        low = CONFIDENCE_BUCKETS[i]
        high = CONFIDENCE_BUCKETS[i + 1]
        label = f"{low:.1f}-{high:.1f}"
        count = sum(
            1 for a in advisories
            if low <= a.get("confidence", 0.0) < high
        )
        if count:
            histogram[label] = count
    # Include exactly 1.0
    ones = sum(1 for a in advisories if a.get("confidence", 0.0) == 1.0)
    if ones:
        histogram["0.9-1.0"] = histogram.get("0.9-1.0", 0) + ones
    return histogram


def compute_uncertainty_distribution(advisories: List[Dict]) -> Dict:
    """Compute uncertainty score distribution.

    Returns:
        Dict with mean, median, and risk-tier counts.
    """
    scores = [
        a.get("hallucination_risk_score", 0.0)
        for a in advisories
    ]
    if not scores:
        return {
            "mean": 0.0,
            "median": 0.0,
            "count": 0,
            "low_uncertainty": 0,
            "medium_uncertainty": 0,
            "high_uncertainty": 0,
        }
    sorted_scores = sorted(scores)
    n = len(sorted_scores)
    return {
        "mean": round(sum(scores) / n, 4),
        "median": round(sorted_scores[n // 2], 4),
        "count": n,
        "low_uncertainty": sum(1 for s in scores if s < 0.3),
        "medium_uncertainty": sum(1 for s in scores if 0.3 <= s < 0.7),
        "high_uncertainty": sum(1 for s in scores if s >= 0.7),
    }


def compute_decision_distribution(advisories: List[Dict]) -> Dict:
    """Compute distribution of advisory decisions."""
    counter: Dict[str, int] = {}
    for a in advisories:
        decision = a.get("decision", "UNKNOWN")
        decision_str = str(decision.value) if hasattr(decision, 'value') else str(decision)
        counter[decision_str] = counter.get(decision_str, 0) + 1
    total = sum(counter.values()) or 1
    return {
        "counts": dict(counter),
        "rates": {k: round(v / total, 4) for k, v in counter.items()},
    }


def compute_triggered_criteria_frequency(advisories: List[Dict]) -> List[Dict]:
    """Compute how often each criterion was triggered.

    Returns:
        List of {criterion, count, rate} sorted by count descending.
    """
    counter: Dict[str, int] = Counter()
    total = len(advisories)
    for a in advisories:
        triggered = a.get("triggered_criteria", [])
        for tc in triggered:
            cid = str(tc) if not hasattr(tc, 'value') else str(tc.value)
            counter[cid] += 1
    result = [
        {
            "criterion": cid,
            "count": count,
            "rate": round(count / max(total, 1), 4),
        }
        for cid, count in counter.most_common()
    ]
    return result


def compute_escalation_rate(advisories: List[Dict]) -> Dict:
    """Compute rate of advisories requiring human escalation.

    Escalation = UNCERTAIN, INSUFFICIENT_EVIDENCE, CANNOT_DETERMINE,
    or hallucination_risk_score > 0.7.

    Returns:
        Dict with escalation_rate, total, escalated_count.
    """
    ESCALATION_DECISIONS = {"UNCERTAIN", "INSUFFICIENT_EVIDENCE", "CANNOT_DETERMINE"}
    total = len(advisories)
    if not total:
        return {"escalation_rate": 0.0, "total": 0, "escalated_count": 0}
    escalated = 0
    for a in advisories:
        decision = a.get("decision", "")
        decision_str = str(decision.value) if hasattr(decision, 'value') else str(decision)
        if decision_str in ESCALATION_DECISIONS:
            escalated += 1
        elif a.get("hallucination_risk_score", 0.0) > 0.7:
            escalated += 1
    return {
        "escalation_rate": round(escalated / total, 4),
        "total": total,
        "escalated_count": escalated,
    }


def compute_grounding_distribution(advisories: List[Dict]) -> Dict:
    """Compute distribution of grounding strengths."""
    scores = [a.get("grounding_strength", 0.0) for a in advisories]
    if not scores:
        return {"mean": 0.0, "low_grounding": 0, "adequate_grounding": 0}
    n = len(scores)
    return {
        "mean": round(sum(scores) / n, 4),
        "low_grounding": sum(1 for s in scores if s < 0.5),
        "adequate_grounding": sum(1 for s in scores if s >= 0.5),
    }


def compute_calibration_drift(
    baseline_advisories: List[Dict],
    current_advisories: List[Dict],
) -> Dict:
    """Compare diagnostic metrics between two calibration runs.

    Args:
        baseline_advisories: Advisories from previous calibration.
        current_advisories: Advisories from current calibration.

    Returns:
        Dict with drift metrics for each diagnostic.
    """
    def _mean_confidence(advs):
        if not advs:
            return 0.0
        return sum(a.get("confidence", 0.0) for a in advs) / len(advs)

    def _escalation(advs):
        return compute_escalation_rate(advs)["escalation_rate"]

    def _uncertainty_mean(advs):
        scores = [a.get("hallucination_risk_score", 0.0) for a in advs]
        if not scores:
            return 0.0
        return sum(scores) / len(scores)

    baseline_conf = _mean_confidence(baseline_advisories)
    current_conf = _mean_confidence(current_advisories)
    baseline_esc = _escalation(baseline_advisories)
    current_esc = _escalation(current_advisories)
    baseline_unc = _uncertainty_mean(baseline_advisories)
    current_unc = _uncertainty_mean(current_advisories)

    return {
        "confidence_drift": round(current_conf - baseline_conf, 4),
        "escalation_drift": round(current_esc - baseline_esc, 4),
        "uncertainty_drift": round(current_unc - baseline_unc, 4),
        "baseline": {
            "mean_confidence": round(baseline_conf, 4),
            "escalation_rate": round(baseline_esc, 4),
            "mean_uncertainty": round(baseline_unc, 4),
        },
        "current": {
            "mean_confidence": round(current_conf, 4),
            "escalation_rate": round(current_esc, 4),
            "mean_uncertainty": round(current_unc, 4),
        },
    }


def compute_all_diagnostics(advisories: List[Dict]) -> Dict:
    """Compute all quality diagnostics in one pass."""
    return {
        "confidence_histogram": compute_confidence_histogram(advisories),
        "uncertainty_distribution": compute_uncertainty_distribution(advisories),
        "decision_distribution": compute_decision_distribution(advisories),
        "triggered_criteria": compute_triggered_criteria_frequency(advisories),
        "escalation_rate": compute_escalation_rate(advisories),
        "grounding_distribution": compute_grounding_distribution(advisories),
        "total_advisories": len(advisories),
    }
