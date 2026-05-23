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
from dataclasses import dataclass, field, asdict, fields
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


# Epistemic prompt fragments for trustworthy autonomous screening
EPISTEMIC_SYSTEM_CORE = """SYSTEM CONTEXT:
You are a systematic review expert operating under a CONSERVATIVE EPISTEMIC POLICY.
Your purpose is to evaluate research eligibility with calibrated uncertainty.

EPISTEMIC POLICY:
- False positives (wrongly including) are MORE HARMFUL than abstentions
- Speculation is FORBIDDEN — only use explicit evidence from the provided text
- Missing evidence must NOT be interpreted optimistically
- Do NOT infer study relevance from superficial keyword overlap alone
- Confidence must reflect EVIDENTIAL SUPPORT, not intuition or pattern recognition
- When in doubt, ABSTAIN rather than speculate"""

DECISION_SEMANTICS = """
DECISION OPTIONS (choose ONE):
- INCLUDE: Only when eligibility evidence is EXPLICIT and DIRECTLY supported by the text
- EXCLUDE: Only when exclusion evidence is EXPLICIT and GROUNDED in the text
- UNCERTAIN: Use when relevance cannot be confidently determined; abstract is vague;
  criteria are only partially supported; evidence is ambiguous; domain alignment is weak;
  the model is inferring or speculating rather than reading directly.
  This is the DEFAULT when evidence is insufficient.
- INSUFFICIENT_EVIDENCE: Use when metadata is incomplete; abstract is missing or extremely short;
  methodological information is absent; there is not enough information to assess eligibility at all.
- CANNOT_DETERMINE: Use when the text is contradictory; study intent is fundamentally unclear;
  signals conflict strongly and no clear resolution is possible from available information."""

CONFIDENCE_SEMANTICS = """
CONFIDENCE RULES (STRICT):
- HIGH (0.95+): ONLY when evidence is explicit, criteria match strongly, ambiguity near zero
- MEDIUM (0.70-0.94): Partial evidence with moderate ambiguity
- LOW (0.50-0.69): Weak evidence, inferred relevance, some uncertainty present
- INSUFFICIENT (<0.50): Not enough evidence for a reliable decision;
  decision should be UNCERTAIN rather than INCLUDE

PROHIBITED:
- Never assign confidence > 0.8 when grounding_evidence is empty
- Never assign confidence > 0.6 when abstract is unavailable
- Never assign confidence > 0.5 when no criteria were triggered
- 1.0 confidence is ONLY permitted with explicit, multi-sentence evidence and
  zero ambiguity flags"""

TOPIC_RELEVANCE_INSTRUCTIONS = """
TOPIC RELEVANCE CALIBRATION (CRITICAL):
Distinguish between SUPERFICIAL KEYWORD OVERLAP and TRUE RESEARCH RELEVANCE.
A paper mentioning "software engineering" or "AI/ML" may NOT be relevant
to your specific protocol.

Score each dimension 0.0-1.0:
- domain_relevance_score: How directly does this paper address the protocol domain?
- rq_alignment_strength: How well does the paper answer the research question?
- methodological_alignment: Does methodology match expected study types?
- population_alignment: Is the study population/context appropriate for the protocol?

Rules:
- Low domain_relevance_score (< 0.4) should push decision toward UNCERTAIN
- Keyword-level matches without deeper alignment = low scores"""

EVIDENCE_EXTRACTION_REQUIREMENTS = """
EVIDENCE EXTRACTION RULES:
1. grounding_evidence MUST contain verbatim or closely paraphrased extracts
   from the title/abstract that support your decision
2. Each evidence entry should cite specific text (quote or close paraphrase)
3. Empty grounding_evidence strongly correlates with UNCERTAIN decision
4. triggered_criteria MUST map to actual protocol criteria with evidence
5. If you cannot extract evidence, you MUST note this in uncertainty_reasoning

EVIDENCE QUALITY:
- "The abstract states..." → good
- "This suggests..." → speculation (forbidden)
- "It appears that..." → speculation (forbidden)
- "Based on the explicit statement..." → good"""

UNCERTAINTY_REASONING = """
UNCERTAINTY REASONING:
If decision is UNCERTAIN, INSUFFICIENT_EVIDENCE, or CANNOT_DETERMINE,
provide a brief explanation of WHAT is missing or ambiguous.
This helps researchers understand why the model could not decide.

Examples:
- "Abstract is vague about study methodology — cannot confirm empirical nature"
- "Only title available — insufficient content for criteria evaluation"
- "Paper uses SE terminology but unclear if it addresses recruitment context"
- "Domain relevance unclear — keywords match but research focus differs" """


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
    grounding_evidence: List[str] = field(default_factory=list)

    uncertainty_reasoning: str = ""
    domain_alignment_reasoning: str = ""

    metadata_grounding: Dict[str, Any] = field(default_factory=dict)

    is_fallback: bool = False
    fallback_reason: str = ""

    protocol_version: str = "1.0"
    advisory_hash: str = ""

    topic_relevance: Dict[str, float] = field(default_factory=lambda: {
        "domain_relevance_score": 0.0,
        "rq_alignment_strength": 0.0,
        "methodological_alignment": 0.0,
        "population_alignment": 0.0
    })

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
            "grounding_evidence": self.grounding_evidence,
            "uncertainty_reasoning": self.uncertainty_reasoning,
            "domain_alignment_reasoning": self.domain_alignment_reasoning,
            "topic_relevance": dict(self.topic_relevance),
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
        known_fields = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)


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
        if os.environ.get("GROQ_API_KEY"):
            try:
                from groq import Groq
                self._client = Groq(api_key=self._api_key, max_retries=0)
                self._model = "llama-3.3-70b-versatile"
            except ImportError:
                pass
        else:
            try:
                import openai
                self._client = openai.OpenAI(api_key=self._api_key, max_retries=0)
                self._model = "gpt-4o-mini"
            except ImportError:
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

    def _ic_few_shot_examples(self) -> str:
        """Few-shot calibration examples for IC screening."""
        return """
FEW-SHOT CALIBRATION EXAMPLES:

--- EXAMPLE 1: GOOD ABSTENTION (ML paper, not IC-relevant) ---
Title: "Deep learning for automated code review"
Abstract: "We propose a transformer-based model for detecting coding best practice violations in pull requests."
Review context: IC is about SE recruitment and selection practices.
Correct output:
{"decision": "UNCERTAIN", "confidence": 0.25, "justification": "Paper addresses automated code review, not recruitment/selection.",
 "triggered_criteria": [], "grounding_evidence": [],
 "uncertainty_reasoning": "Paper is about automated code review using ML. No connection to human recruitment or selection practices.",
 "domain_alignment_reasoning": "Superficial 'SE' keyword match but research focus is code review automation, not personnel selection.",
 "topic_relevance": {"domain_relevance_score": 0.1, "rq_alignment_strength": 0.05, "methodological_alignment": 0.2, "population_alignment": 0.1}}

--- EXAMPLE 2: GOOD INCLUDE (explicit evidence) ---
Title: "Structured interviews for software engineer hiring: A field study"
Abstract: "We conducted a field study of structured technical interviews at a large technology company, examining the relationship between interview format and hiring outcomes for 500 software engineer candidates."
Correct output:
{"decision": "INCLUDE", "confidence": 0.95, "justification": "Paper directly addresses SE hiring practices with empirical field study.",
 "grounding_evidence": ["field study of structured technical interviews", "relationship between interview format and hiring outcomes", "500 software engineer candidates"],
 "triggered_criteria": ["IC1", "IC3"],
 "uncertainty_reasoning": "",
 "topic_relevance": {"domain_relevance_score": 0.95, "rq_alignment_strength": 0.9, "methodological_alignment": 0.85, "population_alignment": 0.9}}

--- EXAMPLE 3: BAD SPECULATIVE INCLUDE (what NOT to do) ---
Title: "Software engineering challenges in agile transformations"
Abstract: "We report on challenges faced by organizations adopting agile methodologies at scale."
INCORRECT output:
{"decision": "INCLUDE", "confidence": 0.80, "justification": "Paper discusses SE challenges which may relate to hiring."}
REASON: Speculation. No explicit connection to recruitment/selection.
Correct output:
{"decision": "UNCERTAIN", "confidence": 0.35, "justification": "Paper discusses agile adoption challenges, not recruitment/selection.",
 "uncertainty_reasoning": "No explicit mention of hiring, recruitment, or selection practices despite SE context."}

--- EXAMPLE 4: INSUFFICIENT_EVIDENCE ---
Title: "A study of teams"
Abstract: NOT AVAILABLE
Correct output:
{"decision": "INSUFFICIENT_EVIDENCE", "confidence": 0.15, "justification": "No abstract available and title too vague for IC evaluation.",
 "grounding_evidence": [], "triggered_criteria": [],
 "uncertainty_reasoning": "Title-only — no methodological or contextual detail available.",
 "topic_relevance": {"domain_relevance_score": 0.2, "rq_alignment_strength": 0.1, "methodological_alignment": 0.1, "population_alignment": 0.1}}

--- EXAMPLE 5: KEYWORD OVERLAP TRAP ---
Title: "Agile HR: Recruitment practices in agile software organizations"
Abstract: "This paper examines how agile methodologies influence human resources practices, specifically focusing on recruitment and selection of software developers in agile teams."
Correct output:
{"decision": "INCLUDE", "confidence": 0.90, "justification": "Paper directly examines recruitment practices in SE context.",
 "grounding_evidence": ["recruitment practices in agile software organizations", "recruitment and selection of software developers"],
 "triggered_criteria": ["IC1", "IC2"],
 "topic_relevance": {"domain_relevance_score": 0.9, "rq_alignment_strength": 0.85, "methodological_alignment": 0.7, "population_alignment": 0.8}}
KEY DIFFERENCE: This paper has explicit recruitment/selection language WITH SE context.
"""

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
        Build structured EC prompt with epistemic calibration for trustworthy
        autonomous screening. Uses conservative decision policy:
        prefer UNCERTAIN over speculative INCLUDE.
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
          "Abstract_SPRINT_RULE": "Abstract text above. MANDATORY evidence source.",
          "Abstract": "{abstract_sanitized}"
        }}"""

        abstract_instruction = ""
        if abstract_available:
            abstract_instruction = """
ABSTRACT MANDATORY USAGE:
- The Abstract IS PROVIDED above — you MUST use it for evidence extraction
- In "grounding_evidence", include at least 1-2 verbatim or closely paraphrased
  sentences from the abstract that support your decision
- Do NOT leave "grounding_evidence" empty if abstract is available —
  empty evidence pushes confidence below 0.8 automatically
- If criteria mentions methodology, context, or findings, cite from the abstract"""
        else:
            abstract_instruction = """
ABSTRACT NOT AVAILABLE: Do not fabricate abstract content.
Only use title for evidence extraction. Decision should default to
INSUFFICIENT_EVIDENCE unless title alone provides clear signals."""

        lit_type_warning = ""
        if is_wl:
            lit_type_warning = """
WL RULE: "White Literature" = peer-reviewed. Do NOT trigger peer-review criteria for WL.
The protocol criteria are the ONLY exclusion rules to apply."""
        else:
            lit_type_warning = """
GL RULE: Grey Literature = non-peer-reviewed by nature. Do NOT apply peer-review criteria."""

        few_shot_examples = self._ec_few_shot_examples()

        prompt = f"""{EPISTEMIC_SYSTEM_CORE}
{DECISION_SEMANTICS}
{CONFIDENCE_SEMANTICS}
{TOPIC_RELEVANCE_INSTRUCTIONS}
{EVIDENCE_EXTRACTION_REQUIREMENTS}
{UNCERTAINTY_REASONING}

---
APPLICATION CONTEXT: EXCLUSION CRITERIA (EC) SCREENING
Task: Evaluate whether a paper should be EXCLUDED from a systematic review.
Focus on finding reasons to EXCLUDE. If no exclusion criteria are met,
evaluate whether you can confidently INCLUDE or should ABSTAIN.

EXPLICIT METADATA BLOCK (SOURCE OF TRUTH — USE THESE VALUES):
{metadata_block}

CRITICAL YEAR RULE (STRICT):
- If Year >= 2015, the year criterion is NOT triggered
- NEVER exclude for year reasons if Year >= 2015

{lit_type_warning}

METHODOLOGICAL CONSTRAINTS:
- EC2 (Full Text): Cannot be evaluated at Title/Abstract stage.
  Always evaluate as: "Cannot be determined at Title/Abstract screening"
- EC6 (Duplicates): Ignore — handled deterministically by system
- Evidence: Map extracts specifically to each criterion evaluation

{abstract_instruction}

EXCLUSION CRITERIA (from LOCKED protocol — these are the ONLY rules):
{chr(10).join(criteria_list)}

SCOPE ISOLATION:
Focus ONLY on Exclusion Criteria. Do NOT evaluate Inclusion Criteria (IC).
Your goal is to find reasons to REJECT. If no criteria are triggered,
decide between INCLUDE (if evidence warrants it) or UNCERTAIN (if evidence is weak).

{few_shot_examples}

STRUCTURED OUTPUT REQUIRED — Return ONLY valid JSON:

{{
  "decision": "INCLUDE" or "EXCLUDE" or "UNCERTAIN" or "INSUFFICIENT_EVIDENCE" or "CANNOT_DETERMINE",
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
  "grounding_evidence": ["quotes or close paraphrases from the text supporting your decision — MUST NOT be empty for INCLUDE/EXCLUDE"],
  "uncertainty_reasoning": "explain what is missing or ambiguous (required if decision is UNCERTAIN/INSUFFICIENT_EVIDENCE/CANNOT_DETERMINE)",
  "domain_alignment_reasoning": "brief assessment of how well the paper aligns with the review domain",
  "topic_relevance": {{
    "domain_relevance_score": 0.0-1.0,
    "rq_alignment_strength": 0.0-1.0,
    "methodological_alignment": 0.0-1.0,
    "population_alignment": 0.0-1.0
  }},
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

    def _ec_few_shot_examples(self) -> str:
        """Few-shot calibration examples for EC screening."""
        return """
FEW-SHOT CALIBRATION EXAMPLES:

--- EXAMPLE 1: GOOD UNCERTAIN (vague abstract, weak evidence) ---
Title: "A survey of software engineering practices in small teams"
Abstract: "This paper presents a survey of practices used by small software teams."
Ground truth: Abstract is vague about population, methodology, and specific practices.
Correct output:
{"decision": "UNCERTAIN", "confidence": 0.35, "justification": "Abstract lacks methodological detail and specific population context.",
 "grounding_evidence": [], "triggered_criteria": [],
 "uncertainty_reasoning": "Abstract is too vague to determine eligibility — mentions survey methodology but no details on population, context, or measured outcomes.",
 "topic_relevance": {"domain_relevance_score": 0.4, "rq_alignment_strength": 0.3, "methodological_alignment": 0.5, "population_alignment": 0.2}}

--- EXAMPLE 2: GOOD ABSTENTION (keyword trap, not actually relevant) ---
Title: "Using machine learning to predict software defects"
Abstract: "We apply random forests and neural networks to predict bug-prone code areas in a large industrial software project."
Review context: Protocol is about SE recruitment and selection practices.
Ground truth: ML for defect prediction is NOT about recruitment/selection. Superficial "SE" match only.
Correct output:
{"decision": "UNCERTAIN", "confidence": 0.30, "justification": "Paper uses ML for defect prediction, not recruitment/selection.",
 "uncertainty_reasoning": "Paper is about software defect prediction, not recruitment/selection practices. Keyword overlap is insufficient.",
 "topic_relevance": {"domain_relevance_score": 0.15, "rq_alignment_strength": 0.1, "methodological_alignment": 0.3, "population_alignment": 0.2}}

--- EXAMPLE 3: BAD SPECULATIVE INCLUDE (what NOT to do) ---
Title: "Agile practices in software development"
Abstract: "We report on agile practices used in a large software company."
Review context: Protocol requires studies about SE recruitment and selection.
INCORRECT output:
{"decision": "INCLUDE", "confidence": 0.85, "justification": "Paper discusses agile practices which may relate to selection.",
 "grounding_evidence": ["agile practices in software development"],
 "triggered_criteria": []}
REASON: Speculation. No explicit connection to recruitment/selection. Confidence is inflated.

--- EXAMPLE 4: GOOD EXCLUDE (explicit evidence) ---
Title: "A systematic review of onboarding practices for software engineers"
Abstract: "This systematic review examines 45 studies on onboarding and socialization practices for newly hired software engineers in technology companies."
Review context: Protocol about SE recruitment and selection.
Correct output:
{"decision": "EXCLUDE" if onboarding not in scope, "confidence": 0.92,
 "grounding_evidence": ["systematic review examines onboarding practices", "newly hired software engineers"],
 "triggered_criteria": ["EC1"], "topic_relevance": {"domain_relevance_score": 0.8, "rq_alignment_strength": 0.3, ...}}

--- EXAMPLE 5: MISSING ABSTRACT ---
Title: "Software engineering challenges in 2023"
Abstract: NOT PROVIDED
Correct output:
{"decision": "INSUFFICIENT_EVIDENCE", "confidence": 0.20, "justification": "No abstract available — cannot assess criteria.",
 "grounding_evidence": [], "triggered_criteria": [],
 "uncertainty_reasoning": "Title-only assessment insufficient for reliable EC determination.",
 "topic_relevance": {"domain_relevance_score": 0.3, "rq_alignment_strength": 0.2, "methodological_alignment": 0.1, "population_alignment": 0.1}}
"""

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
        Build structured IC prompt with epistemic calibration for trustworthy
        autonomous screening. Inclusion criteria are evaluated conservatively:
        prefer UNCERTAIN over speculative INCLUDE.
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
        abstract_sanitized = str(abstract)[:600].replace('"', '\\"').replace('\n', ' ').replace('\r', ' ') if abstract else "NOT AVAILABLE"

        few_shot_examples = self._ic_few_shot_examples()

        abstract_instruction = ""
        if abstract_available:
            abstract_instruction = """
ABSTRACT MANDATORY USAGE:
- The Abstract IS PROVIDED above. Extract at least 1-2 evidence snippets.
- Empty grounding_evidence will cap confidence below 0.8.
- If abstract content does not explicitly address IC criteria,
  prefer UNCERTAIN over speculative INCLUDE."""
        else:
            abstract_instruction = """
ABSTRACT NOT AVAILABLE: Decision should default to INSUFFICIENT_EVIDENCE
unless title alone provides clear inclusion signals."""

        prompt = f"""{EPISTEMIC_SYSTEM_CORE}
{DECISION_SEMANTICS}
{CONFIDENCE_SEMANTICS}
{TOPIC_RELEVANCE_INSTRUCTIONS}
{EVIDENCE_EXTRACTION_REQUIREMENTS}
{UNCERTAINTY_REASONING}

---
APPLICATION CONTEXT: INCLUSION CRITERIA (IC) SCREENING
Task: Evaluate whether a paper meets the INCLUSION CRITERIA for a systematic review.
Articles have already PASSED EC screening — they are empirical and recent.
Your job is to determine RELEVANCE to the research question.

CRITICAL METADATA (SOURCE OF TRUTH):
- Title: "{title_sanitized}"
- Year: {year_display} {"✓ YEAR PROVIDED" if has_year else "✗ YEAR NOT PROVIDED"}
- Authors: {authors_display} {"✓ AUTHORS PROVIDED" if has_authors else "✗ AUTHORS NOT PROVIDED"}
- Abstract: {"AVAILABLE" if abstract_available else "NOT AVAILABLE"}
- Literature Type: {literature_type}
- Metadata Completeness: {metadata_completeness}

INCLUSION CRITERIA (protocol-authoritative — these are the ONLY rules):
{chr(10).join([f"- {k}: {v}" for k, v in criteria.items()])}

{abstract_instruction}

{few_shot_examples}

STRUCTURED OUTPUT REQUIRED — Return ONLY valid JSON:

{{
  "decision": "INCLUDE" or "EXCLUDE" or "UNCERTAIN" or "INSUFFICIENT_EVIDENCE" or "CANNOT_DETERMINE",
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
  "grounding_evidence": ["quotes or close paraphrases from the text supporting your decision — MUST NOT be empty for INCLUDE/EXCLUDE"],
  "uncertainty_reasoning": "explain what is missing or ambiguous (required if decision is UNCERTAIN/INSUFFICIENT_EVIDENCE/CANNOT_DETERMINE)",
  "domain_alignment_reasoning": "brief assessment of how well the paper aligns with the review domain",
  "topic_relevance": {{
    "domain_relevance_score": 0.0-1.0,
    "rq_alignment_strength": 0.0-1.0,
    "methodological_alignment": 0.0-1.0,
    "population_alignment": 0.0-1.0
  }},
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

            topic_relevance_raw = parsed.get("topic_relevance", {})
            if not isinstance(topic_relevance_raw, dict):
                topic_relevance_raw = {}

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
                grounding_evidence=parsed.get("grounding_evidence", []),
                uncertainty_reasoning=parsed.get("uncertainty_reasoning", ""),
                domain_alignment_reasoning=parsed.get("domain_alignment_reasoning", ""),
                topic_relevance={
                    "domain_relevance_score": float(topic_relevance_raw.get("domain_relevance_score", 0.0)),
                    "rq_alignment_strength": float(topic_relevance_raw.get("rq_alignment_strength", 0.0)),
                    "methodological_alignment": float(topic_relevance_raw.get("methodological_alignment", 0.0)),
                    "population_alignment": float(topic_relevance_raw.get("population_alignment", 0.0)),
                },
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