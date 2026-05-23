"""Phase 5A: Deterministic study type detection.

Classifies articles into study types using:
- regex patterns
- metadata analysis
- lexical features
- semantic corroboration
"""

import re
from typing import Dict, List, Optional, Set, Tuple

from .screening_result import Evidence
from .confidence_engine import get_weight

STUDY_TYPES = {
    "empirical_study": {
        "label": "Empirical Study",
        "patterns": [
            r"\b(empirical\s+study|empirical\s+research|empirical\s+investigation)\b",
            r"\b(we\s+(conduct|perform|present|report)\s+(a\s+)?(study|experiment|survey|analysis))\b",
            r"\b((participants?|subjects?)\s+(completed|were|participated|enrolled|recruited))\b",
            r"\b((data\s+(collected|gathered|analyzed)|data\s+collection))\b",
            r"\b(quantitative|qualitative|mixed.metho)\b",
            r"\b(experiment|experimental\s+design)\b",
            r"\b(case\s+study)\b",
            r"\b((research|study)\s+(question|hypothesis|objective|aim|purpose))\b",
            r"\b(methodology|method\s+approach)\b",
            r"\b(results?\s+(show|indicate|suggest|demonstrate|reveal|find))\b",
            r"\b(statistical\s+(analysis|test|method|significance))\b",
            r"\b(pilot\s+study)\b",
            r"\b(longitudinal|cross.sectional|observational)\b",
        ],
    },
    "systematic_review": {
        "label": "Systematic Review",
        "patterns": [
            r"\b(systematic\s+(review|literature\s+review|mapping\s+study|map))\b",
            r"\b(meta.analysis)\b",
            r"\b(PRISMA)\b",
            r"\b(literature\s+review)\b",
            r"\b(mapping\s+study)\b",
            r"\b(evidence\s+(synthesis|gap))\b",
            r"\b((search\s+strategy|database\s+search|snowballing))\b",
            r"\b((inclusion|exclusion)\s+(criterion|criteria))\b",
            r"\b(quality\s+assessment)\b",
            r"\b((study\s+)?selection\s+process)\b",
            r"\b(data\s+extraction)\b",
        ],
    },
    "tertiary_study": {
        "label": "Tertiary Study",
        "patterns": [
            r"\b(tertiary\s+study)\b",
            r"\b(systematic\s+mapping\s+of\s+(systematic\s+)?review)\b",
            r"\b(review\s+of\s+(systematic\s+)?(review|literature\s+review))\b",
            r"\b(meta.synthesis)\b",
            r"\b(overview\s+of\s+review)\b",
        ],
    },
    "experience_report": {
        "label": "Experience Report",
        "patterns": [
            r"\b(experience\s+(report|paper|article))\b",
            r"\b(lesson(s)?\s+learn(t|ed))\b",
            r"\b(our\s+experience\s+(with|in|using|building|implementing|developing))\b",
            r"\b(we\s+describe\s+our\s+experience)\b",
            r"\b(industry\s+(report|case))\b",
            r"\b(practitioner\s+(report|perspective|experience))\b",
            r"\b(field\s+(report|study|observation))\b",
        ],
    },
    "opinion_paper": {
        "label": "Opinion Paper",
        "patterns": [
            r"\b(opinion\s+(paper|piece|article))\b",
            r"\b(position\s+paper)\b",
            r"\b(viewpoint)\b",
            r"\b(perspective\s+(paper|article|piece))\b",
            r"\b(commentary)\b",
            r"\b(we\s+(argue|believe|think|contend|propose|suggest)\s+that)\b",
            r"\b(in\s+our\s+opinion|in\s+my\s+view)\b",
            r"\b(this\s+(paper|article)\s+argues)\b",
        ],
    },
    "tutorial": {
        "label": "Tutorial",
        "patterns": [
            r"\b(tutorial)\b",
            r"\b(how.to\s+(guide|tutorial))\b",
            r"\b(step.by.step\s+guide)\b",
            r"\b(beginners?\s+guide)\b",
            r"\b(walkthrough)\b",
            r"\b(hands.on\s+(tutorial|guide))\b",
            r"\b(getting\s+started\s+(with|guide))\b",
        ],
    },
    "editorial": {
        "label": "Editorial / Foreword",
        "patterns": [
            r"\b(editorial)\b",
            r"\b(foreword)\b",
            r"\b(introduction\s+to\s+(the\s+)?(special\s+)?(issue|section|volume))\b",
            r"\b(guest\s+editorial)\b",
            r"\b(editor.s?\s+(note|introduction|comment))\b",
            r"\b(preface)\b",
            r"\b(acknowledgments?\s+of\s+reviewers)\b",
        ],
    },
    "cfp": {
        "label": "Call for Papers",
        "patterns": [
            r"\b(call\s+for\s+papers?)\b",
            r"\b(cfp)\b",
            r"\b(call\s+for\s+(contributions?|submissions?|participation|workshops?))\b",
            r"\b(important\s+dates|important\s+deadline)\b",
            r"\b(submission\s+(deadline|guidelines?|instructions?|format))\b",
            r"\b(camera.ready\s+(deadline|due))\b",
            r"\b(paper\s+submission\s+(deadline|system|portal))\b",
            r"\b(workshop\s+proposal)\b",
            r"\b(track\s+(chair|proposal))\b",
            r"\b(conference\s+topics?\s+include)\b",
        ],
    },
    "job_posting": {
        "label": "Job Posting",
        "patterns": [
            r"\b(job\s+(posting|listing|opening|vacancy|offer|opportunity|description|advert|announcement))\b",
            r"\b(we\s+are\s+hiring)\b",
            r"\b(apply\s+(now|today|here))\b",
            r"\b(current\s+vacanc)\b",
            r"\b(recruit(er|ing|ment))\b",
            r"\b(salary\s+(range|negotiable|competitive))\b",
            r"\b(position\s+requirement)\b",
            r"\b(qualifications?\s+requir)\b",
            r"\b(job\s+(type|category|function))\b",
            r"\b(equal\s+opportunity\s+employer)\b",
        ],
    },
}


class StudyTypeDetector:
    """Deterministic study type classification.

    Uses multiple signals to classify an article's study type:
    - Title/abstract pattern matching
    - Metadata hints (document type, venue, language)
    - Pattern density scoring per type
    """

    def __init__(self, min_patterns: int = 2) -> None:
        self._min_patterns = min_patterns
        self._compiled: Dict[str, List[re.Pattern]] = {}
        for stype, config in STUDY_TYPES.items():
            self._compiled[stype] = [
                re.compile(p, re.IGNORECASE) for p in config["patterns"]
            ]

    def classify(
        self,
        title: str = "",
        abstract: str = "",
        document_type: str = "",
        venue: str = "",
    ) -> Tuple[str, Dict[str, int], str]:
        """Classify article and return (primary_type, type_scores, rationale).

        Returns the best-matching study type, per-type match counts,
        and a short rationale string.
        """
        text = f"{title} {abstract}"
        type_counts: Dict[str, int] = {}

        for stype in STUDY_TYPES:
            count = 0
            for pat in self._compiled[stype]:
                if pat.search(text):
                    count += 1
            if count > 0:
                type_counts[stype] = count

        if document_type:
            dt_lower = document_type.lower()
            if "review" in dt_lower and "systematic_review" not in type_counts:
                type_counts["systematic_review"] = 1
            if "editorial" in dt_lower:
                type_counts["editorial"] = type_counts.get("editorial", 0) + 2
            if "tutorial" in dt_lower:
                type_counts["tutorial"] = type_counts.get("tutorial", 0) + 2

        if not type_counts:
            return "unknown", {}, "No study type patterns detected"

        best_type = max(type_counts, key=type_counts.get)
        best_count = type_counts[best_type]

        if best_count < self._min_patterns:
            return "unknown", type_counts, (
                f"Best match '{STUDY_TYPES[best_type]['label']}' "
                f"only {best_count}/{self._min_patterns} patterns"
            )

        label = STUDY_TYPES[best_type]["label"]
        rationale = f"Classified as {label} ({best_count} pattern matches)"
        return best_type, type_counts, rationale

    def get_confidence_bonus(self, study_type: str) -> float:
        """Return confidence bonus/penalty based on study type.

        Empirical studies and systematic reviews get a small boost.
        Opinion papers, editorials, tutorials get a penalty.
        """
        bonuses = {
            "empirical_study": 0.05,
            "systematic_review": 0.05,
            "tertiary_study": 0.03,
            "experience_report": 0.0,
            "opinion_paper": -0.1,
            "tutorial": -0.15,
            "editorial": -0.15,
            "cfp": -0.2,
            "job_posting": -0.2,
            "unknown": 0.0,
        }
        return bonuses.get(study_type, 0.0)

    def list_types(self) -> List[Dict[str, str]]:
        return [
            {"id": stype, "label": config["label"], "patterns": len(config["patterns"])}
            for stype, config in STUDY_TYPES.items()
        ]
