"""
APOLLO LLM Assistant - Structured Advisory System
Provides LLM-powered suggestions for human decision-making
(ADVISORY ONLY - researcher makes final decisions)

SPRINT 7.7: Structured Advisory Semantics
- metadata-grounded
- criterion-grounded
- deterministic in structure
- protocol-constrained
- scientifically auditable
"""
import json
import os
import re
import hashlib
import time
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field, asdict
from datetime import datetime

from src.core.criteria_registry import EC_DESCRIPTIONS, IC_DESCRIPTIONS

QC_DESCRIPTIONS = {
    "QC1": "Methodological quality - study design appropriate",
    "QC2": "Methodological quality - data collection robust",
    "QC3": "Methodological quality - analysis transparent",
    "QC4": "Methodological quality - results reproducible",
    "QC5": "Reporting quality - complete documentation"
}

WL_CANONICAL = "White Literature"
GL_CANONICAL = "Grey Literature"

WL_LABELS = {"WL", "White Literature", "WHITE LITERATURE", "white literature", "Wl", "wl"}
GL_LABELS = {"GL", "Grey Literature", "GREY LITERATURE", "grey literature", "Gray Literature", "GRAY LITERATURE", "Gl", "gl"}


def normalize_literature_label(raw: str) -> str:
    """Normalize any literature label to canonical form."""
    if not raw:
        return WL_CANONICAL
    stripped = raw.strip()
    if stripped in WL_LABELS:
        return WL_CANONICAL
    if stripped in GL_LABELS:
        return GL_CANONICAL
    upper = stripped.upper()
    if upper in WL_LABELS or upper == "WHITE LITERATURE":
        return WL_CANONICAL
    if upper in GL_LABELS or upper == "GREY LITERATURE":
        return GL_CANONICAL
    return WL_CANONICAL


@dataclass
class CriterionEvaluation:
    """Structured evaluation of a single criterion."""
    criterion_id: str
    triggered: bool
    evidence: List[str] = field(default_factory=list)
    justification: str = ""
    ambiguity_detected: bool = False
    grounded_metadata_fields: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "CriterionEvaluation":
        return cls(**data)


@dataclass
class StructuredAdvisory:
    """Canonical structured advisory with full metadata grounding."""
    stage: str
    decision: str
    confidence: float

    triggered_criteria: List[str] = field(default_factory=list)
    non_triggered_criteria: List[str] = field(default_factory=list)

    criterion_evaluations: Dict[str, CriterionEvaluation] = field(default_factory=dict)

    confidence: float = 0.5
    justification: str = ""
    reasoning_summary: str = ""

    ambiguity_flags: List[str] = field(default_factory=list)
    evidence_extracts: List[str] = field(default_factory=list)

    metadata_grounding: Dict[str, Any] = field(default_factory=dict)

    is_fallback: bool = False
    fallback_reason: str = ""

    protocol_version: str = "1.0"
    advisory_hash: str = ""

    def __post_init__(self):
        if not self.advisory_hash:
            self.advisory_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Compute deterministic hash of advisory structure."""
        data = {
            "stage": self.stage,
            "decision": self.decision,
            "triggered_criteria": sorted(self.triggered_criteria),
            "criterion_evaluations": {
                k: v.to_dict() for k, v in self.criterion_evaluations.items()
            }
        }
        content = json.dumps(data, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict:
        return {
            "stage": self.stage,
            "decision": self.decision,
            "confidence": self.confidence,
            "triggered_criteria": self.triggered_criteria,
            "non_triggered_criteria": self.non_triggered_criteria,
            "criterion_evaluations": {
                k: v.to_dict() for k, v in self.criterion_evaluations.items()
            },
            "justification": self.justification,
            "reasoning_summary": self.reasoning_summary,
            "ambiguity_flags": self.ambiguity_flags,
            "evidence_extracts": self.evidence_extracts,
            "metadata_grounding": self.metadata_grounding,
            "is_fallback": self.is_fallback,
            "fallback_reason": self.fallback_reason,
            "protocol_version": self.protocol_version,
            "advisory_hash": self.advisory_hash
        }

    def to_display(self) -> str:
        conf = int(self.confidence * 100)
        return f"{self.decision.upper()} ({conf}% confidence)"

    @classmethod
    def from_dict(cls, data: Dict) -> "StructuredAdvisory":
        evals = {}
        for k, v in data.get("criterion_evaluations", {}).items():
            evals[k] = CriterionEvaluation.from_dict(v)
        data = dict(data)
        data["criterion_evaluations"] = evals
        return cls(**data)


@dataclass
class AdvisorySuggestion:
    """Legacy advisory suggestion for backward compatibility."""
    stage: str
    decision: str
    confidence: float
    justification: str

    triggered_criteria: Dict[str, str] = field(default_factory=dict)
    evidence: List[str] = field(default_factory=list)
    ambiguity_flags: List[str] = field(default_factory=list)
    is_fallback: bool = False

    def to_display(self) -> str:
        conf = int(self.confidence * 100)
        return f"{self.decision.upper()} ({conf}% confidence)"

    def to_dict(self) -> Dict:
        return {
            "stage": self.stage,
            "decision": self.decision,
            "confidence": self.confidence,
            "justification": self.justification,
            "triggered_criteria": self.triggered_criteria,
            "evidence": self.evidence,
            "ambiguity_flags": self.ambiguity_flags,
            "is_fallback": self.is_fallback
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "AdvisorySuggestion":
        return cls(**data)


class LLMAssistant:
    """
    LLM Assistant for structured advisory suggestions.

    KEY PRINCIPLE: Advisory ONLY
    - Protocol and canonical metadata are authoritative
    - LLM ONLY assists interpretation
    - All suggestions are logged for audit
    """

    def __init__(self, api_key: Optional[str] = None):
        self._client = None
        self._api_key = api_key or os.environ.get("GROQ_API_KEY") or os.environ.get("OPENAI_API_KEY")
        self._temperature = 0.1
        self._max_tokens = 1200

        if self._api_key:
            self._init_client()

    def _init_client(self) -> None:
        key = os.getenv("GROQ_API_KEY")
        print(f"!!! LLM DIAGNOSTIC !!! Key found: {bool(key)}")
        if not key:
            print("!!! LLM DIAGNOSTIC !!! Warning: GROQ_API_KEY is missing from environment.")
        
        if os.environ.get("GROQ_API_KEY"):
            try:
                from groq import Groq
                self._client = Groq(api_key=self._api_key)
                self._model = "llama-3.3-70b-versatile"
                print("!!! LLM DIAGNOSTIC !!! Groq client initialized successfully")
            except ImportError:
                print("!!! LLM DIAGNOSTIC !!! ERROR: groq library not installed")
                pass
        else:
            try:
                import openai
                self._client = openai.OpenAI(api_key=self._api_key)
                self._model = "gpt-4o-mini"
                print("!!! LLM DIAGNOSTIC !!! OpenAI client initialized successfully")
            except ImportError:
                print("!!! LLM DIAGNOSTIC !!! ERROR: openai library not installed")
                pass

    def is_available(self) -> bool:
        available = self._client is not None and self._api_key is not None
        print(f"!!! LLM STATUS !!! Available: {available} | Client: {bool(self._client)} | Key: {bool(self._api_key)}")
        return available

    def suggest(
        self,
        title: str,
        abstract: str,
        literature_type: str,
        stage: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> StructuredAdvisory:
        year = metadata.get("year") if metadata else None
        if stage == "ec":
            return self.suggest_ec(title, abstract, literature_type, year, metadata=metadata)
        elif stage == "ic":
            return self.suggest_ic(title, abstract, literature_type, metadata=metadata)
        elif stage == "qc":
            return self.suggest_qc(title, abstract, literature_type, metadata=metadata)
        return self._fallback_advisory(stage, "Invalid stage", metadata or {})

    def suggest_ec(
        self,
        title: str,
        abstract: str,
        literature_type: str = "WL",
        year: Optional[int] = None,
        protocol_criteria: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> StructuredAdvisory:
        """
        Structured EC advisory with criterion-by-criterion evaluation.
        
        SPRINT 7.12 FIX: Post-parsing enforcement — override LLM output
        with ground truth from Python's perspective.
        """
        criteria = protocol_criteria if protocol_criteria else EC_DESCRIPTIONS
        metadata = metadata or {}

        canonical_lit = normalize_literature_label(literature_type)
        year_str = str(year) if year else "NOT PROVIDED"

        prompt = self._build_ec_prompt(
            title=title,
            abstract=abstract,
            year_str=year_str,
            year_source=metadata.get("year_source", "metadata"),
            literature_type=canonical_lit,
            metadata_completeness=metadata.get("metadata_completeness", "unknown"),
            criteria=criteria,
            metadata=metadata
        )

        advisory = self._call_structured_llm(prompt, "ec", canonical_lit, metadata)
        
        if "EC2" in criteria or "ec2" in [k.lower() for k in criteria.keys()]:
            advisory.criterion_evaluations["EC2"] = CriterionEvaluation(
                criterion_id="EC2",
                triggered=False,
                evidence=[],
                justification="N/A: Evaluation deferred to Full-Text stage.",
                ambiguity_detected=False,
                grounded_metadata_fields=[]
            )
            if "EC2" not in advisory.non_triggered_criteria:
                advisory.non_triggered_criteria.append("EC2")
            if "EC2" in advisory.triggered_criteria:
                advisory.triggered_criteria = [c for c in advisory.triggered_criteria if str(c).upper() != "EC2"]
        
        ec6_keys = [k for k in criteria.keys() if k.upper() in ["EC6", "DUPLICATE", "DUPLICATES"]]
        if ec6_keys:
            ec6_key = ec6_keys[0]
            advisory.criterion_evaluations[ec6_key] = CriterionEvaluation(
                criterion_id=ec6_key,
                triggered=False,
                evidence=[],
                justification="N/A: Handled by deterministic Global_ID matching.",
                ambiguity_detected=False,
                grounded_metadata_fields=[]
            )
            if ec6_key not in advisory.non_triggered_criteria:
                advisory.non_triggered_criteria.append(ec6_key)
            if ec6_key in advisory.triggered_criteria:
                advisory.triggered_criteria = [c for c in advisory.triggered_criteria if c != ec6_key]
        
        mg = dict(advisory.metadata_grounding) if advisory.metadata_grounding else {}
        
        if year is not None and year > 0:
            mg["year_used"] = True
            
            if year >= 2015:
                new_triggered = [c for c in advisory.triggered_criteria 
                               if str(c).upper() not in ["EC2", "EC4", "YEAR", "PUBLICATION YEAR"]]
                new_non_triggered = list(advisory.non_triggered_criteria)
                if "EC2" not in new_non_triggered:
                    new_non_triggered.append("EC2")
                advisory.triggered_criteria = new_triggered
                advisory.non_triggered_criteria = new_non_triggered
        
        if abstract and len(str(abstract)) > 10:
            mg["abstract_used"] = True
        
        advisory.metadata_grounding = mg
        
        return advisory

    def suggest_ic(
        self,
        title: str,
        abstract: str,
        literature_type: str = "WL",
        protocol_criteria: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> StructuredAdvisory:
        """
        Structured IC advisory with criterion-by-criterion evaluation.
        """
        criteria = protocol_criteria if protocol_criteria else IC_DESCRIPTIONS
        metadata = metadata or {}

        canonical_lit = normalize_literature_label(literature_type)
        year_source = metadata.get("year_source", "unknown")
        completeness = metadata.get("metadata_completeness", "unknown")

        prompt = self._build_ic_prompt(
            title=title,
            abstract=abstract,
            literature_type=canonical_lit,
            year_source=year_source,
            metadata_completeness=completeness,
            criteria=criteria,
            metadata=metadata
        )

        return self._call_structured_llm(prompt, "ic", canonical_lit, metadata)

    def suggest_qc(
        self,
        title: str,
        abstract: str,
        literature_type: str = "WL",
        protocol_criteria: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> StructuredAdvisory:
        """
        Structured QC advisory with criterion-by-criterion evaluation.
        
        QC stage: Quality Criteria assessment - independent from EC/IC.
        """
        criteria = protocol_criteria if protocol_criteria else QC_DESCRIPTIONS
        metadata = metadata or {}

        canonical_lit = normalize_literature_label(literature_type)

        prompt = self._build_qc_prompt(
            title=title,
            abstract=abstract,
            literature_type=canonical_lit,
            criteria=criteria,
            metadata=metadata
        )

        return self._call_structured_llm(prompt, "qc", canonical_lit, metadata)

    def _build_qc_prompt(
        self,
        title: str,
        abstract: str,
        literature_type: str,
        criteria: Dict[str, str],
        metadata: Dict[str, Any]
    ) -> str:
        """
        Build structured QC prompt with EXPLICIT quality assessment criteria.
        QC is independent methodology - does NOT reuse IC or EC criteria.
        """
        title_sanitized = str(title).replace('"', '\\"').replace('\n', ' ').replace('\r', ' ')[:300] if title else ""
        abstract_sanitized = str(abstract)[:800].replace('"', '\\"').replace('\n', ' ').replace('\r', ' ') if abstract else "NOT PROVIDED"
        
        authors_value = metadata.get("authors", "")
        has_authors = bool(authors_value and authors_value != "nan" and str(authors_value).strip())
        authors_display = str(authors_value).replace('"', '\\"').replace('\n', ' ').replace('\r', ' ')[:200] if has_authors else "NOT PROVIDED"
        
        year_value = metadata.get("year")
        has_year = year_value is not None and str(year_value) not in ("", "nan", "NOT PROVIDED")
        year_str = str(year_value) if has_year else "NOT PROVIDED"
        
        abstract_available = bool(abstract and abstract.strip() and abstract != "nan" and len(abstract.strip()) > 10)
        
        criteria_blocks = "\n".join([
            f'    "{cid}": {{"triggered": false, "evidence": [], "justification": "", "ambiguity_detected": false}}'
            for cid in criteria.keys()
        ])

        prompt = f"""SYSTEM CONTEXT:
You are a systematic review quality assessor.

Task: Evaluate the methodological quality of a research paper for potential inclusion in a systematic review.

LITERATURE TYPE: {literature_type}
METHODOLOGY: Quality Criteria Assessment (INDEPENDENT from Inclusion Criteria)

CRITICAL METADATA GROUNDING (HALLUCINATION PREVENTION):
- Title: "{title_sanitized}" (ALWAYS USE THIS)
- Year: {year_str}
- Authors: {authors_display}
- Abstract: {"AVAILABLE" if abstract_available else "NOT AVAILABLE"}

QUALITY CRITERIA (protocol-authoritative):
{chr(10).join([f"- {k}: {v}" for k, v in criteria.items()])}

QUALITY ASSESSMENT INSTRUCTIONS:
1. Evaluate each QC criterion independently
2. Determine if each criterion is MET (not triggered) or NOT MET (triggered)
3. Provide evidence from title/abstract where possible
4. If evidence is insufficient, note ambiguity but do NOT fabricate quality issues
5. QC is about methodological rigor - NOT relevance (that's IC stage)

{("Abstract available for detailed quality assessment." if abstract_available else "WARNING: No abstract available - perform title-only quality assessment if possible.")}

STRUCTURED OUTPUT REQUIRED:
Return ONLY valid JSON:

{{
  "decision": "include" or "exclude",
  "confidence": 0.0-1.0,
  "justification": "2-3 sentence explanation of quality assessment",
  "reasoning_summary": "concise summary of quality evaluation process",
  "triggered_criteria": ["list of QC criterion IDs with issues"],
  "non_triggered_criteria": ["list of QC criterion IDs without issues"],
  "criterion_evaluations": {{
{criteria_blocks}
  }},
  "ambiguity_flags": [],
  "evidence_extracts": ["verbatim text extracts from title/abstract relevant to quality"],
  "metadata_grounding": {{
    "title_used": true,
    "year_used": {str(has_year).lower()},
    "authors_used": {str(has_authors).lower()},
    "abstract_used": {str(abstract_available).lower()},
    "literature_type_used": true
  }}
}}

Return ONLY valid JSON."""

        return prompt

    def _build_ec_prompt(
        self,
        title: str,
        abstract: str,
        year_str: str,
        year_source: str,
        literature_type: str,
        metadata_completeness: Any,
        criteria: Dict[str, str],
        metadata: Dict[str, Any]
    ) -> str:
        """
        Build structured EC prompt with DYNAMIC protocol criteria.
        
        SPRINT 7.12 FIX: Removed hardcoded EC definitions. Use the criteria
        provided by the LOCKED protocol. Added WL=peer-reviewed enforcement.
        """
        is_wl = literature_type == WL_CANONICAL
        
        authors_value = metadata.get("authors", "")
        has_authors = bool(authors_value and authors_value != "nan" and str(authors_value).strip())
        if has_authors:
            authors_display = str(authors_value).replace('"', '\\"').replace('\n', ' ').replace('\r', ' ')[:200]
        else:
            authors_display = "NOT PROVIDED"
        
        year_provided = year_str != "NOT PROVIDED"
        abstract_available = bool(abstract and abstract.strip() and abstract != "nan" and len(abstract.strip()) > 10)
        
        criteria_list = [f"- {k}: {v}" for k, v in criteria.items()]
        criteria_blocks = "\n".join([
            f'    "{cid}": {{"triggered": false, "evidence": [], "justification": "", "ambiguity_detected": false}}'
            for cid in criteria.keys()
        ])
        
        title_sanitized = str(title).replace('"', '\\"').replace('\n', ' ').replace('\r', ' ')[:300] if title else ""
        abstract_sanitized = str(abstract)[:800].replace('"', '\\"').replace('\n', ' ').replace('\r', ' ') if abstract else "NOT PROVIDED"
        
        metadata_block = f"""
        {{
          "Title": "{title_sanitized}",
          "Year": {year_str},
          "Authors": "{authors_display}",
          "Literature_Type": "{literature_type}",
          "Abstract": "{abstract_sanitized}"
        }}"""
        
        abstract_instruction = ""
        if abstract_available:
            abstract_instruction = """
ABSTRACT MANDATORY USAGE:
- The Abstract IS PROVIDED above — you MUST use it for evidence extraction
- In "evidence_extracts", include at least 1-2 relevant sentences from the abstract
- Do NOT leave "evidence_extracts" empty if abstract is available
- Use abstract content to verify criteria matches, not just title
- If criteria mentions methodology, context, or findings, cite from the abstract"""
        else:
            abstract_instruction = """
ABSTRACT NOT AVAILABLE: Do not fabricate abstract content. 
Only use title for evidence extraction."""
        
        lit_type_warning = ""
        if is_wl:
            lit_type_warning = """
WL CRITICAL RULE: "White Literature" classification means the paper IS peer-reviewed.
DO NOT trigger exclusion criteria related to "peer-review" or "publication type" for WL sources.
The protocol criteria you receive are the ONLY exclusion rules to apply."""
        else:
            lit_type_warning = """
GL CONTEXT: Grey Literature sources (blogs, reports, white papers) are NON-PEER-REVIEWED by nature.
EC criteria for peer-review status do NOT apply to GL."""

        prompt = f"""SYSTEM CONTEXT:
You are a systematic review expert. PROTOCOL CRITERIA are the SOLE source of exclusion rules.
You ONLY evaluate against the criteria provided below. Do NOT invent or assume exclusion rules.

EXPLICIT METADATA BLOCK (SOURCE OF TRUTH):
{metadata_block}

CRITICAL YEAR RULE (STRICT ENFORCEMENT):
- If Year >= 2015, the year criterion is NOT triggered — the paper passes the year threshold
- NEVER exclude a paper for year reasons if Year >= 2015

{lit_type_warning}

CRITICAL YEAR RULE (STRICT ENFORCEMENT):
- If Year >= 2015, the year criterion is NOT triggered — the paper passes the year threshold
- NEVER exclude a paper for year reasons if Year >= 2015

METHODOLOGICAL CONSTRAINTS (STRICT ENFORCEMENT):
- EC2 (Full Text Availability): You MUST NOT assume availability. Since we are in the Title/Abstract screening phase, availability is UNKNOWN. Your evaluation for EC2 should always be: "Cannot be evaluated at Title/Abstract screening stage. Proceeding with metadata analysis."
- EC6 (Duplicates): Ignore EC6 (Duplicates). This is handled deterministically by the APOLLO system logic. Your evaluation for EC6 should always be: "Handled by system deterministic engine."
- Evidence Extracts: Strictly map extracts to the criteria. Instead of a general list, provide evidence that refutes a specific EC trigger (e.g., refuting EC1 by finding SE keywords, or refuting EC3 by identifying peer-review indicators).

{abstract_instruction}

EXCLUSION CRITERIA (from LOCKED protocol — these are the ONLY rules):
{chr(10).join(criteria_list)}

METHODOLOGICAL ISOLATION (STRICT):
Focus ONLY on Exclusion Criteria (EC1-EC6). Do NOT discuss or evaluate Inclusion Criteria (IC). Your goal is to find reasons to REJECT the paper. If no exclusion criteria are met, simply state: 'No exclusion triggers found - paper passes EC'.

IMPORTANT REMINDERS:
1. Use the EXACT criteria labels provided (e.g., EC1, EC2, IC1, etc.)
2. Evaluate each criterion independently — one triggered does not affect others
3. Only trigger criteria where clear evidence exists in the metadata
4. "Short publications" or "non-peer-reviewed" criteria apply ONLY to GL if they appear in the criteria list
5. **CONFIDENCE RATIONALE**: If your CONFIDENCE is less than 100%, your 'reasoning_summary' field MUST begin with: '[CONFIDENCE {{X}}%]: ' followed by the explanation of why the metadata is ambiguous or what information is missing (e.g., "[CONFIDENCE 70%]: Year information is missing from metadata, making it impossible to verify EC2 applicability").

STRUCTURED OUTPUT REQUIRED:
Return ONLY valid JSON with this exact structure:

{{
  "decision": "include" or "exclude",
  "confidence": 0.0-1.0,
  "justification": "2-3 sentence explanation using ONLY provided metadata",
  "reasoning_summary": "concise summary of evaluation process",
  "triggered_criteria": ["list of criterion IDs triggered"],
  "non_triggered_criteria": ["list of criterion IDs NOT triggered"],
  "criterion_evaluations": {{
{criteria_blocks}
  }},
  "ambiguity_flags": ["ONLY flag ambiguity if grounded in ACTUAL metadata gaps"],
  "evidence_extracts": ["verbatim text extracts from title/abstract"],
  "metadata_grounding": {{
    "title_used": true,
    "year_used": {str(year_provided).lower()},
    "authors_used": {str(has_authors).lower()},
    "abstract_used": {str(abstract_available).lower()},
    "literature_type_used": true
  }}
}}

Return ONLY valid JSON."""

        return prompt

    def _build_ic_prompt(
        self,
        title: str,
        abstract: str,
        literature_type: str,
        year_source: str,
        metadata_completeness: Any,
        criteria: Dict[str, str],
        metadata: Dict[str, Any]
    ) -> str:
        """
        Build structured IC prompt with EXPLICIT metadata grounding.
        HALLUCINATION PREVENTION: Explicit source validation for all fields.
        """
        authors_value = metadata.get("authors", "")
        has_authors = bool(authors_value and authors_value != "nan" and str(authors_value).strip())
        if has_authors:
            authors_display = str(authors_value).replace('"', '\\"').replace('\n', ' ').replace('\r', ' ')[:200]
        else:
            authors_display = "NOT PROVIDED"
        
        year_value = metadata.get("year")
        has_year = bool(year_value and str(year_value).strip() and str(year_value) != "nan")
        year_display = str(year_value) if has_year else "NOT PROVIDED"
        
        abstract_available = bool(abstract and abstract.strip() and abstract != "nan" and len(abstract.strip()) > 10)
        
        criteria_blocks = "\n".join([
            f'    "{cid}": {{"triggered": false, "evidence": [], "justification": "", "ambiguity_detected": false}}'
            for cid in criteria.keys()
        ])
        
        title_sanitized = str(title).replace('"', '\\"').replace('\n', ' ').replace('\r', ' ')[:300] if title else ""
        abstract_sanitized = str(abstract)[:200].replace('"', '\\"').replace('\n', ' ').replace('\r', ' ') if abstract else "NOT AVAILABLE"

        prompt = f"""SYSTEM CONTEXT:
You are a systematic review expert. PROTOCOL and CANONICAL METADATA are authoritative.

CRITICAL METADATA GROUNDING (HALLUCINATION PREVENTION):
- Title: "{title_sanitized}" (ALWAYS USE THIS)
- Year: {year_display} {"✓ YEAR PROVIDED" if has_year else "✗ YEAR NOT PROVIDED"}
- Authors: {authors_display} {"✓ AUTHORS PROVIDED" if has_authors else "✗ AUTHORS NOT PROVIDED"}
- Abstract: {"AVAILABLE (" + abstract_sanitized + "...)" if abstract_available else "NOT AVAILABLE"}
- Literature Type: {literature_type}
- Metadata Completeness: {metadata_completeness}

ADVISORY CONSTRAINTS (STRICT ENFORCEMENT):
1. IC criteria assess RELEVANCE to research question
2. Articles passing EC are already deemed empirical and recent
3. Focus on SE Recruitment & Selection (R&S) relevance
4. NEVER fabricate ambiguity when metadata is complete
5. NEVER fabricate missing metadata when it is provided
6. NEVER fabricate abstract content when no abstract is available
7. **CONFIDENCE RATIONALE**: If your CONFIDENCE is less than 100%, your 'reasoning_summary' field MUST begin with: '[CONFIDENCE {{X}}%]: ' followed by the explanation of why the metadata is ambiguous or what information is missing (e.g., "[CONFIDENCE 80%]: Abstract is not detailed enough to fully assess IC2 applicability").

INCLUSION CRITERIA (protocol-authoritative):
{chr(10).join([f"- {k}: {v}" for k, v in criteria.items()])}

STRUCTURED OUTPUT REQUIRED:
Return ONLY valid JSON:

{{
  "decision": "include" or "exclude",
  "confidence": 0.0-1.0,
  "justification": "2-3 sentence explanation",
  "reasoning_summary": "concise evaluation summary",
  "triggered_criteria": ["list of criterion IDs triggered"],
  "non_triggered_criteria": ["list of criterion IDs NOT triggered"],
  "criterion_evaluations": {{
{criteria_blocks}
  }},
  "ambiguity_flags": [],
  "evidence_extracts": ["text extracts from title/abstract"],
  "metadata_grounding": {{"title_used": true, "abstract_used": {str(abstract_available).lower()}, "literature_type_used": true, "authors_used": {str(has_authors).lower()}, "year_used": {str(has_year).lower()}}}
}}

Return ONLY valid JSON."""

        return prompt

    def _sanitize_json_string(self, content: str) -> str:
        r"""
        Pre-parsing sanitization to handle LaTeX/BibTeX escape sequences
        that may have been mirrored by the LLM.
        
        Handles: \o{}, \ae{}, special unicode chars, unescaped quotes
        """
        content = content.strip()
        
        content = content.replace(r'\o{}', 'ø')
        content = content.replace(r'\ae{}', 'æ')
        content = re.sub(r'\\"\{(\w)\}', r'\1', content)
        content = re.sub(r"\\'\{(\w)\}", r'\1', content)
        content = re.sub(r'\\\^\{?(\w)\}?', r'\1', content)
        content = re.sub(r'\\~{?(\w)}?', r'\1', content)
        content = content.replace(r'\&', '&')
        content = content.replace(r'\%', '%')
        content = content.replace(r'\#', '#')
        content = content.replace(r'\$', '$')
        content = content.replace(r'\_', '_')
        content = re.sub(r'\\text\{([^}]+)\}', r'\1', content)
        
        content = re.sub(r'\\([{}\[\]])', r'\1', content)
        
        return content
        content = re.sub(r'\\"\{(\w)\}', r'\1', content)
        content = re.sub(r"\\'\{(\w)\}", r'\1', content)
        content = re.sub(r'\\\^\{?(\w)\}?', r'\1', content)
        content = re.sub(r'\\~{?(\w)}?', r'\1', content)
        content = re.sub(r'\\&', '&', content)
        content = re.sub(r'\\%', '%', content)
        content = re.sub(r'\\#', '#', content)
        content = re.sub(r'\$_', '$', content)
        content = re.sub(r'\\_', '_', content)
        content = re.sub(r'\\text\{([^}]+)\}', r'\1', content)
        
        content = re.sub(r'\\([{}\[\]])', r'\1', content)
        
        return content

    def _extract_json_block(self, content: str) -> Optional[Dict]:
        """
        Robust JSON extraction using regex to find JSON block in LLM response.
        Handles markdown code blocks, partial responses, and malformed JSON.
        """
        content = content.strip()
        
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            json_str = json_match.group(0)
            
            json_str = self._sanitize_json_string(json_str)
            
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass
        
        cleaned = self._sanitize_json_string(content)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
        
        content_no_backticks = re.sub(r'^```json\s*', '', content)
        content_no_backticks = re.sub(r'\s*```$', '', content_no_backticks)
        content_no_backticks = self._sanitize_json_string(content_no_backticks)
        
        try:
            return json.loads(content_no_backticks)
        except json.JSONDecodeError:
            return None

    def _call_structured_llm(
        self,
        prompt: str,
        stage: str,
        literature_type: str,
        metadata: Dict[str, Any]
    ) -> StructuredAdvisory:
        """
        Call LLM and parse structured response with robust error handling.
        Includes LaTeX/BibTeX escape sequence handling and retry logic.
        """
        if not self._client:
            return self._fallback_advisory(stage, "No LLM client", metadata)

        messages = [
            {
                "role": "system",
                "content": "You are a systematic review expert. Provide structured JSON responses ONLY. Follow the exact schema provided. IMPORTANT: Do not use LaTeX or BibTeX escape sequences in the JSON output. Use plain ASCII characters."
            },
            {"role": "user", "content": prompt}
        ]

        try:
            time.sleep(0.5)
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=self._temperature,
                max_tokens=self._max_tokens
            )

            content = response.choices[0].message.content
            
            parsed = self._extract_json_block(content)
            
            if parsed is None:
                retry_messages = [
                    {
                        "role": "system",
                        "content": "You must return ONLY valid JSON. No markdown, no explanation. Return exactly the JSON object."
                    },
                    {"role": "user", "content": "Convert this response to valid JSON: " + content[:500]}
                ]
                
                try:
                    retry_response = self._client.chat.completions.create(
                        model=self._model,
                        messages=retry_messages,
                        temperature=0.0,
                        max_tokens=800
                    )
                    retry_content = retry_response.choices[0].message.content
                    parsed = self._extract_json_block(retry_content)
                except:
                    pass
            
            if parsed is None:
                return self._fallback_advisory(stage, "JSON parse failed after sanitization", metadata)

            evals = {}
            for cid, eval_data in parsed.get("criterion_evaluations", {}).items():
                evals[cid] = CriterionEvaluation(
                    criterion_id=cid,
                    triggered=eval_data.get("triggered", False),
                    evidence=eval_data.get("evidence", []),
                    justification=eval_data.get("justification", ""),
                    ambiguity_detected=eval_data.get("ambiguity_detected", False),
                    grounded_metadata_fields=eval_data.get("grounded_metadata_fields", [])
                )

            return StructuredAdvisory(
                stage=stage,
                decision=parsed.get("decision", "skip"),
                confidence=parsed.get("confidence", 0.5),
                triggered_criteria=parsed.get("triggered_criteria", []),
                non_triggered_criteria=parsed.get("non_triggered_criteria", []),
                criterion_evaluations=evals,
                justification=parsed.get("justification", ""),
                reasoning_summary=parsed.get("reasoning_summary", ""),
                ambiguity_flags=parsed.get("ambiguity_flags", []),
                evidence_extracts=parsed.get("evidence_extracts", []),
                metadata_grounding=parsed.get("metadata_grounding", {}),
                is_fallback=False,
                protocol_version="1.0"
            )

        except json.JSONDecodeError as e:
            return self._fallback_advisory(stage, f"JSON parse error: {str(e)[:50]}", metadata)
        except Exception as e:
            error_str = str(e)
            if any(code in error_str for code in ["HTTP", "400", "404", "model", "timeout", "rate"]):
                return self._fallback_advisory(stage, f"LLM API error: {error_str[:50]}", metadata)
            return self._fallback_advisory(stage, f"Error: {error_str[:50]}", metadata)

    def _fallback_advisory(
        self,
        stage: str,
        error: str,
        metadata: Dict[str, Any]
    ) -> StructuredAdvisory:
        """
        Deterministic fallback advisory when LLM unavailable.
        MUST be visually distinct from true advisory output.
        """
        return StructuredAdvisory(
            stage=stage,
            decision="unavailable",
            confidence=0.0,
            triggered_criteria=[],
            non_triggered_criteria=[],
            criterion_evaluations={},
            justification="Structured advisory unavailable. Displaying deterministic fallback summary.",
            reasoning_summary="LLM service unavailable. Manual review required.",
            ambiguity_flags=["LLM not available"],
            evidence_extracts=[],
            metadata_grounding={
                "title_used": False,
                "year_used": False,
                "abstract_used": False,
                "literature_type_used": False
            },
            is_fallback=True,
            fallback_reason=error,
            protocol_version="1.0"
        )

    def _call_llm(
        self,
        prompt: str,
        stage: str,
        literature_type: str
    ) -> AdvisorySuggestion:
        """Legacy compatibility wrapper."""
        advisory = self._call_structured_llm(prompt, stage, literature_type, {})

        triggered = {}
        for cid, eval_obj in advisory.criterion_evaluations.items():
            if eval_obj.triggered:
                triggered[cid] = eval_obj.justification

        return AdvisorySuggestion(
            stage=stage,
            decision=advisory.decision,
            confidence=advisory.confidence,
            justification=advisory.justification,
            triggered_criteria=triggered,
            evidence=advisory.evidence_extracts,
            ambiguity_flags=advisory.ambiguity_flags,
            is_fallback=advisory.is_fallback
        )


def get_llm_assistant() -> LLMAssistant:
    """Get singleton LLM assistant instance."""
    return LLMAssistant()