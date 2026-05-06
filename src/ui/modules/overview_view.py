import streamlit as st
import plotly.graph_objects as go
from src.core.workflow import ReviewStage

GAROUSI_STAGES = [
    ("planning", "Planning", "Setup RQs and Criteria"),
    ("search", "Search & Ingestion", "WL/GL Import"),
    ("screening", "Screening", "Title/Abstract selection"),
    ("quality", "Quality Assessment", "Scoring items"),
    ("extraction", "Data Extraction", "Fragment retrieval"),
    ("synthesis", "Synthesis", "Thematic coding"),
]

from src.core.services import (
    get_settings,
    get_prisma_flow,
    get_gl_inventory,
    format_research_questions,
    format_exclusion_criteria,
    get_protocol_stage_info,
    advance_protocol_stage,
    get_reviewer_id,
)

@st.cache_resource
def get_database():
    from src.core.database import Database
    review_id = st.session_state.get("review_id", 1)
    return Database(review_id=review_id)

def require_stage(required_stage: ReviewStage, db) -> bool:
    current = ReviewStage(db.get_current_stage())
    if current != required_stage:
        st.error(f"[LOCKED] This section requires '{required_stage.value}' stage")
        st.info(f"Workflow: {db.get_stage_prompt()}")
        return False
    return True

def display_protocol_stepper(db):
    progress = db.get_stage_progress()
    current_stage = progress["current_stage"]
    stage_index = progress["stage_index"]
    
    stage_mapping = {
        "calibration": 0, "planning": 0, "search": 1, "screening": 2,
        "cross_audit": 3, "quality": 3, "consensus": 3, "extraction": 4, "synthesis": 5,
    }
    mapped_index = stage_mapping.get(current_stage.lower(), stage_index)
    
    st.markdown("### Protocol Stepper")
    cols = st.columns(len(GAROUSI_STAGES))
    
    for idx, (stage_key, stage_name, stage_desc) in enumerate(GAROUSI_STAGES):
        with cols[idx]:
            if idx < mapped_index:
                status, color, bg_color = "[COMPLETED]", "#10B981", "rgba(16, 185, 129, 0.15)"
            elif idx == mapped_index:
                status, color, bg_color = "[CURRENT]", "#3B82F6", "rgba(59, 130, 246, 0.2)"
            else:
                status, color, bg_color = "[PENDING]", "#6B7280", "rgba(107, 114, 128, 0.1)"
            
            st.markdown(f"""<div style="padding: 0.5rem; background: {bg_color}; border-left: 3px solid {color}; border-radius: 4px; margin-bottom: 0.5rem;">
                <div style="color: {color}; font-weight: 600; font-size: 0.85rem;">{status}</div>
                <div style="color: #E5E7EB; font-size: 0.9rem; font-weight: 500;">{stage_name}</div>
                <div style="color: #9CA3AF; font-size: 0.75rem;">{stage_desc}</div>
            </div>""", unsafe_allow_html=True)

def render_overview_view():
    db = get_database()
    settings = get_settings()
    proj_name = settings.get("project_name", "Research Project")
    
    st.markdown(f"""<div style="margin-bottom: 1.5rem;">
        <h2 style="margin: 0; font-size: 1.75rem;">{proj_name}</h2>
        <p style="color: var(--text-secondary); margin: 0.25rem 0 0 0;">Real-time pipeline statistics and PRISMA flow tracking</p>
    </div>""", unsafe_allow_html=True)
    
    display_protocol_stepper(db)
    
    with st.expander("Protocol Planning", expanded=False):
        col_rq, col_crit = st.columns([1, 1])
        with col_rq:
            st.markdown("**Research Questions**")
            rqs = db.get_research_questions()
            formatted_rqs = format_research_questions(rqs)
            for rq in formatted_rqs:
                st.caption(f"**{rq['id']}:** {rq['question']}...")
        with col_crit:
            st.markdown("**Exclusion Criteria**")
            ec_list = db.get_eligibility_criteria('EC')
            formatted_ec = format_exclusion_criteria(ec_list)
            for ec in formatted_ec:
                st.caption(f"**{ec['id']}:** {ec['description']}...")
    
    stage_info = get_protocol_stage_info(db)
    current_stage = stage_info["current_stage"]
    
    with st.expander("🔧 Protocol Stage Control", expanded=False):
        st.caption(f"Current Stage: **{current_stage.title()}**")
        
        col_status, col_action = st.columns([2, 1])
        with col_status:
            st.success(f"🟢 Active: {current_stage.title()}")
        with col_action:
            if stage_info["can_advance"]:
                next_stage = stage_info["next_stage"]
                next_label = stage_info["stage_labels"][stage_info["current_idx"] + 1]
                if st.button(f"Advance to {next_label}", type="primary"):
                    result = advance_protocol_stage(db, next_stage)
                    if result.get('success'):
                        st.success(f"Advanced to {next_stage.title()}!")
                        st.rerun()
                    else:
                        blockers = result.get('blockers', result.get('reasons', []))
                        st.error(f"Cannot advance: {blockers[0] if blockers else 'Requirements not met'}")

    gl_articles = get_gl_inventory(db)
    
    with st.expander("📥 Grey Literature Inventory", expanded=False):
        if gl_articles.empty:
            st.info("No GL articles imported yet.")
        else:
            st.dataframe(gl_articles[['title', 'status']], use_container_width=True)
    
    prisma = get_prisma_flow(db)
    has_data = prisma["total_imported"] > 0
    
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1: st.metric("Total Imported", prisma["total_imported"])
    with c2: st.metric("Screened", prisma["screened"])
    with c3: st.metric("Pending", prisma["pending_screening"])
    with c4: st.metric("Included (Screening)", prisma["included_screening"])
    with c5: st.metric("Final Included", prisma["final_included"])
    with c6: st.metric("QA Pending", prisma["qa_pending"])
    
    st.divider()
    
    if has_data:
        try:
            fig = go.Figure(data=[go.Sankey(
                node=dict(pad=15, thickness=20, line=dict(color="white", width=0.5),
                    label=["Total Imported", "Screened", "Pending", "Excluded", "Included", "Final", "QA Passed", "QA Failed"]),
                link=dict(source=[0,1,1,1,2,4,4,4], target=[1,2,3,4,5,6,7,5], value=[prisma["total_imported"], prisma["screened"], prisma["pending_screening"], prisma["excluded_screening"], prisma["included_screening"], prisma["final_included"], prisma["qa_passed"], prisma["qa_failed"]])
            )])
            fig.update_layout(title="PRISMA Flow", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="white"), height=350)
            st.plotly_chart(fig, width=True)
        except Exception as e:
            st.warning(f"Sankey unavailable: {e}")
    
    rqs = settings.get("research_questions", [])
    st.divider()
    st.subheader("Research Questions")
    for i, rq in enumerate(rqs, 1):
        rq_stripped = rq.strip()
        st.markdown(f"**{rq_stripped}**" if rq_stripped.upper().startswith("RQ") else f"**RQ{i}:** {rq}")
    
    st.divider()
    st.subheader("Quick Actions")
    if st.button("Refresh Statistics"):
        st.rerun()
    
    with st.expander(" Calibration Phase (Required)", expanded=False):
        st.caption("Protocol Step 1: Calibrate reviewers before screening (κ ≥ 0.8 required)")
        c1, c2 = st.columns(2)
        with c1:
            reviewer_1 = st.text_input("Reviewer 1", value=get_reviewer_id())
            sample_size = st.number_input("Sample size", min_value=5, max_value=50, value=20)
        with c2:
            reviewer_2 = st.text_input("Reviewer 2")
        
        if st.button("Create Calibration Set", width=True):
            if reviewer_1 and reviewer_2:
                set_id = db.create_calibration_set(reviewer_1, sample_size)
                st.success(f"Calibration set #{set_id} created")
                st.rerun()
        
        results = db.get_calibration_results(review_id)
        if results:
            latest = results[0]
            st.metric("Latest Kappa", f"{latest[3]:.3f}" if latest[3] else "N/A")
            if latest[3] and latest[3] >= 0.8:
                st.success("[OK] Kappa threshold met (≥ 0.8)")
            else:
                st.warning("[WARN] Kappa below threshold")
        else:
            st.info("No calibration completed yet")

def get_quick_stats():
    """Get stats for sidebar."""
    from src.core.services import get_dashboard_stats
    db = get_database()
    return get_dashboard_stats(db)