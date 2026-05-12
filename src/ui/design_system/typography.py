"""
APOLLO Scientific Design System - Typography

Defines typography tokens for forensic terminal aesthetic with
scientific documentation clarity.

PRINCIPLES:
- Monospace for data, codes, hashes, identifiers
- Sans-serif for body text, descriptions
- Clear hierarchy for scientific documentation
- WCAG compliant sizing for accessibility
"""

TYPOGRAPHY = {
    "mono": "'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
    "mono_small": "'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
    "sans": "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif",
    "heading_size": "1.25rem",
    "body_size": "0.875rem",
    "small_size": "0.75rem",
    "mono_size": "0.8rem",
}

TYPOGRAPHY_SCALE = {
    "xs": "0.65rem",
    "sm": "0.7rem",
    "base": "0.875rem",
    "lg": "1rem",
    "xl": "1.125rem",
    "2xl": "1.25rem",
    "3xl": "1.5rem",
    "4xl": "2rem",
}

FONT_WEIGHTS = {
    "normal": 400,
    "medium": 500,
    "semibold": 600,
    "bold": 700,
}

LETTER_SPACING = {
    "tight": "-0.01em",
    "normal": "0",
    "wide": "0.05em",
    "wider": "0.1em",
    "widest": "0.15em",
    "ultra": "0.2em",
}

LINE_HEIGHTS = {
    "none": 1,
    "tight": 1.25,
    "snug": 1.375,
    "normal": 1.5,
    "relaxed": 1.625,
    "loose": 2,
}


STYLE_GUIDES = {
    "terminal_header": {
        "font_family": TYPOGRAPHY["mono"],
        "font_size": TYPOGRAPHY_SCALE["3xl"],
        "font_weight": FONT_WEIGHTS["semibold"],
        "letter_spacing": LETTER_SPACING["wider"],
        "text_transform": "uppercase",
    },
    "section_header": {
        "font_family": TYPOGRAPHY["mono"],
        "font_size": TYPOGRAPHY_SCALE["sm"],
        "font_weight": FONT_WEIGHTS["medium"],
        "letter_spacing": LETTER_SPACING["ultra"],
        "text_transform": "uppercase",
    },
    "subsection_header": {
        "font_family": TYPOGRAPHY["mono"],
        "font_size": TYPOGRAPHY_SCALE["base"],
        "font_weight": FONT_WEIGHTS["semibold"],
        "letter_spacing": LETTER_SPACING["wide"],
    },
    "body": {
        "font_family": TYPOGRAPHY["sans"],
        "font_size": TYPOGRAPHY_SCALE["base"],
        "font_weight": FONT_WEIGHTS["normal"],
        "line_height": LINE_HEIGHTS["relaxed"],
    },
    "body_small": {
        "font_family": TYPOGRAPHY["sans"],
        "font_size": TYPOGRAPHY_SCALE["sm"],
        "font_weight": FONT_WEIGHTS["normal"],
        "line_height": LINE_HEIGHTS["normal"],
    },
    "caption": {
        "font_family": TYPOGRAPHY["sans"],
        "font_size": TYPOGRAPHY_SCALE["xs"],
        "font_weight": FONT_WEIGHTS["normal"],
        "color": "text_muted",
    },
    "code": {
        "font_family": TYPOGRAPHY["mono"],
        "font_size": TYPOGRAPHY_SCALE["sm"],
        "font_weight": FONT_WEIGHTS["normal"],
    },
    "hash_identifier": {
        "font_family": TYPOGRAPHY["mono"],
        "font_size": TYPOGRAPHY_SCALE["xs"],
        "font_weight": FONT_WEIGHTS["medium"],
        "letter_spacing": LETTER_SPACING["wide"],
    },
    "metric_value": {
        "font_family": TYPOGRAPHY["mono"],
        "font_size": TYPOGRAPHY_SCALE["xl"],
        "font_weight": FONT_WEIGHTS["bold"],
    },
    "metric_label": {
        "font_family": TYPOGRAPHY["mono"],
        "font_size": TYPOGRAPHY_SCALE["xs"],
        "font_weight": FONT_WEIGHTS["medium"],
        "letter_spacing": LETTER_SPACING["widest"],
        "text_transform": "uppercase",
    },
    "badge": {
        "font_family": TYPOGRAPHY["mono"],
        "font_size": TYPOGRAPHY_SCALE["xs"],
        "font_weight": FONT_WEIGHTS["semibold"],
        "letter_spacing": LETTER_SPACING["wide"],
    },
    "stage_indicator": {
        "font_family": TYPOGRAPHY["mono"],
        "font_size": TYPOGRAPHY_SCALE["sm"],
        "font_weight": FONT_WEIGHTS["semibold"],
        "letter_spacing": LETTER_SPACING["wider"],
    },
    "provenance": {
        "font_family": TYPOGRAPHY["mono"],
        "font_size": TYPOGRAPHY_SCALE["xs"],
        "font_weight": FONT_WEIGHTS["normal"],
        "letter_spacing": LETTER_SPACING["normal"],
    },
}


def get_typography_style(style_name: str) -> dict:
    """Get typography style by name."""
    return STYLE_GUIDES.get(style_name, STYLE_GUIDES["body"])


def build_css_font_stack(theme: str = "default") -> str:
    """Build CSS font stack for a theme."""
    if theme == "mono":
        return TYPOGRAPHY["mono"]
    elif theme == "sans":
        return TYPOGRAPHY["sans"]
    return f"{TYPOGRAPHY['sans']}, {TYPOGRAPHY['mono']}"
