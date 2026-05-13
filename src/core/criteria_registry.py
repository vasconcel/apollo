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
    "EC3": "Not peer-reviewed - WL sources must be peer-reviewed academic publications",
    "EC4": "Duplicate publication (by Global_ID)"
}

IC_DESCRIPTIONS: Dict[str, str] = {
    "IC1": "Addresses recruitment/selection practices in software organizations",
    "IC2": "Reports empirical findings (qualitative or quantitative)",
    "IC3": "Focuses on software industry context"
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
