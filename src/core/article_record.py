"""
APOLLO Article Record Data Structures

Canonical datatype definitions for article records used throughout the
processing pipeline. These dataclasses are imported by both atlas_processor
and screening_session.
"""
from dataclasses import dataclass, field
from typing import Dict, Optional, Any


@dataclass
class EligibilityDecision:
    """EC/IC decision result."""
    decision: str
    criterion: str
    reason: str
    
    def to_display(self) -> str:
        if self.decision == "pending":
            return "PENDING"
        return self.criterion if self.decision == "exclude" else "NO"


@dataclass
class QualityDecision:
    """QC scoring result."""
    scores: Dict[str, float]
    total_score: float
    decision: str
    literature_type: str
    
    def to_display(self) -> str:
        if self.decision == "pending":
            return "PENDING"
        if not self.scores:
            return "NO"
        return f"{self.total_score}/4"
    
    def to_category(self) -> str:
        if self.decision == "pending":
            return "PENDING"
        if not self.scores:
            return "NO"
        if self.total_score >= 2.0:
            return "PASS"
        return "FAIL"


@dataclass
class ArticleRecord:
    """Complete article record with all decisions."""
    library: str = ""
    global_id: str = ""
    local_id: str = ""
    title: str = ""
    abstract: str = ""
    keywords: str = ""
    authors: str = ""
    year: Optional[int] = None
    
    posicao: str = ""
    url: str = ""
    source_file: str = ""
    
    literature_type: str = ""
    ec_decision: str = ""
    ic_decision: str = ""
    qc_score: str = ""
    final_decision: str = ""
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    _llm_reasoning: Optional[Dict] = None