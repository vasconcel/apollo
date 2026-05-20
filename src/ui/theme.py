"""
APOLLO Design System - Clean Academic Research Platform

Modern, professional, visually quiet interface for systematic literature review.
Inspired by Linear, Notion, GitHub - not terminal/console aesthetics.
"""

COLORS = {
    "bg_deep": "#0D0D0E",
    "bg_surface": "#141416",
    "bg_elevated": "#1A1A1D",
    "bg_card": "#1C1C1F",
    "border": "#2A2A2E",
    "border_light": "#3A3A40",
    "border_accent": "#5E9CA0",
    "text_primary": "#E4E4E7",
    "text_secondary": "#A1A1AA",
    "text_muted": "#71717A",
    "cyan": "#5E9CA0",
    "cyan_dim": "#4A7A7E",
    "cyan_bright": "#7FBFCC",
    "cyan_subtle": "rgba(94, 156, 160, 0.12)",
    "cyan_border": "rgba(94, 156, 160, 0.25)",
    "success": "#34D399",
    "warning": "#FBBF24",
    "error": "#F87171",
    "info": "#60A5FA",
    "status_included": "#34D399",
    "status_excluded": "#F87171",
    "status_conflict": "#FBBF24",
    "status_consensus": "#60A5FA",
    "status_pending": "#A1A1AA",
    "status_coded": "#5E9CA0",
    "font_mono": "'JetBrains Mono', 'IBM Plex Mono', 'Consolas', monospace",
    "font_sans": "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif",
}

STATUS_BADGES = {
    "INCLUDED": ("INCLUDED", COLORS["status_included"]),
    "EXCLUDED": ("EXCLUDED", COLORS["status_excluded"]),
    "CONFLICT": ("CONFLICT", COLORS["status_conflict"]),
    "CONSENSUS": ("CONSENSUS", COLORS["status_consensus"]),
    "PENDING": ("PENDING", COLORS["status_pending"]),
    "CODED": ("CODED", COLORS["status_coded"]),
    "PASSED": ("PASSED", COLORS["success"]),
    "FAILED": ("FAILED", COLORS["error"]),
}

TYPOGRAPHY = {
    "mono": "'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
    "mono_small": "'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
    "sans": "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif",
    "heading_size": "1.25rem",
    "body_size": "0.875rem",
    "small_size": "0.75rem",
    "mono_size": "0.8rem",
}

SPACING = {
    "xs": "4px",
    "sm": "8px",
    "md": "12px",
    "lg": "16px",
    "xl": "24px",
    "xxl": "32px",
    "card_padding": "16px",
    "section_gap": "24px",
}

BORDERS = {
    "thin": "1px solid",
    "medium": "1px solid",
    "radius": "6px",
    "card_radius": "8px",
}


def get_status_badge(status: str) -> tuple:
    """Get badge label and color for status."""
    key = status.upper()
    return STATUS_BADGES.get(key, (status.upper(), COLORS["text_muted"]))


def render_status_badge(status: str) -> str:
    """Render HTML status badge."""
    label, color = get_status_badge(status)
    return f'<span style="background:{color};color:#000;padding:2px 8px;font-family:{TYPOGRAPHY["mono"]};font-size:0.7rem;font-weight:600;letter-spacing:0.05em;">{label}</span>'


def render_lit_type_badge(lit_type: str) -> str:
    """Render literature type badge (WL/GL)."""
    color = COLORS["success"] if lit_type == "WL" else COLORS["warning"]
    return f'<span style="background:{color};color:#000;padding:2px 8px;font-family:{TYPOGRAPHY["mono"]};font-size:0.7rem;font-weight:600;">{lit_type}</span>'


def render_metric_block(label: str, value: str, delta: str = None, color: str = None) -> str:
    """Render a compact metric block."""
    style = f"color:{color};" if color else ""
    delta_html = f'<span style="color:{COLORS['text_muted']};font-size:0.7rem;"> {delta}</span>' if delta else ""
    return f'<div style="border:1px solid {COLORS['border_light']};padding:0.75rem;background:{COLORS['bg_card']};"><div style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['text_muted']};text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.25rem;">{label}</div><div style="font-family:{TYPOGRAPHY['mono']};font-size:1.1rem;font-weight:600;{style}">{value}{delta_html}</div></div>'


def render_decision_card(title: str, decision: str, metadata: dict) -> str:
    """Render a structured decision card."""
    badge = render_status_badge(decision)
    meta_items = " | ".join([f"{k}: {v}" for k, v in metadata.items()])
    return f'''<div style="border:1px solid {COLORS['border_light']};padding:1rem;background:{COLORS['bg_card']};">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem;">
<div style="font-family:{TYPOGRAPHY['mono']};font-size:0.9rem;font-weight:600;color:{COLORS['text_primary']};">{title}</div>
<div>{badge}</div>
</div>
<div style="font-family:{TYPOGRAPHY['mono']};font-size:0.7rem;color:{COLORS['text_muted']};">{meta_items}</div>
</div>'''


def render_telemetry_row(label: str, value: str, unit: str = "") -> str:
    """Render a telemetry-style row."""
    return f'<div style="display:flex;justify-content:space-between;padding:0.5rem 0;border-bottom:1px solid {COLORS['border']};font-family:{TYPOGRAPHY['mono']};font-size:{TYPOGRAPHY['mono_size']};"><span style="color:{COLORS['text_secondary']};">{label}</span><span style="color:{COLORS['cyan']};">{value}{unit}</span></div>'


def render_timeline_event(timestamp: str, event: str, details: str = "") -> str:
    """Render a timeline event entry."""
    details_html = f'<div style="font-size:0.7rem;color:{COLORS['text_muted']};margin-top:0.25rem;">{details}</div>' if details else ""
    return f'''<div style="display:flex;gap:1rem;padding:0.75rem 0;border-left:1px solid {COLORS['border_accent']};padding-left:1rem;">
<div style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['cyan_dim']};white-space:nowrap;">{timestamp}</div>
<div style="flex:1;">
<div style="font-family:{TYPOGRAPHY['mono']};font-size:0.75rem;color:{COLORS['text_primary']};">{event}</div>
{details_html}
</div>
</div>'''


def render_audit_entry(timestamp: str, actor: str, action: str, target: str) -> str:
    """Render an audit log entry."""
    return f'''<div style="font-family:{TYPOGRAPHY['mono']};font-size:0.75rem;padding:0.5rem 0;border-bottom:1px solid {COLORS['border']};">
<span style="color:{COLORS['cyan_dim']};">{timestamp}</span>
<span style="color:{COLORS['warning']};">[{actor}]</span>
<span style="color:{COLORS['text_secondary']};">{action}</span>
<span style="color:{COLORS['text_primary']};">{target}</span>
</div>'''


def render_stage_indicator(stage: str, status: str) -> str:
    """Render stage indicator with status."""
    stage_colors = {"EC": COLORS["error"], "IC": COLORS["warning"]}
    color = stage_colors.get(stage, COLORS["cyan"])
    return f'<span style="color:{color};font-family:{TYPOGRAPHY['mono']};font-size:0.7rem;letter-spacing:0.1em;">[{stage}]</span> <span style="color:{COLORS['text_secondary']};font-family:{TYPOGRAPHY['mono']};font-size:0.7rem;">{status}</span>'