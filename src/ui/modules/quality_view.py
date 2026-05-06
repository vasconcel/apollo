"""
APOLLO Quality Assessment (QC) with LLM Reasoning
Stage 2: Quality Criteria scoring for IC-passed articles
WL-Q1 to WL-Q4 for White Literature
GL-Q1 to GL-Q4 for Grey Literature
Threshold: >= 2.0 (default)
LLM-assisted justification for each score
"""
import streamlit as st
import json
import os


def get_database():
    from src.core.database import Database
    return Database(review_id=st.session_state.get("review_id", 1))


WL_CRITERIA = {
    "WL-Q1": "Are the research aims and the SE R&S context clearly stated?",
    "WL-Q2": "Is the research methodology adequately described and appropriate?",
    "WL-Q3": "Are the findings clearly supported by the collected data?",
    "WL-Q4": "Does the study adequately discuss its limitations or threats to validity?"
}

GL_CRITERIA = {
    "GL-Q1": "Is the author's expertise or organizational context explicitly stated?",
    "GL-Q2": "Is the source of experience transparent (e.g., specific hiring cycle, personal narrative)?",
    "GL-Q3": "Are the claims supported by operational artifacts rather than mere opinion?",
    "GL-Q4": "Does the source provide insights beyond generic employer marketing?"
}

SCORE_OPTIONS = [1.0, 0.5, 0.0]


class QualityEngine:
    def __init__(self, threshold=2.0):
        self.threshold = threshold
    
    def evaluate(self, scores_dict: dict) -> dict:
        total = sum(scores_dict.values())
        decision = "include" if total >= self.threshold else "exclude"
        return {
            "total_score": total,
            "decision": decision,
            "threshold": self.threshold
        }


def render_quality():
    """Quality Assessment: WL-Q1→Q4 and GL-Q1→Q4 scoring with LLM reasoning."""
    from src.core.database import Database
    from src.core.llm_reasoning import generate_qc_rationale
    
    db = get_database()
    reviewer_id = st.session_state.get("reviewer_id", "system")
    quality_engine = QualityEngine(threshold=db.get_config("quality_threshold") or 2.0)
    
    st.header("Quality Assessment (QC)")
    st.caption("Stage 2: Apply quality criteria to IC-passed articles | LLM-Assisted Justification")
    st.info(f"Threshold: >= {quality_engine.threshold} (default)")
    
    llm_available = bool(os.environ.get("GROQ_API_KEY") or os.environ.get("OPENAI_API_KEY"))
    if llm_available:
        st.success("🤖 LLM Reasoning Layer: Active")
    else:
        st.warning("⚠️ LLM not configured. Set GROQ_API_KEY or OPENAI_API_KEY for LLM reasoning.")
    
    ic_passed_articles = db.get_ic_passed_articles()
    
    if not ic_passed_articles:
        st.warning("No articles have passed IC stage yet. Complete Eligibility Evaluation first.")
        return
    
    existing_qa = db.get_quality_assessments_for_articles([a["id"] for a in ic_passed_articles])
    pending_articles = [a for a in ic_passed_articles if a["id"] not in existing_qa]
    
    if not pending_articles:
        st.success("All IC-passed articles have been quality assessed!")
    else:
        st.metric("Pending QC Evaluation", len(pending_articles))
        
        if "current_qc_idx" not in st.session_state:
            st.session_state.current_qc_idx = 0
        
        if st.session_state.current_qc_idx >= len(pending_articles):
            st.session_state.current_qc_idx = 0
        
        article = pending_articles[st.session_state.current_qc_idx]
        
        st.divider()
        st.markdown(f"**Article {st.session_state.current_qc_idx + 1} of {len(pending_articles)}**")
        
        lit_type = article.get("literature_type", "WL")
        criteria = WL_CRITERIA if lit_type == "WL" else GL_CRITERIA
        
        with st.container():
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(f"### {article['title']}")
            with c2:
                badge = "WL" if lit_type == "WL" else "GL"
                st.caption(f"Type: {badge}")
            
            c1, c2 = st.columns(2)
            with c1:
                st.caption(f"Authors: {article.get('authors', 'N/A')[:60]}...")
            with c2:
                st.caption(f"Year: {article.get('year', 'N/A')}")
            
            if article.get("abstract"):
                with st.expander("Abstract", expanded=False):
                    st.write(article["abstract"])
        
        st.divider()
        
        st.subheader(f"Quality Criteria ({lit_type})")
        
        with st.form("qc_form"):
            scores = {}
            for q_key, q_desc in criteria.items():
                col_desc, col_score = st.columns([3, 1])
                with col_desc:
                    st.caption(q_desc)
                with col_score:
                    scores[q_key] = st.radio(
                        "Score",
                        SCORE_OPTIONS,
                        format_func=lambda x: str(x),
                        label_visibility="collapsed",
                        key=f"q_{q_key}",
                        index=1
                    )
                st.divider()
            
            result = quality_engine.evaluate(scores)
            
            c_score, c_decision = st.columns(2)
            with c_score:
                st.metric("Total Score", f"{result['total_score']}/{len(criteria)}")
            with c_decision:
                if result["decision"] == "include":
                    st.metric("Decision", "[PASS] Include", delta="PASS")
                else:
                    st.metric("Decision", "[FAIL] Exclude", delta="FAIL", delta_color="inverse")
            
            col_lm, col_prev, col_next, col_submit = st.columns([2, 1, 1, 2])
            
            with col_lm:
                generate_llm = st.checkbox("🤖 Generate LLM Justification", value=llm_available and True, disabled=not llm_available)
            
            with col_prev:
                if st.button("← Previous", disabled=st.session_state.current_qc_idx == 0, key="qc_prev"):
                    st.session_state.current_qc_idx = max(0, st.session_state.current_qc_idx - 1)
                    st.rerun()
            with col_next:
                if st.button("Skip →", disabled=st.session_state.current_qc_idx >= len(pending_articles) - 1, key="qc_next"):
                    st.session_state.current_qc_idx += 1
                    st.rerun()
            with col_submit:
                submit_qc = st.form_submit_button("💾 Save QC Assessment", type="primary")
            
            if submit_qc:
                llm_rationale = None
                llm_confidence = None
                
                if generate_llm:
                    with st.spinner("🤖 Generating LLM justification..."):
                        rationale = generate_qc_rationale(
                            article_title=article["title"],
                            article_abstract=article.get("abstract", ""),
                            literature_type=lit_type,
                            scores=scores,
                            total_score=result["total_score"],
                            decision=result["decision"],
                            threshold=quality_engine.threshold
                        )
                        llm_rationale = rationale
                        llm_confidence = rationale.get("confidence")
                        
                        with st.expander("🤖 LLM Quality Justification"):
                            st.markdown("**Criteria Justifications:**")
                            for crit, just in rationale.get("criteria_justification", {}).items():
                                st.markdown(f"**{crit}**: Score {just.get('score')}")
                                st.caption(f"Evidence: {just.get('evidence', 'N/A')}")
                                st.caption(f"Reasoning: {just.get('reasoning', 'N/A')}")
                            
                            if rationale.get("strengths"):
                                st.markdown("**Strengths:**")
                                for s in rationale["strengths"]:
                                    st.caption(f"✓ {s}")
                            
                            if rationale.get("weaknesses"):
                                st.markdown("**Weaknesses:**")
                                for w in rationale["weaknesses"]:
                                    st.caption(f"✗ {w}")
                
                db.save_quality_assessment(
                    article_id=article["id"],
                    reviewer_id=reviewer_id,
                    literature_type=lit_type,
                    criteria_scores=scores,
                    total_score=result["total_score"],
                    decision=result["decision"],
                    llm_rationale=llm_rationale,
                    llm_confidence=llm_confidence
                )
                
                if st.session_state.current_qc_idx < len(pending_articles) - 1:
                    st.session_state.current_qc_idx += 1
                else:
                    st.session_state.current_qc_idx = 0
                
                st.success(f"QC Decision saved: {result['decision'].upper()} (Score: {result['total_score']})" + (" + LLM Justification" if generate_llm else ""))
                st.rerun()
    
    st.divider()
    st.subheader("QC Summary")
    
    stats = db.get_stats()
    c_pass, c_fail = st.columns(2)
    with c_pass:
        st.metric("QC Passed", stats["qc_passed"])
    with c_fail:
        st.metric("QC Failed", stats["qc_failed"])
    
    st.caption("APOLLO EC/IC/QC pipeline complete.")