"""
APOLLO Design System - Clean Academic Research Platform

Modern, professional, visually quiet interface for systematic literature review.
Inspired by Linear, Notion, GitHub - not terminal/console aesthetics.
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
    "success": "#00D67E",
    "warning": "#FFB020",
    "error": "#FF4757",
    "info": "#58A6FF",
    "status_included": "#00D67E",
    "status_excluded": "#FF4757",
    "status_conflict": "#FFB020",
    "status_consensus": "#58A6FF",
    "status_pending": "#808080",
    "status_coded": "#00c8d7",
    "font_mono": "'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
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