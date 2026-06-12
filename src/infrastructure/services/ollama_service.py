import asyncio
import json
import logging
import os
from collections.abc import Callable
from typing import Any, Optional

import httpx

from src.domain.enums import ScreeningStatus
from src.domain.interfaces import LLMService
from src.domain.models import Criterion, Paper, ScreeningDecision

logger = logging.getLogger(__name__)

_MAX_ABSTRACT_LENGTH = 4000

_SYSTEM_PROMPT_WL = (
    "You are a strict academic screener for a Systematic Literature Review "
    "(SLR) on Recruitment & Selection (R&S) of professionals in Software "
    "Engineering (SE).\n\n"
    "## Your task\n"
    "Evaluate a paper's title and abstract against the inclusion/exclusion "
    "protocol below. Return a single JSON object — no prose, no markdown "
    "fences.\n\n"
    "## CRITICAL DECISION RULE (apply this first)\n"
    "If ANY exclusion criterion (EC1–EC6) is clearly satisfied, the decision "
    "is EXCLUDED. You MUST NOT assign any inclusion criterion (IC1–IC5) when "
    "an EC is applied. EC and IC are mutually exclusive. A paper cannot be "
    "both included and excluded.\n\n"
    "## Inclusion Criteria — ALL require an explicit, unambiguous signal in "
    "the text\n"
    "Apply ONLY when the paper's PRIMARY focus is the hiring pipeline for SE "
    "roles.\n\n"
    "IC1 — The paper explicitly addresses processes of RECRUITING or "
    "SELECTING candidates for Software Engineering roles (programmer, "
    "developer, architect, tester, tech lead, SE manager).\n\n"
    "IC1 REQUIRES at least one of these signals to be present:\n"
    "  • Describes steps to attract, source, or shortlist SE candidates\n"
    "  • Describes job interviews or technical assessments used to HIRE "
    "developers\n"
    "  • Describes tools or systems used to screen or rank job applicants "
    "in SE\n"
    "  • Analyzes job postings/ads to understand SE hiring demand\n"
    "  • Surveys or interviews HIRING MANAGERS or RECRUITERS about SE "
    "hiring practices\n\n"
    "IC1 MUST NOT be applied when:\n"
    "  • The article is about retaining, motivating, or managing EXISTING "
    "employees\n"
    "  • The article studies SE methods (agile, testing, code review, "
    "requirements) without any hiring/recruitment context\n"
    "  • The word \"interview\" refers to a research method (interviewing "
    "developers about their practices), not a job selection interview\n"
    "  • The word \"assessment\" refers to evaluating software quality or a "
    "system, not evaluating a job candidate\n"
    "  • The article is about education, university curricula, or student "
    "skill gaps (unless the primary focus is internship hiring or industry "
    "onboarding)\n"
    "  • The article discusses \"talent\" in the context of retention or "
    "career growth, not the acquisition/hiring pipeline\n"
    "  • The article is about HR practices in general IT companies without "
    "specific focus on the SE role hiring pipeline\n\n"
    "IC2 — The paper describes a specific pipeline, framework, or structured "
    "procedure used in the R&S process for SE roles (e.g., multi-stage "
    "interview process, automated resume screening workflow, technical test "
    "pipeline). Only apply if IC1 also applies.\n\n"
    "IC3 — The paper reports challenges, friction, or perceptions "
    "specifically related to R&S of SE professionals (e.g., difficulty "
    "finding qualified candidates, bias in technical interviews, candidate "
    "experience in SE hiring). Only apply if IC1 also applies.\n\n"
    "IC4 — The paper describes evaluation methods or assessment mechanisms "
    "used to HIRE SE professionals (e.g., coding tests, take-home "
    "assignments, pair programming interviews, structured technical "
    "interviews). Only apply if IC1 also applies.\n\n"
    "IC5 — The paper provides empirical findings or practitioner "
    "experiences specifically about R&S practices in SE. Only apply if IC1 "
    "also applies.\n\n"
    "## Exclusion Criteria\n"
    "EC1 — Not written in English.\n"
    "EC2 — Full text unavailable.\n"
    "EC3 — Short publication without sufficient methodological evidence "
    "(editorial, poster, extended abstract, news article, magazine column). "
    "Also apply EC3 to: practitioner advice columns, career tip articles, salary "
    "negotiation guides, and similar short-form practitioner content without "
    "empirical data or research methodology.\n"
    "EC4 — Published before 2015.\n"
    "EC5 — Not related to Recruitment & Selection in Software Engineering.\n"
    "      Apply EC5 when the paper is primarily about:\n"
    "        • Software development methods (agile, testing, DevOps, code "
    "review, requirements engineering, architecture, program repair, etc.)\n"
    "        • General organizational behavior, HR management, or job "
    "satisfaction for already-hired employees\n"
    "        • Education, academic curricula, or student skill development\n"
    "        • AI/ML techniques applied to non-hiring domains\n"
    "        • Information retrieval, NLP, or data science without hiring "
    "context\n"
    "        • Any domain outside of SE (medicine, finance, physics, "
    "biology, etc.)\n"
    "  NOTE: Do NOT apply EC5 to papers that study the hiring/recruitment\n"
    "  process FROM a bias, fairness, or discrimination lens — these are\n"
    "  explicitly about the R&S pipeline and must be evaluated for IC1.\n"
    "EC6 — Duplicate study (identical or near-identical paper already in "
    "corpus).\n\n"
    "## Negative examples (papers that must be EXCLUDED despite surface "
    "signals)\n"
    "The following types of papers frequently trigger false inclusion — "
    "always exclude them:\n"
    "  • Paper about retaining software developers → EC5 (retention ≠ "
    "recruitment)\n"
    "  • Paper using \"interview\" as a qualitative research method → EC5 "
    "(method ≠ job interview)\n"
    "  • Paper about \"assessing software quality\" or \"automated test "
    "assessment\" → EC5\n"
    "  • Paper about \"human aspects of software development\" (motivation, "
    "wellbeing, collaboration) → EC5\n"
    "  • Paper about competitive programming platforms → EC5 (unless "
    "framed as recruiter assessment tools)\n"
    "  • Paper about agile methods, user stories, sprint planning → EC5\n"
    "  • Paper about talent retention using AI → EC5 (retention ≠ "
    "recruitment)\n"
    "  • Paper about general IT workforce without SE-specific hiring "
    "pipeline → EC5\n"
    "  • Career advice articles, salary guides, or job-search tips aimed at "
    "candidates → EC3 (no methodological contribution), even if the topic is "
    "IT/SE careers\n"
    "  • Paper about well-being, mental health, burnout, or work-life balance "
    "of software engineers → EC5 (post-hire employee experience ≠ R&S "
    "pipeline; Regra 1)\n"
    "  • Paper whose title contains no SE or R&S keyword and has no abstract "
    "available → EXCLUDE under EC5 by default (insufficient evidence to "
    "include)\n"
    "  • Paper about NLP, dialogue systems, conversational AI, or language "
    "model techniques applied to software tools → EC5 (SE methods domain, "
    "not hiring pipeline)\n"
    "  • Paper reporting bias, discrimination, or unfairness IN the hiring\n"
    "    process (gender, race, age) → INCLUDE under IC1;IC3, even if the\n"
    "    primary method is a survey or experiment (NOT EC5)\n"
    "  • Paper extracting or analyzing skills/competencies from job postings\n"
    "    or job advertisements → INCLUDE under IC1;IC2 (job ads ARE R&S signals)\n"
    "  • Paper studying what attributes distinguish good from average SE\n"
    "    candidates, or what hiring managers look for in SE candidates\n"
    "    → INCLUDE under IC1;IC3;IC5 (this IS the R&S evaluation problem)\n"
    "  • Paper about AI-generated or NLP-processed resumes/CVs in the context\n"
    "    of hiring → INCLUDE under IC1;IC3 (resumes only exist for R&S)\n"
    "  • Competitive coding or developer skill profile platform "
    "(e.g. LeetCode-style, OSS activity visualizer, coding leaderboard)"
    " → EC5, even if recruiters are mentioned as secondary users. "
    "The PRIMARY purpose must be the hiring pipeline, not developer "
    "self-improvement or portfolio building.\n"
    "  • Paper about LLM-based agent teaming, multi-agent coordination, "
    "or team composition as an AI/operations-research problem → EC5. "
    "Distinguish from IC1: 'selecting team members for a project' in an "
    "agent simulation is NOT the same as 'selecting candidates for a "
    "software engineering job'.\n"
    "  • Paper with 'recruitment' or 'hiring' only as MOTIVATION for a "
    "tool, not as the PRIMARY CONTRIBUTION. Ask: if you remove the "
    "recruitment framing, does the paper still make sense? If yes → EC5. "
    "Also: if publication year is before 2015, apply EC4 regardless of "
    "R&S relevance.\n"
    "  • Paper titled 'What distinguishes/makes great/excellent [role]?' "
    "or 'What skills do [role] need?' WITHOUT an abstract → "
    "INCLUDE under IC1;IC3;IC5 if the role is a software engineering "
    "role. These papers study hiring evaluation criteria even without "
    "explicitly using the word 'recruitment'.\n"
    "  • Paper with 'recruitment signals', 'job advertisements', or "
    "'job postings' in the TITLE → INCLUDE under IC1;IC2 regardless "
    "of whether the abstract focuses on methodology (e.g. competency "
    "frameworks, agile management). Job ads are primary R&S data sources."
)

_SYSTEM_PROMPT_GL = (
    "You are a strict academic screener for a Systematic Literature Review "
    "(SLR) on Recruitment & Selection (R&S) of professionals in Software "
    "Engineering (SE).\n\n"
    "## Your task\n"
    "Evaluate a grey literature item (web page, blog post, industry report, "
    "job board, or practitioner article) against the inclusion/exclusion "
    "protocol below. Grey literature does NOT have a structured abstract — "
    "you will receive scraped web content. Evaluate based on the PRIMARY "
    "PURPOSE of the page, not surface keywords.\n\n"
    "## CRITICAL DECISION RULE\n"
    "If ANY exclusion criterion (EC1–EC6) is clearly satisfied, the decision "
    "is EXCLUDED. EC and IC are mutually exclusive.\n\n"
    "## Inclusion Criteria for Grey Literature\n"
    "IC1 — The page's PRIMARY purpose is describing, documenting, or "
    "reporting on the process of RECRUITING or SELECTING candidates for "
    "Software Engineering roles.\n\n"
    "IC1 APPLIES to grey literature when the page:\n"
    "  • Is a job posting or vacancies page listing open SE roles with "
    "hiring criteria (e.g. required skills, application process)\n"
    "  • Describes a documented pre-employment screening process used by "
    "an IT/SE organisation (e.g. security checks, technical assessments)\n"
    "  • Is an industry report or survey about SE hiring practices, "
    "recruiter behaviour, or candidate experience in tech hiring\n"
    "  • Describes a tool, platform, or service explicitly designed to "
    "screen, assess, or rank SE job candidates\n\n"
    "IC1 MUST NOT be applied when the page:\n"
    "  • Discusses software engineering practices, tools, or methods "
    "without a hiring context\n"
    "  • Is an opinion piece, blog post, or editorial about the future "
    "of SE, AI in coding, or tech industry trends — even if authored "
    "by a known engineer\n"
    "  • Is an employer branding or 'careers at company X' marketing page "
    "that describes the company culture without documenting R&S steps\n"
    "  • Is a career guide, salary article, or job-search advice page "
    "aimed at candidates (not describing employer R&S processes)\n"
    "  • Lists university courses, student theses, or academic programmes\n\n"
    "IC2 — The page describes a specific pipeline, workflow, or structured "
    "procedure used in R&S for SE roles. Only apply if IC1 applies.\n\n"
    "IC3 — The page reports challenges, friction, or perceptions related "
    "to R&S of SE professionals. Only apply if IC1 applies.\n\n"
    "IC4 — The page describes evaluation methods or assessments used to "
    "hire SE professionals. Only apply if IC1 applies.\n\n"
    "IC5 — The page provides empirical findings or practitioner experiences "
    "about R&S practices in SE. Only apply if IC1 applies.\n\n"
    "## Exclusion Criteria\n"
    "EC1 — Content not in English.\n"
    "EC2 — Page content unavailable (no text scraped, access blocked, "
    "login required, or content too short to evaluate).\n"
    "EC3 — Short-form content without methodological or experiential "
    "substance: news snippets, social media posts, short blog entries, "
    "career tip listicles, salary guides, magazine columns.\n"
    "EC4 — Published before 2015.\n"
    "EC5 — Not related to R&S in SE. Apply when the page is primarily "
    "about SE methods, tools, practices, education, career advice, "
    "employer branding, IT operations, or any non-R&S topic.\n"
    "EC6 — Duplicate.\n\n"
    "## Negative examples — grey literature that must be EXCLUDED\n"
    "  • Blog post about 'the future of software engineering' or 'AI in "
    "coding' → EC5, even if written by a famous engineer\n"
    "  • Company 'IT careers' or 'work with us' page describing culture "
    "without documenting the hiring pipeline → EC5\n"
    "  • Article listing highest-paying SE jobs → EC3;EC5\n"
    "  • University course catalogue or student thesis list → EC3;EC5\n"
    "  • Time-tracking or productivity tool for developers → EC5\n"
    "  • Job board page that failed to load (no content) → EC2\n"
    "  • Blog post or opinion article about future trends in software "
    "engineering, AI in coding, or what it means to be a software "
    "engineer in the coming years → EC5, even if the author is a "
    "well-known engineer and even if the article discusses skills or "
    "roles. Future-of-SE content is NOT R&S research.\n\n"
    "## Positive examples — grey literature that must be INCLUDED\n"
    "  • Company security screening policy describing pre-hire background "
    "checks for IT staff → IC1;IC2;IC4\n"
    "  • Vacancies page of a research software engineering organisation "
    "listing open roles with required skills and application steps → IC1\n"
    "  • Industry white paper reporting survey results on how tech companies "
    "conduct technical interviews → IC1;IC3;IC5\n"
    "  • Tool vendor page describing an automated CV screening platform "
    "for software developers → IC1;IC2;IC4\n"
    "  • Vacancies or open positions page from a software engineering "
    "organisation listing roles with required skills, qualifications, "
    "or application instructions → IC1, even if the page is short and "
    "has no methodology. Job postings are grey literature evidence of "
    "R&S practices. Do NOT apply EC3 to job posting pages.\n"
    "  • Page with scraped content that is mostly cookies/navigation "
    "boilerplate but whose TITLE clearly indicates a pre-employment "
    "screening or security vetting policy for IT/SE roles → IC1;IC2;IC4."
    " Apply EC2 only if there is truly zero substantive content.\n\n"
    "You MUST respond with ONLY a valid JSON object — no markdown, "
    "no commentary."
)

_PROMPT_HEADER = """## Paper
- Title: {title}
- Abstract: {abstract}
- Source Type: {source_type}
- Publication Year: {publication_year}
- Metadata: {metadata}

## Criteria List
{criteria_text}

## Instructions - follow this THREE-STEP logic strictly

### STEP 1 - Evaluate EVERY Criterion (Exhaustive Chain-of-Thought)
Analyze the abstract against EACH criterion below one by one. You MUST
evaluate EVERY criterion — do NOT stop after finding the first match.
For each criterion, reason step-by-step and determine whether it applies
(true) or does not apply (false).

Exclusion Criteria:
{ec_section}

Inclusion Criteria:
{ic_section}

### STEP 2 - Determine Decision from Evaluations
- If ANY Exclusion Criterion is true → decision is "EXCLUDED"
- If ALL Exclusion Criteria are false AND at least one Inclusion
  Criterion is true → decision is "INCLUDED"
- If all criteria are false or it is unclear → decision is "NEEDS_REVIEW"

### STEP 3 - Write Concise Reasoning
Write a concise step-by-step reasoning (max 80 words) that references
the evaluation of each criterion and justifies the final decision.

### CRITICAL GUIDELINES (AVOID FALSE NEGATIVES):
1. INCLUDE borderline topics: Papers exploring "developer career paths",
   "tech diversity/gender barriers", or "Open Source joining trajectories"
   are VALID Recruitment & Selection (R&S) topics. Do NOT exclude them.
2. EXCLUDE technical mechanics: Papers evaluating "Code Reviews",
   "Pull Requests", or "UI/UX Testing" must be EXCLUDED unless they
   explicitly target candidate screening or hiring.
3. Do NOT guess the publication year from the abstract text (e.g., future
   vision dates like 'Vision 2030'). Rely ONLY on the 'Publication Year'
   metadata provided above.

## Response Format (JSON only)
{{"reasoning": "<step-by-step chain-of-thought analysis>", "criteria_evaluation": {{"EC1": false, "EC2": false, "IC1": true, ...}}, "decision": "INCLUDED" | "EXCLUDED" | "NEEDS_REVIEW"}}"""


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

    # Try new "decision" field first, fall back to old "status" field
    decision_raw = data.get("decision")
    if decision_raw not in ("INCLUDED", "EXCLUDED", "NEEDS_REVIEW"):
        decision_raw = data.get("status")
        if decision_raw not in ("INCLUDED", "EXCLUDED", "NEEDS_REVIEW"):
            logger.warning(
                "LLM returned invalid decision '%s' for paper %s", decision_raw, paper_id
            )
            return _fallback_decision(paper_id, f"invalid decision '{decision_raw}'")

    reasoning = data.get("reasoning") or data.get("rationale", "")

    # Extract true criteria from criteria_evaluation map
    criteria_eval: dict = data.get("criteria_evaluation", {})
    applied_codes: list[str] = [
        code for code, val in criteria_eval.items() if val is True
    ]

    # Fall back to old applied_criteria_codes list if no evaluation map
    if not applied_codes:
        applied_codes = data.get("applied_criteria_codes", [])

    # ── Exclusivity guard ──────────────────────────────────────────────────
    ic_codes = {c for c in applied_codes if c.startswith("IC")}
    ec_codes = {c for c in applied_codes if c.startswith("EC")}

    if ic_codes and ec_codes:
        applied_codes = sorted(ec_codes)
        if decision_raw == "INCLUDED":
            decision_raw = "EXCLUDED"
        logger.warning(
            "IC+EC conflict resolved for paper %s: kept %s, dropped %s",
            paper_id,
            sorted(ec_codes),
            sorted(ic_codes),
        )

    if ic_codes and not ec_codes:
        if any(c in ("IC2", "IC3", "IC4", "IC5") for c in ic_codes) and "IC1" not in ic_codes:
            decision_raw = "NEEDS_REVIEW"
            logger.warning(
                "Orphan IC without IC1 for paper %s: %s", paper_id, sorted(ic_codes)
            )

    # Compute confidence from decision clarity (no longer relies on model)
    confidence = 1.0 if decision_raw != "NEEDS_REVIEW" else 0.5

    return ScreeningDecision(
        paper_id=paper_id,
        status=ScreeningStatus(decision_raw),
        confidence_score=confidence,
        rationale=str(reasoning),
        applied_criteria_codes=list(applied_codes),
    )


class UnifiedLLMService(LLMService):
    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        client: httpx.AsyncClient | None = None,
        settings_provider: Callable[[str, str], str] | None = None,
    ) -> None:
        self._model = model or os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
        base = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        self._base_url = base if base.endswith("/") else base + "/"
        self._client = client
        self._owns_client = client is None
        self._settings_provider = settings_provider

    def _resolve_settings(self) -> tuple[str, str, str, str]:
        if self._settings_provider is None:
            return self._model, self._base_url, "", "ollama"
        provider = self._settings_provider("llm_provider", "ollama")
        base_url = self._settings_provider("llm_base_url", self._base_url)
        base_url = base_url if base_url.endswith("/") else base_url + "/"
        model = self._settings_provider("llm_model", self._model)
        api_key = self._settings_provider("llm_api_key", "")
        return model, base_url, api_key, provider

    async def _post_with_retry(
        self,
        client: httpx.AsyncClient,
        model: str,
        messages: list[dict],
        headers: dict | None,
        paper_id: str,
        max_retries: int = 4,
        cooldown_callback: Callable[[float], None] | None = None,
    ) -> dict:
        for attempt in range(max_retries):
            try:
                response = await client.post(
                    "chat/completions",
                    json={
                        "model": model,
                        "messages": messages,
                        "temperature": 0.0,
                        "response_format": {"type": "json_object"},
                    },
                    headers=headers,
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429 and attempt < max_retries - 1:
                    retry_after = exc.response.headers.get("Retry-After")
                    if retry_after:
                        try:
                            delay = int(retry_after)
                        except (ValueError, TypeError):
                            delay = 3 * (2**attempt)
                    else:
                        delay = 3 * (2**attempt)
                    logger.warning(
                        "Rate limit hit (429) for paper %s. Retrying in %s seconds...",
                        paper_id,
                        delay,
                    )
                    if cooldown_callback:
                        cooldown_callback(float(delay))
                    await asyncio.sleep(delay)
                    if cooldown_callback:
                        cooldown_callback(0.0)
                    continue
                raise
        raise RuntimeError("Unreachable — post_with_retry exhausted all attempts")

    async def screen_paper(
        self,
        paper: Paper,
        criteria: list[Criterion],
        few_shot_examples: list[dict] | None = None,
        cooldown_callback: Callable[[float], None] | None = None,
    ) -> ScreeningDecision:
        model, base_url, api_key, _provider = self._resolve_settings()
        client = self._client or httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(300.0),
        )
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        try:
            messages = self._build_messages(paper, criteria, few_shot_examples)
            body = await self._post_with_retry(
                client, model, messages, headers or None, paper.id,
                cooldown_callback=cooldown_callback,
            )
            content: str = body["choices"][0]["message"]["content"]
            return _parse_llm_response(paper.id, content)
        except httpx.HTTPStatusError as exc:
            logger.error("LLM HTTP %s for paper %s", exc.response.status_code, paper.id)
            return _fallback_decision(paper.id, f"HTTP {exc.response.status_code}")
        except httpx.RequestError as exc:
            logger.error("LLM request failed for paper %s: %s", paper.id, exc)
            return _fallback_decision(paper.id, str(exc))
        except (KeyError, IndexError, TypeError) as exc:
            logger.error("Unexpected LLM response structure for paper %s: %s", paper.id, exc)
            return _fallback_decision(paper.id, "unexpected response structure")
        finally:
            if self._owns_client:
                try:
                    await client.aclose()
                except TypeError:
                    pass

    def _build_messages(self, paper: Paper, criteria: list[Criterion], few_shot_examples: list[dict] | None = None) -> list[dict[str, str]]:
        criteria_text = _format_criteria(criteria)
        ec_section = _compile_ec_section(criteria)
        ic_section = _compile_ic_section(criteria)

        abstract = (paper.abstract or "(no abstract)")[:_MAX_ABSTRACT_LENGTH]
        metadata_str = json.dumps(paper.metadata, ensure_ascii=False)
        year_str = str(paper.publication_year) if paper.publication_year is not None else "Unknown"

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

        # Select prompt based on source type
        is_grey = str(getattr(paper, 'source_type', '') or '').upper() in (
            'GL', 'GREY', 'GREY_LITERATURE', 'GRAY', 'GRAY_LITERATURE'
        )
        if not is_grey:
            is_grey = str(getattr(paper, 'paper_id', '') or '').startswith('GL-')
        system_content = _SYSTEM_PROMPT_GL if is_grey else _SYSTEM_PROMPT_WL

        if few_shot_examples:
            blocks = [
                "\n### CALIBRATION MEMORY (LEARN FROM THESE EXAMPLES):",
                "Below are examples of how the human researcher explicitly classified papers for this study. Mimic this reasoning:\n",
            ]
            for ex in few_shot_examples:
                abstract_preview = (ex.get("abstract") or "")[:500]
                blocks.append(
                    f"EXAMPLE TITLE: {ex.get('title') or ''}\n"
                    f"EXAMPLE ABSTRACT: {abstract_preview}...\n"
                    f"HUMAN GROUND TRUTH DECISION: {ex.get('human_decision') or ''}"
                )
            system_content += "\n\n" + "\n\n".join(blocks)

        return [
            {"role": "system", "content": system_content},
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
        abstract = (paper.abstract or "(no abstract)")[:_MAX_ABSTRACT_LENGTH]
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

        model, base_url, api_key, _provider = self._resolve_settings()
        client = self._client or httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(300.0),
        )
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            body = await self._post_with_retry(
                client, model, messages, headers or None, paper.id
            )
            content: str = body["choices"][0]["message"]["content"]
            data: dict = json.loads(content)
            return {
                "q1": float(data.get("q1", 0.0)),
                "q2": float(data.get("q2", 0.0)),
                "q3": float(data.get("q3", 0.0)),
                "q4": float(data.get("q4", 0.0)),
                "rationale": str(data.get("rationale", "")),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("Quality HTTP %s for paper %s", exc.response.status_code, paper.id)
        except httpx.RequestError as exc:
            logger.error("Quality request failed for paper %s: %s", paper.id, exc)
        except Exception as exc:
            logger.error("Quality assessment failed for paper %s: %s", paper.id, exc)
        finally:
            if self._owns_client:
                try:
                    await client.aclose()
                except TypeError:
                    pass
        return {"q1": 0.0, "q2": 0.0, "q3": 0.0, "q4": 0.0, "rationale": "Error"}


    async def aclose(self) -> None:
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception:
                pass
            finally:
                self._client = None

# Backward-compatible alias — all existing imports of OllamaLLMService continue to work.
OllamaLLMService = UnifiedLLMService
