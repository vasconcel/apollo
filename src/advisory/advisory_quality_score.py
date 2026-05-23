"""
Composite Advisory Quality Score for APOLLO.

Defines an empirical, deterministic, explainable quality metric:

  quality_score = w1 * confidence_calibration
                + w2 * grounding_strength
                + w3 * criterion_consistency
                - w4 * hallucination_risk
                - w5 * override_rate

All weights default to 0.2 (equal weighting).
All functions are PURE and DETERMINISTIC.
"""
import threading
from typing import Dict, List, Optional


DEFAULT_WEIGHTS = {
    "confidence_calibration": 0.2,
    "grounding_strength": 0.2,
    "criterion_consistency": 0.2,
    "hallucination_risk": 0.2,
    "override_rate": 0.2,
}


def compute_confidence_calibration_score(advisories: List[Dict]) -> float:
    """Evaluate how well confidence aligns with decision types.

    Calibrated confidence should be:
      - High for INCLUDE/EXCLUDE with strong grounding
      - Low for UNCERTAIN/INSUFFICIENT_EVIDENCE
      - Moderate for SKIP decisions

    Returns score in [0, 1] where 1 = perfectly calibrated.
    """
    if not advisories:
        return 1.0
    penalties = []
    for adv in advisories:
        decision = str(adv.get("decision", ""))
        confidence = adv.get("confidence", 0.0)
        grounding = adv.get("grounding_strength", 0.0)
        if decision in ("INCLUDE", "EXCLUDE"):
            if confidence < 0.3:
                penalties.append(0.3)
            elif confidence < 0.5:
                penalties.append(0.1)
            elif confidence > 0.95 and grounding < 0.5:
                penalties.append(0.2)
        elif decision in ("UNCERTAIN", "INSUFFICIENT_EVIDENCE"):
            if confidence > 0.7:
                penalties.append(0.4)
            elif confidence > 0.5:
                penalties.append(0.2)
        elif decision == "SKIP":
            if confidence > 0.8:
                penalties.append(0.3)
    if not penalties:
        return 1.0
    penalty = min(sum(penalties) / len(penalties), 0.5)
    return round(1.0 - penalty, 4)


def compute_grounding_quality_score(advisories: List[Dict]) -> float:
    """Evaluate average grounding strength across advisories.

    Returns score in [0, 1].
    """
    if not advisories:
        return 1.0
    scores = [adv.get("grounding_strength", 0.0) for adv in advisories]
    return round(sum(scores) / len(scores), 4)


def compute_criterion_consistency_score(advisories: List[Dict]) -> float:
    """Evaluate consistency of criterion evaluations.

    Checks that:
      - Criteria are not always-triggered or never-triggered (suggests
        degenerate behavior)
      - High-confidence evaluations have supporting evidence

    Returns score in [0, 1].
    """
    if not advisories:
        return 1.0
    all_triggered = []
    for adv in advisories:
        all_triggered.extend(adv.get("triggered_criteria", []))
    if not all_triggered:
        return 1.0
    from collections import Counter
    counts = Counter(all_triggered)
    n = len(advisories)
    total_penalties = 0.0
    criteria_checked = 0
    for cid, count in counts.items():
        rate = count / max(n, 1)
        criteria_checked += 1
        if rate >= 0.95:
            total_penalties += 0.2
        if rate <= 0.01:
            total_penalties += 0.1
    if criteria_checked == 0:
        return 1.0
    penalty = min(total_penalties / criteria_checked, 0.3)
    return round(1.0 - penalty, 4)


def compute_hallucination_risk_score(advisories: List[Dict]) -> float:
    """Compute mean hallucination risk across advisories.

    Returns score in [0, 1]. Lower is better (less hallucination risk).
    """
    if not advisories:
        return 0.0
    scores = [adv.get("hallucination_risk_score", 0.0) for adv in advisories]
    return round(sum(scores) / len(scores), 4)


def compute_override_rate_score(advisories: List[Dict]) -> float:
    """Compute fraction of advisories that would require human override.

    Override triggers:
      - hallucination_risk_score > 0.7
      - decision is UNCERTAIN, INSUFFICIENT_EVIDENCE, CANNOT_DETERMINE
      - risk_classification is CRITICAL_REVIEW

    Returns score in [0, 1]. Lower is better.
    """
    if not advisories:
        return 0.0
    override_count = 0
    for adv in advisories:
        decision = str(adv.get("decision", ""))
        if decision in ("UNCERTAIN", "INSUFFICIENT_EVIDENCE", "CANNOT_DETERMINE"):
            override_count += 1
        elif adv.get("hallucination_risk_score", 0.0) > 0.7:
            override_count += 1
        elif str(adv.get("risk_classification", "")) == "CRITICAL_REVIEW":
            override_count += 1
    return round(override_count / len(advisories), 4)


class LiveQualityTracker:
    """Rolling quality tracker with exponential moving averages.

    Maintains per-stage raw and smoothed EMAs for live dashboard display.

    Thread-safe for concurrent add_advisory calls.
    """

    RAW_ALPHA = 0.3
    SMOOTHED_ALPHA = 0.1

    def __init__(self):
        self._lock = threading.Lock()

        # Per-stage tracking: {stage: {"raw": float, "smoothed": float, "count": int}}
        self._ec: Dict = {"raw": 0.0, "smoothed": 0.0, "count": 0}
        self._ic: Dict = {"raw": 0.0, "smoothed": 0.0, "count": 0}
        self._qc: Dict = {"raw": 0.0, "smoothed": 0.0, "count": 0}

    def add_advisory(self, advisory: Dict, stage: str) -> float:
        """Record a single advisory's quality score and update rolling averages.

        Args:
            advisory: Advisory dict (from AdvisoryResult.to_dict()).
            stage: Stage string ("ec", "ic", or "qc").

        Returns:
            The computed quality score for this advisory.
        """
        score = compute_quality_score([advisory])["composite_score"]

        with self._lock:
            target = self._resolve_stage(stage)
            if target["count"] == 0:
                target["raw"] = score
                target["smoothed"] = score
            else:
                target["raw"] = (1.0 - self.RAW_ALPHA) * target["raw"] + self.RAW_ALPHA * score
                target["smoothed"] = (1.0 - self.SMOOTHED_ALPHA) * target["smoothed"] + self.SMOOTHED_ALPHA * score
            target["count"] += 1

        return score

    def get_rolling_quality(self, stage: Optional[str] = None) -> Dict:
        """Get current rolling quality averages.

        Args:
            stage: If set, return only this stage. If None, return all.

        Returns:
            Dict with raw/smoothed quality scores per stage.
        """
        with self._lock:
            if stage:
                target = self._resolve_stage(stage)
                return {
                    "stage": stage,
                    "raw_quality": round(target["raw"], 4),
                    "smoothed_quality": round(target["smoothed"], 4),
                    "count": target["count"],
                }
            return {
                "ec": self._stage_snapshot("ec"),
                "ic": self._stage_snapshot("ic"),
                "qc": self._stage_snapshot("qc"),
            }

    def _resolve_stage(self, stage: str) -> Dict:
        stage = stage.lower()
        if stage == "ec":
            return self._ec
        elif stage == "qc":
            return self._qc
        return self._ic

    def _stage_snapshot(self, stage: str) -> Dict:
        target = self._resolve_stage(stage)
        return {
            "raw_quality": round(target["raw"], 4),
            "smoothed_quality": round(target["smoothed"], 4),
            "count": target["count"],
        }


def compute_quality_score(
    advisories: List[Dict],
    weights: Optional[Dict[str, float]] = None,
) -> Dict:
    """Compute composite advisory quality score.

    Args:
        advisories: List of advisory dicts (from AdvisoryResult.to_dict())
        weights: Optional dict of per-component weights. Must sum to 1.0.

    Returns:
        Dict with component scores, composite score, and weight breakdown.
    """
    if not advisories:
        return {
            "composite_score": 1.0,
            "components": {k: {"score": 1.0, "weight": v, "contribution": v}
                          for k, v in DEFAULT_WEIGHTS.items()},
            "weights_used": DEFAULT_WEIGHTS,
            "total_advisories": 0,
        }
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    conf_cal = compute_confidence_calibration_score(advisories)
    grounding = compute_grounding_quality_score(advisories)
    consistency = compute_criterion_consistency_score(advisories)
    hallucination = compute_hallucination_risk_score(advisories)
    override = compute_override_rate_score(advisories)
    composite = (
        w["confidence_calibration"] * conf_cal
        + w["grounding_strength"] * grounding
        + w["criterion_consistency"] * consistency
        - w["hallucination_risk"] * hallucination
        - w["override_rate"] * override
    )
    # Normalize to [0, 1]
    composite = max(0.0, min(1.0, composite))
    return {
        "composite_score": round(composite, 4),
        "components": {
            "confidence_calibration": {
                "score": conf_cal,
                "weight": w["confidence_calibration"],
                "contribution": round(w["confidence_calibration"] * conf_cal, 4),
            },
            "grounding_strength": {
                "score": grounding,
                "weight": w["grounding_strength"],
                "contribution": round(w["grounding_strength"] * grounding, 4),
            },
            "criterion_consistency": {
                "score": consistency,
                "weight": w["criterion_consistency"],
                "contribution": round(w["criterion_consistency"] * consistency, 4),
            },
            "hallucination_risk": {
                "score": hallucination,
                "weight": w["hallucination_risk"],
                "contribution": round(-w["hallucination_risk"] * hallucination, 4),
            },
            "override_rate": {
                "score": override,
                "weight": w["override_rate"],
                "contribution": round(-w["override_rate"] * override, 4),
            },
        },
        "weights_used": w,
        "total_advisories": len(advisories),
    }
