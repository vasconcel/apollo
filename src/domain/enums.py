from enum import Enum


class SourceType(str, Enum):
    WL = "WL"
    GL = "GL"


class CriterionType(str, Enum):
    INCLUSION = "INCLUSION"
    EXCLUSION = "EXCLUSION"


class ScreeningStatus(str, Enum):
    INCLUDED = "INCLUDED"
    EXCLUDED = "EXCLUDED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
