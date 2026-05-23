from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from src.domain.enums import CriterionType, ScreeningStatus, SourceType


class Paper(BaseModel):
    model_config = {"frozen": True}

    id: str
    title: str = Field(min_length=1)
    url: Optional[str] = None
    abstract: Optional[str] = None
    source_type: SourceType
    publication_year: Optional[int] = None
    metadata: dict = Field(default_factory=dict)

    @field_validator("id", mode="before")
    @classmethod
    def coerce_uuid_to_str(cls, v):
        if isinstance(v, UUID):
            return str(v)
        return v


class Criterion(BaseModel):
    id: str
    type: CriterionType
    code: str = Field(min_length=1)
    description: str = Field(min_length=1)


class ScreeningDecision(BaseModel):
    paper_id: str
    status: ScreeningStatus
    confidence_score: float = Field(ge=0.0, le=1.0)
    rationale: str
    applied_criteria_codes: list[str]
