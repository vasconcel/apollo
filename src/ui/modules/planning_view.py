"""
APOLLO Criteria Configuration
Configure EC, IC, and QC criteria for the review
"""
import streamlit as st
import json


def get_database():
    from src.core.database import Database
    return Database(review_id=st.session_state.get("review_id", 1))


def render_planning():
    """Criteria configuration for EC, IC, QC."""
    st.warning("DEPRECATED: This view is not routed by app.py. Use the Protocol Configuration view instead. Will be removed in a future release.")
    from src.core.database import Database

    db = get_database()
    
    st.header("Protocol Configuration")
    st.caption("Configure eligibility and quality criteria")
    
    tab_ec, tab_ic, tab_qc = st.tabs(["Exclusion Criteria (EC)", "Inclusion Criteria (IC)", "Quality Criteria (QC)"])
    
    with tab_ec:
        st.subheader("Exclusion Criteria")
        st.caption("Binary filters to remove invalid studies")
        
        with st.form("ec_config"):
            ec_1 = st.text_input("EC-1", value="Not empirical software engineering research")
            ec_2 = st.text_input("EC-2", value="Published before 2015")
            ec_3 = st.text_input("EC-3", value="Not peer-reviewed (for WL)")
            ec_4 = st.text_input("EC-4", value="Duplicate publication")
            
            if st.form_submit_button("Update EC Criteria"):
                st.success("EC criteria updated (session only)")
    
    with tab_ic:
        st.subheader("Inclusion Criteria")
        st.caption("Relevance filters for SE R&S domain")
        
        with st.form("ic_config"):
            ic_1 = st.text_input("IC-1", value="Addresses recruitment/selection practices in software organizations")
            ic_2 = st.text_input("IC-2", value="Reports empirical findings (qualitative or quantitative)")
            ic_3 = st.text_input("IC-3", value="Focuses on software industry context")
            
            if st.form_submit_button("Update IC Criteria"):
                st.success("IC criteria updated (session only)")
    
    with tab_qc:
        st.subheader("Quality Criteria")
        st.caption("WL-Q1→Q4 and GL-Q1→Q4 scoring")
        
        st.markdown("**White Literature (WL) Criteria**")
        st.markdown("""
        - WL-Q1: Are the research aims and the SE R&S context clearly stated?
        - WL-Q2: Is the research methodology adequately described and appropriate?
        - WL-Q3: Are the findings clearly supported by the collected data?
        - WL-Q4: Does the study adequately discuss its limitations or threats to validity?
        """)
        
        st.markdown("**Grey Literature (GL) Criteria**")
        st.markdown("""
        - GL-Q1: Is the author's expertise or organizational context explicitly stated?
        - GL-Q2: Is the source of experience transparent (e.g., specific hiring cycle)?
        - GL-Q3: Are the claims supported by operational artifacts rather than mere opinion?
        - GL-Q4: Does the source provide insights beyond generic employer marketing?
        """)
        
        with st.form("qc_config"):
            threshold = st.number_input("Quality Threshold", min_value=0.0, max_value=4.0, value=2.0, step=0.5)
            
            if st.form_submit_button("Update QC Threshold"):
                db.set_config("quality_threshold", threshold)
                st.success(f"QC threshold updated to {threshold}")
    
    st.divider()
    st.subheader("Pipeline Status")
    
    stats = db.get_stats()
    st.json(stats)
    
    st.caption("APOLLO Pipeline: Ingestion → EC → IC → QC")