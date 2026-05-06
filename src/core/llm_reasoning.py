"""
APOLLO LLM Reasoning Layer
Provides explainable decisions for EC/IC/QC using structured reasoning
"""
import json
import os
from typing import Dict, Optional, Any


DEFAULT_EC_CRITERIA = {
    "EC-1": "Not empirical software engineering research",
    "EC-2": "Published before 2015",
    "EC-3": "Not peer-reviewed (for WL)",
    "EC-4": "Duplicate publication"
}

DEFAULT_IC_CRITERIA = {
    "IC-1": "Addresses recruitment/selection practices in software organizations",
    "IC-2": "Reports empirical findings (qualitative or quantitative)",
    "IC-3": "Focuses on software industry context"
}

WL_QUALITY_CRITERIA = {
    "WL-Q1": "Are the research aims and the SE R&S context clearly stated?",
    "WL-Q2": "Is the research methodology adequately described and appropriate?",
    "WL-Q3": "Are the findings clearly supported by the collected data?",
    "WL-Q4": "Does the study adequately discuss its limitations or threats to validity?"
}

GL_QUALITY_CRITERIA = {
    "GL-Q1": "Is the author's expertise or organizational context explicitly stated?",
    "GL-Q2": "Is the source of experience transparent (e.g., specific hiring cycle, personal narrative)?",
    "GL-Q3": "Are the claims supported by operational artifacts rather than mere opinion?",
    "GL-Q4": "Does the source provide insights beyond generic employer marketing?"
}


def get_llm_client():
    """Initialize LLM client (Groq or OpenAI)."""
    api_key = os.environ.get("GROQ_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    
    try:
        if os.environ.get("GROQ_API_KEY"):
            from groq import Groq
            return Groq(api_key=api_key)
        else:
            import openai
            return openai.OpenAI(api_key=api_key)
    except ImportError:
        return None


def generate_ec_rationale(
    article_title: str,
    article_abstract: str,
    year: Optional[int],
    literature_type: str,
    ec_decision: str,
    ec_reason: Optional[str] = None,
    criteria: Dict[str, str] = None
) -> Dict[str, Any]:
    """
    Generate structured rationale for EC (Exclusion Criteria) decision.
    
    Returns JSON-compatible structure with:
    - evidence_used: list of text snippets analyzed
    - criteria_applied: which criteria were evaluated
    - reasoning_trace: structured reasoning steps
    """
    criteria = criteria or DEFAULT_EC_CRITERIA
    
    client = get_llm_client()
    
    if not client:
        return {
            "decision": ec_decision,
            "reason": ec_reason or "Manual decision",
            "evidence_used": [],
            "criteria_applied": [],
            "reasoning_trace": [{"step": "manual", "conclusion": ec_decision}],
            "model": "none",
            "confidence": None
        }
    
    prompt = f"""You are an expert systematic review assistant. Analyze this article for EXCLUSION CRITERIA (EC).

Article Title: {article_title}
Year: {year or 'Unknown'}
Type: {literature_type}
Abstract: {article_abstract[:1000] if article_abstract else 'No abstract available'}

Exclusion Criteria to evaluate:
{chr(10).join([f"- {k}: {v}" for k, v in criteria.items()])}

Task: Determine if article should be EXCLUDED based on EC. Provide structured JSON output:

{{
  "decision": "include" or "exclude",
  "primary_reason": "Which EC criterion triggered exclusion (if any)",
  "evidence_used": ["key phrases from title/abstract that support decision"],
  "criteria_applied": ["list of EC codes evaluated"],
  "reasoning_trace": [
    {{"step": "1", "criterion": "EC-X", "analysis": "...", "conclusion": "pass/fail"}},
    ...
  ],
  "confidence": 0.0-1.0,
  "ambiguity_flags": ["any unclear aspects"]
}}

Return ONLY valid JSON, no additional text."""

    try:
        if hasattr(client, 'chat'):
            response = client.chat.completions.create(
                model="llama-3.1-70b-versatile" if hasattr(client, 'api_key') and 'groq' in str(type(client)) else "gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=1500
            )
            content = response.choices[0].message.content
            
            parsed = json.loads(content.strip().strip("```json").strip("```"))
            
            return {
                "decision": parsed.get("decision", ec_decision),
                "reason": parsed.get("primary_reason", ec_reason),
                "evidence_used": parsed.get("evidence_used", []),
                "criteria_applied": parsed.get("criteria_applied", list(criteria.keys())),
                "reasoning_trace": parsed.get("reasoning_trace", []),
                "model": "llm",
                "confidence": parsed.get("confidence"),
                "ambiguity_flags": parsed.get("ambiguity_flags", [])
            }
    except Exception as e:
        return {
            "decision": ec_decision,
            "reason": ec_reason or f"LLM error: {str(e)[:50]}",
            "evidence_used": [],
            "criteria_applied": list(criteria.keys()),
            "reasoning_trace": [{"step": "error", "conclusion": ec_decision}],
            "model": "error",
            "confidence": None
        }
    
    return {
        "decision": ec_decision,
        "reason": ec_reason or "Manual decision",
        "evidence_used": [],
        "criteria_applied": [],
        "reasoning_trace": [{"step": "fallback", "conclusion": ec_decision}],
        "model": "none",
        "confidence": None
    }


def generate_ic_rationale(
    article_title: str,
    article_abstract: str,
    year: Optional[int],
    literature_type: str,
    ic_decision: str,
    ic_reason: Optional[str] = None,
    criteria: Dict[str, str] = None,
    ec_passed: bool = True
) -> Dict[str, Any]:
    """
    Generate structured rationale for IC (Inclusion Criteria) decision.
    """
    criteria = criteria or DEFAULT_IC_CRITERIA
    
    client = get_llm_client()
    
    if not client:
        return {
            "decision": ic_decision,
            "reason": ic_reason or "Manual decision",
            "evidence_used": [],
            "criteria_applied": [],
            "reasoning_trace": [{"step": "manual", "conclusion": ic_decision}],
            "model": "none",
            "confidence": None
        }
    
    prompt = f"""You are an expert systematic review assistant. Analyze this article for INCLUSION CRITERIA (IC).

Article Title: {article_title}
Year: {year or 'Unknown'}
Type: {literature_type}
EC Status: {'Passed' if ec_passed else 'Failed'}
Abstract: {article_abstract[:1000] if article_abstract else 'No abstract available'}

Inclusion Criteria to evaluate:
{chr(10).join([f"- {k}: {v}" for k, v in criteria.items()])}

Task: Determine if article should be INCLUDED based on IC (relevance to SE R&S domain). Provide structured JSON:

{{
  "decision": "include" or "exclude",
  "primary_reason": "Which IC criterion justifies inclusion OR exclusion",
  "evidence_used": ["key phrases showing relevance to SE R&S"],
  "criteria_applied": ["list of IC codes evaluated"],
  "reasoning_trace": [
    {{"step": "1", "criterion": "IC-X", "analysis": "...", "conclusion": "pass/fail"}},
    ...
  ],
  "relevance_score": 0.0-1.0,
  "ambiguity_flags": ["any unclear aspects"]
}}

Return ONLY valid JSON."""

    try:
        if hasattr(client, 'chat'):
            response = client.chat.completions.create(
                model="llama-3.1-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=1500
            )
            content = response.choices[0].message.content
            
            parsed = json.loads(content.strip().strip("```json").strip("```"))
            
            return {
                "decision": parsed.get("decision", ic_decision),
                "reason": parsed.get("primary_reason", ic_reason),
                "evidence_used": parsed.get("evidence_used", []),
                "criteria_applied": parsed.get("criteria_applied", list(criteria.keys())),
                "reasoning_trace": parsed.get("reasoning_trace", []),
                "relevance_score": parsed.get("relevance_score"),
                "model": "llm",
                "confidence": parsed.get("relevance_score"),
                "ambiguity_flags": parsed.get("ambiguity_flags", [])
            }
    except Exception as e:
        return {
            "decision": ic_decision,
            "reason": ic_reason or f"LLM error: {str(e)[:50]}",
            "evidence_used": [],
            "criteria_applied": list(criteria.keys()),
            "reasoning_trace": [],
            "model": "error",
            "confidence": None
        }
    
    return {
        "decision": ic_decision,
        "reason": ic_reason or "Manual decision",
        "evidence_used": [],
        "criteria_applied": [],
        "reasoning_trace": [],
        "model": "none",
        "confidence": None
    }


def generate_qc_rationale(
    article_title: str,
    article_abstract: str,
    literature_type: str,
    scores: Dict[str, float],
    total_score: float,
    decision: str,
    threshold: float = 2.0
) -> Dict[str, Any]:
    """
    Generate structured rationale for QC (Quality Criteria) scoring.
    """
    if literature_type == "WL":
        criteria = WL_QUALITY_CRITERIA
    else:
        criteria = GL_QUALITY_CRITERIA
    
    client = get_llm_client()
    
    if not client:
        return {
            "scores": scores,
            "total_score": total_score,
            "decision": decision,
            "criteria_justification": {},
            "reasoning_trace": [{"step": "manual", "conclusion": decision}],
            "model": "none"
        }
    
    score_details = "\n".join([f"- {k}: {scores.get(k, 0)} ({criteria.get(k, '')[:50]}...)" for k in criteria.keys()])
    
    prompt = f"""You are an expert systematic review assistant. Analyze this article's QUALITY ASSESSMENT.

Article Title: {article_title}
Type: {literature_type}
Abstract: {article_abstract[:1000] if article_abstract else 'No abstract'}

Scores:
{score_details}

Total Score: {total_score}/{len(criteria)} (Threshold: {threshold})

Task: Provide structured JSON for QC justification:

{{
  "scores": {{"WL-Q1": 1.0, ...}},
  "total_score": float,
  "decision": "include" or "exclude",
  "criteria_justification": {{
    "WL-Q1": {{"score": 1.0, "evidence": "text supporting score", "reasoning": "..."}},
    ...
  }},
  "reasoning_trace": [
    {{"step": "1", "criterion": "WL-Q1", "analysis": "...", "justification": "..."}},
    ...
  ],
  "threshold_compliance": "pass/fail with explanation",
  "strengths": ["list of quality strengths"],
  "weaknesses": ["list of quality weaknesses"],
  "confidence": 0.0-1.0
}}

Return ONLY valid JSON."""

    try:
        if hasattr(client, 'chat'):
            response = client.chat.completions.create(
                model="llama-3.1-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=2000
            )
            content = response.choices[0].message.content
            
            parsed = json.loads(content.strip().strip("```json").strip("```"))
            
            return {
                "scores": parsed.get("scores", scores),
                "total_score": parsed.get("total_score", total_score),
                "decision": parsed.get("decision", decision),
                "criteria_justification": parsed.get("criteria_justification", {}),
                "reasoning_trace": parsed.get("reasoning_trace", []),
                "threshold_compliance": parsed.get("threshold_compliance", f"{'pass' if total_score >= threshold else 'fail'}"),
                "strengths": parsed.get("strengths", []),
                "weaknesses": parsed.get("weaknesses", []),
                "model": "llm",
                "confidence": parsed.get("confidence")
            }
    except Exception as e:
        return {
            "scores": scores,
            "total_score": total_score,
            "decision": decision,
            "criteria_justification": {},
            "reasoning_trace": [{"step": "error", "error": str(e)[:100]}],
            "model": "error"
        }
    
    return {
        "scores": scores,
        "total_score": total_score,
        "decision": decision,
        "criteria_justification": {},
        "reasoning_trace": [],
        "model": "none"
    }


def detect_ambiguity(rationale: Dict[str, Any]) -> bool:
    """Check if LLM rationale indicates ambiguity in decision."""
    if not rationale:
        return False
    
    ambiguity_flags = rationale.get("ambiguity_flags", [])
    confidence = rationale.get("confidence")
    
    if confidence is not None and confidence < 0.7:
        return True
    
    if ambiguity_flags and len(ambiguity_flags) > 0:
        return True
    
    return False