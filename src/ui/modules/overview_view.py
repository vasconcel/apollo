"""
APOLLO Overview Dashboard with LLM Rationale Inspection
Simple status display for EC/IC/QC pipeline with decision auditing
"""
import streamlit as st


def get_database():
    from src.core.database import Database
    return Database(review_id=st.session_state.get("review_id", 1))


def render_overview():
    """APOLLO Pipeline Status Dashboard with LLM Rationale Inspection."""
    db = get_database()
    
    st.header("APOLLO Dashboard")
    st.caption("Decision Support: EC → IC → QC + LLM Reasoning")
    
    stats = db.get_stats()
    
    st.subheader("Pipeline Progress")
    
    col_total, col_wl, col_gl = st.columns(3)
    with col_total:
        st.metric("Total Articles", stats["total_articles"])
    with col_wl:
        wl_count = len([a for a in db.get_articles() if a.get("literature_type") == "WL"])
        st.metric("White Literature", wl_count)
    with col_gl:
        gl_count = len([a for a in db.get_articles() if a.get("literature_type") == "GL"])
        st.metric("Grey Literature", gl_count)
    
    st.divider()
    st.subheader("Eligibility Stage (EC → IC)")
    
    col_ec_in, col_ec_out, col_ic_in, col_ic_out = st.columns(4)
    with col_ec_in:
        st.metric("EC Passed", stats["ec_passed"])
    with col_ec_out:
        st.metric("EC Excluded", stats["ec_excluded"])
    with col_ic_in:
        st.metric("IC Passed", stats["ic_passed"])
    with col_ic_out:
        st.metric("IC Excluded", stats["ic_excluded"])
    
    ec_total = stats["ec_passed"] + stats["ec_excluded"]
    if ec_total > 0:
        ec_progress = stats["ec_passed"] / ec_total
        st.progress(ec_progress)
        st.caption(f"EC Progress: {stats['ec_passed']}/{ec_total} passed ({int(ec_progress*100)}%)")
    
    st.divider()
    st.subheader("Quality Stage (QC)")
    
    col_qc_pass, col_qc_fail = st.columns(2)
    with col_qc_pass:
        st.metric("QC Passed", stats["qc_passed"], delta="Include")
    with col_qc_fail:
        st.metric("QC Failed", stats["qc_failed"], delta="Exclude", delta_color="inverse")
    
    ic_total = stats["ic_passed"]
    if ic_total > 0:
        qc_complete = stats["qc_passed"] + stats["qc_failed"]
        if qc_complete > 0:
            qc_pass_rate = stats["qc_passed"] / qc_complete
            st.progress(qc_pass_rate)
            st.caption(f"QC Completion: {stats['qc_passed']}/{qc_complete} passed ({int(qc_pass_rate*100)}%)")
    
    st.divider()
    st.subheader("🤖 LLM Rationale Inspector")
    st.caption("Audit and inspect LLM-generated reasoning for decisions")
    
    articles = db.get_articles()
    if not articles:
        st.info("No articles in database yet.")
    else:
        article_options = {f"{a['title'][:60]}... (ID: {a['id']})": a['id'] for a in articles}
        selected_article = st.selectbox("Select Article to Inspect", list(article_options.keys()))
        
        if selected_article:
            article_id = article_options[selected_article]
            rationale = db.get_article_rationale(article_id)
            
            if rationale.get("stages"):
                for stage, data in rationale["stages"].items():
                    with st.expander(f"Stage: {stage} | Decision: {data.get('decision', 'N/A')}"):
                        col_d, col_c = st.columns(2)
                        with col_d:
                            st.caption(f"**Decision:** {data.get('decision', 'N/A')}")
                        with col_c:
                            conf = data.get("confidence")
                            if conf is not None:
                                st.caption(f"**Confidence:** {conf:.2f}")
                        
                        st.caption(f"**Reason:** {data.get('reason', 'N/A')}")
                        
                        stage_rationale = data.get("rationale")
                        if stage_rationale:
                            st.markdown("**LLM Reasoning:**")
                            
                            if "reasoning_trace" in stage_rationale:
                                st.markdown("*Reasoning Trace:*")
                                for trace in stage_rationale.get("reasoning_trace", [])[:5]:
                                    st.caption(f"  • {trace}")
                            
                            if "evidence_used" in stage_rationale and stage_rationale["evidence_used"]:
                                st.markdown("*Evidence Used:*")
                                for ev in stage_rationale["evidence_used"][:3]:
                                    st.caption(f"  - {ev}")
                            
                            if stage == "QC":
                                if stage_rationale.get("criteria_justification"):
                                    st.markdown("*Per-Criteria Justification:*")
                                    for crit, just in stage_rationale["criteria_justification"].items():
                                        st.caption(f"**{crit}**: {just.get('reasoning', 'N/A')[:100]}")
                                
                                if stage_rationale.get("strengths"):
                                    st.markdown("*Strengths:*")
                                    for s in stage_rationale["strengths"]:
                                        st.caption(f"  ✓ {s}")
                                
                                if stage_rationale.get("weaknesses"):
                                    st.markdown("*Weaknesses:*")
                                    for w in stage_rationale["weaknesses"]:
                                        st.caption(f"  ✗ {w}")
                        else:
                            st.caption("No LLM rationale generated for this stage.")
            else:
                st.info("No decisions recorded for this article yet.")
    
    st.divider()
    st.subheader("APOLLO Pipeline")
    st.markdown("""
    ```
    ATLAS Excel (WL + GL) → Ingestion → EC (LLM) → IC (LLM) → QC (LLM) → Output
    ```
    - **Stage 1 (EC)**: Apply Exclusion Criteria (binary filter) + LLM rationale
    - **Stage 2 (IC)**: Apply Inclusion Criteria (relevance to SE R&S) + LLM justification
    - **Stage 3 (QC)**: Apply Quality Criteria (WL-Q1→Q4 or GL-Q1→Q4, threshold ≥2.0) + LLM justification
    
    Output: EC/IC/QC decisions + LLM-generated structured rationale
    """)
    
    st.caption("APOLLO - Decision Intelligence Layer with LLM Reasoning")