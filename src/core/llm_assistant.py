"""
APOLLO LLM Assistant - Advisory Suggestions
Provides LLM-powered suggestions for human decision-making
(ADVISORY ONLY - researcher makes final decisions)
"""
import json
import os
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field


@dataclass
class AdvisorySuggestion:
    """LLM advisory suggestion for a stage."""
    stage: str  # "ec", "ic", "qc"
    decision: str
    confidence: float
    justification: str
    
    triggered_criteria: Dict[str, str] = field(default_factory=dict)
    evidence: List[str] = field(default_factory=list)
    ambiguity_flags: List[str] = field(default_factory=list)
    
    def to_display(self) -> str:
        """Format for UI display."""
        conf = int(self.confidence * 100)
        return f"{self.decision.upper()} ({conf}% confidence)"
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "stage": self.stage,
            "decision": self.decision,
            "confidence": self.confidence,
            "justification": self.justification,
            "triggered_criteria": self.triggered_criteria,
            "evidence": self.evidence,
            "ambiguity_flags": self.ambiguity_flags
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "AdvisorySuggestion":
        """Create from dictionary."""
        return cls(**data)


class LLMAssistant:
    """
    LLM Assistant for advisory suggestions.
    
    KEY PRINCIPLE: Advisory ONLY
    - Provides suggestions with confidence scores
    - Gives rationale and criteria support
    - Researcher makes FINAL decision
    - All suggestions are logged for audit
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self._client = None
        self._api_key = api_key or os.environ.get("GROQ_API_KEY") or os.environ.get("OPENAI_API_KEY")
        
        if self._api_key:
            self._init_client()
    
    def _init_client(self) -> None:
        """Initialize LLM client."""
        if os.environ.get("GROQ_API_KEY"):
            try:
                from groq import Groq
                self._client = Groq(api_key=self._api_key)
                # Use available Groq model (llama-3.3-70b-versatile is current)
                self._model = "llama-3.3-70b-versatile"
            except ImportError:
                pass
        else:
            try:
                import openai
                self._client = openai.OpenAI(api_key=self._api_key)
                self._model = "gpt-4o-mini"
            except ImportError:
                pass
    
    def is_available(self) -> bool:
        """Check if LLM is available."""
        return self._client is not None
    
    def suggest_ec(
        self,
        title: str,
        abstract: str,
        literature_type: str = "WL",
        year: Optional[int] = None,
        protocol_criteria: Optional[Dict[str, str]] = None
    ) -> AdvisorySuggestion:
        """
        Get EC stage advisory suggestion.
        
        Args:
            title: Article title
            abstract: Article abstract
            literature_type: "WL" or "GL"
            year: Publication year
            protocol_criteria: Researcher-defined EC criteria (uses defaults if None)
        
        Returns suggestion with trigger criteria for researcher review.
        """
        criteria = protocol_criteria or {
            "EC1": "Not empirical software engineering research",
            "EC2": "Published before 2015",
            "EC3": "Not peer-reviewed (for WL)",
            "EC4": "Duplicate publication (by Global_ID)"
        }
        
        prompt = f"""You are an expert systematic review assistant. Analyze this article for EXCLUSION CRITERIA (EC).

Article Title: {title}
Year: {year or 'Unknown'}
Type: {literature_type}
Abstract: {abstract[:800] if abstract else 'No abstract available'}

ACTIVE EC CRITERIA:
{chr(10).join([f"- {k}: {v}" for k, v in criteria.items()])}

Task: Determine if article should be EXCLUDED. Provide JSON only:

{{
  "decision": "include" or "exclude",
  "confidence": 0.0-1.0,
  "justification": "2-3 sentence explanation",
  "triggered_criteria": {{"EC1": "reason if triggered, empty if not"}},
  "evidence": ["key phrases from title/abstract supporting decision"],
  "ambiguity_flags": ["any unclear aspects or borderline cases"]
}}

Return ONLY valid JSON."""

        return self._call_llm(prompt, "ec", literature_type)
    
    def suggest_ic(
        self,
        title: str,
        abstract: str,
        literature_type: str = "WL",
        protocol_criteria: Optional[Dict[str, str]] = None
    ) -> AdvisorySuggestion:
        """
        Get IC stage advisory suggestion.
        
        Args:
            title: Article title
            abstract: Article abstract
            literature_type: "WL" or "GL"
            protocol_criteria: Researcher-defined IC criteria (uses defaults if None)
        """
        criteria = protocol_criteria or {
            "IC1": "Addresses recruitment/selection practices in software organizations",
            "IC2": "Reports empirical findings (qualitative or quantitative)",
            "IC3": "Focuses on software industry context"
        }
        
        prompt = f"""You are an expert systematic review assistant. Analyze this article for INCLUSION CRITERIA (IC).

Article Title: {title}
Type: {literature_type}
Abstract: {abstract[:800] if abstract else 'No abstract available'}

ACTIVE IC CRITERIA:
{chr(10).join([f"- {k}: {v}" for k, v in criteria.items()])}

Task: Determine if article is RELEVANT to SE Recruitment & Selection research. Provide JSON:

{{
  "decision": "include" or "exclude",
  "confidence": 0.0-1.0,
  "justification": "2-3 sentence explanation",
  "triggered_criteria": {{"IC1": "reason"}},
  "evidence": ["key phrases showing relevance"],
  "ambiguity_flags": ["any unclear aspects"]
}}

Return ONLY valid JSON."""

        return self._call_llm(prompt, "ic", literature_type)
    
    def suggest_qc(
        self,
        title: str,
        abstract: str,
        literature_type: str = "WL",
        protocol_criteria: Optional[Dict[str, str]] = None
    ) -> AdvisorySuggestion:
        """
        Get QC stage advisory suggestion.
        
        Args:
            title: Article title
            abstract: Article abstract  
            literature_type: "WL" or "GL"
            protocol_criteria: Researcher-defined QC criteria (uses defaults if None)
        """
        if literature_type == "WL":
            criteria = protocol_criteria or {
                "WL-Q1": "Are the research aims and the SE R&S context clearly stated?",
                "WL-Q2": "Is the research methodology adequately described and appropriate?",
                "WL-Q3": "Are the findings clearly supported by the collected data?",
                "WL-Q4": "Does the study adequately discuss its limitations or threats to validity?"
            }
        else:
            criteria = protocol_criteria or {
                "GL-Q1": "Is the author's expertise or organizational context explicitly stated?",
                "GL-Q2": "Is the source of experience transparent (e.g., specific hiring cycle)?",
                "GL-Q3": "Are the claims supported by operational artifacts rather than mere opinion?",
                "GL-Q4": "Does the source provide insights beyond generic employer marketing?"
            }
        
        prompt = f"""You are an expert systematic review assistant. Analyze this article's QUALITY.

Article Title: {title}
Type: {literature_type}
Abstract: {abstract[:800] if abstract else 'No abstract available'}

ACTIVE {literature_type} QUALITY CRITERIA:
{chr(10).join([f"- {k}: {v}" for k, v in criteria.items()])}

Task: Score each criterion (0, 0.5, or 1.0) and determine if PASS (total >= 2.0). Provide JSON:

{{
  "decision": "include" or "exclude",
  "confidence": 0.0-1.0,
  "justification": "2-3 sentence explanation",
  "triggered_criteria": {{"WL-Q1": 1.0, "WL-Q2": 0.5, ...}},
  "evidence": ["text snippets supporting scores"],
  "ambiguity_flags": ["any weaknesses or gaps in reporting"]
}}

Return ONLY valid JSON."""

        return self._call_llm(prompt, "qc", literature_type)
    
    def _call_llm(
        self,
        prompt: str,
        stage: str,
        literature_type: str
    ) -> AdvisorySuggestion:
        """Call LLM and parse response with robust error handling."""
        if not self._client:
            return self._fallback_suggestion(stage, "No LLM client initialized")
        
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": "You are a systematic review expert. Provide structured JSON responses only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=800
            )
            
            content = response.choices[0].message.content
            
            # Try to parse as JSON
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                # Try stripping markdown code blocks
                content = content.strip().strip("```json").strip("```").strip()
                parsed = json.loads(content)
            
            return AdvisorySuggestion(
                stage=stage,
                decision=parsed.get("decision", "skip"),
                confidence=parsed.get("confidence", 0.5),
                justification=parsed.get("justification", "No justification provided"),
                triggered_criteria=parsed.get("triggered_criteria", {}),
                evidence=parsed.get("evidence", []),
                ambiguity_flags=parsed.get("ambiguity_flags", [])
            )
        
        except json.JSONDecodeError as e:
            return self._fallback_suggestion(stage, f"JSON parse error: {str(e)[:50]}")
        except Exception as e:
            # Generic fallback for any LLM error - never crash workflow
            error_str = str(e)
            if "HTTP" in error_str or "400" in error_str or "404" in error_str or "model" in error_str:
                return self._fallback_suggestion(stage, f"LLM API error: {error_str[:50]}")
            return self._fallback_suggestion(stage, f"Error: {error_str[:50]}")
    
    def _fallback_suggestion(
        self,
        stage: str,
        error: Optional[str] = None
    ) -> AdvisorySuggestion:
        """Return fallback suggestion when LLM unavailable."""
        return AdvisorySuggestion(
            stage=stage,
            decision="skip",
            confidence=0.0,
            justification=f"LLM unavailable: {error}" if error else "LLM not configured",
            triggered_criteria={},
            evidence=[],
            ambiguity_flags=["LLM not available"]
        )


def get_llm_assistant() -> LLMAssistant:
    """Get singleton LLM assistant instance."""
    return LLMAssistant()