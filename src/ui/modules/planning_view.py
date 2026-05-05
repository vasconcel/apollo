import streamlit as st

from src.core.database import Database


def get_database():
    """Returns a cached Database instance with current review_id."""
    review_id = st.session_state.get("review_id", 1)
    return Database(review_id=review_id)


def render_planning():
    """Research Questions and Criteria configuration."""
    db = get_database()
    
    st.markdown("**Protocol Configuration**")
    
    col_rq, col_crit = st.columns([1, 1])
    
    with col_rq:
        st.markdown("**Research Questions**")
        rqs = db.get_research_questions()
        for rq in rqs:
            st.caption(f"**{rq[0]}:** {rq[1][:70]}...")
    
    with col_crit:
        st.markdown("**Exclusion Criteria**")
        ec_list = db.get_eligibility_criteria('EC')
        for ec in ec_list[:5]:
            st.caption(f"**{ec[0]}:** {ec[2][:60]}...")
    
    current_stage = db.get_current_stage()
    
    with st.expander("Protocol Stage Control", expanded=False):
        st.caption(f"Current Stage: **{current_stage.title()}**")
        
        stage_options = ["planning", "search", "screening", "quality", "extraction", "synthesis"]
        stage_labels = ["Planning", "Search & Ingestion", "Screening", "Quality Assessment", "Data Extraction", "Synthesis"]
        
        current_idx = stage_options.index(current_stage) if current_stage in stage_options else 0
        next_stage = stage_options[current_idx + 1] if current_idx < len(stage_options) - 1 else None
        
        col_status, col_action = st.columns([2, 1])
        with col_status:
            st.success(f"Active: {current_stage.title()}")
        with col_action:
            if next_stage:
                if st.button(f"Advance to {stage_labels[current_idx + 1]}", type="primary"):
                    db.set_stage(next_stage)
                    st.rerun()
        
        if st.button("Reset to Planning", type="secondary"):
            db.set_stage("planning")
            st.rerun()