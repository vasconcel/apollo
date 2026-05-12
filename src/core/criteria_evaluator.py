"""
APOLLO Criteria Evaluator - EC/IC/QC Evaluation Logic

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


class QualityDecision:
    """QC scoring result."""
    def __init__(self, scores: dict, total_score: float, decision: str, literature_type: str):
        self.scores = scores
        self.total_score = total_score
        self.decision = decision
        self.literature_type = literature_type
    
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


class QualityCriteria:
    WL_CRITERIA = {
        "WL-Q1": "Are the research aims and the SE R&S context clearly stated?",
        "WL-Q2": "Is the research methodology adequately described and appropriate?",
        "WL-Q3": "Are the findings clearly supported by the collected data?",
        "WL-Q4": "Does the study adequately discuss its limitations or threats to validity?"
    }
    
    GL_CRITERIA = {
        "GL-Q1": "Is the author's expertise or organizational context explicitly stated?",
        "GL-Q2": "Is the source of experience transparent?",
        "GL-Q3": "Are the claims supported by operational artifacts rather than mere opinion?",
        "GL-Q4": "Does the source provide insights beyond generic employer marketing?"
    }
    
    THRESHOLD = 2.0
    
    @classmethod
    def evaluate(cls, title: str, abstract: str, literature_type: str) -> QualityDecision:
        text = f"{title} {abstract}".lower()
        criteria = cls.WL_CRITERIA if literature_type == "WL" else cls.GL_CRITERIA
        scores = {}
        
        for criterion, description in criteria.items():
            scores[criterion] = cls._evaluate_criterion(criterion, text)
        
        total = sum(scores.values())
        decision = "include" if total >= cls.THRESHOLD else "exclude"
        
        return QualityDecision(scores=scores, total_score=total, decision=decision, literature_type=literature_type)
    
    @classmethod
    def _evaluate_criterion(cls, criterion: str, text: str) -> float:
        if criterion == "WL-Q1": return 1.0 if any(k in text for k in ["aim", "objective", "purpose"]) else 0.0
        if criterion == "WL-Q2": return 1.0 if any(k in text for k in ["methodology", "method", "approach"]) else 0.0
        if criterion == "WL-Q3": return 1.0 if any(k in text for k in ["result", "finding", "show"]) else 0.0
        if criterion == "WL-Q4": return 1.0 if any(k in text for k in ["limitation", "threat"]) else 0.0
        
        if criterion == "GL-Q1": return 1.0 if any(k in text for k in ["author", "expert", "experience"]) else 0.0
        if criterion == "GL-Q2": return 1.0 if any(k in text for k in ["company", "organization"]) else 0.0
        if criterion == "GL-Q3": return 1.0 if any(k in text for k in ["data", "metric", "artifact"]) else 0.0
        if criterion == "GL-Q4": return 1.0 if any(k in text for k in ["challenge", "difficulty"]) else 0.0
        return 0.0