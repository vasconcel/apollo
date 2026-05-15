"""
APOLLO Consolidated Advisory Helpers

Reusable helpers for advisory rendering to reduce duplication.
"""
import streamlit as st
from typing import Dict, Any, Optional

from src.ui.design_system.semantic_colors import COLORS
from src.ui.design_system.typography import TYPOGRAPHY


def advisory_signal_label(confidence: float) -> str:
    """
    Convert numeric confidence to human-readable signal label.
    
    Args:
        confidence: Numeric confidence value (0.0 to 1.0)
    
    Returns:
        Signal label string
    """
    if confidence >= 0.7:
        return "Strong heuristic alignment"
    elif confidence >= 0.4:
        return "Moderate LLM signal"
    else:
        return "Weak heuristic alignment"


def render_advisory_metadata_grounding(metadata_grounding: Dict[str, bool]) -> None:
    """
    Render metadata grounding information compactly.
    
    Args:
        metadata_grounding: Dictionary with boolean grounding flags
    """
    if not metadata_grounding:
        return
    
    st.markdown(f'''
    <div style="
        font-family: {TYPOGRAPHY['mono']};
        font-size: 0.55rem;
        color: {COLORS['text_muted']};
        border-left: 2px solid {COLORS['success']};
        padding: 0.5rem;
        margin-bottom: 0.75rem;
    ">
        METADATA GROUNDING: title={metadata_grounding.get("title_used", False)} | 
        abstract={metadata_grounding.get("abstract_used", False)} | 
        lit_type={metadata_grounding.get("literature_type_used", False)}
    </div>
    ''', unsafe_allow_html=True)


def render_advisory_fallback_warning() -> None:
    """Render fallback warning when LLM is unavailable."""
    st.warning("⚠ STRUCTURED ADVISORY UNAVAILABLE — LLM service unavailable. Manual review required.")


def format_year_display(year: Any, year_source: str) -> str:
    """
    Format year for display with provenance.
    
    Args:
        year: Year value (int, str, or None)
        year_source: Source of year ('atlas', 'regex', 'doi', etc.)
    
    Returns:
        Formatted year string
    """
    year_src_labels = {
        "atlas": "ATLAS",
        "doi": "DOI", 
        "regex": "Extracted",
        "manual": "Manual",
        "csv": "CSV",
        "bibtex": "BibTeX",
        "ris": "RIS",
        "missing": "Missing",
        "unknown": "Unknown"
    }
    
    if year and str(year) not in ["", "nan", "None"]:
        label = year_src_labels.get(year_source, year_source)
        if year_source != "missing":
            return f"{year} ({label})"
        return str(year)
    elif year_source != "missing":
        return f"Unknown ({year_src_labels.get(year_source, year_source)})"
    else:
        return "Unknown"


def render_metadata_table(
    primary_fields: Dict[str, str],
    secondary_fields: Optional[Dict[str, str]] = None,
    secondary_expander_label: str = "Provenance Details"
) -> None:
    """
    Render metadata table with optional secondary expander.
    
    Args:
        primary_fields: Primary fields to display
        secondary_fields: Secondary fields to show in expander
        secondary_expander_label: Label for secondary expander
    """
    table_rows = "".join([
        f"| {k} | {v} |" 
        for k, v in primary_fields.items()
    ])
    
    st.markdown(f"""
    | Field | Value |
    |-------|--------|
    {table_rows}
    """)
    
    if secondary_fields:
        with st.expander(secondary_expander_label, expanded=False):
            secondary_rows = "".join([
                f"| {k} | {v} |"
                for k, v in secondary_fields.items()
            ])
            st.markdown(f"""
            | Field | Value |
            |-------|--------|
            {secondary_rows}
            """, unsafe_allow_html=True)