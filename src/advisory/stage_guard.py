"""
APOLLO Stage Isolation Guard

Enforces stage-specific criteria isolation:
- EC workers must NEVER emit IC criteria
- IC workers must NEVER emit EC criteria
- Adds invariant validation before persistence
- Adds automatic corruption detection and quarantine
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field


EC_CRITERIA_PREFIXES = frozenset({"EC1", "EC2", "EC3", "EC4", "EC5", "EC6", "EC7"})
IC_CRITERIA_PREFIXES = frozenset({"IC1", "IC2", "IC3", "IC4", "IC5", "IC6", "IC7", "IC8", "IC9"})


STAGE_CRITERIA_MAP = {
    "ec": EC_CRITERIA_PREFIXES,
    "ic": IC_CRITERIA_PREFIXES,
}


def get_stage_prefixes(stage: str) -> frozenset:
    stage_lower = stage.strip().lower()
    if stage_lower == "ec":
        return EC_CRITERIA_PREFIXES
    elif stage_lower == "ic":
        return IC_CRITERIA_PREFIXES
    return frozenset()


def get_opposite_stage_prefixes(stage: str) -> frozenset:
    stage_lower = stage.strip().lower()
    if stage_lower == "ec":
        return IC_CRITERIA_PREFIXES
    elif stage_lower == "ic":
        return EC_CRITERIA_PREFIXES
    return frozenset()


@dataclass
class StageIsolationReport:
    passed: bool = True
    stage: str = ""
    contamination_found: bool = False
    contaminated_criteria: List[str] = field(default_factory=list)
    quarantined: bool = False
    warning: str = ""

    def to_dict(self) -> Dict:
        return {
            "passed": self.passed,
            "stage": self.stage,
            "contamination_found": self.contamination_found,
            "contaminated_criteria": self.contaminated_criteria,
            "quarantined": self.quarantined,
            "warning": self.warning,
        }


def validate_criteria_stage_isolation(
    triggered_criteria: List[str],
    non_triggered_criteria: List[str],
    criterion_evaluations: Any,
    stage: str,
) -> StageIsolationReport:
    stage_lower = stage.strip().lower()
    if stage_lower not in ("ec", "ic"):
        return StageIsolationReport(
            passed=True, stage=stage,
            warning=f"Stage '{stage}' not in isolation scope (ec/ic only), skipping"
        )
    forbidden = get_opposite_stage_prefixes(stage)
    contaminated: List[str] = []
    for cid in triggered_criteria or []:
        cid_upper = cid.upper().strip()
        if any(cid_upper.startswith(p) for p in forbidden):
            contaminated.append(cid_upper)
    for cid in non_triggered_criteria or []:
        cid_upper = cid.upper().strip()
        if any(cid_upper.startswith(p) for p in forbidden):
            contaminated.append(cid_upper)
    if criterion_evaluations:
        try:
            if isinstance(criterion_evaluations, dict):
                for cid in criterion_evaluations:
                    cid_upper = cid.upper().strip()
                    if any(cid_upper.startswith(p) for p in forbidden):
                        contaminated.append(cid_upper)
            elif isinstance(criterion_evaluations, list):
                for ce in criterion_evaluations:
                    if isinstance(ce, dict):
                        cid = ce.get("criterion_id", ce.get("criterion", ""))
                        cid_upper = cid.upper().strip()
                        if any(cid_upper.startswith(p) for p in forbidden):
                            contaminated.append(cid_upper)
        except Exception:
            pass
    contaminated = list(dict.fromkeys(contaminated))
    if contaminated:
        return StageIsolationReport(
            passed=False,
            stage=stage,
            contamination_found=True,
            contaminated_criteria=contaminated,
            quarantined=True,
            warning=f"Stage contamination detected in {stage}: {contaminated}. "
                    f"Advisory quarantined for review.",
        )
    return StageIsolationReport(passed=True, stage=stage)


def strip_contaminated_criteria(
    triggered_criteria: List[str],
    non_triggered_criteria: List[str],
    stage: str,
) -> Tuple[List[str], List[str]]:
    forbidden = get_opposite_stage_prefixes(stage)
    clean_triggered = [
        c for c in (triggered_criteria or [])
        if not any(c.upper().strip().startswith(p) for p in forbidden)
    ]
    clean_non_triggered = [
        c for c in (non_triggered_criteria or [])
        if not any(c.upper().strip().startswith(p) for p in forbidden)
    ]
    return clean_triggered, clean_non_triggered


def quarantine_advisory(advisory: Any, stage: str, reason: str) -> Any:
    from .advisory_models import AdvisoryDecision, AdvisoryResult
    if isinstance(advisory, AdvisoryResult):
        advisory.decision = AdvisoryDecision.UNCERTAIN
        advisory.justification = f"[QUARANTINED] {reason} | Original: {advisory.justification}"
        advisory.triggered_criteria = []
        if hasattr(advisory, 'criterion_evaluations'):
            advisory.criterion_evaluations = []
        advisory.error = f"STAGE_CONTAMINATION: {reason}"
    return advisory
