"""
APOLLO Scientific Design System

Canonical design system for scientific UX alignment.
Encodes workflow authority, provenance lineage, reproducibility guarantees,
audit chain semantics, and deterministic screening authority.

MODULES:
- semantic_colors: Semantic color tokens for scientific states
- typography: Typography scale and style guides
- spacing: Spacing tokens for layout rhythm
- workflow_components: Workflow visualization (Protocol → EC → IC → QC → Export → Replay)
- provenance_components: Article and session provenance visualization
- audit_components: Audit chain and tampering detection visualization
- reproducibility_components: Reproducibility state and deterministic execution
- article_decision_card: Canonical article decision display
- protocol_authority_banner: Protocol authority visualization
- session_lineage_panel: Session lineage tracking

USAGE:
    from src.ui.design_system import (
        render_workflow_stepper,
        render_provenance_panel,
        render_audit_status_badge,
        render_replay_verification_panel,
        render_article_decision_card,
        render_protocol_authority_banner,
        render_session_lineage_panel,
    )

VERIFICATION:
    - Semantic consistency across all routed views
    - No duplicated inline styling
    - No conflicting visual semantics
    - WCAG AA accessibility compliance
"""

from src.ui.design_system.semantic_colors import (
    COLORS,
    SEMANTIC_COLORS,
    WORKFLOW_STAGE_COLORS,
    get_semantic_color,
    get_workflow_stage_color,
    get_decision_semantic,
)

from src.ui.design_system.typography import (
    TYPOGRAPHY,
    TYPOGRAPHY_SCALE,
    FONT_WEIGHTS,
    LETTER_SPACING,
    LINE_HEIGHTS,
    STYLE_GUIDES,
    get_typography_style,
    build_css_font_stack,
)

from src.ui.design_system.spacing import (
    SPACING,
    SPACING_SCALE,
    LAYOUT,
    BORDERS,
    TOUCH_TARGETS,
    GRID,
    get_spacing,
    get_layout_value,
)

from src.ui.design_system.workflow_components import (
    WORKFLOW_STAGES,
    render_workflow_stepper,
    render_stage_progress,
    render_stage_lock_banner,
    render_canonical_workflow_summary,
)

from src.ui.design_system.provenance_components import (
    render_provenance_panel,
    render_provenance_rows,
    render_literature_type_indicator,
    render_metadata_completeness,
    render_decision_history,
    render_source_lineage,
)

from src.ui.design_system.audit_components import (
    render_audit_status_badge,
    render_hash_verification_panel,
    render_audit_event_log,
    render_tamper_detection_alert,
    render_session_integrity_summary,
)

from src.ui.design_system.reproducibility_components import (
    render_replay_verification_panel,
    render_determinism_status_indicator,
    render_checksum_verification_panel,
    render_reproducibility_bundle_summary,
    render_bundle_file_manifest,
)

from src.ui.design_system.article_decision_card import (
    render_article_decision_card,
)

from src.ui.design_system.protocol_authority_banner import (
    render_protocol_authority_banner,
)

from src.ui.design_system.session_lineage_panel import (
    render_session_lineage_panel,
    render_session_stats,
)

__all__ = [
    "COLORS",
    "SEMANTIC_COLORS",
    "WORKFLOW_STAGE_COLORS",
    "get_semantic_color",
    "get_workflow_stage_color",
    "get_decision_semantic",
    "TYPOGRAPHY",
    "TYPOGRAPHY_SCALE",
    "FONT_WEIGHTS",
    "LETTER_SPACING",
    "LINE_HEIGHTS",
    "STYLE_GUIDES",
    "get_typography_style",
    "build_css_font_stack",
    "SPACING",
    "SPACING_SCALE",
    "LAYOUT",
    "BORDERS",
    "TOUCH_TARGETS",
    "GRID",
    "get_spacing",
    "get_layout_value",
    "WORKFLOW_STAGES",
    "render_workflow_stepper",
    "render_stage_progress",
    "render_stage_lock_banner",
    "render_canonical_workflow_summary",
    "render_provenance_panel",
    "render_provenance_rows",
    "render_literature_type_indicator",
    "render_metadata_completeness",
    "render_decision_history",
    "render_source_lineage",
    "render_audit_status_badge",
    "render_hash_verification_panel",
    "render_audit_event_log",
    "render_tamper_detection_alert",
    "render_session_integrity_summary",
    "render_replay_verification_panel",
    "render_determinism_status_indicator",
    "render_checksum_verification_panel",
    "render_reproducibility_bundle_summary",
    "render_bundle_file_manifest",
    "render_article_decision_card",
    "render_protocol_authority_banner",
    "render_session_lineage_panel",
    "render_session_stats",
]
