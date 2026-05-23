"""
Protocol Diagnostics Engine for APOLLO.

Pure deterministic analysis layer. No LLM calls, no advisory mutations,
no protocol rewriting. Derives weakness signals strictly from calibration
telemetry and cached advisory decisions.

SIGNALS:
  1. Never-triggered criteria
  2. Always-triggered criteria
  3. High ambiguity criteria
  4. High quarantine criteria
  5. Low grounding criteria
  6. Confidence instability
  7. EC/IC semantic overlap
  8. Excessive rejection/acceptance skew
  9. Criteria redundancy candidates
  10. Criteria requiring implicit inference
"""
import statistics
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field

from .advisory_models import AdvisoryConfig, AdvisoryDecision


@dataclass
class DiagnosticSignal:
    """A single diagnostic signal from protocol analysis."""
    signal_type: str
    criterion_id: str
    severity: str  # "low", "medium", "high"
    description: str
    evidence: Dict
    recommendation: str


def _parse_advisories(advisories: List[Dict], stage: str) -> List[Dict]:
    """Normalize advisories for analysis (defensive)."""
    parsed = []
    for a in advisories:
        parsed.append({
            "cache_key": a.get("cache_key", ""),
            "decision": a.get("decision", "UNKNOWN"),
            "confidence": float(a.get("confidence", 0.0)),
            "triggered_criteria": list(a.get("triggered_criteria", [])),
            "criterion_evaluations": list(a.get("criterion_evaluations", [])),
            "hallucination_risk_score": float(a.get("hallucination_risk_score", 0.0)),
            "grounding_strength": float(a.get("grounding_strength", 0.0)),
            "evidence_span": int(a.get("evidence_span", 0)),
            "stage": stage,
        })
    return parsed


def _severity_from_rate(rate: float, high: float, medium: float = 0.0) -> str:
    if rate >= high:
        return "high"
    if rate >= medium:
        return "medium"
    return "low"


def signal_never_triggered(
    all_criteria: List[str],
    triggered_counts: Dict[str, int],
    total: int,
    config: AdvisoryConfig,
    stage: str,
) -> List[DiagnosticSignal]:
    """Signal: criteria with 0 activations across the sample."""
    signals = []
    threshold = config.diagnostics_never_triggered_threshold
    for cid in all_criteria:
        count = triggered_counts.get(cid, 0)
        rate = count / max(total, 1)
        if rate <= threshold:
            sev = _severity_from_rate(1.0 - rate, 0.5, 0.2)
            signals.append(DiagnosticSignal(
                signal_type="never_triggered",
                criterion_id=cid,
                severity=sev,
                description=f"Criterion {cid} activated 0 times out of {total} advisories in {stage.upper()}",
                evidence={
                    "activation_rate": 0.0,
                    "total_advisories": total,
                    "stage": stage,
                },
                recommendation=f"Review if {cid} is too narrow or requires rephrasing for this study population",
            ))
    return signals


def signal_always_triggered(
    all_criteria: List[str],
    triggered_counts: Dict[str, int],
    total: int,
    config: AdvisoryConfig,
    stage: str,
) -> List[DiagnosticSignal]:
    """Signal: criteria activated at >= threshold rate."""
    signals = []
    threshold = config.diagnostics_always_triggered_threshold
    for cid in all_criteria:
        count = triggered_counts.get(cid, 0)
        rate = count / max(total, 1)
        if rate >= threshold:
            sev = _severity_from_rate(rate, 0.99, 0.95)
            signals.append(DiagnosticSignal(
                signal_type="always_triggered",
                criterion_id=cid,
                severity=sev,
                description=f"Criterion {cid} activated in {count}/{total} ({rate:.0%}) advisories in {stage.upper()}",
                evidence={
                    "activation_rate": round(rate, 4),
                    "total_advisories": total,
                    "stage": stage,
                },
                recommendation=f"Consider if {cid} provides discriminative value or needs splitting",
            ))
    return signals


def signal_high_ambiguity(
    advisories: List[Dict],
    config: AdvisoryConfig,
    stage: str,
) -> List[DiagnosticSignal]:
    """Signal: high hallucination risk / ambiguity markers."""
    signals = []
    threshold = config.diagnostics_high_ambiguity_threshold
    high_amb = [a for a in advisories if a["hallucination_risk_score"] > threshold]
    if not high_amb:
        return signals

    ambiguous_decision_types = {
        a.get("decision", ""): a.get("hallucination_risk_score", 0)
        for a in high_amb
    }

    signals.append(DiagnosticSignal(
        signal_type="high_ambiguity",
        criterion_id=f"{stage.upper()}_GENERAL",
        severity=_severity_from_rate(len(high_amb) / max(len(advisories), 1), 0.3, 0.15),
        description=f"{len(high_amb)}/{len(advisories)} advisories exceed ambiguity threshold in {stage.upper()}",
        evidence={
            "count": len(high_amb),
            "total": len(advisories),
            "rate": round(len(high_amb) / max(len(advisories), 1), 4),
            "ambiguity_threshold": threshold,
            "affected_decisions": ambiguous_decision_types,
            "stage": stage,
        },
        recommendation="Review high-ambiguity studies and consider if protocol criteria need clarification",
    ))
    return signals


def signal_high_quarantine(
    advisories: List[Dict],
    config: AdvisoryConfig,
    stage: str,
) -> List[DiagnosticSignal]:
    """Signal: high quarantine rate (UNCERTAIN / INSUFFICIENT_EVIDENCE)."""
    signals = []
    threshold = config.diagnostics_high_quarantine_threshold
    quarantine_decisions = {
        AdvisoryDecision.UNCERTAIN.value,
        AdvisoryDecision.INSUFFICIENT_EVIDENCE.value,
        AdvisoryDecision.CANNOT_DETERMINE.value,
    }
    quarantined = [a for a in advisories if a["decision"] in quarantine_decisions]
    if not quarantined:
        return signals

    rate = len(quarantined) / max(len(advisories), 1)
    if rate >= threshold:
        signals.append(DiagnosticSignal(
            signal_type="high_quarantine",
            criterion_id=f"{stage.upper()}_GENERAL",
            severity=_severity_from_rate(rate, 0.4, 0.2),
            description=f"{len(quarantined)}/{len(advisories)} ({rate:.0%}) studies quarantined in {stage.upper()}",
            evidence={
                "quarantine_count": len(quarantined),
                "total": len(advisories),
                "quarantine_rate": round(rate, 4),
                "quarantine_threshold": threshold,
                "stage": stage,
            },
            recommendation=f"High quarantine rate suggests criteria do not match study characteristics",
        ))
    return signals


def signal_low_grounding(
    advisories: List[Dict],
    config: AdvisoryConfig,
    stage: str,
) -> List[DiagnosticSignal]:
    """Signal: low grounding strength in advisory justifications."""
    signals = []
    threshold = config.diagnostics_low_grounding_threshold
    low = [a for a in advisories if a["grounding_strength"] < threshold]
    if not low:
        return signals

    mean_grounding = (
        statistics.mean(a["grounding_strength"] for a in advisories)
        if advisories else 0.0
    )

    low_evidence_span = [a for a in low if a["evidence_span"] < 50]
    lack_evidence = len(low_evidence_span)

    signals.append(DiagnosticSignal(
        signal_type="low_grounding",
        criterion_id=f"{stage.upper()}_GENERAL",
        severity=_severity_from_rate(len(low) / max(len(advisories), 1), 0.5, 0.3),
        description=f"{len(low)}/{len(advisories)} advisories have grounding < {threshold} in {stage.upper()}",
        evidence={
            "low_grounding_count": len(low),
            "total": len(advisories),
            "low_grounding_rate": round(len(low) / max(len(advisories), 1), 4),
            "mean_grounding": round(mean_grounding, 4),
            "lack_evidence_span": lack_evidence,
            "grounding_threshold": threshold,
            "stage": stage,
        },
        recommendation=f"Low grounding suggests abstracts may lack sufficient detail for reliable screening",
    ))
    return signals


def signal_confidence_instability(
    advisories: List[Dict],
    config: AdvisoryConfig,
    stage: str,
) -> List[DiagnosticSignal]:
    """Signal: high variance in criterion confidence scores."""
    signals = []
    threshold = config.diagnostics_confidence_instability_threshold

    all_confidences = [a["confidence"] for a in advisories if a["confidence"] > 0]
    if len(all_confidences) < 3:
        return signals

    try:
        variance = statistics.variance(all_confidences)
    except statistics.StatisticsError:
        variance = 0.0

    if variance >= threshold:
        mean_conf = statistics.mean(all_confidences)
        signals.append(DiagnosticSignal(
            signal_type="confidence_instability",
            criterion_id=f"{stage.upper()}_GENERAL",
            severity=_severity_from_rate(variance, 0.5, 0.3),
            description=f"Advisory confidence variance {variance:.3f} exceeds threshold {threshold} in {stage.upper()}",
            evidence={
                "confidence_variance": round(variance, 4),
                "confidence_mean": round(mean_conf, 4),
                "confidence_std": round(variance ** 0.5, 4),
                "num_advisories": len(all_confidences),
                "instability_threshold": threshold,
                "stage": stage,
            },
            recommendation=f"Unstable confidence suggests inconsistent criterion interpretation",
        ))

    return signals


def signal_overlap(
    overlap: Dict,
    config: AdvisoryConfig,
) -> List[DiagnosticSignal]:
    """Signal: EC/IC semantic overlap in criteria activation."""
    signals = []
    threshold = config.diagnostics_overlap_threshold
    rate = overlap.get("ec_ic_overlap_rate", 0.0)
    if rate > threshold:
        signals.append(DiagnosticSignal(
            signal_type="ec_ic_overlap",
            criterion_id="EC+IC",
            severity=_severity_from_rate(rate, 0.7, 0.5),
            description=f"EC/IC criteria co-activation rate {rate:.1%} exceeds overlap threshold {threshold:.0%}",
            evidence={
                "overlap_rate": rate,
                "overlap_count": overlap.get("ec_ic_overlap_count", 0),
                "overlap_threshold": threshold,
            },
            recommendation=f"Consider merging or clarifying EC and IC criteria to reduce redundancy",
        ))
    return signals


def signal_skew(
    advisories: List[Dict],
    config: AdvisoryConfig,
    stage: str,
) -> List[DiagnosticSignal]:
    """Signal: excessive rejection or acceptance skew."""
    signals = []
    high = config.diagnostics_skew_acceptance_threshold_high
    low = config.diagnostics_skew_acceptance_threshold_low

    includes = sum(1 for a in advisories if a["decision"] == AdvisoryDecision.INCLUDE.value)
    excludes = sum(1 for a in advisories if a["decision"] == AdvisoryDecision.EXCLUDE.value)
    total = len(advisories)
    if total == 0:
        return signals

    include_rate = includes / total
    exclude_rate = excludes / total

    if include_rate >= high:
        signals.append(DiagnosticSignal(
            signal_type="acceptance_skew",
            criterion_id=f"{stage.upper()}_GENERAL",
            severity=_severity_from_rate(include_rate, 0.99, 0.95),
            description=f"Include rate {include_rate:.0%} exceeds high threshold {high:.0%} in {stage.upper()} — excessive acceptance",
            evidence={
                "include_rate": round(include_rate, 4),
                "exclude_rate": round(exclude_rate, 4),
                "total": total,
                "includes": includes,
                "excludes": excludes,
                "skew_threshold_high": high,
                "stage": stage,
            },
            recommendation=f"Criteria may be too permissive; consider stricter thresholds",
        ))
    elif exclude_rate >= high:
        signals.append(DiagnosticSignal(
            signal_type="acceptance_skew",
            criterion_id=f"{stage.upper()}_GENERAL",
            severity=_severity_from_rate(exclude_rate, 0.99, 0.95),
            description=f"Exclude rate {exclude_rate:.0%} exceeds high threshold {high:.0%} in {stage.upper()} — excessive rejection",
            evidence={
                "include_rate": round(include_rate, 4),
                "exclude_rate": round(exclude_rate, 4),
                "total": total,
                "includes": includes,
                "excludes": excludes,
                "skew_threshold_high": high,
                "stage": stage,
            },
            recommendation=f"Criteria may be too restrictive; consider broadening eligibility",
        ))

    return signals


def signal_criteria_redundancy(
    advisories: List[Dict],
    all_criteria: List[str],
    stage: str,
) -> List[DiagnosticSignal]:
    """Signal: criteria that always co-trigger, suggesting redundancy."""
    signals = []
    if len(all_criteria) < 2 or len(advisories) < 2:
        return signals

    co_occurrence = {}
    for c in all_criteria:
        co_occurrence[c] = {}

    for a in advisories:
        trig = set(a.get("triggered_criteria", []))
        for c1 in trig:
            for c2 in trig:
                if c1 < c2:
                    pair = (c1, c2)
                    co_occurrence[c1][c2] = co_occurrence[c1].get(c2, 0) + 1

    total = len(advisories)
    redundancy_threshold = 0.8
    for c1 in sorted(co_occurrence.keys()):
        for c2, count in sorted(co_occurrence[c1].items()):
            rate = count / max(total, 1)
            if rate >= redundancy_threshold and count >= 2:
                signals.append(DiagnosticSignal(
                    signal_type="criteria_redundancy",
                    criterion_id=f"{c1}+{c2}",
                    severity=_severity_from_rate(rate, 0.95, 0.8),
                    description=f"Criteria {c1} and {c2} co-triggered in {count}/{total} ({rate:.0%}) {stage.upper()} advisories",
                    evidence={
                        "co_triggered_count": count,
                        "total": total,
                        "co_trigger_rate": round(rate, 4),
                        "criterion_a": c1,
                        "criterion_b": c2,
                        "stage": stage,
                    },
                    recommendation=f"Consider merging {c1} and {c2} or clarifying their distinct scope",
                ))

    return signals


def signal_implicit_inference(
    advisories: List[Dict],
    config: AdvisoryConfig,
    stage: str,
) -> List[DiagnosticSignal]:
    """Signal: criteria triggered despite low grounding, requiring implicit inference."""
    signals = []
    threshold = config.diagnostics_low_grounding_threshold

    for a in advisories:
        triggered = a.get("triggered_criteria", [])
        grounding = a["grounding_strength"]
        if not triggered or not grounding:
            continue
        if grounding < threshold:
            for cid in triggered:
                signals.append(DiagnosticSignal(
                    signal_type="implicit_inference",
                    criterion_id=cid,
                    severity="medium",
                    description=f"Criterion {cid} triggered in {stage.upper()} despite low grounding ({grounding:.2f})",
                    evidence={
                        "grounding_strength": round(grounding, 4),
                        "grounding_threshold": threshold,
                        "decision": a.get("decision", ""),
                        "advisory_key": a.get("cache_key", ""),
                        "stage": stage,
                    },
                    recommendation=f"Review if {cid} requires implicit inference beyond available evidence",
                ))

    return signals


def run_diagnostics(
    ec_advisories: List[Dict],
    ic_advisories: List[Dict],
    all_criteria: List[str],
    overlap: Dict,
    config: AdvisoryConfig,
) -> List[Dict]:
    """Run all diagnostic signals and return serialized results.

    Pure deterministic function. No side effects.
    """
    ec = _parse_advisories(ec_advisories, "ec")
    ic = _parse_advisories(ic_advisories, "ic")

    ec_triggered = {}
    for a in ec:
        for c in a["triggered_criteria"]:
            ec_triggered[c] = ec_triggered.get(c, 0) + 1

    ic_triggered = {}
    for a in ic:
        for c in a["triggered_criteria"]:
            ic_triggered[c] = ic_triggered.get(c, 0) + 1

    signals: List[DiagnosticSignal] = []

    signals.extend(signal_never_triggered(all_criteria, ec_triggered, len(ec), config, "ec"))
    signals.extend(signal_never_triggered(all_criteria, ic_triggered, len(ic), config, "ic"))

    signals.extend(signal_always_triggered(all_criteria, ec_triggered, len(ec), config, "ec"))
    signals.extend(signal_always_triggered(all_criteria, ic_triggered, len(ic), config, "ic"))

    signals.extend(signal_high_ambiguity(ec, config, "ec"))
    signals.extend(signal_high_ambiguity(ic, config, "ic"))

    signals.extend(signal_high_quarantine(ec, config, "ec"))
    signals.extend(signal_high_quarantine(ic, config, "ic"))

    signals.extend(signal_low_grounding(ec, config, "ec"))
    signals.extend(signal_low_grounding(ic, config, "ic"))

    signals.extend(signal_confidence_instability(ec, config, "ec"))
    signals.extend(signal_confidence_instability(ic, config, "ic"))

    signals.extend(signal_overlap(overlap, config))

    signals.extend(signal_skew(ec, config, "ec"))
    signals.extend(signal_skew(ic, config, "ic"))

    signals.extend(signal_criteria_redundancy(ec, all_criteria, "ec"))
    signals.extend(signal_criteria_redundancy(ic, all_criteria, "ic"))

    signals.extend(signal_implicit_inference(ec, config, "ec"))
    signals.extend(signal_implicit_inference(ic, config, "ic"))

    return [
        {
            "signal_type": s.signal_type,
            "criterion_id": s.criterion_id,
            "severity": s.severity,
            "description": s.description,
            "evidence": s.evidence,
            "recommendation": s.recommendation,
        }
        for s in signals
    ]
