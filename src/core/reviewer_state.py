"""
APOLLO Reviewer State Management
Tracks individual researcher decisions for audit trail

AUDIT REQUIREMENTS:
- Every human decision logged separately
- Every AI suggestion logged separately  
- Timestamps preserved
- Protocol snapshot preserved
- Deterministic hashes preserved
"""
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from enum import Enum
import json
import hashlib


class DecisionChoice(Enum):
    """Researcher decision choices."""
    INCLUDE = "include"
    EXCLUDE = "exclude"
    SKIP = "skip"
    NEEDS_DISCUSSION = "needs_discussion"


@dataclass
class AISuggestion:
    """AI advisory suggestion (separate from human decision)."""
    article_id: str
    session_id: str
    stage: str
    
    suggestion: str  # "include", "exclude", "skip"
    confidence: float
    justification: str
    
    criteria_analyzed: Dict[str, str] = field(default_factory=dict)
    evidence: List[str] = field(default_factory=list)
    
    model: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    suggestion_hash: str = ""
    
    def __post_init__(self):
        """Generate suggestion hash."""
        content = f"{self.article_id}|{self.session_id}|{self.stage}|{self.suggestion}|{self.confidence}|{self.timestamp}"
        self.suggestion_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class DecisionRecord:
    """Single human decision record for audit."""
    article_id: str
    session_id: str
    stage: str
    
    researcher_id: str
    decision: str  # Human's FINAL decision
    notes: str = ""
    
    ai_suggestion: Optional[str] = None  # What AI suggested (for comparison)
    ai_confidence: Optional[float] = None  # AI confidence
    
    protocol_snapshot: str = ""  # Protocol version snapshot
    input_checksum: str = ""  # Input file checksum
    
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    decision_hash: str = ""
    
    def __post_init__(self):
        """Generate decision hash."""
        content = f"{self.article_id}|{self.session_id}|{self.stage}|{self.researcher_id}|{self.decision}|{self.timestamp}"
        self.decision_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @property
    def is_human_decision(self) -> bool:
        """Verify this is a human-authored decision."""
        return bool(self.researcher_id and self.decision)
    
    @property
    def did_override_ai(self) -> bool:
        """Check if human overrode AI suggestion."""
        if not self.ai_suggestion:
            return False
        return self.decision != self.ai_suggestion
    
    @classmethod
    def from_dict(cls, data: Dict) -> "DecisionRecord":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class ReviewerState:
    """State tracker for a single reviewer with full audit trail."""
    researcher_id: str
    session_id: str
    
    decisions: List[DecisionRecord] = field(default_factory=list)
    ai_suggestions: List[AISuggestion] = field(default_factory=list)
    
    stage: str = "ec"
    
    protocol_version: str = "1.0"
    protocol_snapshot: str = ""
    input_checksum: str = ""
    
    def record_ai_suggestion(
        self,
        article_id: str,
        stage: str,
        suggestion: str,
        confidence: float,
        justification: str,
        criteria: Optional[Dict] = None,
        model: str = ""
    ) -> AISuggestion:
        """Record AI suggestion separately (advisory only)."""
        ai_record = AISuggestion(
            article_id=article_id,
            session_id=self.session_id,
            stage=stage,
            suggestion=suggestion,
            confidence=confidence,
            justification=justification,
            criteria_analyzed=criteria or {},
            model=model or "llama-3.1-70b-versatile"
        )
        self.ai_suggestions.append(ai_record)
        return ai_record
    
    def record_decision(
        self,
        article_id: str,
        stage: str,
        decision: str,
        notes: str = "",
        ai_suggestion: Optional[str] = None,
        ai_confidence: Optional[float] = None
    ) -> DecisionRecord:
        """Record HUMAN decision (final authority)."""
        record = DecisionRecord(
            article_id=article_id,
            session_id=self.session_id,
            stage=stage,
            researcher_id=self.researcher_id,
            decision=decision,
            notes=notes,
            ai_suggestion=ai_suggestion,
            ai_confidence=ai_confidence,
            protocol_snapshot=self.protocol_version,
            input_checksum=self.input_checksum
        )
        
        self.decisions.append(record)
        return record
    
    def get_ai_suggestion_for_article(
        self, 
        article_id: str, 
        stage: str
    ) -> Optional[AISuggestion]:
        """Get AI suggestion for article."""
        for s in reversed(self.ai_suggestions):
            if s.article_id == article_id and s.stage == stage:
                return s
        return None
    
    def get_human_decisions_only(self) -> List[DecisionRecord]:
        """Get human decisions only (for scientific defensibility)."""
        return [d for d in self.decisions if d.is_human_decision]
    
    def get_ai_overrides(self) -> List[DecisionRecord]:
        """Get cases where human overrode AI."""
        return [d for d in self.decisions if d.did_override_ai]
    
    def get_article_decision(self, article_id: str, stage: str) -> Optional[DecisionRecord]:
        """Get decision for specific article and stage."""
        for d in self.decisions:
            if d.article_id == article_id and d.stage == stage:
                return d
        return None
    
    def get_progress(self) -> Dict:
        """Get reviewer progress."""
        return {
            "researcher_id": self.researcher_id,
            "stage": self.stage,
            "total_decisions": len(self.decisions),
            "ai_suggestions_logged": len(self.ai_suggestions),
            "ai_overrides": len(self.get_ai_overrides()),
            "protocol_version": self.protocol_version
        }
    
    def save(self, output_path: str) -> None:
        """Save state to file."""
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self._to_dict(), f, indent=2, ensure_ascii=False)
    
    def _to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "researcher_id": self.researcher_id,
            "session_id": self.session_id,
            "stage": self.stage,
            "protocol_version": self.protocol_version,
            "decisions": [d.to_dict() for d in self.decisions],
            "ai_suggestions": [s.to_dict() for s in self.ai_suggestions],
            "stats": self.get_progress()
        }
    
    @classmethod
    def load(cls, output_path: str) -> Optional["ReviewerState"]:
        """Load state from file."""
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            state = cls(
                researcher_id=data["researcher_id"],
                session_id=data["session_id"],
                stage=data.get("stage", "ec")
            )
            
            state.decisions = [
                DecisionRecord.from_dict(d) for d in data.get("decisions", [])
            ]
            
            return state
        except FileNotFoundError:
            return None


@dataclass
class ReviewerConsensus:
    """Consensus resolution for multiple reviewers."""
    article_id: str
    session_id: str
    stage: str
    
    decisions: Dict[str, str] = field(default_factory=dict)
    
    consensus_decision: str = ""
    resolution_notes: str = ""
    resolved_by: str = ""
    resolved_at: str = ""
    
    def add_decision(self, researcher_id: str, decision: str) -> None:
        """Add reviewer decision."""
        self.decisions[researcher_id] = decision
    
    def compute_consensus(self) -> str:
        """Compute consensus decision."""
        if len(self.decisions) < 2:
            return list(self.decisions.values())[0] if self.decisions else "needs_decision"
        
        decisions = list(self.decisions.values())
        
        if len(set(decisions)) == 1:
            self.consensus_decision = decisions[0]
        elif "exclude" in decisions:
            self.consensus_decision = "exclude"
        elif "needs_discussion" in decisions:
            self.consensus_decision = "needs_discussion"
        else:
            self.consensus_decision = "include"
        
        return self.consensus_decision
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)


def compute_agreement_rate(consensus_list: List[ReviewerConsensus]) -> Dict[str, float]:
    """Compute inter-rater agreement metrics."""
    if not consensus_list:
        return {"agreement_rate": 0.0, "kappa": 0.0}
    
    total_articles = len(consensus_list)
    
    agreement_count = sum(
        1 for c in consensus_list 
        if len(set(c.decisions.values())) == 1
    )
    
    agreement_rate = agreement_count / total_articles if total_articles > 0 else 0.0
    
    return {
        "agreement_rate": agreement_rate,
        "total_articles": total_articles,
        "agreed": agreement_count,
        "disagreed": total_articles - agreement_count
    }