import streamlit as st
import sqlite3
import pandas as pd

from src.core.database import Database
from src.core.workflow import ReviewStage
from src.core.consensus import ConsensusEngine
from src.core.analytics import prepare_kappa


def get_database():
    review_id = st.session_state.get("review_id", 1)
    return Database(review_id=review_id)


def get_consensus_engine():
    db = get_database()
    return ConsensusEngine(db.db_path)


def require_stage(required_stage: ReviewStage) -> bool:
    db = get_database()
    current = ReviewStage(db.get_current_stage())
    if current != required_stage:
        st.error(f"[LOCKED] This section requires '{required_stage.value}' stage")
        st.info(f"Workflow: {db.get_stage_prompt()}")
        return False
    return True


def get_stats():
    db = get_database()
    conn = sqlite3.connect(db.db_path)
    articles_df = pd.read_sql_query("SELECT * FROM articles", conn)
    total_articles = len(articles_df)
    decisions_df = pd.read_sql_query("SELECT * FROM screening_decisions", conn)
    final_df = pd.read_sql_query("SELECT * FROM final_decisions", conn)
    qa_df = pd.read_sql_query("SELECT * FROM quality_assessments", conn)
    conn.close()
    return {
        "total_articles": total_articles,
        "decisions": decisions_df,
        "final": final_df,
        "qa": qa_df
    }


def render_consensus():
    st.header("Reliability & Resolution")
    st.caption("Inter-reviewer agreement and conflict resolution")
    
    db = get_database()
    consensus_engine = get_consensus_engine()
    
    if not require_stage(ReviewStage.CONSENSUS):
        return
    
    stats = get_stats()
    decisions = stats["decisions"]
    total_articles = stats["total_articles"]
    
    if total_articles == 0:
        st.info("No articles available. Please import literature data first.")
        return
    
    st.subheader(" Inter-Rater Reliability (Cohen's Kappa)")
    
    st.markdown('<div class="ais-card">', unsafe_allow_html=True)
    
    if not decisions.empty and len(decisions["reviewer_id"].unique()) >= 2:
        kappa, pivot = prepare_kappa(decisions)
        
        c1, c2, c3 = st.columns(3)
        with c1:
            if kappa is not None:
                st.metric("Cohen's Kappa", f"{kappa:.3f}", help="0.0-0.20: Poor, 0.21-0.40: Fair, 0.41-0.60: Moderate, 0.61-0.80: Good, 0.81-1.00: Excellent")
            else:
                st.metric("Cohen's Kappa", "N/A", help="Need at least 2 reviewers with overlapping articles")
        
        with c2:
            reviewers_count = len(decisions["reviewer_id"].unique())
            st.metric("Reviewers", reviewers_count)
        
        with c3:
            st.metric("Decisions Recorded", len(decisions))
        
        if kappa is not None:
            if kappa < 0.2:
                st.error("[WARN] **Poor agreement** - Reviewers largely disagree. Recommend additional reviewer training and protocol clarification.")
            elif kappa < 0.4:
                st.warning("[WARN] **Fair agreement** - Some conflicts expected. Close monitoring recommended.")
            elif kappa < 0.6:
                st.success("[OK] **Moderate agreement** - Acceptable for systematic reviews.")
            elif kappa < 0.8:
                st.success("[OK] [OK] **Good agreement** - High reliability.")
            else:
                st.success("[OK] [OK] [OK] **Excellent agreement** - Near-perfect consensus.")
            
            with st.expander("📖 Kappa Interpretation Guide"):
                st.markdown("""
                | Kappa Value | Interpretation | Recommendation |
                |-----------|----------------|--------------|
                | < 0.20 | Poor | Additional training, protocol clarification |
                | 0.21-0.40 | Fair | Acceptable, monitor conflicts |
                | 0.41-0.60 | Moderate | Standard for systematic reviews |
                | 0.61-0.80 | Good | High reliability |
                | > 0.80 | Excellent | Near-perfect consensus |
                """)
    else:
        st.warning("Not enough data for kappa calculation. Need at least 2 reviewers with overlapping articles.")
    
    st.divider()
    
    st.subheader("[FLAG] Conflict Resolution")
    
    conflicts = consensus_engine.detect_conflicts()
    
    conn = sqlite3.connect(db.db_path)
    resolved = pd.read_sql_query("SELECT article_id FROM final_decisions", conn)
    resolved_ids = set(resolved["article_id"].tolist()) if not resolved.empty else set()
    conn.close()
    
    total_conflicts = len(conflicts)
    unresolved_count = sum(1 for cid in conflicts["article_id"] if cid not in resolved_ids)
    
    if total_conflicts > 0:
        progress = (total_conflicts - unresolved_count) / total_conflicts if total_conflicts > 0 else 0
        st.progress(progress)
        st.caption(f"Conflict Resolution Progress: {total_conflicts - unresolved_count} of {total_conflicts} resolved ({int(progress*100)}%)")
    
    if conflicts.empty:
        st.success("[PASS] No conflicts detected - all reviewers agree!")
    else:
        st.error(f"Found {total_conflicts} articles with conflicting decisions that need human mediation")
        
        conn = sqlite3.connect(db.db_path)
        
        for _, conflict in conflicts.iterrows():
            article_id = conflict["article_id"]
            
            article = pd.read_sql_query(f"SELECT id, title, abstract, literature_type FROM articles WHERE id = {article_id}", conn).iloc[0]
            
            article_decisions = pd.read_sql_query(f"""
                SELECT reviewer_id, decision, exclusion_reason, criteria_snapshot 
                FROM screening_decisions 
                WHERE article_id = {article_id}
            """, conn)
            
            is_resolved = article_id in resolved_ids
            
            with st.expander(f"{'[PASS]' if is_resolved else '[FLAG]'} Article ID {article_id}: {article['title'][:60]}... ({'RESOLVED' if is_resolved else 'UNRESOLVED'})"):
                st.markdown(f"**📄 Title:** {article['title']}")
                st.caption(f"**Type:** {article['literature_type']}")
                
                if article['abstract']:
                    with st.expander("📝 Abstract"):
                        st.write(article['abstract'][:500] + "..." if len(str(article['abstract'])) > 500 else article['abstract'])
                
                st.markdown("**👥 Reviewer Decisions:**")
                
                cols = st.columns(len(article_decisions))
                for i, (_, row) in enumerate(article_decisions.iterrows()):
                    with cols[i]:
                        decision_emoji = "[PASS]" if row['decision'] == 'include' else "" if row['decision'] == 'exclude' else "[WARN]"
                        st.markdown(f"**{row['reviewer_id']}**: {decision_emoji} {row['decision'].upper()}")
                        
                        if row['decision'] == 'exclude' and row['exclusion_reason']:
                            st.caption(f"Exclusion Reason: {row['exclusion_reason']}")
                        elif row['decision'] == 'include' and row['criteria_snapshot']:
                            st.caption(f"Included Criteria: {row['criteria_snapshot'][:50]}...")
                
                st.divider()
                
                if not is_resolved:
                    st.markdown("**Resolution Form**")
                    
                    with st.form(f"resolve_{article_id}"):
                        c1, c2 = st.columns([1, 2])
                        with c1:
                            final_decision = st.radio(
                                "Final Decision", 
                                ["include", "exclude"],
                                horizontal=True,
                                key=f"fd_{article_id}"
                            )
                        with c2:
                            resolution_notes = st.text_input(
                                "Resolution Notes (Required)", 
                                placeholder="Explain rationale for final decision...",
                                key=f"notes_{article_id}"
                            )
                        
                        col_submit, col_spacer = st.columns([1, 2])
                        with col_submit:
                            submit_resolved = st.form_submit_button(
                                "[PASS] Resolve Conflict",
                                type="primary",
                                width=True
                            )
                        
                        if submit_resolved:
                            if not resolution_notes.strip():
                                st.error("Resolution notes are required before finalizing")
                            else:
                                db.save_final_decision(
                                    article_id,
                                    final_decision,
                                    st.session_state.get("reviewer_id", "Reviewer_1"),
                                    resolution_notes
                                )
                                st.success("Conflict resolved! Final decision saved.")
                                st.rerun()
                else:
                    conn2 = sqlite3.connect(db.db_path)
                    resolution = pd.read_sql_query(f"SELECT * FROM final_decisions WHERE article_id = {article_id}", conn2).iloc[0]
                    conn2.close()
                    
                    st.markdown("**[PASS] Resolved Decision:**")
                    decision_emoji = "[PASS]" if resolution['final_decision'] == 'include' else ""
                    st.markdown(f"**Final Decision:** {decision_emoji} {resolution['final_decision'].upper()}")
                    st.markdown(f"**Resolved By:** {resolution['resolved_by']}")
                    st.markdown(f"**Notes:** {resolution['resolution_notes']}")
        
        conn.close()
    
    st.divider()
    
    st.subheader(" Auto-Consensus")
    st.caption("Automatically finalize unanimous decisions to save time")
    
    conn = sqlite3.connect(db.db_path)
    
    unanimous = pd.read_sql_query("""
        SELECT article_id, GROUP_CONCAT(decision) as decisions
        FROM screening_decisions
        GROUP BY article_id
        HAVING COUNT(DISTINCT decision) = 1
    """, conn)
    
    already_final = pd.read_sql_query("SELECT article_id FROM final_decisions", conn)
    already_final_ids = set(already_final["article_id"].tolist()) if not already_final.empty else set()
    
    candidates = [x for x in unanimous["article_id"] if x not in already_final_ids]
    candidate_count = len(candidates)
    
    conn.close()
    
    col_auto, col_info = st.columns([1, 2])
    
    with col_auto:
        if st.button("[PASS] Auto-finalize Unanimous Decisions", width=True, disabled=candidate_count == 0):
            with st.spinner("Finalizing unanimous decisions..."):
                count = consensus_engine.auto_resolve_consensus(db)
            st.success(f"Auto-resolved {count} articles with unanimous agreement!")
            st.rerun()
    
    with col_info:
        if candidate_count > 0:
            st.info(f"Ready to auto-finalize: {candidate_count} articles where all reviewers agreed")
        else:
            st.success("All unanimous decisions already finalized")
    
    st.caption("This automatically moves articles where ALL reviewers gave the SAME decision to the final decisions table.")