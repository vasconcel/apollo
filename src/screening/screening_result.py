"""Phase 2A + Phase 4E: Immutable result contract + explainability."""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any


class ScreeningDecision(Enum):
    INCLUDE = "INCLUDE"
    EXCLUDE = "EXCLUDE"
    REVIEW = "REVIEW"
    UNCERTAIN = "UNCERTAIN"


@dataclass(frozen=True)
class Evidence:
    rule_id: str
    rule_name: str
    evidence_type: str
    match: str
    context: Optional[str] = None
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "evidence_type": self.evidence_type,
            "match": self.match,
        }
        if self.context is not None:
            d["context"] = self.context
        if self.confidence != 1.0:
            d["confidence"] = self.confidence
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Evidence":
        return cls(
            rule_id=d["rule_id"],
            rule_name=d["rule_name"],
            evidence_type=d["evidence_type"],
            match=d["match"],
            context=d.get("context"),
            confidence=d.get("confidence", 1.0),
        )


@dataclass(frozen=True)
class ScreeningResult:
    article_id: str
    decision: ScreeningDecision
    confidence: float
    evidence: List[Evidence] = field(default_factory=list)
    triggered_rules: List[str] = field(default_factory=list)
    semantic_signals: Dict[str, float] = field(default_factory=dict)
    escalation_required: bool = False
    rationale: str = ""
    processing_stage: str = "ec"
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    study_type: str = ""
    consensus_trace: Dict[str, Any] = field(default_factory=dict)
    hard_negative: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "article_id": self.article_id,
            "decision": self.decision.value,
            "confidence": self.confidence,
            "evidence": [e.to_dict() for e in self.evidence],
            "triggered_rules": list(self.triggered_rules),
            "semantic_signals": dict(self.semantic_signals),
            "escalation_required": self.escalation_required,
            "rationale": self.rationale,
            "processing_stage": self.processing_stage,
            "created_at": self.created_at,
            "study_type": self.study_type,
            "consensus_trace": dict(self.consensus_trace),
            "hard_negative": self.hard_negative,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ScreeningResult":
        return cls(
            article_id=d["article_id"],
            decision=ScreeningDecision(d["decision"]),
            confidence=d["confidence"],
            evidence=[Evidence.from_dict(e) for e in d.get("evidence", [])],
            triggered_rules=list(d.get("triggered_rules", [])),
            semantic_signals=dict(d.get("semantic_signals", {})),
            escalation_required=d.get("escalation_required", False),
            rationale=d.get("rationale", ""),
            processing_stage=d.get("processing_stage", "ec"),
            created_at=d.get(
                "created_at", datetime.now(timezone.utc).isoformat()
            ),
            study_type=d.get("study_type", ""),
            consensus_trace=dict(d.get("consensus_trace", {})),
            hard_negative=d.get("hard_negative", False),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, s: str) -> "ScreeningResult":
        return cls.from_dict(json.loads(s))

    def explain(self) -> Dict[str, Any]:
        triggered = []
        for ev in self.evidence:
            triggered.append({
                "rule_id": ev.rule_id,
                "rule_name": ev.rule_name,
                "type": ev.evidence_type,
                "match": ev.match,
                "context": ev.context or "",
            })

        base = {
            "article_id": self.article_id,
            "final_decision": self.decision.value,
            "confidence_score": self.confidence,
            "triggered_rules": triggered,
            "triggered_rule_ids": list(self.triggered_rules),
            "evidence_count": len(self.evidence),
            "has_conflicting_evidence": self._has_conflicting(),
            "escalation_required": self.escalation_required,
            "escalation_reason": (
                self.rationale.split("Escalation reasons:")[-1].strip()
                if "Escalation reasons:" in self.rationale
                else ""
            ),
            "semantic_signals": dict(self.semantic_signals) if self.semantic_signals else {},
            "rationale_summary": self.rationale[:300] if self.rationale else "",
            "study_type": self.study_type,
            "hard_negative": self.hard_negative,
        }
        if self.consensus_trace:
            base["consensus_trace"] = {
                k: v for k, v in self.consensus_trace.items()
                if k != "evidence_breakdown"
            }
        return base

    def _has_conflicting(self) -> bool:
        has_inc = False
        has_exc = False
        for ev in self.evidence:
            if ev.evidence_type == "exclusion_pattern":
                has_exc = True
            else:
                has_inc = True
        return has_inc and has_exc
