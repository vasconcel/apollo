"""
APOLLO Workflow - Simple EC -> IC Pipeline
Minimal stage machine for decision support only
"""
from enum import Enum


class ReviewStage(Enum):
    """Simplified review stages for APOLLO EC/IC pipeline."""
    
    ELIGIBILITY = "eligibility"    # EC + IC evaluation
    
    @classmethod
    def get_order(cls):
        return [cls.ELIGIBILITY]
    
    def get_index(self) -> int:
        return self.get_order().index(self)

    def can_transition_to(self, next_stage: 'ReviewStage') -> bool:
        return False


VALID_TRANSITIONS = {
    ReviewStage.ELIGIBILITY: None,  # Terminal stage
}


def is_valid_transition(current: ReviewStage, target: ReviewStage) -> bool:
    """Check if transition from current to target is valid."""
    allowed = VALID_TRANSITIONS.get(current)
    return allowed == target


def get_stage_prompt(stage: ReviewStage) -> str:
    """Get instructional prompt for stage."""
    prompts = {
        ReviewStage.ELIGIBILITY: "Apply EC (Exclusion) then IC (Inclusion) criteria"
    }
    return prompts.get(stage, "Unknown stage")


def get_stage_display_name(stage: ReviewStage) -> str:
    """Get user-friendly stage name."""
    names = {
        ReviewStage.ELIGIBILITY: "Eligibility (EC/IC)"
    }
    return names.get(stage, stage.value.title())