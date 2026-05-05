import streamlit as st
import sqlite3
import pandas as pd

from src.core.database import Database
from src.core.workflow import ReviewStage
from src.core.quality import QualityEngine


def get_database():
    review_id = st.session_state.get("review_id", 1)
    return Database(review_id=review_id)


def get_quality_engine():
    return QualityEngine()


def require_stage(required_stage: ReviewStage) -> bool:
    db = get_database()
    current = ReviewStage(db.get_current_stage())
    if current != required_stage:
        st.error(f"[LOCKED] This section requires '{required_stage.value}' stage")
        st.info(f"Workflow: {db.get_stage_prompt()}")
        return False
    return True


def get_settings():
    from src.core.config_manager import load_config
    config_mgr = load_config()
    return {
        "project_name": config_mgr.get("project_name", "My Research Project"),
        "project_description": config_mgr.get("project_description"),
        "research_questions": config_mgr.get("research_questions"),
        "inclusion_criteria": config_mgr.get("inclusion_criteria"),
        "exclusion_criteria": config_mgr.get("exclusion_criteria"),
        "quality_criteria": config_mgr.get("quality_criteria"),
        "extraction_fields": config_mgr.get("extraction_fields")
    }


def render_quality():
    st.header("🧪 Quality Assessment")
    st.caption("Appraise included articles using quality criteria")
    
    db = get_database()
    quality_engine = get_quality_engine()
    settings = get_settings()
    
    if not require_stage(ReviewStage.EXTRACTION):
        return
    
    conn = sqlite3.connect(db.db_path)
    
    passed_screening = pd.read_sql_query("""
        SELECT a.id, a.title, a.abstract, a.literature_type
        FROM articles a
        JOIN final_decisions f ON a.id = f.article_id
        WHERE f.final_decision = 'include'
    """, conn)
    
    assessed = pd.read_sql_query("""
        SELECT article_id, decision FROM quality_assessments
    """, conn)
    
    conn.close()
    
    if not passed_screening.empty:
        assessed_ids = assessed["article_id"].tolist() if not assessed.empty else []
        ready_for_qc = passed_screening[~passed_screening["id"].isin(assessed_ids)]
        
        if ready_for_qc.empty:
            st.success("[PASS] All included articles have been quality assessed!")
            
            st.subheader(" QC Summary")
            if not assessed.empty:
                qc_passed = len(assessed[assessed["decision"] == "include"])
                qc_failed = len(assessed[assessed["decision"] == "exclude"])
                
                c1, c2 = st.columns(2)
                with c1:
                    st.metric("[PASS] Passed QC", qc_passed)
                with c2:
                    st.metric(" Failed QC", qc_failed)
        else:
            total_ready = len(passed_screening)
            assessed_count = len(passed_screening) - len(ready_for_qc)
            progress = assessed_count / total_ready if total_ready > 0 else 0
            
            with st.container():
                st.markdown('<div class="ais-card">', unsafe_allow_html=True)
                st.progress(progress)
                st.caption(f"QC Progress: {assessed_count}/{total_ready} assessed ({int(progress*100)}%)")
                st.markdown('</div>', unsafe_allow_html=True)
            
            st.divider()
            
            st.subheader("📄 Select Article for Assessment")
            
            article_titles = ready_for_qc["title"].tolist()
            selected_title = st.selectbox("Article", article_titles)
            
            if selected_title:
                art = ready_for_qc[ready_for_qc["title"] == selected_title].iloc[0]
                
                st.markdown('<div class="ais-card">', unsafe_allow_html=True)
                st.markdown(f"### {art['title']}")
                c1, c2 = st.columns(2)
                with c1:
                    lit_badge = "📚 WL" if art['literature_type'] == "WL" else "📥 GL"
                    st.caption(f"{lit_badge} Type: {art['literature_type']}")
                with c2:
                    st.caption(f"🆔 ID: {art['id']}")
                
                if art['abstract']:
                    with st.expander("📝 Abstract", expanded=True):
                        st.write(art['abstract'][:800] + "..." if len(str(art['abstract'])) > 800 else art['abstract'])
                st.markdown('</div>', unsafe_allow_html=True)
                
                st.divider()
                st.markdown(f"### Quality Criteria")
                
                if art['literature_type'] == "WL":
                    q_list = settings["quality_criteria"]["WL"]
                else:
                    q_list = settings["quality_criteria"]["GL"]
                
                st.markdown('<div class="ais-card">', unsafe_allow_html=True)
                
                with st.form("qc_form"):
                    scores = {}
                    for q in q_list:
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.caption(q)
                        with col2:
                            scores[q] = st.radio("", [1.0, 0.5, 0.0], label_visibility="collapsed", key=f"q_{q}")
                    
                    st.divider()
                    result = quality_engine.evaluate(scores)
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        st.metric("Total Score", f"{result['total_score']:.1f}")
                    with c2:
                        if result['decision'] == 'include':
                            st.metric("Decision", "[PASS] Include", delta="PASS")
                        else:
                            st.metric("Decision", " Exclude", delta="FAIL", delta_color="inverse")
                    
                    if st.form_submit_button("💾 Save Assessment", type="primary"):
                        db.save_quality_assessment(
                            art['id'],
                            st.session_state.get("reviewer_id", "Reviewer_1"),
                            scores,
                            result['total_score'],
                            result['decision']
                        )
                        st.success("Quality assessment saved!")
                        st.rerun()
                
                st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("No articles have passed screening yet. Complete screening first.")