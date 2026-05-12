"""
APOLLO Scientific Design System - Provenance Components

Components for visualizing article and session provenance lineage.

PURPOSE:
- Display literature type (WL/GL) provenance
- Show DOI/source/year lineage
- Display metadata completeness
- Track decision history through stages
"""

import streamlit as st
from typing import Dict, Optional
from datetime import datetime
from src.ui.design_system.semantic_colors import SEMANTIC_COLORS, get_semantic_color
from src.ui.design_system.typography import TYPOGRAPHY


def render_provenance_panel(
    article_metadata: Dict,
    include_raw: bool = False
) -> None:
    """
    Render full provenance panel for an article.

    Args:
        article_metadata: Article metadata dictionary
        include_raw: Whether to show raw metadata
    """
    st.markdown(f"""
    <div style="
        border: 1px solid #252525;
        background: #0D0D0D;
        padding: 1rem;
        margin: 0.5rem 0;
    ">
        <div style="
            font-family: {TYPOGRAPHY['mono']};
            font-size: 0.6rem;
            color: #00c8d7;
            letter-spacing: 0.15em;
            margin-bottom: 0.75rem;
            border-bottom: 1px solid #1A1A1A;
            padding-bottom: 0.5rem;
        ">
            ▸ PROVENANCE METADATA
        </div>
        {render_provenance_rows(article_metadata)}
    </div>
    """, unsafe_allow_html=True)

    if include_raw and "raw_data" in article_metadata:
        with st.expander("Raw Metadata"):
            st.json(article_metadata.get("raw_data", {}))


def render_provenance_rows(metadata: Dict) -> str:
    """Render provenance rows from metadata dictionary."""
    rows = []

    field_map = {
        "title": ("Title", "title"),
        "authors": ("Authors", "authors"),
        "year": ("Year", "year"),
        "doi": ("DOI", "doi"),
        "url": ("URL", "url"),
        "source": ("Source", "source"),
        "library": ("Library", "library"),
        "literature_type": ("Lit. Type", "literature_type"),
        "year_source": ("Year Source", "year_source"),
        "metadata_completeness": ("Completeness", "metadata_completeness"),
    }

    for key, (label, field) in field_map.items():
        value = metadata.get(field, "")
        if value:
            rows.append(f'''
            <div style="
                display: flex;
                justify-content: space-between;
                padding: 0.25rem 0;
                border-bottom: 1px solid #1A1A1A;
                font-family: {TYPOGRAPHY['mono']};
                font-size: 0.7rem;
            ">
                <span style="color: #808080;">{label}</span>
                <span style="color: #E5E5E5;">{value}</span>
            </div>
            ''')

    return "".join(rows)


def render_literature_type_indicator(lit_type: str) -> None:
    """
    Render literature type badge with full context.

    Args:
        lit_type: 'WL' for White Literature or 'GL' for Grey Literature
    """
    semantic = get_semantic_color(lit_type)

    description = "White Literature - Peer-reviewed academic sources" if lit_type == "WL" else "Grey Literature - Non-peer-reviewed sources"

    st.markdown(f"""
    <div style="
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.25rem 0.75rem;
        border: 1px solid {semantic['border']};
        background: {semantic['bg']};
    ">
        <span style="
            font-family: {TYPOGRAPHY['mono']};
            font-size: 0.8rem;
            font-weight: 600;
            color: {semantic['text']};
        ">
            {lit_type}
        </span>
        <span style="
            font-family: {TYPOGRAPHY['mono']};
            font-size: 0.6rem;
            color: #808080;
        ">
            {description}
        </span>
    </div>
    """, unsafe_allow_html=True)


def render_metadata_completeness(completeness: str) -> None:
    """
    Render metadata completeness indicator.

    Args:
        completeness: 'complete', 'partial', or 'minimal'
    """
    if completeness == "complete":
        semantic = get_semantic_color("METADATA_COMPLETE")
    elif completeness == "partial":
        semantic = get_semantic_color("METADATA_PARTIAL")
    else:
        semantic = get_semantic_color("METADATA_MINIMAL")

    labels = {
        "complete": "Complete",
        "partial": "Partial",
        "minimal": "Minimal",
        "unknown": "Unknown"
    }

    st.markdown(f"""
    <div style="
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.2rem 0.5rem;
        border: 1px solid {semantic['border']};
        background: {semantic['bg']};
    ">
        <span style="
            font-family: {TYPOGRAPHY['mono']};
            font-size: 0.65rem;
            color: {semantic['text']};
        ">
            {labels.get(completeness, 'Unknown')} Metadata
        </span>
    </div>
    """, unsafe_allow_html=True)


def render_decision_history(article_review) -> None:
    """
    Render decision history timeline for an article.

    Args:
        article_review: ArticleReview object
    """
    decisions = []

    if article_review.ec_stage:
        decisions.append({
            "stage": "EC",
            "decision": article_review.ec_stage,
            "timestamp": article_review.ec_timestamp,
            "notes": article_review.ec_notes
        })

    if article_review.ic_stage:
        decisions.append({
            "stage": "IC",
            "decision": article_review.ic_stage,
            "timestamp": article_review.ic_timestamp,
            "notes": article_review.ic_notes
        })

    if article_review.qc_stage:
        decisions.append({
            "stage": "QC",
            "decision": article_review.qc_stage,
            "timestamp": article_review.qc_timestamp,
            "notes": article_review.qc_notes
        })

    if not decisions:
        st.caption("No decisions recorded yet")
        return

    st.markdown(f"""
    <div style="
        border: 1px solid #252525;
        background: #0D0D0D;
        padding: 1rem;
        margin: 0.5rem 0;
    ">
        <div style="
            font-family: {TYPOGRAPHY['mono']};
            font-size: 0.6rem;
            color: #00c8d7;
            letter-spacing: 0.15em;
            margin-bottom: 0.75rem;
            border-bottom: 1px solid #1A1A1A;
            padding-bottom: 0.5rem;
        ">
            ▸ DECISION HISTORY
        </div>
    """, unsafe_allow_html=True)

    for i, decision in enumerate(decisions):
        semantic = get_semantic_color(decision["decision"])
        is_last = i == len(decisions) - 1

        connector = "└─" if is_last else "├─"

        st.markdown(f"""
        <div style="
            font-family: {TYPOGRAPHY['mono']};
            font-size: 0.7rem;
            padding: 0.25rem 0;
            border-left: 2px solid {semantic['border']};
            padding-left: 0.75rem;
            margin-left: 0.5rem;
        ">
            <span style="color: {semantic['text']}; font-weight: 600;">[{decision['stage']}]</span>
            <span style="color: #E5E5E5;">{decision['decision'].upper()}</span>
            {f'<span style="color: #808080; margin-left: 0.5rem;">@ {decision["timestamp"][:19] if decision["timestamp"] else "N/A"}</span>' if decision["timestamp"] else ""}
            {f'<div style="color: #4A4A4A; margin-top: 0.25rem; margin-left: 2rem;">{decision["notes"]}</div>' if decision["notes"] else ""}
        </div>
        """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


def render_source_lineage(
    source: str,
    year: str,
    year_source: str,
    doi: str = None
) -> None:
    """
    Render source lineage information.

    Args:
        source: Source database/platform
        year: Publication year
        year_source: How year was determined (atlas, doi, manual)
        doi: Optional DOI
    """
    year_src_labels = {
        "atlas": "ATLAS Export",
        "doi": "DOI Parsed",
        "manual": "Manual Entry",
        "unknown": "Unknown"
    }

    st.markdown(f"""
    <div style="
        display: flex;
        gap: 1.5rem;
        padding: 0.5rem;
        font-family: {TYPOGRAPHY['mono']};
        font-size: 0.7rem;
    ">
        <div>
            <span style="color: #4A4A4A;">SOURCE:</span>
            <span style="color: #E5E5E5;">{source or "N/A"}</span>
        </div>
        <div>
            <span style="color: #4A4A4A;">YEAR:</span>
            <span style="color: #E5E5E5;">{year or "N/A"}</span>
            <span style="color: #808080; margin-left: 0.25rem;">({year_src_labels.get(year_source, year_source)})</span>
        </div>
        {f'<div><span style="color: #4A4A4A;">DOI:</span> <span style="color: #00c8d7;">{doi}</span></div>' if doi else ""}
    </div>
    """, unsafe_allow_html=True)
