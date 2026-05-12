"""
APOLLO Criteria Registry - SINGLE CANONICAL SOURCE

This module is the ONLY source of truth for all screening criteria keywords.
No keyword literals are allowed in any other module.

BEFORE this file existed, keywords were duplicated across:
- atlas_processor.py
- protocol_engine.py
- llm_assistant.py
- llm_reasoning.py

All consuming modules MUST import from here. No duplicated literals allowed.

Audit (BEFORE):
- atlas_processor.py:213-214,241-243 -> SE, recruitment, empirical, industry keywords
- protocol_engine.py:258-267,308-309,331-340 -> SAME keyword sets duplicated
- llm_assistant.py:148-152 -> criterion descriptions
- llm_reasoning.py:10-35 -> criterion descriptions

Audit (AFTER):
All keywords consumed from this registry only.
"""
from typing import Dict, List


SE_KEYWORDS: List[str] = [
    "software", "software engineering", "programming", "development",
    "code", "developer", "software engineer", "agile", "devops"
]

RECRUITMENT_KEYWORDS: List[str] = [
    "recruit", "hire", "hiring", "selection", "talent",
    "interview", "hiring process", "recruitment"
]

EMPIRICAL_KEYWORDS: List[str] = [
    "empirical", "study", "research", "survey", "case study",
    "experiment", "quantitative", "qualitative", "results", "findings"
]

INDUSTRY_KEYWORDS: List[str] = [
    "software", "software industry", "tech company", "IT company",
    "software development", "software team", "developer", "programming"
]

EC_DESCRIPTIONS: Dict[str, str] = {
    "EC1": "Not empirical software engineering research",
    "EC2": "Published before 2015",
    "EC3": "Not peer-reviewed (for WL)",
    "EC4": "Duplicate publication (by Global_ID)"
}

IC_DESCRIPTIONS: Dict[str, str] = {
    "IC1": "Addresses recruitment/selection practices in software organizations",
    "IC2": "Reports empirical findings (qualitative or quantitative)",
    "IC3": "Focuses on software industry context"
}

WL_QC_DESCRIPTIONS: Dict[str, str] = {
    "WL-Q1": "Are the research aims and the SE R&S context clearly stated?",
    "WL-Q2": "Is the research methodology adequately described and appropriate?",
    "WL-Q3": "Are the findings clearly supported by the collected data?",
    "WL-Q4": "Does the study adequately discuss its limitations or threats to validity?"
}

GL_QC_DESCRIPTIONS: Dict[str, str] = {
    "GL-Q1": "Is the author's expertise or organizational context explicitly stated?",
    "GL-Q2": "Is the source of experience transparent (e.g., specific hiring cycle, personal narrative)?",
    "GL-Q3": "Are the claims supported by operational artifacts rather than mere opinion?",
    "GL-Q4": "Does the source provide insights beyond generic employer marketing?"
}


WL_QC_SCORING_KEYWORDS: Dict[str, Dict[str, List[str]]] = {
    "WL-Q1": {
        "full": ["aim", "objective", "purpose", "research question",
                 "goal", "context", "motivation", "investigate", "explore", "examine"],
        "partial": []
    },
    "WL-Q2": {
        "full": ["methodology", "method", "approach", "design", "procedure",
                 "technique", "survey", "case study", "experiment", "interview",
                 "qualitative", "quantitative"],
        "partial": []
    },
    "WL-Q3": {
        "full": ["result", "finding", "conclusion", "show", "demonstrate",
                 "indicate", "reveal"],
        "partial": ["discussion"]
    },
    "WL-Q4": {
        "full": ["limitation", "threat", "validity", "reliability",
                 "constraint", "future work"],
        "partial": ["discussion"]
    }
}

GL_QC_SCORING_KEYWORDS: Dict[str, Dict[str, List[str]]] = {
    "GL-Q1": {
        "full": ["author", "expert", "experience", "years", "background",
                 "senior", "lead", "manager"],
        "partial": ["we", "our", "based on"]
    },
    "GL-Q2": {
        "full": ["company", "organization", "team", "department",
                 "size", "location", "industry"],
        "partial": ["case", "example"]
    },
    "GL-Q3": {
        "full": ["data", "metric", "statistic", "figure", "table",
                 "example", "artifact", "tool", "process"],
        "partial": ["show", "result", "experience"]
    },
    "GL-Q4": {
        "full": ["challenge", "difficulty", "problem", "issue",
                 "lesson", "learn", "recommend"],
        "partial": ["benefit", "advantage", "feature"]
    }
}


def evaluate_se_context(text: str) -> bool:
    """Check if text contains SE context."""
    text_lower = text.lower() if text else ""
    return any(kw in text_lower for kw in SE_KEYWORDS)


def evaluate_recruitment(text: str) -> bool:
    """Check if text contains recruitment keywords."""
    text_lower = text.lower() if text else ""
    return any(kw in text_lower for kw in RECRUITMENT_KEYWORDS)


def evaluate_empirical(text: str) -> bool:
    """Check if text contains empirical keywords."""
    text_lower = text.lower() if text else ""
    return any(kw in text_lower for kw in EMPIRICAL_KEYWORDS)


def evaluate_industry(text: str) -> bool:
    """Check if text contains industry keywords."""
    text_lower = text.lower() if text else ""
    return any(kw in text_lower for kw in INDUSTRY_KEYWORDS)


def evaluate_wl_qc_score(criterion: str, text: str) -> float:
    """Evaluate WL QC criterion score (0.0, 0.5, or 1.0)."""
    if criterion not in WL_QC_SCORING_KEYWORDS:
        return 0.0
    text_lower = text.lower() if text else ""
    scoring = WL_QC_SCORING_KEYWORDS[criterion]
    if any(kw in text_lower for kw in scoring["full"]):
        return 1.0
    if any(kw in text_lower for kw in scoring["partial"]):
        return 0.5
    return 0.0


def evaluate_gl_qc_score(criterion: str, text: str) -> float:
    """Evaluate GL QC criterion score (0.0, 0.5, or 1.0)."""
    if criterion not in GL_QC_SCORING_KEYWORDS:
        return 0.0
    text_lower = text.lower() if text else ""
    scoring = GL_QC_SCORING_KEYWORDS[criterion]
    if any(kw in text_lower for kw in scoring["full"]):
        return 1.0
    if any(kw in text_lower for kw in scoring["partial"]):
        return 0.5
    return 0.0
