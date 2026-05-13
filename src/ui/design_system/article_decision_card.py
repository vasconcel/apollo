"""
APOLLO Scientific Design System - Article Decision Card

Canonical article decision component displaying:
- Literature type (WL/GL)
- Provenance metadata
- DOI/source/year lineage
- Metadata completeness
- Decision history
- Audit verification state

PURPOSE:
- Provenance visible without inspecting exports
- Lineage preserved visually
- Canonical decision authority encoded
"""

import streamlit as st
from typing import Dict, Optional
from datetime import datetime
from src.ui.design_system.semantic_colors import (
    SEMANTIC_COLORS, get_semantic_color, get_workflow_stage_color
)
from src.ui.design_system.typography import TYPOGRAPHY
from src.ui.design_system.provenance_components import (
    render_literature_type_indicator,
    render_metadata_completeness,
    render_decision_history,
    render_source_lineage,
)
from src.ui.design_system.audit_components import render_audit_status_badge


def render_article_decision_card(
    article_review,
    current_stage: str,
    show_full_details: bool = True,
    show_audit_state: bool = True
) -> None:
    """
    Render canonical article decision card with full provenance.

    Args:
        article_review: ArticleReview object
        current_stage: Current screening stage
        show_full_details: Whether to show full metadata
        show_audit_state: Whether to show audit verification
    """
    lit_type = article_review.get_literature_type()
    lit_semantic = get_semantic_color(lit_type)

    current_decision = article_review.get_current_stage_decision(current_stage)
    decision_semantic = get_semantic_color(current_decision.upper() if current_decision else "PENDING")

    st.markdown(f"""
    <div style="
        border: 1px solid #252525;
        background: #0D0D0D;
        margin: 0.5rem 0;
    ">
        <!-- Header -->
        <div style="
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1rem;
            border-bottom: 1px solid #1A1A1A;
            background: #111111;
        ">
            <div style="display: flex; align-items: center; gap: 1rem;">
                {render_literature_type_badge_html(lit_type)}
                <span style="
                    font-family: {TYPOGRAPHY['mono']};
                    font-size: 0.65rem;
                    color: #4A4A4A;
                ">
                    ID: {article_review.article_id[:12]}...
                </span>
            </div>
            {render_decision_badge_html(current_decision, decision_semantic)}
        </div>

        <!-- Title & Authors -->
        <div style="padding: 1rem;">
            <h3 style="
                font-family: {TYPOGRAPHY['sans']};
                font-size: 1rem;
                font-weight: 600;
                color: #E5E5E5;
                margin: 0 0 0.75rem 0;
                line-height: 1.4;
            ">
                {article_review.title if article_review.title and article_review.title != 'nan' else '[Title Unavailable]'}
            </h3>
            {render_authors_year_html(article_review.metadata)}
        </div>

        <!-- Source Lineage -->
        <div style="
            padding: 0.75rem 1rem;
            border-top: 1px solid #1A1A1A;
            background: #0A0A0A;
        ">
            {render_source_lineage_html(article_review.metadata)}
        </div>

        <!-- Stage Decisions Summary -->
        {render_stage_decisions_summary(article_review)}

        <!-- Metadata Completeness -->
        <div style="
            padding: 0.75rem 1rem;
            border-top: 1px solid #1A1A1A;
        ">
            {render_completeness_html(article_review.get_metadata_completeness())}
        </div>

        <!-- Audit State -->
        {render_audit_state_section(article_review) if show_audit_state else ''}

        <!-- Notes -->
        {render_notes_section(article_review, current_stage) if article_review.ec_notes or article_review.ic_notes else ''}
    </div>
    """, unsafe_allow_html=True)

    if show_full_details:
        with st.expander("Full Abstract"):
            st.markdown(article_review.abstract if article_review.abstract and article_review.abstract != 'nan' else "_No abstract available_")

        if article_review.metadata.get("keywords"):
            st.markdown(f"**Keywords:** {article_review.metadata.get('keywords')}")


def render_literature_type_badge_html(lit_type: str) -> str:
    """Render literature type badge HTML."""
    semantic = get_semantic_color(lit_type)
    label = "White Literature" if lit_type == "WL" else "Grey Literature"

    return f'''
    <div style="
        display: inline-flex;
        flex-direction: column;
        align-items: center;
        gap: 0.25rem;
    ">
        <span style="
            background: {semantic['badge']};
            color: #000;
            padding: 2px 8px;
            font-family: {TYPOGRAPHY['mono']};
            font-size: 0.75rem;
            font-weight: 700;
        ">
            {lit_type}
        </span>
        <span style="
            font-family: {TYPOGRAPHY['mono']};
            font-size: 0.5rem;
            color: #4A4A4A;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        ">
            {label.split()[0]}
        </span>
    </div>
    '''


def render_decision_badge_html(decision: str, semantic: dict) -> str:
    """Render decision badge HTML."""
    if not decision:
        return f'''
        <span style="
            padding: 0.2rem 0.5rem;
            border: 1px solid #4A4A4A;
            font-family: {TYPOGRAPHY['mono']};
            font-size: 0.65rem;
            color: #4A4A4A;
        ">
            PENDING
        </span>
        '''

    return f'''
    <span style="
        padding: 0.2rem 0.5rem;
        border: 1px solid {semantic['border']};
        background: {semantic['bg']};
        font-family: {TYPOGRAPHY['mono']};
        font-size: 0.65rem;
        font-weight: 600;
        color: {semantic['text']};
    ">
        {decision.upper()}
    </span>
    '''


def render_authors_year_html(metadata: Dict) -> str:
    """Render authors and year HTML."""
    authors = metadata.get("authors", "")
    year = metadata.get("year", "")

    author_display = authors if authors and authors != "nan" else "_Authors unavailable_"
    year_display = year if year and year != "nan" else "_Year unknown_"

    return f'''
    <div style="
        font-family: {TYPOGRAPHY['mono']};
        font-size: 0.75rem;
        color: #808080;
    ">
        <span style="color: #E5E5E5;">{author_display}</span>
        <span style="margin: 0 0.5rem; color: #4A4A4A;">•</span>
        <span style="color: #E5E5E5;">{year_display}</span>
    </div>
    '''


def render_source_lineage_html(metadata: Dict) -> str:
    """Render source lineage HTML."""
    source = metadata.get("source", "")
    library = metadata.get("library", "")
    doi = metadata.get("doi", "")
    url = metadata.get("url", "")
    year_source = metadata.get("year_source", "unknown")

    year_src_labels = {
        "atlas": "ATLAS",
        "doi": "DOI",
        "manual": "Manual",
        "unknown": "?"
    }

    parts = []

    if source and source != "nan":
        parts.append(f"Source: {source}")
    if library and library != "nan":
        parts.append(f"Library: {library}")

    lineage_text = " | ".join(parts) if parts else "Source: Unknown"
    year_src = year_src_labels.get(year_source, year_source)

    html = f'''
    <div style="
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-family: {TYPOGRAPHY['mono']};
        font-size: 0.65rem;
    ">
        <span style="color: #808080;">{lineage_text}</span>
        <span style="
            color: #00c8d7;
            background: rgba(0, 200, 215, 0.1);
            padding: 0.1rem 0.3rem;
            border: 1px solid rgba(0, 200, 215, 0.3);
        ">
            Year from {year_src}
        </span>
    </div>
    '''

    if doi and doi != "nan":
        html += f'''
        <div style="
            font-family: {TYPOGRAPHY['mono']};
            font-size: 0.6rem;
            color: #4A4A4A;
            margin-top: 0.25rem;
        ">
            DOI: <span style="color: #00c8d7;">{doi}</span>
        </div>
        '''
    elif url and url != "nan":
        html += f'''
        <div style="
            font-family: {TYPOGRAPHY['mono']};
            font-size: 0.6rem;
            color: #4A4A4A;
            margin-top: 0.25rem;
            word-break: break-all;
        ">
            URL: <span style="color: #00c8d7;">{url[:60]}...</span>
        </div>
        '''

    return html


def render_stage_decisions_summary(article_review) -> str:
    """Render summary of decisions across all stages."""
    ec_dec = article_review.ec_stage or "pending"
    ic_dec = article_review.ic_stage or "—"

    ec_sem = get_semantic_color(ec_dec.upper() if ec_dec != "pending" else "PENDING")
    ic_sem = get_semantic_color(ic_dec.upper() if ic_dec not in ("—", "pending") else "PENDING")

    return f'''
    <div style="
        display: flex;
        gap: 0.5rem;
        padding: 0.75rem 1rem;
        border-top: 1px solid #1A1A1A;
        background: #0A0A0A;
    ">
        <div style="flex: 1; text-align: center;">
            <div style="
                font-family: {TYPOGRAPHY['mono']};
                font-size: 0.55rem;
                color: #4A4A4A;
                text-transform: uppercase;
                letter-spacing: 0.1em;
                margin-bottom: 0.25rem;
            ">EC</div>
            <span style="
                font-family: {TYPOGRAPHY['mono']};
                font-size: 0.65rem;
                font-weight: 600;
                color: {ec_sem['text']};
            ">
                {ec_dec.upper() if ec_dec != 'pending' else '—'}
            </span>
        </div>
        <div style="width: 1px; background: #1A1A1A;"></div>
        <div style="flex: 1; text-align: center;">
            <div style="
                font-family: {TYPOGRAPHY['mono']};
                font-size: 0.55rem;
                color: #4A4A4A;
                text-transform: uppercase;
                letter-spacing: 0.1em;
                margin-bottom: 0.25rem;
            ">IC</div>
            <span style="
                font-family: {TYPOGRAPHY['mono']};
                font-size: 0.65rem;
                font-weight: 600;
                color: {ic_sem['text']};
            ">
                {ic_dec.upper() if ic_dec not in ('—', 'pending') else '—'}
            </span>
        </div>
    </div>
    '''


def render_completeness_html(completeness: str) -> str:
    """Render metadata completeness HTML."""
    if completeness == "complete":
        semantic = get_semantic_color("METADATA_COMPLETE")
        label = "Complete Metadata"
    elif completeness == "partial":
        semantic = get_semantic_color("METADATA_PARTIAL")
        label = "Partial Metadata"
    elif completeness == "minimal":
        semantic = get_semantic_color("METADATA_MINIMAL")
        label = "Minimal Metadata"
    else:
        semantic = get_semantic_color("PENDING")
        label = "Unknown Completeness"

    return f'''
    <div style="
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.25rem 0.5rem;
        border: 1px solid {semantic['border']};
        background: {semantic['bg']};
    ">
        <span style="
            font-family: {TYPOGRAPHY['mono']};
            font-size: 0.6rem;
            color: {semantic['text']};
        ">
            {label}
        </span>
    </div>
    '''


def render_audit_state_section(article_review) -> str:
    """Render audit state section."""
    timestamps = []
    if article_review.ec_timestamp:
        timestamps.append(f"EC: {article_review.ec_timestamp[:19]}")
    if article_review.ic_timestamp:
        timestamps.append(f"IC: {article_review.ic_timestamp[:19]}")

    if not timestamps:
        return ''

    return f'''
    <div style="
        padding: 0.75rem 1rem;
        border-top: 1px solid #1A1A1A;
        background: #0A0A0A;
    ">
        <div style="
            display: flex;
            justify-content: space-between;
            align-items: center;
        ">
            <span style="
                font-family: {TYPOGRAPHY['mono']};
                font-size: 0.6rem;
                color: #4A4A4A;
                text-transform: uppercase;
                letter-spacing: 0.05em;
            ">
                Audit Trail
            </span>
            <span style="
                font-family: {TYPOGRAPHY['mono']};
                font-size: 0.6rem;
                color: #00c8d7;
            ">
                {' | '.join(timestamps)}
            </span>
        </div>
    </div>
    '''


def render_notes_section(article_review, current_stage: str) -> str:
    """Render researcher notes section."""
    notes = {
        "ec": article_review.ec_notes,
        "ic": article_review.ic_notes,
    }

    active_notes = {k: v for k, v in notes.items() if v}

    if not active_notes:
        return ''

    notes_html = ""
    for stage, note in active_notes.items():
        stage_sem = get_workflow_stage_color(stage)
        notes_html += f'''
        <div style="
            margin-bottom: 0.5rem;
            padding: 0.5rem;
            background: #111111;
            border-left: 2px solid {stage_sem['border']};
        ">
            <span style="
                font-family: {TYPOGRAPHY['mono']};
                font-size: 0.6rem;
                color: {stage_sem['text']};
                font-weight: 600;
            ">[{stage.upper()}]</span>
            <span style="
                font-family: {TYPOGRAPHY['sans']};
                font-size: 0.75rem;
                color: #808080;
                margin-left: 0.5rem;
            ">{note}</span>
        </div>
        '''

    return f'''
    <div style="
        padding: 0.75rem 1rem;
        border-top: 1px solid #1A1A1A;
    ">
        <div style="
            font-family: {TYPOGRAPHY['mono']};
            font-size: 0.6rem;
            color: #4A4A4A;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.5rem;
        ">Researcher Notes</div>
        {notes_html}
    </div>
    '''
