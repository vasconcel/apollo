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
    """
    Complete article record with all decisions.
    
    Metadata Grounding v2.0:
    - All raw ATLAS row values preserved in metadata dict
    - year and authors fields prevent hallucination
    - source_sheet tracks origin (WL/GL) for separation
    """
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
    source_sheet: str = ""
    ec_decision: str = ""
    ic_decision: str = ""
    qc_score: str = ""
    final_decision: str = ""
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    _llm_reasoning: Optional[Dict] = None
    
    def has_year(self) -> bool:
        """Check if year is available - prevents hallucination."""
        return self.year is not None
    
    def has_authors(self) -> bool:
        """Check if authors field is populated."""
        return bool(self.authors and self.authors.strip() and self.authors.strip() != "nan")
    
    def get_year_display(self) -> str:
        """Get year as string or NOT AVAILABLE indicator."""
        return str(self.year) if self.has_year() else "NOT PROVIDED"
    
    def get_authors_display(self) -> str:
        """Get authors or NOT AVAILABLE indicator."""
        return self.authors if self.has_authors() else "NOT PROVIDED"
    
    def get_metadata_completeness(self) -> str:
        """Assess metadata completeness for LLM grounding."""
        has_title = bool(self.title and self.title.strip() and self.title != "nan")
        has_abstract = bool(self.abstract and len(str(self.abstract).strip()) > 10 and self.abstract != "nan")
        
        if self.literature_type == "WL":
            if has_title and has_abstract and self.has_year():
                return "complete"
            elif has_title:
                return "partial"
        else:
            if has_title and self.has_year():
                return "complete"
            elif has_title:
                return "partial"
        return "minimal"
    
    def is_gl(self) -> bool:
        """Check if this is Grey Literature."""
        return self.literature_type == "GL"
    
    def is_wl(self) -> bool:
        """Check if this is White Literature."""
        return self.literature_type == "WL"