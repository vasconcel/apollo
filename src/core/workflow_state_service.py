"""
APOLLO Workflow State Service

Deterministic workflow/state-transition orchestration for ScreeningSession.
Centralizes stage semantics, completion checks, and field mappings
that were previously duplicated across NavigationService, SessionQueryService,
and ScreeningSession.

Contains no Streamlit, advisory, persistence, or audit logic.
"""

from typing import Dict, List, Optional


class WorkflowStateService:
    """Stateless workflow orchestration for ScreeningSession.

    Centralises:
    - stage field name mapping
    - stage validation and ordering
    - workflow completion checks
    - stage transition rules

    All methods are @staticmethod — no instance state, no persistence,
    no navigation, no query, no audit, no ingestion logic.
    """

    STAGE_ORDER: List[str] = ["ec", "ic", "qc", "complete"]

    STAGE_FIELD_MAP: Dict[str, str] = {
        "ec": "ec_stage",
        "ic": "ic_stage",
    }

    STAGE_COUNTER_MAP: Dict[str, str] = {
        "ec": "ec_completed",
        "ic": "ic_completed",
    }

    @staticmethod
    def stage_field(stage: str) -> str:
        """Get article field name for a given stage decision.

        Args:
            stage: Stage identifier ("ec" or "ic").

        Returns:
            Field name ("ec_stage", "ic_stage") or empty string if unknown.
        """
        return WorkflowStateService.STAGE_FIELD_MAP.get(stage, "")

    @staticmethod
    def stage_counter(stage: str) -> str:
        """Get session counter field name for a given stage.

        Args:
            stage: Stage identifier ("ec" or "ic").

        Returns:
            Counter field name ("ec_completed", "ic_completed") or
            empty string if unknown.
        """
        return WorkflowStateService.STAGE_COUNTER_MAP.get(stage, "")

    @staticmethod
    def is_valid_stage(stage: str) -> bool:
        """Check if a stage identifier is valid.

        Args:
            stage: Stage identifier.

        Returns:
            True if stage is in STAGE_ORDER.
        """
        return stage in WorkflowStateService.STAGE_ORDER

    @staticmethod
    def can_transition_to_stage(current_stage: str, target_stage: str) -> bool:
        """Check if a stage transition is valid.

        Args:
            current_stage: Current stage identifier.
            target_stage: Requested stage identifier.

        Returns:
            True if target_stage follows current_stage in STAGE_ORDER
            and both are valid stages.
        """
        if not WorkflowStateService.is_valid_stage(current_stage):
            return False
        if not WorkflowStateService.is_valid_stage(target_stage):
            return False
        if target_stage == current_stage:
            return True
        order = WorkflowStateService.STAGE_ORDER
        return order.index(target_stage) == order.index(current_stage) + 1

    @staticmethod
    def is_workflow_complete(
        stage: str,
        current_index: int,
        total_count: int,
    ) -> bool:
        """Check if the workflow is complete.

        Workflow is complete when stage is 'complete' or
        current_index has passed all articles.

        Args:
            stage: Current stage identifier.
            current_index: Current article index.
            total_count: Total number of articles.

        Returns:
            True if workflow is complete.
        """
        return stage == "complete" or current_index >= total_count

    @staticmethod
    def get_next_stage(current_stage: str) -> Optional[str]:
        """Get the next stage in workflow order.

        Args:
            current_stage: Current stage identifier.

        Returns:
            Next stage identifier, or None if already at final stage.
        """
        order = WorkflowStateService.STAGE_ORDER
        if current_stage not in order:
            return None
        idx = order.index(current_stage)
        if idx + 1 < len(order):
            return order[idx + 1]
        return None
