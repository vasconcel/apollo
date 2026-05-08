"""
APOLLO Human-in-the-Loop Review Interface
Streamlit UI for researcher-driven screening

KEYBOARD SHORTCUTS:
- I: Include
- E: Exclude  
- D: Needs Discussion
- S: Skip
- N: Next (after decision)
- Esc: Save and exit
"""
import streamlit as st
import os
import pandas as pd
from datetime import datetime

from src.core.atlas_processor import ATLASLoader, APOLLODecisionEngine
from src.core.screening_session import (
    ScreeningSession, SessionStage, 
    save_screening_session, load_screening_session, recover_session
)
from src.core.reviewer_state import ReviewerState
from src.core.llm_assistant import LLMAssistant
from src.core.export_engine import ExportEngine
from src.core.calibration_engine import CalibrationEngine


st.session_state.setdefault("session", None)
st.session_state.setdefault("reviewer_state", None)
st.session_state.setdefault("last_action", "")


def render_progress_bar(session: ScreeningSession):
    """Render compact progress bar."""
    progress = session.get_progress()
    
    total = progress["total"]
    current = progress["current"]
    pct = int((current / total * 100)) if total > 0 else 0
    
    # Compact progress bar
    st.progress(pct, text=f"{current}/{total} papers reviewed ({pct}%)")
    
    # Compact stage counters
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("EC", f"{progress['ec_completed']}")
    with c2:
        ic_total = len(session.get_ec_included_articles())
        st.metric("IC passed", f"{ic_total}")
    with c3:
        included = progress.get("included", 0)
        st.metric("Included", included)


def render_decision_summary(session: ScreeningSession):
    """Render compact decision summary."""
    progress = session.get_progress()
    
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Include", progress["included"], delta_color="normal")
    with c2:
        st.metric("Exclude", progress["excluded"], delta_color="inverse")
    with c3:
        st.metric("Discuss", progress["discussion"])
    with c4:
        pending = progress.get(f"{session.stage}_pending", 0)
        st.metric("Pending", pending)


def render_review_sidebar():
    """Render compact sidebar for long review sessions."""
    with st.sidebar:
        st.markdown("**APOLLO**")
        st.caption("Scientific Screening Assistant")
        st.divider()
        
        # Keyboard shortcuts compact
        st.caption("**Shortcuts:** I Incl | E Excl | S Skip")
        
        st.divider()
        
        if "session" in st.session_state and st.session_state.session:
            session = st.session_state.session
            
            st.caption(f"Session: {session.session_id[:12]}...")
            st.caption(f"Protocol: {session.protocol_version}")
            
            current_stage = session.stage
            render_protocol_config_panel(session, current_stage)
            
            st.divider()
            
            progress = session.get_progress()
            render_progress_bar(session)
            
            st.divider()
            render_decision_summary(session)
            
            st.divider()
            
            if st.button("Save Session", use_container_width=True):
                save_session_state()
                st.success("Saved!")
            
            if st.button("Recover Session"):
                recovered = recover_session()
                if recovered:
                    st.session_state.session = recovered
                    st.rerun()
                else:
                    st.warning("No sessions to recover")
        else:
            st.info("No active session")
        
        st.divider()
        
        if st.button("Load Session"):
            from src.core.screening_session import list_sessions
            sessions = list_sessions()
            if sessions:
                session_ids = [s["session_id"] for s in sessions]
                selected = st.selectbox("Select session", session_ids)
                if selected:
                    loaded = load_screening_session(selected)
                    if loaded:
                        st.session_state.session = loaded
                        st.rerun()
                recovered = recover_session()
                if recovered:
                    st.session_state.session = recovered
                    st.rerun()
                else:
                    st.warning("No sessions to recover")
        else:
            st.info("No active session")
        
        st.divider()
        
        if st.button("📂 Load Session"):
            from src.core.screening_session import list_sessions
            sessions = list_sessions()
            if sessions:
                session_ids = [s["session_id"] for s in sessions]
                selected = st.selectbox("Select session", session_ids)
                if selected:
                    loaded = load_screening_session(selected)
                    if loaded:
                        st.session_state.session = loaded
                        st.rerun()


def render_protocol_info():
    """Render active protocol info."""
    
    return


def render_protocol_config_panel(session, current_stage: str):
    """Render protocol configuration panel in sidebar."""
    import logging
    from src.core.dynamic_protocol import DynamicProtocol, Criterion
    
    logger = logging.getLogger(__name__)
    
    if not session.dynamic_protocol:
        session.dynamic_protocol = DynamicProtocol().to_dict()
    
    try:
        protocol = DynamicProtocol.from_dict(session.dynamic_protocol)
    except (TypeError, ValueError) as e:
        logger.warning(f"Failed to load dynamic protocol: {e}. Rebuilding default.")
        st.warning("Protocol state was corrupted. Resetting to default.")
        session.dynamic_protocol = DynamicProtocol().to_dict()
        protocol = DynamicProtocol.from_dict(session.dynamic_protocol)
    stage_protocol = protocol.get_stage_protocol(current_stage)
    
    if not stage_protocol:
        return
    
    with st.expander(f"⚙️ {current_stage.upper()} Criteria Configuration", expanded=False):
        st.caption(f"Edit {current_stage.upper()} criteria - changes apply immediately")
        
        new_criteria = {}
        col1, col2 = st.columns([1, 1])
        
        idx = 0
        for criterion_id, criterion in stage_protocol.criteria.items():
            with (col1 if idx % 2 == 0 else col2):
                enabled = st.checkbox(
                    f"Enable {criterion_id}",
                    value=criterion.enabled,
                    key=f"enable_{criterion_id}"
                )
                new_desc = st.text_input(
                    f"{criterion_id} description",
                    value=criterion.description,
                    key=f"desc_{criterion_id}"
                )
                new_criteria[criterion_id] = {
                    "id": criterion_id,
                    "description": new_desc,
                    "enabled": enabled,
                    "weight": criterion.weight
                }
            idx += 1
        
        st.divider()
        
        new_criterion_id = st.text_input("New criterion ID (e.g., EC5)", key="new_criterion_id")
        new_criterion_desc = st.text_input("New criterion description", key="new_criterion_desc")
        
        if st.button("➕ Add Criterion", key="add_criterion"):
            if new_criterion_id and new_criterion_desc:
                new_criteria[new_criterion_id] = {
                    "id": new_criterion_id,
                    "description": new_criterion_desc,
                    "enabled": True,
                    "keywords": [],
                    "weight": 1.0
                }
                st.success(f"Added {new_criterion_id}")
                st.rerun()
        
        for criterion_id, criterion_data in new_criteria.items():
            try:
                stage_protocol.criteria[criterion_id] = Criterion.from_dict(criterion_data)
            except (TypeError, ValueError) as e:
                logger.error(f"Failed to deserialize criterion {criterion_id}: {e}")
                st.error(f"Failed to save criterion {criterion_id}. Please refresh.")
        
        try:
            session.dynamic_protocol = protocol.to_dict()
        except Exception as e:
            logger.error(f"Failed to serialize protocol: {e}")
            st.error("Failed to save protocol changes. Please refresh.")


def render_article_card(article):
    """Render article as a modern research-focused card."""
    with st.container():
        # Title - large and prominent
        st.markdown(f"### {article.title}")
        
        # Metadata row - compact and readable
        metadata = article.metadata
        
        md_cols = st.columns(4)
        with md_cols[0]:
            st.caption(f"**Type:** {metadata.get('literature_type', 'WL')}")
        with md_cols[1]:
            gid = metadata.get('global_id', '')
            st.caption(f"**ID:** {gid[:16] if gid else 'N/A'}...")
        with md_cols[2]:
            st.caption(f"**Library:** {metadata.get('library', 'N/A')}")
        with md_cols[3]:
            keywords = metadata.get('keywords', '')
            if keywords:
                kw_preview = keywords[:40] + "..." if len(keywords) > 40 else keywords
                st.caption(f"**Keywords:** {kw_preview}")
        
        st.markdown("---")
        
        # Abstract with clean typography
        abstract = article.abstract
        if abstract:
            st.markdown(f"<div style='line-height: 1.7; color: #C9D1D9; padding: 0.5rem; background: #161B22; border-radius: 6px;'>{abstract}</div>", unsafe_allow_html=True)
        else:
            st.warning("No abstract available for this paper")


def render_llm_suggestion_panel(suggestion, stage: str):
    """Render LLM suggestion as advisory panel."""
    if not suggestion:
        st.info("AI suggestions not available - review manually")
        return
    
    st.markdown("---")
    st.markdown("**AI Advisory Suggestion (Non-binding)**")
    
    cols = st.columns([1, 1])
    
    with cols[0]:
        decision = suggestion.get("decision", "skip").upper()
        confidence = suggestion.get("confidence", 0.0)
        
        if decision == "INCLUDE":
            st.success(f"**{decision}** ({int(confidence*100)}% confidence)")
        elif decision == "EXCLUDE":
            st.error(f"**{decision}** ({int(confidence*100)}% confidence)")
        else:
            st.warning(f"**{decision}** ({int(confidence*100)}% confidence)")
    
    with cols[1]:
        criteria = suggestion.get("triggered_criteria", {})
        if criteria:
            st.caption("**Criteria Analysis:**")
            for criterion, reason in criteria.items():
                if reason:
                    st.caption(f"- {criterion}: {reason[:60]}...")
    
    justification = suggestion.get("justification", "")
    if justification:
        st.caption(f"_{justification}_")
    
    evidence = suggestion.get("evidence", [])
    if evidence:
        with st.expander("Evidence"):
            for e in evidence[:5]:
                st.caption(f"- {e}")


def render_decision_buttons(stage: str):
    """Render researcher decision buttons."""
    st.subheader("🎯 Your Decision")
    
    cols = st.columns(4)
    
    with cols[0]:
        include_btn = st.button(
            "✅ Include",
            type="primary",
            use_container_width=True,
            disabled=stage not in ["ec", "ic", "qc"]
        )
    
    with cols[1]:
        exclude_btn = st.button(
            "❌ Exclude",
            type="primary",
            use_container_width=True,
            disabled=stage not in ["ec", "ic", "qc"]
        )
    
    with cols[2]:
        discuss_btn = st.button(
            "💬 Needs Discussion",
            use_container_width=True,
            disabled=stage not in ["ec", "ic", "qc"]
        )
    
    with cols[3]:
        skip_btn = st.button(
            "⏭️ Skip",
            use_container_width=True,
            disabled=stage not in ["ec", "ic", "qc"]
        )
    
    notes = ""
    if include_btn or exclude_btn or discuss_btn:
        notes = st.text_area(
            "Notes (optional)",
            placeholder="Add notes about this decision...",
            key="decision_notes"
        )
    
    choice = None
    if include_btn:
        choice = "include"
    elif exclude_btn:
        choice = "exclude"
    elif discuss_btn:
        choice = "needs_discussion"
    elif skip_btn:
        choice = "skip"
    
    return choice, notes


def save_session_state():
    """Save current session state."""
    if "session" in st.session_state and st.session_state.session:
        session = st.session_state.session
        session.save("sessions")


def load_atlas_and_start_session(uploaded_file, stage: str = "ec"):
    """Load ATLAS file and start review session."""
    import uuid
    
    temp_path = f"temp_session_{uuid.uuid4().hex[:8]}.xlsx"
    
    with open(temp_path, "wb") as f:
        f.write(uploaded_file.getvalue())
    
    try:
        wl_df, gl_df = ATLASLoader.load_atlas_file(temp_path)
        wl_df = ATLASLoader.normalize_wl_columns(wl_df)
        gl_df = ATLASLoader.normalize_gl_columns(gl_df)
        
        engine = APOLLODecisionEngine(enable_llm_reasoning=False)
        
        wl_results = engine.process_wl_articles(wl_df)
        gl_results = engine.process_gl_articles(gl_df)
        
        from src.core.screening_session import create_session
        session = create_session(wl_results + gl_results, "1.0")
        session.stage = stage
        
        reviewer_state = ReviewerState(
            researcher_id="researcher_1",
            session_id=session.session_id,
            stage=stage
        )
        
        st.session_state.session = session
        st.session_state.reviewer_state = reviewer_state
        st.session_state.wl_results = wl_results
        st.session_state.gl_results = gl_results
        st.session_state.temp_path = temp_path
        
        return True
    
    except Exception as e:
        st.error(f"Error loading file: {e}")
        return False


def render_stage_selector_with_indicator() -> str:
    """Render stage selector with prominent modern indicator."""
    session = st.session_state.session
    
    stage_names = {
        "ec": "Exclusion Criteria",
        "ic": "Inclusion Criteria", 
        "qc": "Quality Assessment"
    }
    stage_descriptions = {
        "ec": "Filter out: Not SE research | Before 2015 | Not peer-reviewed | Duplicates",
        "ic": "Filter in: Addresses SE recruitment/selection | Empirical findings",
        "qc": "Assess quality: Methodology | Findings | Limitations"
    }
    
    # Stage selector with cleaner layout
    stage_options = ["ec", "ic", "qc"]
    stage_index = stage_options.index(session.stage) if session.stage in stage_options else 0
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        selected_stage = st.selectbox(
            "Stage",
            options=stage_options,
            index=stage_index,
            format_func=lambda x: stage_names[x],
            key="stage_selector"
        )
    
    if selected_stage != session.stage:
        session.stage = selected_stage
        st.session_state.reviewer_state.stage = selected_stage
    
    # Prominent stage indicator - styled for long sessions
    with col2:
        st.markdown(f"""
        <div style='padding: 0.75rem; background: #1F2937; border-radius: 6px; border-left: 3px solid #2563EB;'>
            <strong style='font-size: 1.1rem;'>{stage_names.get(session.stage, session.stage)}</strong><br>
            <span style='color: #9CA3AF; font-size: 0.85rem;'>{stage_descriptions.get(session.stage, '')}</span>
        </div>
        """, unsafe_allow_html=True)
    
    return session.stage


def render_blocked_message(article, stage: str) -> bool:
    """Render explicit blocked-paper message. Returns True if blocked."""
    if article.can_proceed_to_stage(stage):
        return False
    
    if stage == "ic" and not article.is_ec_included:
        st.error("BLOCKED: This article was excluded at EC stage and cannot proceed to IC stage.")
        st.caption("Reason: " + (article.ec_notes or "EC exclusion decision"))
        return True
    
    if stage == "qc" and not article.is_ic_included:
        st.error("BLOCKED: This article was excluded at IC stage and cannot proceed to QC stage.")
        st.caption("Reason: " + (article.ic_notes or "IC exclusion decision"))
        return True
    
    return False


def render_decision_controls_with_notes(stage: str) -> tuple:
    """Render decision buttons with notes - modern ergonic layout."""
    st.markdown("#### Your Decision")
    
    # Decision buttons in a row - prominent and distinct
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        include_btn = st.button(
            "Include",
            type="primary",
            use_container_width=True,
            disabled=stage not in ["ec", "ic", "qc"]
        )
    
    with col2:
        exclude_btn = st.button(
            "Exclude", 
            type="primary",
            use_container_width=True,
            disabled=stage not in ["ec", "ic", "qc"]
        )
    
    with col3:
        discuss_btn = st.button(
            "Needs Discussion",
            use_container_width=True,
            disabled=stage not in ["ec", "ic", "qc"]
        )
    
    with col4:
        skip_btn = st.button(
            "Skip",
            use_container_width=True,
            disabled=stage not in ["ec", "ic", "qc"]
        )
    
    # Notes field - always visible for audit trail
    notes = st.text_area(
        "Reviewer Notes (optional)",
        placeholder="Document your reasoning for audit trail...",
        key="decision_notes",
        label_visibility="collapsed"
    )
    
    choice = None
    if include_btn:
        choice = "include"
    elif exclude_btn:
        choice = "exclude"
    elif discuss_btn:
        choice = "needs_discussion"
    elif skip_btn:
        choice = "skip"
    
    return choice, notes


def render_export_section():
    """Render export options."""
    st.divider()
    st.subheader("📥 Export Results")
    
    cols = st.columns(4)
    
    with cols[0]:
        if st.button("📊 Excel", use_container_width=True):
            export_to_excel()
    
    with cols[1]:
        if st.button("📄 Session JSON", use_container_width=True):
            export_session_json()
    
    with cols[2]:
        if st.button("📋 Audit Log", use_container_width=True):
            export_audit_log()
    
    with cols[3]:
        if st.button("📊 Calibration CSV", use_container_width=True):
            export_calibration_matrix()
    
    st.caption("**For Inter-Rater Reliability**:")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⚠️ Disagreement Report", use_container_width=True):
            export_disagreement_report()
    
    with col2:
        if st.button("📊 Cohen's Kappa CSV", use_container_width=True):
            export_calibration_matrix()


def export_to_excel():
    """Export decisions to Excel."""
    session = st.session_state.session
    reviewer = st.session_state.reviewer_state
    
    engine = ExportEngine(protocol_version=session.protocol_version)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"exports/decisions_{session.session_id}_{timestamp}.xlsx"
    
    os.makedirs("exports", exist_ok=True)
    
    engine.export_decisions_excel(session, output_path)
    
    with open(output_path, "rb") as f:
        st.download_button(
            "📊 Download Excel",
            data=f.read(),
            file_name=f"APOLLO_decisions_{timestamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )


def export_session_json():
    """Export session JSON."""
    session = st.session_state.session
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"exports/session_{session.session_id}_{timestamp}.json"
    
    os.makedirs("exports", exist_ok=True)
    
    session.save("exports")
    
    with open(session.save("exports"), "r") as f:
        content = f.read()
    
    st.download_button(
        "📄 Download Session",
        data=content,
        file_name=f"APOLLO_session_{timestamp}.json",
        mime="application/json"
    )


def export_audit_log():
    """Export audit log."""
    session = st.session_state.session
    reviewer = st.session_state.reviewer_state
    
    engine = ExportEngine(protocol_version=session.protocol_version)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"exports/audit_{session.session_id}_{timestamp}.json"
    
    os.makedirs("exports", exist_ok=True)
    
    engine.export_audit_log(reviewer, output_path)
    
    with open(output_path, "r") as f:
        content = f.read()
    
    st.download_button(
        "📋 Download Audit",
        data=content,
        file_name=f"APOLLO_audit_{timestamp}.json",
        mime="application/json"
    )


def export_calibration_matrix():
    """Export calibration-ready decision matrix."""
    session = st.session_state.session
    reviewer = st.session_state.reviewer_state
    
    if not reviewer.decisions:
        st.warning("No decisions recorded")
        return
    
    decision_data = []
    for d in reviewer.decisions:
        decision_data.append({
            "article_id": d.article_id,
            "stage": d.stage,
            "researcher": d.researcher_id,
            "decision": d.decision,
            "ai_suggestion": d.ai_suggestion or "",
            "ai_confidence": d.ai_confidence or 0.0,
            "notes": d.notes,
            "timestamp": d.timestamp,
            "did_override_ai": d.did_override_ai
        })
    
    df = pd.DataFrame(decision_data)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"exports/calibration_{session.session_id}_{timestamp}.csv"
    
    os.makedirs("exports", exist_ok=True)
    df.to_csv(output_path, index=False)
    
    with open(output_path, "r") as f:
        content = f.read()
    
    st.download_button(
        "📊 Download Calibration CSV",
        data=content,
        file_name=f"APOLLO_calibration_{timestamp}.csv",
        mime="text/csv"
    )


def export_disagreement_report():
    """Export disagreement report for calibration."""
    session = st.session_state.session
    reviewer = st.session_state.reviewer_state
    
    overrides = reviewer.get_ai_overrides()
    
    if not overrides:
        st.info("No AI overrides - perfect agreement!")
        return
    
    data = []
    for o in overrides:
        data.append({
            "article_id": o.article_id,
            "stage": o.stage,
            "human_decision": o.decision,
            "ai_suggestion": o.ai_suggestion,
            "ai_confidence": o.ai_confidence,
            "reason": o.notes or "Human overrode AI",
            "timestamp": o.timestamp
        })
    
    df = pd.DataFrame(data)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"exports/disagreements_{session.session_id}_{timestamp}.csv"
    
    os.makedirs("exports", exist_ok=True)
    df.to_csv(output_path, index=False)
    
    with open(output_path, "r") as f:
        content = f.read()
    
    st.download_button(
        "⚠️ Download Disagreement Report",
        data=content,
        file_name=f"APOLLO_disagreements_{timestamp}.csv",
        mime="text/csv"
    )


def render_review_interface():
    """Main review interface."""
    st.header("🔬 APOLLO - Human-in-the-Loop Screening")
    st.caption("Researcher makes final decisions with LLM advisory suggestions")
    
    render_protocol_info()
    
    st.divider()
    
    if "session" not in st.session_state or not st.session_state.session:
        render_start_new_session()
    else:
        render_active_session()


def render_start_new_session():
    """Render start new session UI."""
    st.subheader("📁 Start New Screening Session")
    
    st.info("""
    **Upload ATLAS Excel file** to begin screening:
    - WL sheet: Library, Global_ID, Local_ID, Title, Abstract, Keywords
    - GL sheet: Posicao, Title, URL, Source_File
    """)
    
    uploaded_file = st.file_uploader("Upload ATLAS Excel", type=["xlsx"])
    
    if uploaded_file:
        stage = st.selectbox(
            "Start at stage",
            options=["ec", "ic", "qc"],
            format_func=lambda x: {"ec": "Exclusion Criteria (EC)", "ic": "Inclusion Criteria (IC)", "qc": "Quality Assessment (QC)"}[x]
        )
        
        if st.button("🚀 Start Screening", type="primary", use_container_width=True):
            if load_atlas_and_start_session(uploaded_file, stage):
                st.rerun()


def render_active_session():
    """Render active session UI."""
    session = st.session_state.session
    reviewer = st.session_state.reviewer_state
    
    render_review_sidebar()
    
    st.divider()
    
    article = session.get_current_article()
    
    if not article:
        st.success("Screening Complete!")
        
        render_export_section()
        
        if st.button("Start New Session"):
            del st.session_state.session
            del st.session_state.reviewer_state
            st.rerun()
        
        return
    
    current_stage = render_stage_selector_with_indicator()
    
    render_article_card(article)
    
    st.divider()
    
    # Check if article is blocked from current stage
    is_blocked = render_blocked_message(article, current_stage)
    
    # Show LLM suggestion panel (only if not blocked)
    llm_assistant = LLMAssistant()
    
    protocol_criteria = None
    if session.dynamic_protocol:
        from src.core.dynamic_protocol import DynamicProtocol
        protocol = DynamicProtocol.from_dict(session.dynamic_protocol)
        stage_protocol = protocol.get_stage_protocol(current_stage)
        if stage_protocol:
            protocol_criteria = {k: v.description for k, v in stage_protocol.criteria.items() if v.enabled}
    
    suggestion = None
    if not is_blocked and llm_assistant.is_available():
        try:
            if current_stage == "ec":
                suggestion = llm_assistant.suggest_ec(
                    article.title,
                    article.abstract,
                    article.metadata.get("literature_type", "WL"),
                    protocol_criteria=protocol_criteria
                )
            elif current_stage == "ic":
                suggestion = llm_assistant.suggest_ic(
                    article.title,
                    article.abstract,
                    article.metadata.get("literature_type", "WL"),
                    protocol_criteria=protocol_criteria
                )
            elif current_stage == "qc":
                suggestion = llm_assistant.suggest_qc(
                    article.title,
                    article.abstract,
                    article.metadata.get("literature_type", "WL"),
                    protocol_criteria=protocol_criteria
                )
        except Exception:
            pass
    
    if suggestion and not is_blocked:
        render_llm_suggestion_panel(suggestion.to_dict() if hasattr(suggestion, "to_dict") else {}, current_stage)
    elif not is_blocked:
        st.info("LLM suggestions not available - review manually")
    
    # Use new decision controls with notes field always visible
    choice, notes = render_decision_controls_with_notes(current_stage)
    
    if choice and choice != "skip":
        article_review = session.articles[session.current_index]
        
        if current_stage == "ec":
            article_review.ec_stage = choice
            article_review.ec_notes = notes
        elif current_stage == "ic":
            article_review.ic_stage = choice
            article_review.ic_notes = notes
        elif current_stage == "qc":
            article_review.qc_stage = choice
            article_review.qc_notes = notes
        
        reviewer.record_decision(
            article_id=article.article_id,
            stage=current_stage,
            decision=choice,
            notes=notes
        )
        
        if choice == "include":
            session.included_count += 1
        elif choice == "exclude":
            session.excluded_count += 1
        elif choice == "needs_discussion":
            session.discussion_count += 1
        
        if current_stage == "ec":
            session.ec_completed += 1
        elif current_stage == "ic":
            session.ic_completed += 1
        elif current_stage == "qc":
            session.qc_completed += 1
        
        save_session_state()
        
        session.advance()
        
        st.rerun()
    
    elif choice == "skip":
        session.advance(skip=True)
        st.rerun()


def render():
    """Render the full review interface."""
    if "session_state" not in st.session_state:
        st.session_state.session = None
        st.session_state.reviewer_state = None
        st.session_state.wl_results = []
        st.session_state.gl_results = []
    
    render_review_interface()