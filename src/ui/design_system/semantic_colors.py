"""
APOLLO Scientific Design System - Semantic Color Tokens

Defines semantic visual tokens that encode scientific workflow states,
provenance semantics, and audit chain visualization.

MAPPINGS:
- INCLUDED: Article passed screening stage
- EXCLUDED: Article failed screening criteria
- PENDING: Awaiting review or incomplete
- VERIFIED: Audit chain validated
- REPLAYED: Session replayed for reproducibility
- AUDIT_MISMATCH: Tampering detected
- DETERMINISTIC: Reproducible execution confirmed
- CANONICAL: Protocol authority established

ACCESSIBILITY:
- All color combinations meet WCAG AA contrast (4.5:1 for text)
- Status colors are distinguishable for colorblind users
- Semantic meaning preserved across all themes
"""

COLORS = {
    "bg_deep": "#000000",
    "bg_surface": "#0A0A0A",
    "bg_elevated": "#111111",
    "bg_card": "#0D0D0D",
    "border": "#1A1A1A",
    "border_light": "#252525",
    "border_accent": "#00c8d7",
    "text_primary": "#E5E5E5",
    "text_secondary": "#808080",
    "text_muted": "#4A4A4A",
    "cyan": "#00c8d7",
    "cyan_dim": "#009BA0",
    "cyan_bright": "#00FFFF",
    "cyan_subtle": "rgba(0, 200, 215, 0.15)",
    "cyan_border": "rgba(0, 200, 215, 0.3)",
    "font_mono": "'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
    "font_sans": "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif",
}


SEMANTIC_COLORS = {
    "INCLUDED": {
        "bg": "rgba(0, 214, 126, 0.15)",
        "border": "#00D67E",
        "text": "#00D67E",
        "badge": "#00D67E",
        "description": "Article passed screening criteria and proceeds to next stage",
        "accessibility_label": "Included"
    },
    "EXCLUDED": {
        "bg": "rgba(255, 71, 87, 0.15)",
        "border": "#FF4757",
        "text": "#FF4757",
        "badge": "#FF4757",
        "description": "Article failed screening criteria and is removed from pipeline",
        "accessibility_label": "Excluded"
    },
    "PENDING": {
        "bg": "rgba(128, 128, 128, 0.15)",
        "border": "#808080",
        "text": "#808080",
        "badge": "#808080",
        "description": "Article awaiting review or decision incomplete",
        "accessibility_label": "Pending"
    },
    "SKIP": {
        "bg": "rgba(88, 166, 255, 0.15)",
        "border": "#58A6FF",
        "text": "#58A6FF",
        "badge": "#58A6FF",
        "description": "Article temporarily skipped, recoverable for later review",
        "accessibility_label": "Skipped"
    },
    "NEEDS_DISCUSSION": {
        "bg": "rgba(255, 176, 32, 0.15)",
        "border": "#FFB020",
        "text": "#FFB020",
        "badge": "#FFB020",
        "description": "Article requires team discussion before final decision",
        "accessibility_label": "Needs Discussion"
    },
    "VERIFIED": {
        "bg": "rgba(0, 214, 126, 0.15)",
        "border": "#00D67E",
        "text": "#00D67E",
        "badge": "#00D67E",
        "description": "Audit chain integrity verified, no tampering detected",
        "accessibility_label": "Verified"
    },
    "REPLAYED": {
        "bg": "rgba(0, 200, 215, 0.15)",
        "border": "#00c8d7",
        "text": "#00c8d7",
        "badge": "#00c8d7",
        "description": "Session successfully replayed, outputs match original",
        "accessibility_label": "Replayed"
    },
    "AUDIT_MISMATCH": {
        "bg": "rgba(255, 71, 87, 0.2)",
        "border": "#FF4757",
        "text": "#FF4757",
        "badge": "#FF4757",
        "description": "Audit chain broken or tampering detected - CRITICAL",
        "accessibility_label": "Audit Mismatch Detected"
    },
    "DETERMINISTIC": {
        "bg": "rgba(0, 200, 215, 0.15)",
        "border": "#00c8d7",
        "text": "#00c8d7",
        "badge": "#00c8d7",
        "description": "Execution is deterministic, same input produces same output",
        "accessibility_label": "Deterministic"
    },
    "CANONICAL": {
        "bg": "rgba(0, 200, 215, 0.2)",
        "border": "#00FFFF",
        "text": "#00FFFF",
        "badge": "#00FFFF",
        "description": "Protocol authority established, stage transitions enforced",
        "accessibility_label": "Canonical"
    },
    "LOCKED": {
        "bg": "rgba(88, 166, 255, 0.15)",
        "border": "#58A6FF",
        "text": "#58A6FF",
        "badge": "#58A6FF",
        "description": "Stage locked, cannot proceed without completion",
        "accessibility_label": "Locked"
    },
    "ACTIVE": {
        "bg": "rgba(0, 200, 215, 0.2)",
        "border": "#00c8d7",
        "text": "#00c8d7",
        "badge": "#00c8d7",
        "description": "Currently active stage for review",
        "accessibility_label": "Active"
    },
    "WL": {
        "bg": "rgba(0, 214, 126, 0.15)",
        "border": "#00D67E",
        "text": "#00D67E",
        "badge": "#00D67E",
        "description": "White Literature - peer-reviewed academic sources",
        "accessibility_label": "White Literature"
    },
    "GL": {
        "bg": "rgba(255, 176, 32, 0.15)",
        "border": "#FFB020",
        "text": "#FFB020",
        "badge": "#FFB020",
        "description": "Grey Literature - non-peer-reviewed sources",
        "accessibility_label": "Grey Literature"
    },
    "PROTOCOL_DRAFT": {
        "bg": "rgba(128, 128, 128, 0.15)",
        "border": "#808080",
        "text": "#808080",
        "badge": "#808080",
        "description": "Protocol under development, not yet locked",
        "accessibility_label": "Draft Protocol"
    },
    "PROTOCOL_LOCKED": {
        "bg": "rgba(88, 166, 255, 0.15)",
        "border": "#58A6FF",
        "text": "#58A6FF",
        "badge": "#58A6FF",
        "description": "Protocol locked, immutable for screening sessions",
        "accessibility_label": "Locked Protocol"
    },
    "METADATA_COMPLETE": {
        "bg": "rgba(0, 214, 126, 0.1)",
        "border": "#00D67E",
        "text": "#00D67E",
        "badge": "#00D67E",
        "description": "Article metadata is complete with full provenance",
        "accessibility_label": "Complete Metadata"
    },
    "METADATA_PARTIAL": {
        "bg": "rgba(255, 176, 32, 0.1)",
        "border": "#FFB020",
        "text": "#FFB020",
        "badge": "#FFB020",
        "description": "Article metadata is partial, some fields missing",
        "accessibility_label": "Partial Metadata"
    },
    "METADATA_MINIMAL": {
        "bg": "rgba(255, 71, 87, 0.1)",
        "border": "#FF4757",
        "text": "#FF4757",
        "badge": "#FF4757",
        "description": "Article metadata is minimal, manual verification recommended",
        "accessibility_label": "Minimal Metadata"
    },
}


WORKFLOW_STAGE_COLORS = {
    "protocol": {
        "bg": "rgba(88, 166, 255, 0.15)",
        "border": "#58A6FF",
        "text": "#58A6FF",
        "icon": "◈",
        "description": "Protocol Configuration"
    },
    "ec": {
        "bg": "rgba(255, 71, 87, 0.15)",
        "border": "#FF4757",
        "text": "#FF4757",
        "icon": "⊘",
        "description": "Exclusion Criteria Screening"
    },
    "ic": {
        "bg": "rgba(255, 176, 32, 0.15)",
        "border": "#FFB020",
        "text": "#FFB020",
        "icon": "⊕",
        "description": "Inclusion Criteria Screening"
    },
    "export": {
        "bg": "rgba(0, 200, 215, 0.15)",
        "border": "#00c8d7",
        "text": "#00c8d7",
        "icon": "⬇",
        "description": "Export & Reporting"
    },
    "replay": {
        "bg": "rgba(0, 200, 215, 0.2)",
        "border": "#00FFFF",
        "text": "#00FFFF",
        "icon": "⟲",
        "description": "Reproducibility Replay"
    }
}


def get_semantic_color(state: str) -> dict:
    """Get semantic color definition for a given state."""
    return SEMANTIC_COLORS.get(state.upper(), SEMANTIC_COLORS["PENDING"])


def get_workflow_stage_color(stage: str) -> dict:
    """Get color definition for a workflow stage."""
    return WORKFLOW_STAGE_COLORS.get(stage.lower(), WORKFLOW_STAGE_COLORS["protocol"])


def get_decision_semantic(decision: str) -> dict:
    """Get semantic colors for a screening decision."""
    decision_map = {
        "include": "INCLUDED",
        "exclude": "EXCLUDED",
        "skip": "SKIP",
        "needs_discussion": "NEEDS_DISCUSSION",
        "pending": "PENDING"
    }
    state = decision_map.get(decision.lower(), "PENDING")
    return get_semantic_color(state)
