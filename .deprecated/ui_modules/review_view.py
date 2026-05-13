"""
APOLLO Human-in-the-Loop Review Interface - Forensic Terminal Aesthetic
Streamlit UI for researcher-driven screening

V1.0.0 UPDATES:
- Specialized rendering for Grey Literature (GL) with source URL prominence.
- Improved decision persistence and audit note capturing.
- Strict stage blocking logic (EC -> IC -> QC).
"""
import streamlit as st
import os
import pandas as pd
from datetime import datetime
import logging
from typing import Optional

from src.ui.theme import COLORS, TYPOGRAPHY
from src.ui.components import section_header, divider, terminal_header
from src.core.atlas_processor import ATLASLoader, APOLLODecisionEngine
from src.core.screening_session import (
    ScreeningSession, SessionStage, 
    save_screening_session, load_screening_session, recover_session
)
from src.core.reviewer_state import ReviewerState
from src.core.llm_assistant import LLMAssistant
from src.core.export_engine import ExportEngine

logger = logging.getLogger(__name__)

# ==============================================================================
# 1. SESSION MANAGEMENT HELPERS
# ==============================================================================

def save_session_state():
    """Silently persists session to disk."""
    if "session" in st.session_state and st.session_state.session:
        st.session_state.session.save("sessions")

def handle_load_session(session_id: str):
    """Loads a specific session and updates UI state."""
    loaded = load_screening_session(session_id)
    if loaded:
        st.session_state.session = loaded
        # Reconstruct reviewer state from session metadata if possible
        st.session_state.reviewer_state = ReviewerState(
            researcher_id="researcher_1",
            session_id=loaded.session_id,
            stage=loaded.stage
        )
        st.rerun()

# ==============================================================================
# 2. SIDEBAR COMPONENTS
# ==============================================================================

def render_review_sidebar():
    """Compact sidebar for session management and protocol configuration."""
    with st.sidebar:
        st.markdown(f"<div style='{TYPOGRAPHY['mono']}; font-size: 0.8rem; color: {COLORS['cyan']};'>● SESSION CONTROL</div>", unsafe_allow_html=True)
        
        if "session" in st.session_state and st.session_state.session:
            session = st.session_state.session
            st.caption(f"ID: {session.session_id[:12]}...")
            st.caption(f"Stage: {session.stage.upper()}")
            
            # Progress & Stats
            progress = session.get_progress()
            st.progress(progress["current"] / progress["total"] if progress["total"] > 0 else 0)
            st.caption(f"{progress['current']}/{progress['total']} papers reviewed")
            
            c1, c2 = st.columns(2)
            c1.metric("INC", progress["included"])
            c2.metric("EXC", progress["excluded"])
            
            divider()
            
            # Dynamic Protocol Config
            from src.ui.modules.protocol_view import render_protocol_config_panel
            render_protocol_config_panel(session, session.stage)
            
            if st.button("💾 SAVE SESSION", width="stretch"):
                save_session_state()
                st.toast("Progress persisted to disk", icon="💾")
                
        else:
            st.info("No active session loaded")
            
        divider()
        
        # Session Loading Logic
        with st.expander("📂 LOAD PREVIOUS SESSION"):
            from src.core.screening_session import list_sessions
            sessions = list_sessions()
            if sessions:
                # Get unique sessions sorted by date
                session_options = {f"{s['session_id'][:8]} ({s['date']})": s['session_id'] for s in sessions}
                selected_label = st.selectbox("Select Session", options=list(session_options.keys()))
                if st.button("CONFIRM LOAD"):
                    handle_load_session(session_options[selected_label])
            else:
                st.caption("No sessions found in /sessions")

# ==============================================================================
# 3. ARTICLE RENDERING (THE CORE CARD)
# ==============================================================================

def render_article_card(article):
    """Renders article with forensic focus on metadata and GL URLs."""
    lit_type = article.metadata.get('literature_type', 'WL')
    
    with st.container():
        if lit_type == "WL":
            st.markdown(f"""
                <div style="background:{COLORS['cyan']}15; border:1px solid {COLORS['cyan']}44; border-radius:4px; padding:8px 12px; margin-bottom:12px;">
                    <span style="color:{COLORS['cyan']}; font-family:{TYPOGRAPHY['mono']}; font-size:0.85rem; font-weight:bold;">▸ WHITE LITERATURE SCREENING</span>
                    <span style="color:{COLORS['text_muted']}; font-family:{TYPOGRAPHY['mono']}; font-size:0.75rem; margin-left:12px;">Peer-reviewed academic corpus</span>
                </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
                <div style="background:{COLORS['warning']}15; border:1px solid {COLORS['warning']}44; border-radius:4px; padding:8px 12px; margin-bottom:12px;">
                    <span style="color:{COLORS['warning']}; font-family:{TYPOGRAPHY['mono']}; font-size:0.85rem; font-weight:bold;">▸ GREY LITERATURE SCREENING</span>
                    <span style="color:{COLORS['text_muted']}; font-family:{TYPOGRAPHY['mono']}; font-size:0.75rem; margin-left:12px;">Non-peer-reviewed source inspection required</span>
                </div>
            """, unsafe_allow_html=True)
        
        st.markdown(f"## {article.title}")
        
        meta = article.metadata
        year_value = meta.get('year', 'N/A')
        year_source = meta.get('year_source', 'unknown')
        
        if year_source == "structured":
            year_label = f"{year_value} [STRUCTURED]"
        elif year_source == "regex":
            year_label = f"{year_value} [INFERRED]"
        else:
            year_label = str(year_value) if year_value else "N/A"
        
        cols = st.columns([1, 1, 1, 1])
        cols[0].caption(f"**ID:** {article.article_id[:8]}")
        cols[1].caption(f"**Year:** {year_label}")
        cols[2].caption(f"**Source:** {meta.get('library', meta.get('source_file', 'ATLAS Import'))}")
        
        url = meta.get('url', '')
        if url:
            cols[3].markdown(f"[🔗 OPEN SOURCE URL]({url})")
        
        divider()
        
        abstract = article.abstract
        
        if lit_type == "GL" and ("[MANUAL REVIEW REQUIRED]" in abstract or not abstract):
            st.warning("⚠️ **METHODOLOGICAL NOTICE:** Grey Literature abstract is unavailable in ATLAS export. Please perform evaluation by visiting the Source URL provided above.")
        
        if not abstract or "[ABSTRACT MISSING" in abstract:
            st.markdown(f"""
                <div style="background:{COLORS['warning']}22; padding:1rem; border-radius:8px; border:1px solid {COLORS['warning']}44; margin-bottom:1rem;">
                    <span style="color:{COLORS['warning']}; font-family:{TYPOGRAPHY['mono']}; font-size:0.8rem;">⚠️ No abstract available. Manual source inspection required.</span>
                </div>
            """, unsafe_allow_html=True)
        
        st.markdown(f"""
            <div style="background:{COLORS['bg_card']}; padding:1.5rem; border-radius:8px; border:1px solid {COLORS['border_light']}; line-height:1.6; color:#E5E5E5;">
                {abstract if abstract and not "[ABSTRACT MISSING" in abstract else "<i>No abstract available for this record.</i>"}
            </div>
        """, unsafe_allow_html=True)

# ==============================================================================
# 4. DECISION CONTROLS
# ==============================================================================

def render_decision_controls(session: ScreeningSession, article):
    """Render ergonomic buttons and captures reasoning."""
    st.markdown(f"<div style='{TYPOGRAPHY['mono']}; font-size: 0.8rem; color: {COLORS['text_muted']}; margin-top:2rem;'>▸ DECISION CONSOLE</div>", unsafe_allow_html=True)
    
    is_blocked = False
    lit_type = article.metadata.get('literature_type', 'WL')
    
    if session.stage == "ic":
        if article.ec_stage == "exclude":
            st.error("🚫 ARTICLE BLOCKED: Failed Exclusion Criteria (EC).")
            is_blocked = True
        elif lit_type == "GL" and article.metadata.get('ic_decision') == "PENDING":
            st.warning("⚠️ **GL METHODOLOGICAL BLOCK:** Grey Literature that passed EC requires manual source inspection. Please visit the Source URL to complete evaluation.")
            st.info("📋 Use DISCUSS button to mark this for manual review, or EXCLUDE if the source is inaccessible.")
            is_blocked = False
    elif session.stage == "qc":
        if article.ec_stage == "exclude" or article.ic_stage == "exclude":
            st.error("🚫 ARTICLE BLOCKED: Failed Previous Screening Stage.")
            is_blocked = True

    c1, c2, c3, c4 = st.columns(4)
    
    # Logic for button states
    btn_disabled = is_blocked
    
    with c1:
        inc = st.button("✅ INCLUDE", width="stretch", type="primary", disabled=btn_disabled)
    with c2:
        exc = st.button("❌ EXCLUDE", width="stretch", disabled=btn_disabled)
    with c3:
        dis = st.button("💬 DISCUSS", width="stretch", disabled=btn_disabled)
    with c4:
        skp = st.button("⏭️ SKIP", width="stretch")

    notes = st.text_area("Audit Notes / Reasoning:", placeholder="Enter justification for this decision...", key=f"note_{article.article_id}")

    # Process Decision
    decision = None
    if inc: decision = "include"
    if exc: decision = "exclude"
    if dis: decision = "needs_discussion"
    
    if decision:
        # Update Session Data
        session.apply_decision(article.article_id, session.stage, decision, notes)
        
        # Log in ReviewerState for audit
        if "reviewer_state" in st.session_state:
            st.session_state.reviewer_state.record_decision(
                article_id=article.article_id,
                stage=session.stage,
                decision=decision,
                notes=notes
            )
        
        save_session_state()
        session.advance()
        st.rerun()
        
    if skp:
        session.advance(skip=True)
        st.rerun()

# ==============================================================================
# 5. MAIN RENDERER
# ==============================================================================

def render_review_interface():
    """Main entry point for the review module."""

    st.warning("DEPRECATED: This view is not routed by app.py. Canonical workflow uses EC/IC/QC Screening views. Will be removed in a future release.")

    # Initialize session if empty
    if "session" not in st.session_state or st.session_state.session is None:
        terminal_header("SCREENING SESSION", "Ready for ingestion", status="IDLE")
        
        c1, c2 = st.columns([2, 1])
        with c1:
            st.markdown("### Start New Session")
            uploaded_file = st.file_uploader("Upload ATLAS Excel File (WL/GL)", type=["xlsx"])
            if uploaded_file:
                from src.core.atlas_processor import create_screening_session
                # Salva arquivo temporário para processamento
                with open("temp_atlas.xlsx", "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # Inicia sessão
                session, rev_state, _, _ = create_screening_session("temp_atlas.xlsx")
                st.session_state.session = session
                st.session_state.reviewer_state = rev_state
                st.rerun()
        return

    # Active Session View
    session = st.session_state.session
    render_review_sidebar()
    
    terminal_header(
        f"{session.stage.upper()} SCREENING", 
        f"Reviewing {session.protocol_version} protocol",
        status="ACTIVE"
    )

    # Stage Selector (Horizontal)
    stages = ["ec", "ic", "qc"]
    selected_stage = st.segmented_control(
        "Current Workflow Stage:", 
        options=stages, 
        format_func=lambda x: x.upper(),
        default=session.stage
    )
    if selected_stage != session.stage:
        session.stage = selected_stage
        st.rerun()

    divider()

    # Get Current Article
    article = session.get_current_article()
    
    if article:
        render_article_card(article)
        
        # LLM Advisory (Optional)
        llm = LLMAssistant()
        if llm.is_available():
            with st.expander("🤖 AI ADVISORY SUGGESTION (Non-Binding)", expanded=False):
                suggestion = llm.suggest(
                    title=article.title,
                    abstract=article.abstract,
                    literature_type=article.metadata.get('literature_type', 'WL'),
                    stage=session.stage,
                    metadata=article.metadata
                )
                st.write(suggestion.to_display())
                st.caption(suggestion.justification)
                if suggestion.ambiguity_flags:
                    st.info(f"Ambiguity flags: {', '.join(suggestion.ambiguity_flags)}")
        
        render_decision_controls(session, article)
    else:
        st.success("🏁 All articles in this stage have been reviewed.")
        if st.button("Refresh / Start Over"):
            session.current_index = 0
            st.rerun()

def render():
    """Wrapper for app.py routing."""
    render_review_interface()