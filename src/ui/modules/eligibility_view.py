"""
APOLLO Eligibility Evaluation (EC + IC) with LLM Reasoning
Stage 1: Exclusion Criteria (EC) - Binary filtering with LLM explanations
Stage 2: Inclusion Criteria (IC) - Relevance to SE R&S domain with LLM justification
"""
import streamlit as st
import json
import os


def get_database():
    from src.core.database import Database
    return Database(review_id=st.session_state.get("review_id", 1))


def get_default_ec():
    return {
        "EC-1": "Not empirical software engineering research",
        "EC-2": "Published before 2015",
        "EC-3": "Not peer-reviewed (for WL)",
        "EC-4": "Duplicate publication"
    }


def get_default_ic():
    return {
        "IC-1": "Addresses recruitment/selection practices in software organizations",
        "IC-2": "Reports empirical findings (qualitative or quantitative)",
        "IC-3": "Focuses on software industry context"
    }


def render_eligibility():
    """Eligibility Evaluation: EC → IC pipeline with LLM reasoning support."""
    from src.core.database import Database
    from src.core.llm_reasoning import generate_ec_rationale, generate_ic_rationale, detect_ambiguity
    
    db = get_database()
    reviewer_id = st.session_state.get("reviewer_id", "system")
    
    st.header("Eligibility Evaluation")
    st.caption("Stage 1: EC (Exclusion) → Stage 2: IC (Inclusion) | LLM-Assisted Reasoning")
    
    llm_available = bool(os.environ.get("GROQ_API_KEY") or os.environ.get("OPENAI_API_KEY"))
    if llm_available:
        st.success("🤖 LLM Reasoning Layer: Active")
    else:
        st.warning("⚠️ LLM not configured. Set GROQ_API_KEY or OPENAI_API_KEY for LLM reasoning.")
    
    tab_ec, tab_ic = st.tabs(["Stage 1: Exclusion Criteria (EC)", "Stage 2: Inclusion Criteria (IC)"])
    
    with tab_ec:
        st.subheader("Exclusion Criteria")
        st.markdown("Apply binary filtering to remove invalid studies")
        
        pending_ec = db.get_pending_articles_for_eligibility("EC", reviewer_id)
        
        if not pending_ec:
            st.success("All articles have been evaluated for EC")
        else:
            st.metric("Pending EC Evaluation", len(pending_ec))
            
            if "current_ec_idx" not in st.session_state:
                st.session_state.current_ec_idx = 0
            
            if st.session_state.current_ec_idx >= len(pending_ec):
                st.session_state.current_ec_idx = 0
            
            article = pending_ec[st.session_state.current_ec_idx]
            
            st.divider()
            st.markdown(f"**Article {st.session_state.current_ec_idx + 1} of {len(pending_ec)}**")
            
            with st.container():
                st.markdown(f"### {article['title']}")
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.caption(f"Authors: {article.get('authors', 'N/A')[:50]}...")
                with c2:
                    st.caption(f"Year: {article.get('year', 'N/A')}")
                with c3:
                    lit_badge = "WL" if article.get("literature_type") == "WL" else "GL"
                    st.caption(f"Type: {lit_badge}")
                
                if article.get("abstract"):
                    with st.expander("Abstract", expanded=False):
                        st.write(article["abstract"])
            
            st.divider()
            
            ec_criteria = get_default_ec()
            selected_ec = None
            
            with st.form("ec_form"):
                decision = st.radio(
                    "EC Decision",
                    ["include", "exclude"],
                    format_func=lambda x: "[PASS] Include" if x == "include" else "[FAIL] Exclude",
                    horizontal=True
                )
                
                if decision == "exclude":
                    st.markdown("**Exclusion Reason (required):**")
                    selected_ec = st.selectbox(
                        "Select EC Criterion",
                        [""] + list(ec_criteria.keys()),
                        format_func=lambda x: f"{x}: {ec_criteria[x]}" if x else x
                    )
                
                col_lm, col_prev, col_next, col_submit = st.columns([2, 1, 1, 2])
                
                with col_lm:
                    generate_llm = st.checkbox("🤖 Generate LLM Rationale", value=llm_available and True, disabled=not llm_available)
                
                with col_prev:
                    if st.button("← Previous", disabled=st.session_state.current_ec_idx == 0):
                        st.session_state.current_ec_idx = max(0, st.session_state.current_ec_idx - 1)
                        st.rerun()
                with col_next:
                    if st.button("Skip →", disabled=st.session_state.current_ec_idx >= len(pending_ec) - 1):
                        st.session_state.current_ec_idx += 1
                        st.rerun()
                with col_submit:
                    submit_ec = st.form_submit_button("💾 Save EC Decision", type="primary")
                
                if submit_ec:
                    if decision == "exclude" and not selected_ec:
                        st.error("Exclusion requires selecting an EC criterion")
                    else:
                        reason = ec_criteria.get(selected_ec, "") if selected_ec else None
                        llm_rationale = None
                        llm_confidence = None
                        
                        if generate_llm:
                            with st.spinner("🤖 Generating LLM reasoning..."):
                                rationale = generate_ec_rationale(
                                    article_title=article["title"],
                                    article_abstract=article.get("abstract", ""),
                                    year=article.get("year"),
                                    literature_type=article.get("literature_type", "WL"),
                                    ec_decision=decision,
                                    ec_reason=reason,
                                    criteria=ec_criteria
                                )
                                llm_rationale = rationale
                                llm_confidence = rationale.get("confidence")
                                
                                if detect_ambiguity(rationale):
                                    st.warning("🤖 LLM detected ambiguity in decision")
                                
                                with st.expander("🤖 LLM Reasoning Trace"):
                                    st.json(rationale)
                        
                        db.save_eligibility_decision(
                            article_id=article["id"],
                            reviewer_id=reviewer_id,
                            stage="EC",
                            decision=decision,
                            reason=reason,
                            criteria_snapshot=json.dumps(ec_criteria),
                            llm_rationale=llm_rationale,
                            llm_confidence=llm_confidence
                        )
                        
                        if st.session_state.current_ec_idx < len(pending_ec) - 1:
                            st.session_state.current_ec_idx += 1
                        else:
                            st.session_state.current_ec_idx = 0
                        
                        st.success(f"EC Decision saved: {decision.upper()}" + (" + LLM Rationale" if generate_llm else ""))
                        st.rerun()
    
    with tab_ic:
        st.subheader("Inclusion Criteria")
        st.markdown("Apply relevance filtering to SE R&S domain")
        
        pending_ic = db.get_pending_articles_for_eligibility("IC", reviewer_id)
        
        if not pending_ic:
            st.success("All EC-passed articles have been evaluated for IC")
        else:
            st.metric("Pending IC Evaluation", len(pending_ic))
            
            if "current_ic_idx" not in st.session_state:
                st.session_state.current_ic_idx = 0
            
            if st.session_state.current_ic_idx >= len(pending_ic):
                st.session_state.current_ic_idx = 0
            
            article = pending_ic[st.session_state.current_ic_idx]
            
            st.divider()
            st.markdown(f"**Article {st.session_state.current_ic_idx + 1} of {len(pending_ic)}**")
            
            with st.container():
                st.markdown(f"### {article['title']}")
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.caption(f"Authors: {article.get('authors', 'N/A')[:50]}...")
                with c2:
                    st.caption(f"Year: {article.get('year', 'N/A')}")
                with c3:
                    lit_badge = "WL" if article.get("literature_type") == "WL" else "GL"
                    st.caption(f"Type: {lit_badge}")
                
                if article.get("abstract"):
                    with st.expander("Abstract", expanded=False):
                        st.write(article["abstract"])
            
            st.divider()
            
            ic_criteria = get_default_ic()
            
            with st.form("ic_form"):
                decision = st.radio(
                    "IC Decision",
                    ["include", "exclude"],
                    format_func=lambda x: "[PASS] Include" if x == "include" else "[FAIL] Exclude",
                    horizontal=True
                )
                
                selected_ic = {}
                if decision == "include":
                    st.markdown("**Inclusion Criteria Met:**")
                    for ic_key, ic_desc in ic_criteria.items():
                        selected_ic[ic_key] = st.checkbox(f"{ic_key}: {ic_desc}")
                
                col_lm, col_prev, col_next, col_submit = st.columns([2, 1, 1, 2])
                
                with col_lm:
                    generate_llm = st.checkbox("🤖 Generate LLM Rationale", value=llm_available and True, disabled=not llm_available)
                
                with col_prev:
                    if st.button("← Previous", disabled=st.session_state.current_ic_idx == 0, key="ic_prev"):
                        st.session_state.current_ic_idx = max(0, st.session_state.current_ic_idx - 1)
                        st.rerun()
                with col_next:
                    if st.button("Skip →", disabled=st.session_state.current_ic_idx >= len(pending_ic) - 1, key="ic_next"):
                        st.session_state.current_ic_idx += 1
                        st.rerun()
                with col_submit:
                    submit_ic = st.form_submit_button("💾 Save IC Decision", type="primary")
                
                if submit_ic:
                    if decision == "include" and not any(selected_ic.values()):
                        st.error("Inclusion requires at least one IC criterion to be met")
                    else:
                        met_criteria = [k for k, v in selected_ic.items() if v]
                        reason = "; ".join(met_criteria) if met_criteria else "No criteria met"
                        
                        llm_rationale = None
                        llm_confidence = None
                        
                        if generate_llm:
                            with st.spinner("🤖 Generating LLM reasoning..."):
                                rationale = generate_ic_rationale(
                                    article_title=article["title"],
                                    article_abstract=article.get("abstract", ""),
                                    year=article.get("year"),
                                    literature_type=article.get("literature_type", "WL"),
                                    ic_decision=decision,
                                    ic_reason=reason,
                                    criteria=ic_criteria,
                                    ec_passed=True
                                )
                                llm_rationale = rationale
                                llm_confidence = rationale.get("confidence")
                                
                                if detect_ambiguity(rationale):
                                    st.warning("🤖 LLM detected ambiguity in decision")
                                
                                with st.expander("🤖 LLM Reasoning Trace"):
                                    st.json(rationale)
                        
                        db.save_eligibility_decision(
                            article_id=article["id"],
                            reviewer_id=reviewer_id,
                            stage="IC",
                            decision=decision,
                            reason=reason,
                            criteria_snapshot=json.dumps(ic_criteria),
                            llm_rationale=llm_rationale,
                            llm_confidence=llm_confidence
                        )
                        
                        if st.session_state.current_ic_idx < len(pending_ic) - 1:
                            st.session_state.current_ic_idx += 1
                        else:
                            st.session_state.current_ic_idx = 0
                        
                        st.success(f"IC Decision saved: {decision.upper()}" + (" + LLM Rationale" if generate_llm else ""))
                        st.rerun()
    
    st.divider()
    st.subheader("Eligibility Summary")
    
    stats = db.get_stats()
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("Total", stats["total_articles"])
    with c2:
        st.metric("EC Passed", stats["ec_passed"])
    with c3:
        st.metric("EC Excluded", stats["ec_excluded"])
    with c4:
        st.metric("IC Passed", stats["ic_passed"])
    with c5:
        st.metric("IC Excluded", stats["ic_excluded"])
    
    st.caption("Next: Proceed to Quality Assessment (QC)")