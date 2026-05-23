"""
APOLLO Calibration Tracker

Tracks disagreements between AI advisory and human final decisions
to build a scientifically valid calibration dataset.

This is NOT ML prediction - only empirical data collection infrastructure.
"""

import os
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, timezone

from .advisory_models import (
    CalibrationEvent,
    AdvisoryResult,
    compute_metadata_completeness,
    safe_enum_value
)


CALIBRATION_DIR = Path("data/calibration")
CALIBRATION_FILE = "calibration_events.jsonl"


def _get_calibration_path() -> Path:
    """Get calibration file path, creating directory if needed."""
    CALIBRATION_DIR.mkdir(parents=True, exist_ok=True)
    return CALIBRATION_DIR / CALIBRATION_FILE


def log_calibration_event(
    article_id: str,
    protocol_version: str,
    stage: str,
    advisory: AdvisoryResult,
    human_decision: str,
    metadata: dict = None,
    override_reason: str = "",
    override_severity: str = ""
) -> CalibrationEvent:
    """
    Log a calibration event when human makes a decision different from AI advisory.

    Args:
        article_id: Unique article identifier
        protocol_version: Protocol version used
        stage: Screening stage (ec/ic/qc)
        advisory: The advisory from AI
        human_decision: The human's final decision (INCLUDE/EXCLUDE)
        metadata: Article metadata for completeness calculation
        override_reason: Optional reason for override
        override_severity: Severity level (LOW/MEDIUM/HIGH/CRITICAL)

    Returns:
        CalibrationEvent that was logged
    """
    ai_decision = safe_enum_value(advisory.decision, "UNKNOWN")
    human_decision_upper = human_decision.upper() if human_decision else "UNKNOWN"

    metadata_completeness = compute_metadata_completeness(
        title=advisory.cache_key[:20],
        abstract="",
        metadata=metadata
    )

    risk_class = safe_enum_value(advisory.risk_classification, "UNKNOWN") if advisory.risk_classification else "UNKNOWN"
    validation_queue = safe_enum_value(advisory.validation_queue, "UNKNOWN") if advisory.validation_queue else "UNKNOWN"

    disagreement = (ai_decision != human_decision_upper and ai_decision != "UNKNOWN")

    event = CalibrationEvent(
        article_id=article_id,
        protocol_version=protocol_version,
        stage=stage,
        ai_decision=ai_decision,
        human_decision=human_decision_upper,
        ai_confidence=advisory.confidence if advisory.confidence else 0.0,
        metadata_completeness=metadata_completeness,
        risk_classification=risk_class,
        ambiguity_detected=False,
        fallback_used=advisory.is_fallback if advisory else False,
        triggered_criteria=advisory.triggered_criteria if advisory and advisory.triggered_criteria else [],
        validation_queue=validation_queue,
        disagreement=disagreement,
        override_reason=override_reason,
        override_severity=override_severity,
        timestamp=datetime.now(timezone.utc).isoformat()
    )

    _append_event(event)
    return event


def _append_event(event: CalibrationEvent) -> None:
    """Append event to calibration log with duplicate prevention and integrity validation."""
    path = _get_calibration_path()
    
    existing_events = load_calibration_events(limit=1000)
    event_id = f"{event.article_id}_{event.stage}_{event.timestamp}"
    for existing in existing_events:
        existing_id = f"{existing.article_id}_{existing.stage}_{existing.timestamp}"
        if event_id == existing_id:
            return
    
    event_data = event.to_dict()
    required_fields = ["article_id", "protocol_version", "stage", "ai_decision", "human_decision"]
    for field in required_fields:
        if field not in event_data or event_data[field] is None:
            return
    
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event_data, ensure_ascii=False) + "\n")


def load_calibration_events(limit: Optional[int] = None) -> List[CalibrationEvent]:
    """Load all calibration events from storage."""
    path = _get_calibration_path()
    if not path.exists():
        return []

    events = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    data = json.loads(line)
                    events.append(CalibrationEvent.from_dict(data))
                except json.JSONDecodeError:
                    continue
            if limit and len(events) >= limit:
                break

    return events


def compute_calibration_metrics() -> Dict:
    """
    Compute deterministic calibration metrics from collected events.

    NO ML - pure empirical tracking only.
    """
    events = load_calibration_events()

    if not events:
        return {
            "total_events": 0,
            "agreement_rate": 0.0,
            "override_count": 0,
            "agreement_by_risk": {},
            "agreement_by_stage": {}
        }

    total = len(events)
    disagreements = sum(1 for e in events if e.disagreement)
    agreement_count = total - disagreements

    agreement_rate = agreement_count / total if total > 0 else 0.0

    risk_agreement = {}
    for risk in ["LOW_RISK", "MEDIUM_RISK", "HIGH_RISK", "CRITICAL_REVIEW"]:
        risk_events = [e for e in events if e.risk_classification == risk]
        if risk_events:
            risk_disagreements = sum(1 for e in risk_events if e.disagreement)
            risk_agreement[risk] = 1.0 - (risk_disagreements / len(risk_events))
        else:
            risk_agreement[risk] = 0.0

    stage_agreement = {}
    for stage in ["ec", "ic", "qc"]:
        stage_events = [e for e in events if e.stage == stage]
        if stage_events:
            stage_disagreements = sum(1 for e in stage_events if e.disagreement)
            stage_agreement[stage] = 1.0 - (stage_disagreements / len(stage_events))
        else:
            stage_agreement[stage] = 0.0

    metadata_agreement = {
        "high_completeness": 0.0,
        "medium_completeness": 0.0,
        "low_completeness": 0.0
    }
    high_meta = [e for e in events if e.metadata_completeness >= 0.7]
    med_meta = [e for e in events if 0.3 <= e.metadata_completeness < 0.7]
    low_meta = [e for e in events if e.metadata_completeness < 0.3]

    if high_meta:
        metadata_agreement["high_completeness"] = 1.0 - (sum(1 for e in high_meta if e.disagreement) / len(high_meta))
    if med_meta:
        metadata_agreement["medium_completeness"] = 1.0 - (sum(1 for e in med_meta if e.disagreement) / len(med_meta))
    if low_meta:
        metadata_agreement["low_completeness"] = 1.0 - (sum(1 for e in low_meta if e.disagreement) / len(low_meta))

    false_exclusion_est = sum(1 for e in events if e.disagreement and e.ai_decision == "INCLUDE" and e.human_decision == "EXCLUDE")
    false_inclusion_est = sum(1 for e in events if e.disagreement and e.ai_decision == "EXCLUDE" and e.human_decision == "INCLUDE")

    return {
        "total_events": total,
        "agreement_rate": round(agreement_rate, 3),
        "override_count": disagreements,
        "agreement_by_risk": {k: round(v, 3) for k, v in risk_agreement.items()},
        "agreement_by_stage": {k: round(v, 3) for k, v in stage_agreement.items()},
        "agreement_by_metadata": {k: round(v, 3) for k, v in metadata_agreement.items()},
        "false_exclusion_estimate": false_exclusion_est,
        "false_inclusion_estimate": false_inclusion_est,
        "last_updated": datetime.now(timezone.utc).isoformat()
    }


def get_calibration_stats() -> Dict:
    """Get lightweight stats for UI display."""
    events = load_calibration_events()

    if not events:
        return {
            "total": 0,
            "agreement_rate": "N/A",
            "disagreements": 0
        }

    total = len(events)
    disagreements = sum(1 for e in events if e.disagreement)
    agreement_rate = (total - disagreements) / total if total > 0 else 0

    return {
        "total": total,
        "agreement_rate": f"{agreement_rate:.1%}",
        "disagreements": disagreements
    }


def get_calibration_summary() -> Dict:
    """Get enhanced calibration summary for operational panel."""
    events = load_calibration_events()

    if not events:
        return {
            "agreement_rate": "N/A",
            "override_rate": "N/A",
            "critical_overrides": 0,
            "high_overrides": 0,
            "medium_overrides": 0,
            "low_overrides": 0,
            "low_risk_sample_agreement": "N/A",
            "false_exclusion": 0,
            "false_inclusion": 0,
            "hallucination_risk_rate": "N/A"
        }

    total = len(events)
    disagreements = sum(1 for e in events if e.disagreement)
    agreement_rate = (total - disagreements) / total if total > 0 else 0
    override_rate = disagreements / total if total > 0 else 0

    critical_overrides = sum(1 for e in events if e.override_severity == "CRITICAL")
    high_overrides = sum(1 for e in events if e.override_severity == "HIGH")
    medium_overrides = sum(1 for e in events if e.override_severity == "MEDIUM")
    low_overrides = sum(1 for e in events if e.override_severity == "LOW")

    low_risk_events = [e for e in events if e.risk_classification == "LOW_RISK"]
    if low_risk_events:
        low_risk_disagreements = sum(1 for e in low_risk_events if e.disagreement)
        low_risk_agreement = 1.0 - (low_risk_disagreements / len(low_risk_events))
    else:
        low_risk_agreement = None

    false_exclusion = sum(1 for e in events if e.disagreement and e.ai_decision == "INCLUDE" and e.human_decision == "EXCLUDE")
    false_inclusion = sum(1 for e in events if e.disagreement and e.ai_decision == "EXCLUDE" and e.human_decision == "INCLUDE")

    high_risk_events = sum(1 for e in events if e.override_severity in ("CRITICAL", "HIGH"))
    hallucination_risk_rate = (high_risk_events / total) * 100 if total > 0 else 0

    return {
        "agreement_rate": f"{agreement_rate * 100:.1f}%",
        "override_rate": f"{override_rate * 100:.1f}%",
        "critical_overrides": critical_overrides,
        "high_overrides": high_overrides,
        "medium_overrides": medium_overrides,
        "low_overrides": low_overrides,
        "low_risk_sample_agreement": f"{low_risk_agreement * 100:.1f}%" if low_risk_agreement is not None else "N/A",
        "false_exclusion": false_exclusion,
        "false_inclusion": false_inclusion,
        "hallucination_risk_rate": f"{hallucination_risk_rate:.1f}%"
    }


def get_calibration_filtered_articles(articles: List, protocol_version: str, stage: str) -> List:
    """Get filtered articles for Calibration Review mode - disagreements and overrides only."""
    calibration_events = load_calibration_events()
    calibration_article_ids = {e.article_id for e in calibration_events if e.disagreement}

    filtered = []
    for article in articles:
        if hasattr(article, 'article_id') and article.article_id in calibration_article_ids:
            filtered.append(article)

    filtered.sort(key=lambda a: getattr(a, 'article_id', ''))
    return filtered