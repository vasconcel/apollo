"""
APOLLO Decision Engine - Human-in-the-Loop Orchestration
Orchestrates human screening workflow instead of automatic decisions
"""
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import pandas as pd

from src.core.atlas_processor import (
    ATLASLoader,
    ExclusionCriteria,
    InclusionCriteria,
    QualityCriteria,
    ArticleRecord
)
from src.core.protocol_engine import ProtocolEngine
from src.core.screening_session import (
    ScreeningSession,
    SessionStage,
    ReviewDecision,
    create_session
)
from src.core.reviewer_state import ReviewerState, DecisionChoice


@dataclass
class LLMSuggestion:
    """LLM advisory suggestion for researcher."""
    decision: str
    confidence: float
    justification: str
    criteria_support: Dict[str, str] = field(default_factory=dict)
    
    def to_display(self) -> str:
        """Format for UI display."""
        confidence_pct = int(self.confidence * 100)
        return f"{self.decision.upper()} ({confidence_pct}% confidence)"
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "decision": self.decision,
            "confidence": self.confidence,
            "justification": self.justification,
            "criteria_support": self.criteria_support
        }


@dataclass
class HumanDecision:
    """Researcher's explicit decision."""
    choice: str
    notes: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def is_valid(self) -> bool:
        """Check if decision is valid."""
        return self.choice in ["include", "exclude", "skip", "needs_discussion"]


class HumanDecisionEngine:
    """
    Human-in-the-loop decision engine.
    
    Key design principles:
    - LLM provides ADVISORY suggestions only
    - Researcher makes FINAL explicit decisions
    - All decisions are auditable
    - Supports EC -> IC -> QC staged workflow
    """
    
    def __init__(
        self,
        protocol: Optional[Dict] = None,
        enable_llm_suggestions: bool = True,
        researcher_id: str = "researcher_1"
    ):
        self.protocol = protocol
        self.enable_llm_suggestions = enable_llm_suggestions
        self.researcher_id = researcher_id
        
        self._protocol_engine = ProtocolEngine(protocol) if protocol else None
        
        self.session: Optional[ScreeningSession] = None
        self.reviewer_state: Optional[ReviewerState] = None
        
        self._llm_client = None
        if enable_llm_suggestions:
            self._init_llm_client()
    
    def _init_llm_client(self) -> None:
        """Initialize LLM client."""
        import os
        api_key = os.environ.get("GROQ_API_KEY") or os.environ.get("OPENAI_API_KEY")
        
        if not api_key:
            return
        
        try:
            if os.environ.get("GROQ_API_KEY"):
                from groq import Groq
                self._llm_client = Groq(api_key=api_key)
            else:
                import openai
                self._llm_client = openai.OpenAI(api_key=api_key)
        except ImportError:
            pass
    
    def load_articles(
        self,
        input_path: str
    ) -> Tuple[List[ArticleRecord], List[ArticleRecord]]:
        """Load articles from ATLAS file."""
        wl_df, gl_df = ATLASLoader.load_atlas_file(input_path)
        wl_df = ATLASLoader.normalize_wl_columns(wl_df)
        gl_df = ATLASLoader.normalize_gl_columns(gl_df)
        
        engine = APOLLODecisionEngine(enable_llm_reasoning=False, protocol=self.protocol)
        
        wl_results = engine.process_wl_articles(wl_df)
        gl_results = engine.process_gl_articles(gl_df)
        
        return wl_results, gl_results
    
    def start_session(
        self,
        wl_records: List[ArticleRecord],
        gl_records: List[ArticleRecord],
        stage: str = "ec"
    ) -> ScreeningSession:
        """Start a new screening session."""
        all_records = wl_records + gl_records
        
        self.session = create_session(
            article_records=all_records,
            protocol_version=self.protocol.get("protocol_version", "1.0") if self.protocol else "1.0"
        )
        self.session.stage = stage
        self.session.researcher_id = self.researcher_id
        
        self.reviewer_state = ReviewerState(
            researcher_id=self.researcher_id,
            session_id=self.session.session_id,
            stage=stage
        )
        
        return self.session
    
    def get_current_article(self) -> Optional[Dict]:
        """Get current article with metadata for review."""
        if not self.session:
            return None
        
        article = self.session.get_current_article()
        if not article:
            return None
        
        return {
            "article_id": article.article_id,
            "title": article.title,
            "abstract": article.abstract,
            "metadata": article.metadata,
            "current_stage": self.session.stage,
            "progress": self.session.get_progress()
        }
    
    def get_llm_suggestion(
        self,
        title: str,
        abstract: str,
        stage: str,
        literature_type: str = "WL"
    ) -> Optional[LLMSuggestion]:
        """Get LLM advisory suggestion."""
        if not self.enable_llm_suggestions or not self._llm_client:
            return None
        
        try:
            if stage == "ec":
                return self._get_ec_suggestion(title, abstract, literature_type)
            elif stage == "ic":
                return self._get_ic_suggestion(title, abstract, literature_type)
            elif stage == "qc":
                return self._get_qc_suggestion(title, abstract, literature_type)
        except Exception:
            pass
        
        return None
    
    def _get_ec_suggestion(
        self,
        title: str,
        abstract: str,
        literature_type: str
    ) -> LLMSuggestion:
        """Get EC stage suggestion."""
        criteria = ExclusionCriteria.CRITERIA
        
        prompt = f"""Analyze article for Exclusion Criteria (EC):
        
Title: {title}
Abstract: {abstract[:500] if abstract else 'No abstract'}
Type: {literature_type}

Exclusion criteria:
{chr(10).join([f"- {k}: {v}" for k, v in criteria.items()])}

Provide JSON with:
{{"decision": "include" or "exclude", "confidence": 0.0-1.0, "justification": "brief reason", "triggered_criteria": ["EC codes"]}}
"""
        return self._call_llm(prompt, "ec")
    
    def _get_ic_suggestion(
        self,
        title: str,
        abstract: str,
        literature_type: str
    ) -> LLMSuggestion:
        """Get IC stage suggestion."""
        criteria = InclusionCriteria.CRITERIA
        
        prompt = f"""Analyze article for Inclusion Criteria (IC):
        
Title: {title}
Abstract: {abstract[:500] if abstract else 'No abstract'}
Type: {literature_type}

Inclusion criteria:
{chr(10).join([f"- {k}: {v}" for k, v in criteria.items()])}

Provide JSON with:
{{"decision": "include" or "exclude", "confidence": 0.0-1.0, "justification": "brief reason"}}
"""
        return self._call_llm(prompt, "ic")
    
    def _get_qc_suggestion(
        self,
        title: str,
        abstract: str,
        literature_type: str
    ) -> LLMSuggestion:
        """Get QC stage suggestion."""
        criteria = WL_QUALITY_CRITERIA if literature_type == "WL" else GL_CRITERIA
        
        prompt = f"""Analyze article Quality (QC) score:
        
Title: {title}
Abstract: {abstract[:500] if abstract else 'No abstract'}
Type: {literature_type}

Quality criteria:
{chr(10).join([f"- {k}: {v}" for k, v in criteria.items()])}

Provide JSON with:
{{"score": total, "threshold": 2.0, "decision": "include" or "exclude", "confidence": 0.0-1.0, "justification": "brief reason"}}
"""
        return self._call_llm(prompt, "qc")
    
    def _call_llm(self, prompt: str, stage: str) -> LLMSuggestion:
        """Call LLM and parse response."""
        import json as json_module
        
        try:
            if hasattr(self._llm_client, 'chat'):
                response = self._llm_client.chat.completions.create(
                    model="llama-3.1-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=500
                )
                content = response.choices[0].message.content
                
                parsed = json_module.loads(
                    content.strip().strip("```json").strip("```")
                )
                
                return LLMSuggestion(
                    decision=parsed.get("decision", "skip"),
                    confidence=parsed.get("confidence", 0.5),
                    justification=parsed.get("justification", "No justification provided"),
                    criteria_support=parsed.get("triggered_criteria", {})
                )
        except Exception:
            pass
        
        return None
    
    def record_researcher_decision(
        self,
        article_id: str,
        stage: str,
        choice: str,
        notes: str = ""
    ) -> bool:
        """Record researcher's explicit decision."""
        if not self.reviewer_state:
            return False
        
        llm_suggestion = None
        if self.session and self.session.current_index < len(self.session.articles):
            article = self.session.articles[self.session.current_index]
            llm_suggestion = article.llm_suggestion.get("decision") if article.llm_suggestion else None
        
        self.reviewer_state.record_decision(
            article_id=article_id,
            stage=stage,
            decision=choice,
            notes=notes,
            llm_suggestion=llm_suggestion
        )
        
        if choice == "include":
            self.session.included_count += 1
        elif choice == "exclude":
            self.session.excluded_count += 1
        elif choice == "needs_discussion":
            self.session.discussion_count += 1
        
        if stage == "ec":
            self.session.ec_completed += 1
        elif stage == "ic":
            self.session.ic_completed += 1
        elif stage == "qc":
            self.session.qc_completed += 1
        
        article = self.session.get_current_article()
        if article:
            if stage == "ec":
                article.ec_stage = choice
                article.ec_notes = notes
                article.ec_timestamp = datetime.now().isoformat()
            elif stage == "ic":
                article.ic_stage = choice
                article.ic_notes = notes
                article.ic_timestamp = datetime.now().isoformat()
            elif stage == "qc":
                article.qc_stage = choice
                article.qc_notes = notes
                article.qc_timestamp = datetime.now().isoformat()
        
        return True
    
    def advance_to_next(self) -> bool:
        """Advance to next article."""
        if self.session:
            self.session.advance()
            return self.session.current_index < self.session.total_count
        return False
    
    def set_stage(self, stage: str) -> None:
        """Change current stage."""
        if self.session:
            self.session.stage = stage
        if self.reviewer_state:
            self.reviewer_state.stage = stage
    
    def save_session(self, output_dir: str = "sessions") -> str:
        """Save current session."""
        if self.session:
            return self.session.save(output_dir)
        return ""
    
    def export_decisions(
        self,
        output_path: str,
        wl_records: List[ArticleRecord],
        gl_records: List[ArticleRecord]
    ) -> None:
        """Export decisions to Excel."""
        engine = APOLLODecisionEngine(enable_llm_reasoning=False, protocol=self.protocol)
        engine.export_to_excel(output_path, wl_records, gl_records)


WL_QUALITY_CRITERIA = {
    "WL-Q1": "Are the research aims and the SE R&S context clearly stated?",
    "WL-Q2": "Is the research methodology adequately described and appropriate?",
    "WL-Q3": "Are the findings clearly supported by the collected data?",
    "WL-Q4": "Does the study adequately discuss its limitations or threats to validity?"
}

GL_CRITERIA = {
    "GL-Q1": "Is the author's expertise or organizational context explicitly stated?",
    "GL-Q2": "Is the source of experience transparent (e.g., specific hiring cycle)?",
    "GL-Q3": "Are the claims supported by operational artifacts rather than mere opinion?",
    "GL-Q4": "Does the source provide insights beyond generic employer marketing?"
}


class APOLLODecisionEngine:
    """Legacy - kept for backward compatibility."""
    
    def __init__(self, enable_llm_reasoning: bool = True, protocol: Dict = None):
        from src.core.atlas_processor import APOLLODecisionEngine as OriginalEngine
        self._engine = OriginalEngine(enable_llm_reasoning, protocol)
    
    def process_wl_articles(self, wl_df: pd.DataFrame):
        return self._engine.process_wl_articles(wl_df)
    
    def process_gl_articles(self, gl_df: pd.DataFrame):
        return self._engine.process_gl_articles(gl_df)
    
    def export_to_excel(self, output_path, wl_results, gl_results):
        return self._engine.export_to_excel(output_path, wl_results, gl_results)