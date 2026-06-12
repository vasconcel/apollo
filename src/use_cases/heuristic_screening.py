import re
from typing import Optional

from src.domain.enums import CriterionType, ScreeningStatus
from src.domain.models import Criterion, Paper, ScreeningDecision

_EC3_KEYWORD_PATTERN = re.compile(
    r"\b(poster|editorial|extended abstract|keynote|tutorial)\b",
    re.IGNORECASE,
)


def _rule_ec4(paper: Paper) -> Optional[ScreeningDecision]:
    year = getattr(paper, 'publication_year', 0) or 0
    if 0 < year < 2015:
        return ScreeningDecision(
            paper_id=paper.id,
            status=ScreeningStatus.EXCLUDED,
            confidence_score=1.0,
            rationale=(
                f"Excluded by EC4: publication year {year} "
                "is before 2015."
            ),
            applied_criteria_codes=["EC4"],
        )
    elif year == 0:
        pass
    return None


def _rule_ec3(paper: Paper) -> Optional[ScreeningDecision]:
    texts_to_check = [paper.title] if paper.title else []
    texts_to_check.extend(
        str(val) for val in paper.metadata.values()
        if isinstance(val, str) and val
    )

    for text in texts_to_check:
        if _EC3_KEYWORD_PATTERN.search(text):
            return ScreeningDecision(
                paper_id=paper.id,
                status=ScreeningStatus.EXCLUDED,
                confidence_score=1.0,
                rationale=(
                    f"Excluded by EC3: title/metadata matches heuristic "
                    f"keyword pattern."
                ),
                applied_criteria_codes=["EC3"],
            )
    return None


def _rule_ec1(paper: Paper) -> Optional[ScreeningDecision]:
    language = paper.metadata.get("Language")
    if language is not None and isinstance(language, str) and language.strip():
        if language.strip().lower() != "english":
            return ScreeningDecision(
                paper_id=paper.id,
                status=ScreeningStatus.EXCLUDED,
                confidence_score=1.0,
                rationale=(
                    f"Excluded by EC1: language is '{language.strip()}', "
                    "not English."
                ),
                applied_criteria_codes=["EC1"],
            )
    return None


_RULE_DISPATCH = {
    "EC4": _rule_ec4,
    "EC3": _rule_ec3,
    "EC1": _rule_ec1,
}


class HeuristicScreeningUseCase:
    def execute(
        self,
        paper: Paper,
        criteria: list[Criterion],
    ) -> Optional[ScreeningDecision]:
        for criterion in criteria:
            if criterion.type is not CriterionType.EXCLUSION:
                continue
            rule_fn = _RULE_DISPATCH.get(criterion.code)
            if rule_fn is None:
                continue
            decision = rule_fn(paper)
            if decision is not None:
                return decision
        return None
