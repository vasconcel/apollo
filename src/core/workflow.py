"""Review workflow state machine for methodological enforcement."""

from enum import Enum
from typing import Optional


class ReviewStage(Enum):
    """Canonical review stages following systematic review methodology."""
    
    CALIBRATION = "calibration"      # Initial calibration of inclusion criteria
    SCREENING = "screening"       # Title/Abstract screening
    CROSS_AUDIT = "cross_audit"   # Inter-rater reliability check
    CONSENSUS = "consensus"        # Consensus resolution
    EXTRACTION = "extraction"     # Data extraction
    SYNTHESIS = "synthesis"    # Thematic synthesis
    
    @classmethod
    def get_order(cls):
        """Return stage order as list."""
        return [cls.CALIBRATION, cls.SCREENING, cls.CROSS_AUDIT, cls.CONSENSUS, cls.EXTRACTION, cls.SYNTHESIS]
    
    def get_index(self) -> int:
        """Return position in workflow."""
        return self.get_order().index(self)
    
    def can_transition_to(self, next_stage: 'ReviewStage') -> bool:
        """Check if transition is allowed (only forward, one step at a time)."""
        current_idx = self.get_index()
        next_idx = next_stage.get_index()
        return next_idx == current_idx + 1
    
    def get_allowed_next(cls) -> Optional['ReviewStage']:
        """Return next stage if exists."""
        idx = cls.get_index()
        order = cls.get_order()
        return order[idx + 1] if idx < len(order) - 1 else None


VALID_TRANSITIONS = {
    ReviewStage.CALIBRATION: ReviewStage.SCREENING,
    ReviewStage.SCREENING: ReviewStage.CROSS_AUDIT,
    ReviewStage.CROSS_AUDIT: ReviewStage.CONSENSUS,
    ReviewStage.CONSENSUS: ReviewStage.EXTRACTION,
    ReviewStage.EXTRACTION: ReviewStage.SYNTHESIS,
    ReviewStage.SYNTHESIS: None,  # Terminal stage
}


def is_valid_transition(current: ReviewStage, target: ReviewStage) -> bool:
    """Check if transition from current to target is methodologically valid."""
    allowed = VALID_TRANSITIONS.get(current)
    return allowed == target


def get_stage_prompt(stage: ReviewStage) -> str:
    """Get instructional prompt for stage."""
    prompts = {
        ReviewStage.CALIBRATION: "Calibrate inclusion/exclusion criteria with sample titles",
        ReviewStage.SCREENING: "Screen titles and abstracts against inclusion criteria",
        ReviewStage.CROSS_AUDIT: "Calculate inter-rater reliability (Kappa > 0.6 required)",
        ReviewStage.CONSENSUS: "Resolve disagreements through discussion or third reviewer",
        ReviewStage.EXTRACTION: "Extract evidence fragments from included studies",
        ReviewStage.SYNTHESIS: "Generate themes and synthesize findings"
    }
    return prompts.get(stage, "Unknown stage")


def get_stage_display_name(stage: ReviewStage) -> str:
    """Get user-friendly stage name."""
    names = {
        ReviewStage.CALIBRATION: "Calibration",
        ReviewStage.SCREENING: "Screening",
        ReviewStage.CROSS_AUDIT: "Cross-Audit",
        ReviewStage.CONSENSUS: "Consensus",
        ReviewStage.EXTRACTION: "Extraction",
        ReviewStage.SYNTHESIS: "Synthesis"
    }
    return names.get(stage, stage.value.title())