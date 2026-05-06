"""
APOLLO Workflow - Simple EC -> IC -> QC Pipeline
Minimal stage machine for decision support only
"""
from enum import Enum


class ReviewStage(Enum):
    """Simplified review stages for APOLLO EC/IC/QC pipeline."""
    
    ELIGIBILITY = "eligibility"    # EC + IC evaluation
    QUALITY = "quality"             # QC scoring
    
    @classmethod
    def get_order(cls):
        return [cls.ELIGIBILITY, cls.QUALITY]
    
    def get_index(self) -> int:
        return self.get_order().index(self)
    
    def can_transition_to(self, next_stage: 'ReviewStage') -> bool:
        current_idx = self.get_index()
        next_idx = next_stage.get_index()
        return next_idx == current_idx + 1


VALID_TRANSITIONS = {
    ReviewStage.ELIGIBILITY: ReviewStage.QUALITY,
    ReviewStage.QUALITY: None,  # Terminal stage
}


def is_valid_transition(current: ReviewStage, target: ReviewStage) -> bool:
    """Check if transition from current to target is valid."""
    allowed = VALID_TRANSITIONS.get(current)
    return allowed == target


def get_stage_prompt(stage: ReviewStage) -> str:
    """Get instructional prompt for stage."""
    prompts = {
        ReviewStage.ELIGIBILITY: "Apply EC (Exclusion) then IC (Inclusion) criteria",
        ReviewStage.QUALITY: "Apply QC scoring (WL-Q1→Q4 or GL-Q1→Q4) with threshold ≥2.0"
    }
    return prompts.get(stage, "Unknown stage")


def get_stage_display_name(stage: ReviewStage) -> str:
    """Get user-friendly stage name."""
    names = {
        ReviewStage.ELIGIBILITY: "Eligibility (EC/IC)",
        ReviewStage.QUALITY: "Quality (QC)"
    }
    return names.get(stage, stage.value.title())