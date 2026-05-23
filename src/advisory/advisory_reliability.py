"""
Advisory Reliability Estimation for APOLLO.

Deterministic, inspectable reliability scoring for LLM-generated advisories.

reliability_score ∈ [0, 1] computed from:
  - confidence calibration (high confidence + wrong decision = penalty)
  - grounding strength (evidence quality)
  - hallucination risk
  - criterion evaluation consistency
  - historical override rate
  - uncertainty markers (UNCERTAIN, INSUFFICIENT_EVIDENCE)

All functions are PURE and DETERMINISTIC. No ML, no external dependencies.
"""
import json
import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import Counter

from .advisory_models import AdvisoryResult

# ---------------------------------------------------------------------------
# Default weights
# ---------------------------------------------------------------------------

DEFAULT_RELIABILITY_WEIGHTS = {
    "confidence": 0.20,
    "grounding": 0.20,
    "hallucination": 0.20,
    "criterion": 0.15,
    "historical": 0.15,
    "uncertainty_penalty": 0.10,
}

ESCALATION_THRESHOLD_DEFAULT = 0.50
CRITICAL_ESCALATION_THRESHOLD_DEFAULT = 0.30

# ---------------------------------------------------------------------------
# Per-advisory reliability score
# ---------------------------------------------------------------------------


def compute_advisory_reliability(
    advisory: AdvisoryResult,
    override_rate: float = 0.0,
    weights: Optional[Dict[str, float]] = None,
) -> float:
    """Compute reliability score for a single advisory.

    Args:
        advisory: The AdvisoryResult to evaluate.
        override_rate: Historical human override rate for this stage (0-1).
        weights: Optional weight overrides.

    Returns:
        reliability_score ∈ [0, 1]. Higher = more reliable.
    """
    w = dict(weights or DEFAULT_RELIABILITY_WEIGHTS)
    score = 0.0

    # 1. Confidence reliability: penalize overconfidence on uncertain decisions
    conf_rel = _confidence_reliability(advisory)
    score += w.get("confidence", 0.20) * conf_rel

    # 2. Grounding reliability: evidence quality
    grounding_rel = _grounding_reliability(advisory)
    score += w.get("grounding", 0.20) * grounding_rel

    # 3. Hallucination reliability: inverse of hallucination risk
    hallucination_rel = _hallucination_reliability(advisory)
    score += w.get("hallucination", 0.20) * hallucination_rel

    # 4. Criterion reliability: consistency of criterion evaluations
    criterion_rel = _criterion_reliability(advisory)
    score += w.get("criterion", 0.15) * criterion_rel

    # 5. Historical reliability: inverse of override rate
    historical_rel = max(0.0, 1.0 - override_rate)
    score += w.get("historical", 0.15) * historical_rel

    # 6. Uncertainty penalty: flat penalty for uncertain decision types
    uncertainty_penalty = _uncertainty_penalty(advisory)
    score -= w.get("uncertainty_penalty", 0.10) * uncertainty_penalty

    return max(0.0, min(1.0, round(score, 4)))


def compute_reliability_components(
    advisory: AdvisoryResult,
    override_rate: float = 0.0,
) -> Dict[str, float]:
    """Return per-component breakdown for explainability."""
    return {
        "reliability_score": compute_advisory_reliability(advisory, override_rate),
        "confidence_reliability": _confidence_reliability(advisory),
        "grounding_reliability": _grounding_reliability(advisory),
        "hallucination_reliability": _hallucination_reliability(advisory),
        "criterion_reliability": _criterion_reliability(advisory),
        "historical_reliability": max(0.0, 1.0 - override_rate),
        "uncertainty_penalty": _uncertainty_penalty(advisory),
    }


def _decision_value(advisory: AdvisoryResult) -> str:
    """Extract decision string, handling str enums."""
    d = getattr(advisory, "decision", None)
    if d is None:
        return ""
    if isinstance(d, str):
        return d
    return str(d.value) if hasattr(d, "value") else str(d)


def _risk_value(advisory: AdvisoryResult) -> str:
    """Extract risk classification string, handling enums."""
    r = getattr(advisory, "risk_classification", None)
    if r is None:
        return ""
    if isinstance(r, str):
        return r
    return str(r.value) if hasattr(r, "value") else str(r)


def _confidence_reliability(advisory: AdvisoryResult) -> float:
    """Evaluate confidence calibration.

    Overconfidence (high confidence + wrong/uncertain decision) is penalized.
    Underconfidence (low confidence + clear decision) is mildly penalized.
    """
    decision = _decision_value(advisory)
    confidence = getattr(advisory, "confidence", 0.0) or 0.0
    parser_conf = getattr(advisory, "parser_confidence", 0.0) or 0.0

    score = confidence

    # Overconfidence on uncertain decisions
    if decision in ("UNCERTAIN", "INSUFFICIENT_EVIDENCE", "CANNOT_DETERMINE"):
        if confidence > 0.7:
            score -= 0.5
        elif confidence > 0.5:
            score -= 0.2
    # Overconfidence on INCLUDE/EXCLUDE without grounding
    elif decision in ("INCLUDE", "EXCLUDE"):
        grounding = getattr(advisory, "grounding_strength", 0.0) or 0.0
        if confidence > 0.9 and grounding < 0.3:
            score -= 0.3
    # Underconfidence on clear decisions
    if decision in ("INCLUDE", "EXCLUDE") and confidence < 0.2:
        score -= 0.1

    # Parser confidence acts as a ceiling on reliability
    if parser_conf > 0.0 and parser_conf < confidence:
        score = score * (1.0 - (confidence - parser_conf))

    return max(0.0, min(1.0, score))


def _grounding_reliability(advisory: AdvisoryResult) -> float:
    """Evaluate evidence/grounding quality."""
    grounding = getattr(advisory, "grounding_strength", 0.0) or 0.0

    # Evidence span multiplier: short evidence = less reliable
    evidence_span = getattr(advisory, "evidence_span", 0) or 0
    span_factor = min(1.0, evidence_span / 3.0) if evidence_span > 0 else 0.5

    # Unsupported claims detected = reliability cap
    unsupported = getattr(advisory, "unsupported_claims_detected", False)
    if unsupported:
        grounding = min(grounding, 0.5)

    # Grounding evidence list
    evidence_list = getattr(advisory, "grounding_evidence", None) or []
    evidence_count_factor = min(1.0, len(evidence_list) / 3.0) if evidence_list else 0.0

    combined = grounding * (0.5 + 0.3 * span_factor + 0.2 * evidence_count_factor)
    return max(0.0, min(1.0, combined))


def _hallucination_reliability(advisory: AdvisoryResult) -> float:
    """Compute reliability from hallucination risk (inverse relationship)."""
    risk = getattr(advisory, "hallucination_risk_score", 0.0) or 0.0
    return max(0.0, 1.0 - risk)


def _criterion_reliability(advisory: AdvisoryResult) -> float:
    """Evaluate consistency and coverage of criterion evaluations.

    Penalizes:
      - Low-confidence criterion evaluations
      - All criteria triggered (degenerate)
      - No criteria triggered (degenerate)
      - Conflicting evaluations (same criteria both satisfied and not)
    """
    evaluations = getattr(advisory, "criterion_evaluations", None) or []
    if not evaluations:
        return 0.5

    scores = []
    for ev in evaluations:
        ev_conf = getattr(ev, "confidence", 0.5) or 0.5
        scores.append(ev_conf)

    mean_conf = sum(scores) / len(scores) if scores else 0.5

    # Degenerate detection
    triggered = getattr(advisory, "triggered_criteria", None) or []
    non_triggered = getattr(advisory, "non_triggered_criteria", None) or []
    all_criteria = len(triggered) + len(non_triggered)
    if all_criteria > 0:
        trigger_rate = len(triggered) / all_criteria
        if trigger_rate >= 0.95 or trigger_rate <= 0.05:
            mean_conf *= 0.7

    return max(0.0, min(1.0, mean_conf))


def _uncertainty_penalty(advisory: AdvisoryResult) -> float:
    """Compute penalty for uncertainty signals.

    Returns 0.0 (no penalty) to 1.0 (max penalty).
    """
    decision = _decision_value(advisory)
    penalty = 0.0

    if decision in ("UNCERTAIN",):
        penalty = 0.8
    elif decision in ("INSUFFICIENT_EVIDENCE", "CANNOT_DETERMINE"):
        penalty = 0.6
    elif decision in ("SKIP",):
        penalty = 0.3

    risk = _risk_value(advisory)
    if risk == "CRITICAL_REVIEW":
        penalty = max(penalty, 0.7)
    elif risk == "HIGH_RISK":
        penalty = max(penalty, 0.4)

    hallucination = getattr(advisory, "hallucination_risk_score", 0.0) or 0.0
    if hallucination > 0.7:
        penalty = max(penalty, 0.5)

    return min(1.0, penalty)


# ---------------------------------------------------------------------------
# Batch reliability
# ---------------------------------------------------------------------------


def compute_batch_reliability(
    advisories: List[AdvisoryResult],
    override_rate: float = 0.0,
) -> Dict:
    """Compute aggregate reliability stats for a batch of advisories."""
    if not advisories:
        return {
            "mean_reliability": 0.0,
            "min_reliability": 0.0,
            "max_reliability": 0.0,
            "reliable_count": 0,
            "total_count": 0,
            "reliability_distribution": {},
        }

    scores = [compute_advisory_reliability(a, override_rate) for a in advisories]
    threshold = 0.5
    reliable = sum(1 for s in scores if s >= threshold)

    buckets = {"0.0-0.2": 0, "0.2-0.4": 0, "0.4-0.6": 0, "0.6-0.8": 0, "0.8-1.0": 0}
    for s in scores:
        if s < 0.2:
            buckets["0.0-0.2"] += 1
        elif s < 0.4:
            buckets["0.2-0.4"] += 1
        elif s < 0.6:
            buckets["0.4-0.6"] += 1
        elif s < 0.8:
            buckets["0.6-0.8"] += 1
        else:
            buckets["0.8-1.0"] += 1

    return {
        "mean_reliability": round(sum(scores) / len(scores), 4),
        "min_reliability": round(min(scores), 4),
        "max_reliability": round(max(scores), 4),
        "reliable_count": reliable,
        "total_count": len(scores),
        "reliable_rate": round(reliable / len(scores), 4),
        "reliability_distribution": buckets,
    }


# ---------------------------------------------------------------------------
# Escalation rules
# ---------------------------------------------------------------------------


def check_escalation(
    advisory: AdvisoryResult,
    reliability_score: float,
    override_rate: float = 0.0,
    reliability_threshold: float = ESCALATION_THRESHOLD_DEFAULT,
    critical_threshold: float = CRITICAL_ESCALATION_THRESHOLD_DEFAULT,
) -> Dict:
    """Evaluate escalation rules for a single advisory.

    Args:
        advisory: The advisory to evaluate.
        reliability_score: Pre-computed reliability score.
        override_rate: Historical override rate for this stage.
        reliability_threshold: Threshold for standard escalation.
        critical_threshold: Threshold for critical escalation.

    Returns:
        Dict with:
          - escalate: bool
          - critical: bool
          - reasons: List[str]
          - reliability_score: float
    """
    reasons = []

    # Rule 1: Low reliability score
    if reliability_score < critical_threshold:
        reasons.append(f"reliability_critical: score={reliability_score:.2f}")
    elif reliability_score < reliability_threshold:
        reasons.append(f"reliability_low: score={reliability_score:.2f}")

    # Rule 2: Uncertain decision
    decision = _decision_value(advisory)
    if decision in ("UNCERTAIN",):
        reasons.append("decision_uncertain")
    elif decision in ("INSUFFICIENT_EVIDENCE", "CANNOT_DETERMINE"):
        reasons.append("decision_insufficient_evidence")

    # Rule 3: Weak grounding
    grounding = getattr(advisory, "grounding_strength", 0.0) or 0.0
    if grounding < 0.3:
        reasons.append(f"weak_grounding: strength={grounding:.2f}")

    # Rule 4: High hallucination risk
    hallucination = getattr(advisory, "hallucination_risk_score", 0.0) or 0.0
    if hallucination > 0.7:
        reasons.append(f"high_hallucination_risk: score={hallucination:.2f}")
    elif hallucination > 0.5:
        reasons.append(f"elevated_hallucination_risk: score={hallucination:.2f}")

    # Rule 5: Conflicting criterion evaluations
    evaluations = getattr(advisory, "criterion_evaluations", None) or []
    if _has_conflicting_evaluations(evaluations):
        reasons.append("conflicting_criteria")

    # Rule 6: Insufficient evidence span
    evidence_span = getattr(advisory, "evidence_span", 0) or 0
    if evidence_span == 0:
        reasons.append("no_evidence_span")
    elif evidence_span == 1:
        reasons.append("minimal_evidence_span")

    # Rule 7: Historical override rate
    if override_rate > 0.3:
        reasons.append(f"high_override_rate: rate={override_rate:.2f}")

    # Rule 8: Unsupported claims detected
    unsupported = getattr(advisory, "unsupported_claims_detected", False)
    if unsupported:
        reasons.append("unsupported_claims_detected")

    # Rule 9: Risk classification
    risk = str(getattr(advisory, "risk_classification", "") or "")
    if risk == "CRITICAL_REVIEW":
        reasons.append("critical_risk_classification")
    elif risk == "HIGH_RISK":
        reasons.append("high_risk_classification")

    is_critical = any(
        r.startswith("reliability_critical")
        or r == "decision_uncertain"
        or r.startswith("high_hallucination_risk")
        or r == "critical_risk_classification"
        or r == "unsupported_claims_detected"
        for r in reasons
    )
    escalate = len(reasons) > 0

    return {
        "escalate": escalate,
        "critical": is_critical,
        "reasons": reasons,
        "reliability_score": reliability_score,
    }


def _has_conflicting_evaluations(evaluations: List) -> bool:
    """Check if the same criterion appears with conflicting satisfied values."""
    if not evaluations:
        return False
    seen: Dict[str, bool] = {}
    for ev in evaluations:
        cid = getattr(ev, "criterion_id", None) or ""
        sat = getattr(ev, "satisfied", False)
        if cid in seen and seen[cid] != sat:
            return True
        seen[cid] = sat
    return False


# ---------------------------------------------------------------------------
# Adaptive threshold calibration
# ---------------------------------------------------------------------------


class ThresholdCalibrator:
    """Rolling-window threshold calibration from override history.

    Tracks human override events to adapt escalation thresholds per stage.
    Lightweight: simple counters and rolling averages. No ML.

    Thresholds are tightened when override rate is high (system is wrong often).
    Thresholds are loosened when override rate is low (system is reliable).
    """

    def __init__(self, window_size: int = 100):
        self._window_size = window_size
        self._lock = threading.Lock()
        self._ec: List[bool] = []  # True = override occurred
        self._ic: List[bool] = []

    def record_override(self, stage: str, was_overridden: bool):
        """Record whether a human override occurred for an advisory."""
        queue = self._ec if stage == "ec" else self._ic
        with self._lock:
            queue.append(was_overridden)
            if len(queue) > self._window_size:
                queue.pop(0)

    def get_override_rate(self, stage: str) -> float:
        """Get current override rate for a stage."""
        queue = self._ec if stage == "ec" else self._ic
        with self._lock:
            if not queue:
                return 0.0
            return sum(queue) / len(queue)

    def get_threshold(self, stage: str, base_threshold: float = ESCALATION_THRESHOLD_DEFAULT) -> float:
        """Compute adaptive threshold.

        High override rate → tighten threshold (require higher reliability).
        Low override rate → loosen threshold (accept lower reliability).
        """
        override_rate = self.get_override_rate(stage)
        # Adjust threshold: ±0.2 based on override rate deviation from 0.15
        adjustment = (override_rate - 0.15) * 1.5
        new_threshold = base_threshold + adjustment
        return max(0.1, min(0.9, round(new_threshold, 3)))

    def get_state(self, stage: str) -> Dict:
        """Get calibration state for dashboard display."""
        with self._lock:
            queue = self._ec if stage == "ec" else self._ic
            overrides = sum(queue)
            total = len(queue)
        return {
            "stage": stage,
            "total_advisories": total,
            "override_count": overrides,
            "override_rate": round(overrides / total, 4) if total > 0 else 0.0,
            "window_size": self._window_size,
            "adaptive_threshold": self.get_threshold(stage),
        }


# ---------------------------------------------------------------------------
# Lightweight operational metrics
# ---------------------------------------------------------------------------


class OperationalMetrics:
    """Minimal runtime metrics for dashboard display.

    Tracks only:
      - throughput (advisories processed per second)
      - queue depth
      - average latency
      - escalation rate
      - estimated precision
      - human agreement rate
    """

    def __init__(self, window_size: int = 100):
        self._window_size = window_size
        self._lock = threading.Lock()
        self._throughput: List[float] = []
        self._latencies: List[float] = []
        self._escalations: List[bool] = []
        self._agreements: List[bool] = []
        self._queue_depths: List[int] = []
        self._total_processed: int = 0

    def record_processed(self, latency_ms: float):
        with self._lock:
            self._latencies.append(latency_ms)
            if len(self._latencies) > self._window_size:
                self._latencies.pop(0)
            self._total_processed += 1
            self._throughput.append(time.time())
            if len(self._throughput) > self._window_size:
                self._throughput.pop(0)

    def record_escalation(self, escalated: bool):
        with self._lock:
            self._escalations.append(escalated)
            if len(self._escalations) > self._window_size:
                self._escalations.pop(0)

    def record_agreement(self, agreed: bool):
        with self._lock:
            self._agreements.append(agreed)
            if len(self._agreements) > self._window_size:
                self._agreements.pop(0)

    def record_queue_depth(self, depth: int):
        with self._lock:
            self._queue_depths.append(depth)
            if len(self._queue_depths) > self._window_size:
                self._queue_depths.pop(0)

    def get_throughput(self) -> float:
        with self._lock:
            if len(self._throughput) < 2:
                return 0.0
            window = self._throughput[-min(len(self._throughput), 50):]
            if len(window) < 2:
                return 0.0
            elapsed = window[-1] - window[0]
            return round((len(window) - 1) / elapsed, 2) if elapsed > 0 else 0.0

    def get_avg_latency_ms(self) -> float:
        with self._lock:
            if not self._latencies:
                return 0.0
            return round(sum(self._latencies) / len(self._latencies), 1)

    def get_escalation_rate(self) -> float:
        with self._lock:
            if not self._escalations:
                return 0.0
            return round(sum(self._escalations) / len(self._escalations), 4)

    def get_agreement_rate(self) -> float:
        with self._lock:
            if not self._agreements:
                return 0.0
            return round(sum(self._agreements) / len(self._agreements), 4)

    def get_avg_queue_depth(self) -> float:
        with self._lock:
            if not self._queue_depths:
                return 0.0
            return round(sum(self._queue_depths) / len(self._queue_depths), 1)

    def get_estimated_precision(self) -> float:
        agreement = self.get_agreement_rate()
        if agreement == 0.0:
            return 0.0
        escalation = self.get_escalation_rate()
        return round(max(0.0, agreement * (1.0 - escalation)), 4)

    def get_stats(self) -> Dict:
        return {
            "throughput_items_per_sec": self.get_throughput(),
            "queue_depth_avg": self.get_avg_queue_depth(),
            "latency_avg_ms": self.get_avg_latency_ms(),
            "escalation_rate": self.get_escalation_rate(),
            "estimated_precision": self.get_estimated_precision(),
            "human_agreement_rate": self.get_agreement_rate(),
            "total_processed": self._total_processed,
        }

    def reset(self):
        with self._lock:
            self._throughput.clear()
            self._latencies.clear()
            self._escalations.clear()
            self._agreements.clear()
            self._queue_depths.clear()
            self._total_processed = 0

import time


# ---------------------------------------------------------------------------
# Module-level singletons
# ---------------------------------------------------------------------------

_global_calibrator: Optional[ThresholdCalibrator] = None
_global_metrics: Optional[OperationalMetrics] = None
_calibrator_lock = threading.Lock()
_metrics_lock = threading.Lock()


def get_threshold_calibrator() -> ThresholdCalibrator:
    global _global_calibrator
    if _global_calibrator is None:
        with _calibrator_lock:
            if _global_calibrator is None:
                _global_calibrator = ThresholdCalibrator()
    return _global_calibrator


def get_operational_metrics() -> OperationalMetrics:
    global _global_metrics
    if _global_metrics is None:
        with _metrics_lock:
            if _global_metrics is None:
                _global_metrics = OperationalMetrics()
    return _global_metrics


def reset_reliability_globals():
    global _global_calibrator, _global_metrics
    with _calibrator_lock:
        _global_calibrator = None
    with _metrics_lock:
        _global_metrics = None
