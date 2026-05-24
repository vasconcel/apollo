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

_USER_PROMPT_TEMPLATE = """## Paper
- Title: {title}
- Abstract: {abstract}
- Source Type: {source_type}
- Year: {publication_year}
- Metadata: {metadata}

## Criteria
{criteria_text}

## Instructions - follow this TWO-STEP logic strictly

### STEP 1 - Exclusion Criteria (EC)
Check EVERY Exclusion Criterion. In particular:
- EC5 (relevance to SE R&S) is a strict gate: the paper MUST explicitly
  discuss Recruitment & Selection processes, pipelines, challenges, or
  practices for Software Engineering roles. If it does not explicitly
  address SE R&S, mark EXCLUDED under EC5.
- If ANY EC criterion matches, the paper is EXCLUDED. Write your EC
  reasoning first, then stop.

### STEP 2 - Inclusion Criteria (IC)
Only if NO EC criterion matched: evaluate the Inclusion Criteria.
- The paper must actively satisfy ALL relevant IC criteria (empirical
  findings, experiences, practices, challenges in SE R&S).
- If it meets them, mark INCLUDED. If it does not, mark EXCLUDED.
- If you cannot determine, mark NEEDS_REVIEW.

### Required reasoning format
The 'AI Rationale' must be highly concise, precise, and limited to a
maximum of 60 words. Immediately specify the exact criterion (e.g., EC5
or IC1) and state the direct cause. Do NOT write generic introductory
sentences or full paragraphs of summary.

## Response Format (JSON only)
{{"status": "INCLUDED" | "EXCLUDED" | "NEEDS_REVIEW", "confidence_score": <0.0-1.0>, "rationale": "<step-by-step reasoning>", "applied_criteria_codes": ["code1", ...]}}"""


def _format_criteria(criteria: list[Criterion]) -> str:
    lines: list[str] = []
    for c in criteria:
        tag = "INCLUSION" if c.type.value == "INCLUSION" else "EXCLUSION"
        lines.append(f"  - [{tag}] {c.code}: {c.description}")
    return "\n".join(lines) if lines else "  (none)"


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
                    "temperature": 0.1,
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

        abstract = paper.abstract or "(no abstract)"
        metadata_str = json.dumps(paper.metadata, ensure_ascii=False)
        year_str = str(paper.publication_year) if paper.publication_year is not None else "N/A"

        user_content = _USER_PROMPT_TEMPLATE.format(
            title=paper.title,
            abstract=abstract,
            source_type=paper.source_type.value,
            publication_year=year_str,
            metadata=metadata_str,
            criteria_text=criteria_text,
        )

        return [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]
