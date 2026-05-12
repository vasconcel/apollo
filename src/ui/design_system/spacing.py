"""
APOLLO Scientific Design System - Spacing

Defines spacing tokens for consistent layout rhythm and
scientific data visualization alignment.

PRINCIPLES:
- 4px base unit for grid alignment
- Clear visual hierarchy through spacing scale
- Consistent padding for data cards and tables
- Accessible touch targets (minimum 44px)
"""

SPACING = {
    "0": "0",
    "px": "1px",
    "0.5": "0.125rem",
    "1": "0.25rem",
    "2": "0.5rem",
    "3": "0.75rem",
    "4": "1rem",
    "5": "1.25rem",
    "6": "1.5rem",
    "8": "2rem",
    "10": "2.5rem",
    "12": "3rem",
    "16": "4rem",
    "20": "5rem",
    "24": "6rem",
}

SPACING_SCALE = {
    "xs": "0.25rem",
    "sm": "0.5rem",
    "md": "1rem",
    "lg": "1.5rem",
    "xl": "2rem",
    "2xl": "3rem",
    "3xl": "4rem",
}


LAYOUT = {
    "card_padding": "1rem",
    "card_padding_large": "1.5rem",
    "section_gap": "1.5rem",
    "page_margin": "1rem",
    "sidebar_width": "16rem",
    "content_max_width": "80rem",
}


BORDERS = {
    "thin": "1px solid",
    "medium": "1px solid",
    "thick": "2px solid",
    "radius": "0px",
    "card_radius": "0px",
}


TOUCH_TARGETS = {
    "minimum": "44px",
    "recommended": "48px",
}


GRID = {
    "columns": 12,
    "gutter": "1rem",
    "margin": "1rem",
}


def get_spacing(size: str) -> str:
    """Get spacing value by size key."""
    return SPACING.get(size, SPACING["md"])


def get_layout_value(key: str) -> str:
    """Get layout value by key."""
    return LAYOUT.get(key, "1rem")
