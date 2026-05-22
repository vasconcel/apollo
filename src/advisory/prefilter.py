"""
APOLLO Advisory Prefilter: Deterministic Heuristic Exclusion

Before ANY LLM call, detect obvious non-study artifacts using
deterministic heuristics (title/URL patterns, metadata signals).

This prevents expensive advisory generation for clearly irrelevant content
and reduces API costs, latency, and noise in the pipeline.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import re
import time


PREFILTER_REJECT_REASONS = {
    "jobs_careers_page": "Jobs/careers listing, not a research study",
    "university_program_page": "University program description, not a research study",
    "generic_se_page": "Generic 'what is software engineering' overview, not original research",
    "recruitment_ad": "Recruitment advertisement for study participants, not a study itself",
    "conference_homepage": "Conference homepage or Call for Papers, not a research article",
    "institutional_page": "Institutional/organizational page, not a research study",
    "educational_content": "Pure educational or tutorial content, not original research",
    "duplicate_title": "Duplicate or near-duplicate of previously seen article",
    "empty_metadata": "Missing both title and abstract — insufficient for screening",
    "non_english": "Non-English title detected — requires translation before screening",
    "book_review": "Book review or editorial, not original research",
    "opinion_piece": "Opinion/position piece without empirical methodology",
    "errata_correction": "Errata, correction, or retraction notice",
    "dataset_documentation": "Dataset or tool documentation, not a research study",
}

PREFILTER_DECISION_MAP = {
    "jobs_careers_page": "EXCLUDE",
    "university_program_page": "EXCLUDE",
    "generic_se_page": "EXCLUDE",
    "recruitment_ad": "EXCLUDE",
    "conference_homepage": "EXCLUDE",
    "institutional_page": "EXCLUDE",
    "educational_content": "EXCLUDE",
    "duplicate_title": "EXCLUDE",
    "empty_metadata": "INSUFFICIENT_EVIDENCE",
    "non_english": "UNCERTAIN",
    "book_review": "EXCLUDE",
    "opinion_piece": "EXCLUDE",
    "errata_correction": "EXCLUDE",
    "dataset_documentation": "EXCLUDE",
}


JOBS_PATTERNS = re.compile(
    r'\b(job\s+(posting|listing|opening|vacancy|offer|opportunity)|'
    r'career(s|)\s+(page|site|opportunit|portal)|'
    r'we\s+are\s+hiring|join\s+our\s+team|'
    r'current\s+openings|apply\s+(now|today)|'
    r'employment\s+opportunit|work\s+with\s+us)\b',
    re.IGNORECASE,
)

UNIVERSITY_PROGRAM_PATTERNS = re.compile(
    r"\b(bachelor(?:'s|)\s+(of|in|degree)|"
    r"master(?:'s|)\s+(of|in|degree)|"
    r"ph\.?d\.?\s+(program|admission|applications?|position)|"
    r"(undergraduate|graduate|postgraduate)\s+(program|course|degree|admission)|"
    r"curriculum\s+(overview|description)|"
    r"course\s+(catalogue|catalog|description|offering)|"
    r"programme\s+specification|"
    r"degree\s+requirements?|"
    r"admission\s+requirements?|"
    r"scholarship\s+opportunit)\b",
    re.IGNORECASE,
)

GENERIC_SE_PATTERNS = re.compile(
    r'\b(what\s+is\s+(software\s+)?engineering|'
    r'introduction\s+to\s+software\s+engineering|'
    r'overview\s+of\s+software\s+engineering|'
    r'fundamentals?\s+of\s+software\s+engineering|'
    r'software\s+engineering\s+(basics|101|fundamentals)|'
    r'definition\s+of\s+software\s+engineering)\b',
    re.IGNORECASE,
)

RECRUITMENT_AD_PATTERNS = re.compile(
    r'\b(participants?\s+(wanted|needed|required|recruited|sought)|'
    r'volunteers?\s+(wanted|needed|required)|'
    r'call\s+for\s+(participants?|volunteers?)|'
    r'research\s+participants?\s+(wanted|needed)|'
    r'subjects?\s+(wanted|needed)|'
    r'we\s+are\s+looking\s+for\s+participants?|'
    r'take\s+part\s+in\s+(a\s+)?(study|research|survey)|'
    r'participate\s+in\s+(a\s+)?(study|research|survey))\b',
    re.IGNORECASE,
)

CONFERENCE_PATTERNS = re.compile(
    r'\b(call\s+for\s+(papers?|submissions?|abstracts?|workshops?|tutorials?)|'
    r'(conference|workshop|symposium)\s+(homepage|website|page|site)|'
    r'cfp:|submission\s+(guidelines?|instructions?|deadline)|'
    r'important\s+dates|'
    r'(paper|abstract)\s+submission\s+(deadline|due|date)|'
    r'program\s+committee|'
    r'keynote\s+(speakers?|talks?)|'
    r'conference\s+program|'
    r'proceedings?\s+of\s+the)\b',
    re.IGNORECASE,
)

INSTITUTIONAL_PATTERNS = re.compile(
    r'\b(about\s+us|our\s+(team|mission|vision|values)|'
    r'department\s+(homepage|page|website)|'
    r'research\s+(group|lab|center|institute|unit)\s+(homepage|page|website)|'
    r'faculty\s+(directory|listing|members?|profiles?)|'
    r'staff\s+(directory|listing)|'
    r'contact\s+us|'
    r'news\s+and\s+events|'
    r'annual\s+report)\b',
    re.IGNORECASE,
)

EDUCATIONAL_PATTERNS = re.compile(
    r'\b(tutorial\s+(on|about)|'
    r'lecture\s+notes?\s+(on|about)|'
    r'learning\s+(objects?|materials?|resources?)|'
    r'teaching\s+(materials?|resources?|guide)|'
    r'(step[- ]by[- ]step|beginner(\'?s)?|intermediate(\'?s)?)\s+guide|'
    r'cheat\s+sheet|'
    r'reference\s+(card|manual|guide)|'
    r'how[- ]to\s+guide|'
    r'crash\s+course)\b',
    re.IGNORECASE,
)

DUPLICATE_NORMALIZE = re.compile(r'[^a-z0-9]+')


def _normalize_for_dedup(text: str) -> str:
    return DUPLICATE_NORMALIZE.sub(' ', text.lower()).strip()


@dataclass
class PrefilterResult:
    is_reject: bool = False
    reason_key: str = ""
    reason: str = ""
    decision: str = ""
    confidence: float = 1.0
    matched_pattern: str = ""
    elapsed_ms: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "is_reject": self.is_reject,
            "reason_key": self.reason_key,
            "reason": self.reason,
            "decision": self.decision,
            "confidence": self.confidence,
            "matched_pattern": self.matched_pattern,
            "elapsed_ms": self.elapsed_ms,
        }

    def to_advisory_dict(self) -> Dict:
        return {
            "decision": self.decision,
            "confidence": self.confidence,
            "justification": self.reason,
            "triggered_criteria": [],
            "criterion_evaluations": {},
            "prefilter_applied": True,
            "prefilter_reason": self.reason_key,
            "prefilter_detail": self.reason,
        }


class PrefilterEngine:
    """Deterministic pre-filtering engine for non-study artifacts."""

    def __init__(self):
        self._seen_titles: Dict[str, str] = {}
        self._hit_count: int = 0
        self._total_count: int = 0

    @property
    def hit_rate(self) -> float:
        if self._total_count == 0:
            return 0.0
        return self._hit_count / self._total_count

    def check(self, title: str, abstract: str = "", url: str = "") -> PrefilterResult:
        start = time.time()
        self._total_count += 1
        title_stripped = (title or "").strip()
        abstract_stripped = (abstract or "").strip()
        url_stripped = (url or "").strip()
        combined = f"{title_stripped} {abstract_stripped} {url_stripped}"

        if not title_stripped and not abstract_stripped:
            elapsed = (time.time() - start) * 1000
            self._hit_count += 1
            return PrefilterResult(
                is_reject=True,
                reason_key="empty_metadata",
                reason=PREFILTER_REJECT_REASONS["empty_metadata"],
                decision=PREFILTER_DECISION_MAP["empty_metadata"],
                matched_pattern="empty_title_and_abstract",
                elapsed_ms=elapsed,
            )

        checks = [
            ("non_english", lambda t: self._detect_non_english(t)),
            ("jobs_careers_page", lambda c: bool(JOBS_PATTERNS.search(c))),
            ("university_program_page", lambda c: bool(UNIVERSITY_PROGRAM_PATTERNS.search(c))),
            ("generic_se_page", lambda c: bool(GENERIC_SE_PATTERNS.search(c))),
            ("recruitment_ad", lambda c: bool(RECRUITMENT_AD_PATTERNS.search(c))),
            ("conference_homepage", lambda c: bool(CONFERENCE_PATTERNS.search(c))),
            ("institutional_page", lambda c: bool(INSTITUTIONAL_PATTERNS.search(c))),
            ("educational_content", lambda c: bool(EDUCATIONAL_PATTERNS.search(c))),
        ]

        for reason_key, check_fn in checks:
            if check_fn(title_stripped) or check_fn(combined):
                elapsed = (time.time() - start) * 1000
                self._hit_count += 1
                return PrefilterResult(
                    is_reject=True,
                    reason_key=reason_key,
                    reason=PREFILTER_REJECT_REASONS.get(reason_key, "Prefilter heuristic matched"),
                    decision=PREFILTER_DECISION_MAP.get(reason_key, "EXCLUDE"),
                    matched_pattern=f"pattern_match:{reason_key}",
                    elapsed_ms=elapsed,
                )

        if title_stripped:
            norm_title = _normalize_for_dedup(title_stripped)
            if norm_title in self._seen_titles:
                elapsed = (time.time() - start) * 1000
                self._hit_count += 1
                return PrefilterResult(
                    is_reject=True,
                    reason_key="duplicate_title",
                    reason=PREFILTER_REJECT_REASONS["duplicate_title"],
                    decision=PREFILTER_DECISION_MAP["duplicate_title"],
                    matched_pattern=f"duplicate:{self._seen_titles[norm_title]}",
                    elapsed_ms=elapsed,
                )
            self._seen_titles[norm_title] = title_stripped[:80]

        elapsed = (time.time() - start) * 1000
        return PrefilterResult(is_reject=False, elapsed_ms=elapsed)

    def _detect_non_english(self, text: str) -> bool:
        if not text:
            return False
        latin_chars = sum(1 for c in text if 'a' <= c.lower() <= 'z' or c in ' -.,;:!?\'"')
        if len(text) == 0:
            return False
        ratio = latin_chars / len(text)
        return ratio < 0.5

    def check_batch(self, articles: List[Dict]) -> List[Tuple[Dict, PrefilterResult]]:
        results: List[Tuple[Dict, PrefilterResult]] = []
        for article in articles:
            title = article.get("title", article.get("article_title", ""))
            abstract = article.get("abstract", "")
            url = article.get("url", "")
            result = self.check(title, abstract, url)
            results.append((article, result))
        return results

    def reset(self):
        self._seen_titles.clear()
        self._hit_count = 0
        self._total_count = 0


_global_prefilter: Optional[PrefilterEngine] = None


def get_prefilter() -> PrefilterEngine:
    global _global_prefilter
    if _global_prefilter is None:
        _global_prefilter = PrefilterEngine()
    return _global_prefilter
