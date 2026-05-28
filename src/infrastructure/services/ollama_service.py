import json
import logging
import os
from typing import Any

import httpx

from src.domain.enums import ScreeningStatus
from src.domain.interfaces import LLMService
from src.domain.models import Criterion, Paper, ScreeningDecision

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a strict scientific reviewer conducting a Systematic Literature "
    "Review (SLR) following the Garousi et al. Multivocal Literature Review "
    "(MLR) protocol. Your screening must follow a strict two-step sequential "
    "logic: first evaluate ALL Exclusion Criteria (EC); only if none match do "
    "you proceed to evaluate Inclusion Criteria (IC). Be conservative and "
    "critical — do NOT leniently include papers. "
    "Respond with ONLY a valid JSON object — no markdown, no commentary."
)

_PROMPT_HEADER = """## Paper
- Title: {title}
- Abstract: {abstract}
- Source Type: {source_type}
- Year: {publication_year}
- Metadata: {metadata}

## Criteria List
{criteria_text}

## Instructions - follow this TWO-STEP logic strictly

### STEP 1 - Exclusion Criteria (EC)
Check EVERY Exclusion Criterion. In particular:
{ec_section}

- If ANY EC criterion matches, the paper is EXCLUDED. Write your EC
  reasoning first, then stop.

### STEP 2 - Inclusion Criteria (IC)
Only if NO EC criterion matched: evaluate the Inclusion Criteria.
{ic_section}

- If the paper satisfies the Inclusion Criteria, mark INCLUDED.
  If it does not, mark EXCLUDED.
- If you cannot determine, mark NEEDS_REVIEW.

### Required reasoning format
The 'AI Rationale' must be highly concise, precise, and limited to a
maximum of 60 words. Immediately specify the exact criterion (e.g., EC5
or IC1) and state the direct cause. Do NOT write generic introductory
sentences or full paragraphs of summary.

### CRITICAL GUIDELINES (AVOID FALSE NEGATIVES):
1. INCLUDE border-line topics: Papers exploring "developer career paths", "tech diversity/gender barriers", or "Open Source joining trajectories" are VALID Recruitment & Selection (R&S) topics. Do NOT exclude them.
2. EXCLUDE technical mechanics: Papers evaluating "Code Reviews", "Pull Requests", or "UI/UX Testing" must be EXCLUDED unless they explicitly target candidate screening or hiring.

## Response Format (JSON only)
{{"status": "INCLUDED" | "EXCLUDED" | "NEEDS_REVIEW", "confidence_score": <0.0-1.0>, "rationale": "<step-by-step reasoning>", "applied_criteria_codes": ["code1", ...]}}"""


def _format_criteria(criteria: list[Criterion]) -> str:
    lines: list[str] = []
    for c in criteria:
        tag = "INCLUSION" if c.type.value == "INCLUSION" else "EXCLUSION"
        lines.append(f"  - [{tag}] {c.code}: {c.description}")
    return "\n".join(lines) if lines else "  (none)"


def _compile_ec_section(criteria: list[Criterion]) -> str:
    ec = [c for c in criteria if c.type.value == "EXCLUSION"]
    return "\n".join(f"- {c.code}: {c.description}" for c in ec) or "  (none)"


def _compile_ic_section(criteria: list[Criterion]) -> str:
    ic = [c for c in criteria if c.type.value == "INCLUSION"]
    return "\n".join(f"- {c.code}: {c.description}" for c in ic) or "  (none)"


def _fallback_decision(paper_id: str, reason: str = "LLM error") -> ScreeningDecision:
    return ScreeningDecision(
        paper_id=paper_id,
        status=ScreeningStatus.NEEDS_REVIEW,
        confidence_score=0.0,
        rationale=f"Screening failed — {reason}.",
        applied_criteria_codes=[],
    )


def _parse_llm_response(paper_id: str, content: str) -> ScreeningDecision:
    try:
        data: dict[str, Any] = json.loads(content)
    except json.JSONDecodeError:
        logger.warning("LLM returned malformed JSON for paper %s", paper_id)
        return _fallback_decision(paper_id, "malformed JSON from LLM")

    status_raw = data.get("status")
    if status_raw not in ("INCLUDED", "EXCLUDED", "NEEDS_REVIEW"):
        logger.warning("LLM returned invalid status '%s' for paper %s", status_raw, paper_id)
        return _fallback_decision(paper_id, f"invalid status '{status_raw}'")

    confidence = data.get("confidence_score")
    if not isinstance(confidence, (int, float)) or not (0.0 <= confidence <= 1.0):
        logger.warning("LLM returned out-of-range confidence %s for paper %s", confidence, paper_id)
        return _fallback_decision(paper_id, f"invalid confidence {confidence}")

    rationale = data.get("rationale", "")
    applied_codes: list[str] = data.get("applied_criteria_codes", [])

    return ScreeningDecision(
        paper_id=paper_id,
        status=ScreeningStatus(status_raw),
        confidence_score=float(confidence),
        rationale=str(rationale),
        applied_criteria_codes=list(applied_codes),
    )


class OllamaLLMService(LLMService):
    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._model = model or os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
        base = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        self._base_url = base.rstrip("/")
        self._client = client or httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(300.0),
        )

    async def screen_paper(
        self,
        paper: Paper,
        criteria: list[Criterion],
    ) -> ScreeningDecision:
        try:
            messages = self._build_messages(paper, criteria)
            response = await self._client.post(
                "/chat/completions",
                json={
                    "model": self._model,
                    "messages": messages,
                    "temperature": 0.0,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            body = response.json()
            content: str = body["choices"][0]["message"]["content"]
            return _parse_llm_response(paper.id, content)
        except httpx.HTTPStatusError as exc:
            logger.error("Ollama HTTP %s for paper %s", exc.response.status_code, paper.id)
            return _fallback_decision(paper.id, f"HTTP {exc.response.status_code}")
        except httpx.RequestError as exc:
            logger.error("Ollama request failed for paper %s: %s", paper.id, exc)
            return _fallback_decision(paper.id, str(exc))
        except (KeyError, IndexError, TypeError) as exc:
            logger.error("Unexpected Ollama response structure for paper %s: %s", paper.id, exc)
            return _fallback_decision(paper.id, "unexpected response structure")

    def _build_messages(self, paper: Paper, criteria: list[Criterion]) -> list[dict[str, str]]:
        criteria_text = _format_criteria(criteria)
        ec_section = _compile_ec_section(criteria)
        ic_section = _compile_ic_section(criteria)

        abstract = paper.abstract or "(no abstract)"
        metadata_str = json.dumps(paper.metadata, ensure_ascii=False)
        year_str = str(paper.publication_year) if paper.publication_year is not None else "N/A"

        user_content = _PROMPT_HEADER.format(
            title=paper.title,
            abstract=abstract,
            source_type=paper.source_type.value,
            publication_year=year_str,
            metadata=metadata_str,
            criteria_text=criteria_text,
            ec_section=ec_section,
            ic_section=ic_section,
        )

        if paper.source_type.value == "GL":
            gl_warning = (
                "[WARNING: The following paper is Grey Literature (GL) written by a practitioner. "
                "Do NOT expect traditional academic structures, literature reviews, or formal empirical "
                "methodologies. Evaluate the eligibility strictly based on whether it reports real-world "
                "industry practices, corporate hiring procedures, blog post narratives, or lived experiences "
                "of candidates/recruiters (IC5). If it does, do not exclude under EC5.]\n\n"
            )
            user_content = gl_warning + user_content

        return [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

    # ── Quality Assessment ──────────────────────────────────────────────────

    _QUALITY_SYSTEM_PROMPT = (
        "You are a rigorous methodological quality assessor in a Systematic "
        "Literature Review (SLR). Evaluate the paper against the quality "
        "criteria below. Respond with ONLY a valid JSON object — no markdown, "
        "no commentary."
    )

    _WL_QA_PROMPT = """## Paper
- Title: {title}
- Abstract: {abstract}
- Source Type: White Literature (WL)
- Year: {publication_year}

## Quality Assessment Questions (WL — White Literature)

Answer each question with 1.0 (Yes), 0.5 (Partially), or 0.0 (No).

**WL-Q1**: Is the research design clearly described and appropriate for the stated objectives?
- 1.0 = Yes, clearly described and fully appropriate.
- 0.5 = Partially described or partially appropriate.
- 0.0 = No, not described or inappropriate.

**WL-Q2**: Is the data collection methodology clearly described and suitable for the research context?
- 1.0 = Yes, clearly described and suitable.
- 0.5 = Partially described or partially suitable.
- 0.0 = No, not described or unsuitable.

**WL-Q3**: Are the analytical methods rigorous and appropriate for the data collected?
- 1.0 = Yes, rigorous and appropriate.
- 0.5 = Partially rigorous or partially appropriate.
- 0.0 = No, not rigorous or inappropriate.

**WL-Q4**: Are the conclusions supported by the evidence and are limitations discussed?
- 1.0 = Yes, conclusions supported and limitations discussed.
- 0.5 = Partially supported or limitations only partially addressed.
- 0.0 = No, conclusions unsupported or no limitations discussed.

## Response Format (JSON only)
{{"q1": <1.0|0.5|0.0>, "q2": <1.0|0.5|0.0>, "q3": <1.0|0.5|0.0>, "q4": <1.0|0.5|0.0>, "rationale": "<brief explanation>"}}"""

    _GL_QA_PROMPT = """## Paper
- Title: {title}
- Abstract: {abstract}
- Source Type: Grey Literature (GL)
- Year: {publication_year}

## Quality Assessment Questions (GL — Grey Literature)

Answer each question with 1.0 (Yes), 0.5 (Partially), or 0.0 (No).

**GL-Q1**: Is the author's expertise or organizational context explicitly stated?
- 1.0 = Yes, explicitly stated.
- 0.5 = Partially stated or implied.
- 0.0 = No, not stated.

**GL-Q2**: Is the source of experience transparent (e.g., specific hiring cycle, personal narrative)?
- 1.0 = Yes, transparent.
- 0.5 = Partially transparent.
- 0.0 = No, not transparent.

**GL-Q3**: Are the claims supported by operational artifacts (e.g., process steps, rubrics, or data)?
- 1.0 = Yes, supported.
- 0.5 = Partially supported.
- 0.0 = No, unsupported.

**GL-Q4**: Does the source provide insights beyond generic employer marketing (e.g., trade-offs)?
- 1.0 = Yes, provides substantive insights.
- 0.5 = Partially insightful.
- 0.0 = No, generic or purely promotional.

## Response Format (JSON only)
{{"q1": <1.0|0.5|0.0>, "q2": <1.0|0.5|0.0>, "q3": <1.0|0.5|0.0>, "q4": <1.0|0.5|0.0>, "rationale": "<brief explanation>"}}"""

    async def evaluate_quality(self, paper: Paper) -> dict:
        abstract = paper.abstract or "(no abstract)"
        year_str = str(paper.publication_year) if paper.publication_year is not None else "N/A"

        if paper.source_type.value == "WL":
            user_content = self._WL_QA_PROMPT.format(
                title=paper.title,
                abstract=abstract,
                publication_year=year_str,
            )
        else:
            user_content = self._GL_QA_PROMPT.format(
                title=paper.title,
                abstract=abstract,
                publication_year=year_str,
            )

        messages = [
            {"role": "system", "content": self._QUALITY_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        try:
            response = await self._client.post(
                "/chat/completions",
                json={
                    "model": self._model,
                    "messages": messages,
                    "temperature": 0.0,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            body = response.json()
            content: str = body["choices"][0]["message"]["content"]
            data: dict = json.loads(content)
            return {
                "q1": float(data.get("q1", 0.0)),
                "q2": float(data.get("q2", 0.0)),
                "q3": float(data.get("q3", 0.0)),
                "q4": float(data.get("q4", 0.0)),
                "rationale": str(data.get("rationale", "")),
            }
        except Exception as exc:
            logger.error("Quality assessment failed for paper %s: %s", paper.id, exc)
            return {"q1": 0.0, "q2": 0.0, "q3": 0.0, "q4": 0.0, "rationale": f"Error: {exc}"}
