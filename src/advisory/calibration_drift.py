"""
Calibration Drift Detection for APOLLO.

Statistical drift detection comparing advisory distributions across
time windows or calibration runs using Jensen-Shannon divergence.

Drift types:
  - stable: drift_score < 0.05
  - mild drift: 0.05 <= drift_score < 0.15
  - structural drift: drift_score >= 0.15

All functions are PURE and DETERMINISTIC.
"""
import math
import threading
from typing import Dict, List, Optional, Tuple
from collections import Counter


def _kl_divergence(p: List[float], q: List[float]) -> float:
    """Compute KL-divergence D_KL(p || q) where p and q are probability distributions."""
    kl = 0.0
    for pi, qi in zip(p, q):
        if pi > 0:
            if qi > 0:
                kl += pi * math.log(pi / qi)
            else:
                kl += pi * math.log(pi / 1e-10)
    return kl


def jensen_shannon_divergence(p: List[float], q: List[float]) -> float:
    """Compute Jensen-Shannon divergence (symmetric, bounded [0, 1]).

    JS(P, Q) = 0.5 * D_KL(P || M) + 0.5 * D_KL(Q || M)
    where M = 0.5 * (P + Q)
    """
    if not p or not q:
        return 0.0
    if len(p) != len(q):
        return 1.0
    m = [(pi + qi) / 2.0 for pi, qi in zip(p, q)]
    js = 0.5 * _kl_divergence(p, m) + 0.5 * _kl_divergence(q, m)
    return min(js / math.log(2), 1.0)


def _distribution_from_counts(counts: Dict[str, int]) -> Tuple[List[str], List[float]]:
    """Convert a dict of {label: count} to an ordered list of probabilities."""
    total = sum(counts.values()) or 1
    labels = sorted(counts.keys())
    probs = [counts[l] / total for l in labels]
    return labels, probs


def _distribution_from_values(values: List[float], bins: int = 10) -> List[float]:
    """Bin continuous values into a probability distribution."""
    if not values:
        return [0.0] * bins
    hist = [0] * bins
    for v in values:
        idx = min(int(v * bins), bins - 1)
        hist[idx] += 1
    total = sum(hist) or 1
    return [h / total for h in hist]


def detect_decision_drift(
    baseline_decisions: Dict[str, int],
    current_decisions: Dict[str, int],
) -> Dict:
    """Detect drift in decision distribution.

    Args:
        baseline_decisions: {decision_label: count} from earlier period
        current_decisions: {decision_label: count} from current period

    Returns:
        Dict with js_divergence, drift_score, drift_type, distributions
    """
    all_labels = sorted(set(baseline_decisions.keys()) | set(current_decisions.keys()))
    baseline_probs = [baseline_decisions.get(l, 0) / max(sum(baseline_decisions.values()), 1) for l in all_labels]
    current_probs = [current_decisions.get(l, 0) / max(sum(current_decisions.values()), 1) for l in all_labels]
    js = jensen_shannon_divergence(baseline_probs, current_probs)
    return {
        "js_divergence": round(js, 4),
        "drift_score": round(js, 4),
        "drift_type": _classify_drift(js),
        "labels": all_labels,
        "baseline_distribution": dict(zip(all_labels, baseline_probs)),
        "current_distribution": dict(zip(all_labels, current_probs)),
    }


def detect_confidence_drift(
    baseline_confidences: List[float],
    current_confidences: List[float],
    bins: int = 10,
) -> Dict:
    """Detect drift in confidence distribution using JS-divergence."""
    if not baseline_confidences or not current_confidences:
        return {
            "js_divergence": 0.0,
            "drift_score": 0.0,
            "drift_type": "stable",
            "baseline": {
                "mean": round(sum(baseline_confidences) / max(len(baseline_confidences), 1), 4),
                "count": len(baseline_confidences),
            },
            "current": {
                "mean": round(sum(current_confidences) / max(len(current_confidences), 1), 4),
                "count": len(current_confidences),
            },
        }
    baseline_dist = _distribution_from_values(baseline_confidences, bins)
    current_dist = _distribution_from_values(current_confidences, bins)
    js = jensen_shannon_divergence(baseline_dist, current_dist)
    return {
        "js_divergence": round(js, 4),
        "drift_score": round(js, 4),
        "drift_type": _classify_drift(js),
        "baseline": {
            "mean": round(sum(baseline_confidences) / max(len(baseline_confidences), 1), 4),
            "count": len(baseline_confidences),
        },
        "current": {
            "mean": round(sum(current_confidences) / max(len(current_confidences), 1), 4),
            "count": len(current_confidences),
        },
    }


def detect_criteria_drift(
    baseline_frequencies: Dict[str, float],
    current_frequencies: Dict[str, float],
) -> Dict:
    """Detect drift in criterion activation frequencies."""
    all_criteria = sorted(set(baseline_frequencies.keys()) | set(current_frequencies.keys()))
    baseline_probs = [baseline_frequencies.get(c, 0.0) for c in all_criteria]
    current_probs = [current_frequencies.get(c, 0.0) for c in all_criteria]
    js = jensen_shannon_divergence(baseline_probs, current_probs)
    return {
        "js_divergence": round(js, 4),
        "drift_score": round(js, 4),
        "drift_type": _classify_drift(js),
        "criteria_count": len(all_criteria),
        "active_criteria_changes": _count_active_changes(baseline_frequencies, current_frequencies),
    }


def detect_drift(
    baseline: Dict,
    current: Dict,
) -> Dict:
    """Run all drift detectors between baseline and current calibration runs.

    Args:
        baseline: Calibration report dict (from calibration_runner)
        current: Calibration report dict (from calibration_runner)

    Returns:
        Dict with per-metric drift scores + overall composite.
    """
    decision_drift = detect_decision_drift(
        baseline.get("decision_counts", {}),
        current.get("decision_counts", {}),
    )
    conf_drift = detect_confidence_drift(
        baseline.get("confidences", []),
        current.get("confidences", []),
    )
    criteria_drift = detect_criteria_drift(
        baseline.get("criteria_frequencies", {}),
        current.get("criteria_frequencies", {}),
    )
    scores = [decision_drift["drift_score"], conf_drift["drift_score"], criteria_drift["drift_score"]]
    composite = sum(scores) / len(scores) if scores else 0.0
    return {
        "composite_drift_score": round(composite, 4),
        "composite_drift_type": _classify_drift(composite),
        "decision_drift": decision_drift,
        "confidence_drift": conf_drift,
        "criteria_drift": criteria_drift,
    }


def _classify_drift(score: float) -> str:
    if score < 0.05:
        return "stable"
    elif score < 0.15:
        return "mild drift"
    return "structural drift"


def _count_active_changes(baseline: Dict[str, float], current: Dict[str, float]) -> Dict:
    activated = [k for k in current if current.get(k, 0) > 0 and baseline.get(k, 0) == 0]
    deactivated = [k for k in baseline if baseline.get(k, 0) > 0 and current.get(k, 0) == 0]
    return {
        "newly_active_count": len(activated),
        "newly_active": activated[:10],
        "deactivated_count": len(deactivated),
        "deactivated": deactivated[:10],
    }


# ---------------------------------------------------------------------------
# IncrementalDriftTracker — Part 4: Real-time drift stream
# ---------------------------------------------------------------------------

class IncrementalDriftTracker:
    """Rolling-window drift tracker for live monitoring.

    Maintains a fixed-size window of recent observations and computes
    drift relative to an accumulated historical distribution.

    Thread-safe for concurrent add_observation calls.
    """

    DECISION_BINS = ("INCLUDE", "EXCLUDE", "SKIP", "UNCERTAIN", "INSUFFICIENT_EVIDENCE", "UNAVAILABLE")
    CONFIDENCE_BINS = 10
    CRITERIA_BINS = ("triggered", "not_triggered")
    DRIFT_STABLE = 0.05
    DRIFT_MILD = 0.15

    def __init__(self, window_size: int = 100):
        self._window_size = window_size
        self._lock = threading.Lock()

        # Rolling window (ring buffer)
        self._window: List[Dict] = []

        # Cumulative histograms (all-time)
        self._decision_hist: Dict[str, int] = {d: 0 for d in self.DECISION_BINS}
        self._confidence_hist: List[int] = [0] * self.CONFIDENCE_BINS
        self._criteria_hist: Dict[str, int] = {"triggered": 0, "not_triggered": 0}
        self._total_observations: int = 0

    def add_observation(self, decision: str, confidence: float, triggered_criteria: Optional[list] = None):
        """Record a new observation and maintain rolling window."""
        with self._lock:
            histogram_entry = {
                "decision": decision,
                "confidence": confidence,
                "triggered_count": len(triggered_criteria or []),
            }

            # Maintain rolling window
            self._window.append(histogram_entry)
            if len(self._window) > self._window_size:
                self._window.pop(0)

            # Update cumulative histograms
            decision = decision.upper() if decision else "UNAVAILABLE"
            if decision in self._decision_hist:
                self._decision_hist[decision] += 1
            else:
                self._decision_hist["UNAVAILABLE"] += 1

            bin_idx = min(int(confidence * self.CONFIDENCE_BINS), self.CONFIDENCE_BINS - 1) if confidence > 0 else 0
            self._confidence_hist[bin_idx] += 1

            if triggered_criteria:
                self._criteria_hist["triggered"] += 1
            else:
                self._criteria_hist["not_triggered"] += 1

            self._total_observations += 1

    def compute_drift(self) -> Dict:
        """Compute drift score from rolling window vs cumulative distribution.

        Returns:
            Dict with per-component JS divergences, composite score, and drift type.
        """
        with self._lock:
            if len(self._window) < 2 or self._total_observations < 2:
                return {
                    "composite_drift_score": 0.0,
                    "composite_drift_type": "stable",
                    "window_size": len(self._window),
                    "total_observations": self._total_observations,
                }

            # Build rolling window distribution from window items
            win_decisions: Dict[str, int] = {d: 0 for d in self.DECISION_BINS}
            win_confidence: List[int] = [0] * self.CONFIDENCE_BINS
            win_criteria: Dict[str, int] = {"triggered": 0, "not_triggered": 0}

            for entry in self._window:
                d = entry["decision"].upper() if entry["decision"] else "UNAVAILABLE"
                if d in win_decisions:
                    win_decisions[d] += 1
                else:
                    win_decisions["UNAVAILABLE"] += 1

                c = entry.get("confidence", 0.0)
                bin_idx = min(int(c * self.CONFIDENCE_BINS), self.CONFIDENCE_BINS - 1) if c > 0 else 0
                win_confidence[bin_idx] += 1

                if entry.get("triggered_count", 0) > 0:
                    win_criteria["triggered"] += 1
                else:
                    win_criteria["not_triggered"] += 1

            # Compute JS divergences
            decision_js = self._js_from_histograms(win_decisions, self._decision_hist)
            confidence_js = self._js_from_counts(win_confidence, self._confidence_hist)
            criteria_js = self._js_from_histograms(win_criteria, self._criteria_hist)

            scores = [decision_js, confidence_js, criteria_js]
            composite = sum(scores) / len(scores) if scores else 0.0

            return {
                "composite_drift_score": round(composite, 4),
                "composite_drift_type": _classify_drift(composite),
                "decision_drift_score": round(decision_js, 4),
                "confidence_drift_score": round(confidence_js, 4),
                "criteria_drift_score": round(criteria_js, 4),
                "window_size": len(self._window),
                "total_observations": self._total_observations,
            }

    def compute_composite_drift(self) -> Dict:
        """Alias for compute_drift. Returns the same structure."""
        return self.compute_drift()

    def get_drift_event(self) -> Dict:
        """Return a telemetry-ready drift event dict."""
        drift = self.compute_drift()
        score = drift["composite_drift_score"]
        is_drift = score >= self.DRIFT_STABLE
        return {
            "drift_detected": is_drift,
            "composite_drift_score": score,
            "drift_type": drift["composite_drift_type"],
            "window_size": drift["window_size"],
            "total_observations": drift["total_observations"],
        }

    def _js_from_histograms(self, a: Dict[str, int], b: Dict[str, int]) -> float:
        """Compute JS divergence between two histogram dicts with aligned keys."""
        all_keys = sorted(set(a.keys()) | set(b.keys()))
        pa = [a.get(k, 0) / max(sum(a.values()), 1) for k in all_keys]
        pb = [b.get(k, 0) / max(sum(b.values()), 1) for k in all_keys]
        return jensen_shannon_divergence(pa, pb)

    def _js_from_counts(self, a: List[int], b: List[int]) -> float:
        """Compute JS divergence between two count arrays."""
        pa = [v / max(sum(a), 1) for v in a]
        pb = [v / max(sum(b), 1) for v in b]
        return jensen_shannon_divergence(pa, pb)
