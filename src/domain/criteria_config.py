from src.domain.enums import CriterionType
from src.domain.models import Criterion

DEFAULT_CRITERIA: list[Criterion] = [
    # ── Exclusion Criteria ──────────────────────────────────────────────
    Criterion(
        id="ec-1",
        type=CriterionType.EXCLUSION,
        code="EC1",
        description="Sources not written in English.",
    ),
    Criterion(
        id="ec-2",
        type=CriterionType.EXCLUSION,
        code="EC2",
        description="Sources whose full text was unavailable.",
    ),
    Criterion(
        id="ec-3",
        type=CriterionType.EXCLUSION,
        code="EC3",
        description="Short publications lacking sufficient methodological or "
        "experiential evidence (editorials, posters, extended abstracts).",
    ),
    Criterion(
        id="ec-4",
        type=CriterionType.EXCLUSION,
        code="EC4",
        description="Sources published before 2015.",
    ),
    Criterion(
        id="ec-5",
        type=CriterionType.EXCLUSION,
        code="EC5",
        description="Sources unrelated to SE R&S.",
    ),
    Criterion(
        id="ec-6",
        type=CriterionType.EXCLUSION,
        code="EC6",
        description="Duplicate studies.",
    ),
    # ── Inclusion Criteria ──────────────────────────────────────────────
    Criterion(
        id="ic-1",
        type=CriterionType.INCLUSION,
        code="IC1",
        description="Sources explicitly addressing R&S processes for SE roles.",
    ),
    Criterion(
        id="ic-2",
        type=CriterionType.INCLUSION,
        code="IC2",
        description="Sources describing stages, pipelines, structures, or "
        "procedures of SE R&S.",
    ),
    Criterion(
        id="ic-3",
        type=CriterionType.INCLUSION,
        code="IC3",
        description="Sources reporting challenges, frictions, or perceptions "
        "related to SE R&S.",
    ),
    Criterion(
        id="ic-4",
        type=CriterionType.INCLUSION,
        code="IC4",
        description="Sources describing practices, assessment methods, or "
        "evaluation mechanisms.",
    ),
    Criterion(
        id="ic-5",
        type=CriterionType.INCLUSION,
        code="IC5",
        description="Sources providing empirical findings or "
        "practitioner-reported experiences.",
    ),
]
