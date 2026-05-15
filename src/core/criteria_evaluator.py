"""
APOLLO Criteria Evaluator - EC/IC Evaluation Logic

Default deterministic evaluation logic for ATLAS processing.
Used as fallback when no protocol is provided. Separated from
atlas_processor for independent testing.
"""
from typing import Optional
from src.core.criteria_registry import (
    SE_KEYWORDS, RECRUITMENT_KEYWORDS, EMPIRICAL_KEYWORDS, INDUSTRY_KEYWORDS,
    EC_DESCRIPTIONS, IC_DESCRIPTIONS
)


class EligibilityDecision:
    """EC/IC decision result."""
    def __init__(self, decision: str, criterion: str, reason: str):
        self.decision = decision
        self.criterion = criterion
        self.reason = reason
    
    def to_display(self) -> str:
        if self.decision == "pending":
            return "PENDING"
        return self.criterion if self.decision == "exclude" else "NO"


class ExclusionCriteria:
    CRITERIA = EC_DESCRIPTIONS
    ENABLE_DUPLICATE_CHECK = False
    
    @classmethod
    def evaluate(cls, title: str, abstract: str, year: Optional[int] = None,
                 is_wl: bool = True, is_duplicate: bool = False,
                 duplicate_flag: str = "") -> EligibilityDecision:
        
        text = f"{title} {abstract}".lower()
        
        if year and year < 2015:
            return EligibilityDecision("exclude", "EC2", f"Published in {year}, before 2015")
        
        if not any(kw in text for kw in SE_KEYWORDS):
            return EligibilityDecision("exclude", "EC1", "No software engineering context detected")
        
        if cls.ENABLE_DUPLICATE_CHECK and is_duplicate:
            return EligibilityDecision("exclude", "EC4", "Duplicate Global_ID detected")
        
        if duplicate_flag and duplicate_flag.lower() in ["true", "yes", "1", "duplicate"]:
            return EligibilityDecision("exclude", "EC4", f"ATLAS marked as duplicate: {duplicate_flag}")
        
        if is_wl and (not abstract or len(abstract.strip()) < 50):
            return EligibilityDecision("exclude", "EC3", "No sufficient abstract for peer-review assessment")
        
        return EligibilityDecision("include", "NO", "Passed all exclusion criteria")


class InclusionCriteria:
    CRITERIA = IC_DESCRIPTIONS
    
    @classmethod
    def evaluate(cls, title: str, abstract: str) -> EligibilityDecision:
        text = f"{title} {abstract}".lower()
        
        has_recruitment = any(kw in text for kw in RECRUITMENT_KEYWORDS)
        has_empirical = any(kw in text for kw in EMPIRICAL_KEYWORDS)
        has_industry = any(kw in text for kw in INDUSTRY_KEYWORDS)
        
        if has_recruitment:
            if has_empirical or has_industry:
                return EligibilityDecision("include", "NO", "Addresses SE R&S with empirical findings or industry context")
            else:
                return EligibilityDecision("exclude", "IC2", "Addresses recruitment but lacks empirical context")
        
        if has_industry and has_empirical:
            return EligibilityDecision("include", "NO", "Empirical SE research relevant to scope")

        return EligibilityDecision("exclude", "IC1", "Does not address recruitment/selection in software context")


class QualityDecision:
    """QC decision result."""
    def __init__(self, scores: dict, total_score: float, decision: str, literature_type: str = "WL"):
        self.scores = scores
        self.total_score = total_score
        self.decision = decision
        self.literature_type = literature_type

    def to_display(self) -> str:
        return f"{self.total_score:.1f}/8.0" if self.decision == "include" else "N/A"


class QualityCriteria:
    """Quality assessment criteria - stub implementation."""

    WL_QUESTIONS = {
        "WL-Q1": "Are the research aims and the SE R&S context clearly stated?",
        "WL-Q2": "Is the research methodology adequately described?",
        "WL-Q3": "Are the findings clearly supported by the collected data?",
        "WL-Q4": "Does the study adequately discuss its limitations?"
    }

    GL_QUESTIONS = {
        "GL-Q1": "Is the author's expertise or organizational context stated?",
        "GL-Q2": "Is the source of experience transparent?",
        "GL-Q3": "Are claims supported by operational artifacts?",
        "GL-Q4": "Does the source provide insights beyond generic marketing?"
    }

    THRESHOLD = 2.0

    @classmethod
    def evaluate(cls, title: str, abstract: str, literature_type: str = "WL") -> QualityDecision:
        """
        Evaluate quality criteria - stub returns pending.

        Note: Full QC implementation requires protocol-driven scoring.
        This stub provides basic structure for protocol integration.
        """
        return QualityDecision(
            scores={"Q1": 0.0, "Q2": 0.0, "Q3": 0.0, "Q4": 0.0},
            total_score=0.0,
            decision="pending",
            literature_type=literature_type
        )