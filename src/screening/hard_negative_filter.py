"""Phase 5A: Hard Negative Filter — deterministic hard exclusion.

Hard negatives produce EXCLUDE with confidence >= 0.95.
They bypass REVIEW and never escalate to LLM.
"""

import re
from typing import Dict, List, Optional, Tuple, Any

from .screening_result import Evidence

HARD_NEGATIVE_THRESHOLD = 0.95

HARD_NEGATIVE_PATTERNS: Dict[str, Tuple[str, str, List[str], List[str]]] = {
    "job_posting": (
        "Job posting / vacancy",
        "exclusion_pattern",
        [
            r"\b(job\s+(posting|listing|opening|vacancy|offer|opportunity|description|advert))\b",
            r"\b(we\s+are\s+hiring)\b",
            r"\b(career\s+opportunity)\b",
            r"\b(apply\s+(now|today))\b",
            r"\b(join\s+our\s+team)\b",
            r"\b(current\s+vacanc(y|ies))\b",
            r"\b(hiring\s+(for|process|event|fair))\b",
            r"\b(employment\s+opportunity)\b",
            r"\b(recruit(ing|ment)?\s+process)\b",
            r"\b(position\s+(is\s+)?(open|available|filled))\b",
            r"\b(contract\s*(type|term|position))\b",
            r"\b((hourly|annual)\s+(salary|wage|compensation))\b",
            r"\b(equal\s+opportunity\s+employer)\b",
            r"\b(job\s+requirement)\b",
            r"\b(responsibilities\s+include)\b",
            r"\b(qualifications\s+required)\b",
            r"\b(salary\s+range)\b",
            r"\b(benefits\s+include)\b",
            r"\b(how\s+to\s+apply)\b",
            r"\b(cover\s+letter)\b",
            r"\b(resume|r[eé]sum[eé])\b",
        ],
    ),
    "recruitment_ad": (
        "Recruitment advertisement",
        "exclusion_pattern",
        [
            r"\b(recruit(er|ing|ment)?\s+(agency|consultant|firm|company))\b",
            r"\b(headhunter)\b",
            r"\b(talent\s+(acquisition|search|partner|pool))\b",
            r"\b(staffing\s+(agency|solution|service))\b",
            r"\b(manpower)\b",
            r"\b(executive\s+search)\b",
            r"\b(placement\s+(agency|service|consultancy))\b",
            r"\b(career\s+(fair|page|site|portal|website))\b",
            r"\b(job\s+(board|site|portal|search|engine))\b",
            r"\b(linkedin|indeed|monster|glassdoor)\s+(job|posting|listing)\b",
        ],
    ),
    "salary_discussion": (
        "Salary / compensation discussion",
        "exclusion_pattern",
        [
            r"\b(salary\s+(survey|negotiation|discussion|review|increase|raise))\b",
            r"\b(compensation\s+(package|structure|plan|review))\b",
            r"\b(pay\s+(scale|grade|band|range|equity))\b",
            r"\b(wage\s+(gap|disparity|negotiation))\b",
            r"\b(total\s+compensation)\b",
            r"\b(payroll)\b",
            r"\b(remuneration)\b",
        ],
    ),
    "university_admission": (
        "University admission / application",
        "exclusion_pattern",
        [
            r"\b(admissions?\s+(process|criteria|requirement|office|cycle|policy))\b",
            r"\b(apply\s+to\s+(university|college|program|graduate|undergraduate))\b",
            r"\b(application\s+(fee|deadline|status|portal))\b",
            r"\b(college\s+admission)\b",
            r"\b(graduate\s+school\s+admission)\b",
            r"\b(matriculation)\b",
            r"\b(entrance\s+(exam|test|requirement|score))\b",
            r"\b(scholarship\s+application)\b",
            r"\b(how\s+to\s+get\s+into)\b",
            r"\b(admission\s+essay)\b",
            r"\b(statement\s+of\s+purpose)\b",
        ],
    ),
    "bootcamp": (
        "Bootcamp / coding school",
        "exclusion_pattern",
        [
            r"\b(bootcamp|coding\s+school|code\s+academy)\b",
            r"\b(intensive\s+(coding|programming|software)\s+(course|program|bootcamp))\b",
            r"\b(learn\s+to\s+code)\b",
            r"\b(become\s+a\s+(developer|programmer|software\s+engineer))\b",
            r"\b(coding\s+course)\b",
            r"\b(programming\s+course\s+for\s+beginners?)\b",
            r"\b(web\s+development\s+(course|bootcamp|class))\b",
        ],
    ),
    "marketing_promo": (
        "Marketing / promotional content",
        "exclusion_pattern",
        [
            r"\b(sponsored|advertisement|paid\s+(content|post|promotion))\b",
            r"\b(buy\s+(now|today|this\s+product))\b",
            r"\b(discount\s+(offer|code|deal))\b",
            r"\b(limited\s+time\s+offer)\b",
            r"\b(sign\s+up\s+(now|today|for\s+free))\b",
            r"\b(free\s+(trial|consultation|demo|download))\b",
            r"\b(promotional\s+(content|material|offer))\b",
            r"\b(marketing\s+(campaign|strategy|plan|material))\b",
        ],
    ),
    "career_advice": (
        "Career advice / guidance",
        "exclusion_pattern",
        [
            r"\b(career\s+(advice|guidance|counseling|counselling|tip|path|change|transition))\b",
            r"\b(how\s+to\s+get\s+a\s+job)\b",
            r"\b(job\s+(search|hunt|seek|market|interview)\s+(tip|strategy|advice|guide))\b",
            r"\b(resume\s+(tip|advice|guide|building|writing))\b",
            r"\b(interview\s+(tip|advice|question|preparation|technique))\b",
            r"\b(networking\s+(tip|strategy|advice|event))\b",
            r"\b(professional\s+development\s+(tip|advice))\b",
            r"\b(workplace\s+(tip|advice|culture|etiquette))\b",
        ],
    ),
}

MATCH_REQUIRED_PATTERNS = 2


class HardNegativeFilter:
    """Deterministic hard-negative filter.

    Matches article content against hard-negative patterns.
    If sufficient matches found, returns EXCLUDE with confidence >= 0.95.
    """

    def __init__(self) -> None:
        self._compiled: Dict[str, List[re.Pattern]] = {}
        for rule_id, (name, etype, patterns) in HARD_NEGATIVE_PATTERNS.items():
            compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
            self._compiled[rule_id] = compiled
        self._rule_ids = list(HARD_NEGATIVE_PATTERNS.keys())

    def evaluate(
        self,
        title: str = "",
        abstract: str = "",
        full_text: str = "",
    ) -> Tuple[bool, List[Evidence], int]:
        """Evaluate article against hard-negative patterns.

        Returns (is_hard_negative, evidence_list, total_matches).
        """
        text = f"{title} {abstract} {full_text}"
        evidence_list: List[Evidence] = []
        total_matches = 0

        for rule_id in self._rule_ids:
            patterns = self._compiled[rule_id]
            name, etype, raw_patterns = HARD_NEGATIVE_PATTERNS[rule_id]
            matches = 0
            matched_patterns: List[str] = []
            for i, pat in enumerate(patterns):
                if pat.search(text):
                    matches += 1
                    matched_patterns.append(raw_patterns[i])

            if matches > 0:
                total_matches += matches
                for mp in matched_patterns[:3]:
                    evidence_list.append(
                        Evidence(
                            rule_id=rule_id,
                            rule_name=name,
                            evidence_type=etype,
                            match=mp,
                            confidence=HARD_NEGATIVE_THRESHOLD,
                        )
                    )

        is_hard_negative = total_matches >= MATCH_REQUIRED_PATTERNS
        return is_hard_negative, evidence_list, total_matches

    def list_rules(self) -> List[Dict[str, Any]]:
        return [
            {
                "rule_id": rid,
                "name": HARD_NEGATIVE_PATTERNS[rid][0],
                "patterns_count": len(self._compiled[rid]),
            }
            for rid in self._rule_ids
        ]

    def classify(self, title: str, abstract: str = "") -> str:
        """Return the primary category matched, or empty string."""
        text = f"{title} {abstract}"
        best_count = 0
        best_id = ""
        for rule_id in self._rule_ids:
            patterns = self._compiled[rule_id]
            matches = sum(1 for p in patterns if p.search(text))
            if matches > best_count:
                best_count = matches
                best_id = rule_id
        return best_id
