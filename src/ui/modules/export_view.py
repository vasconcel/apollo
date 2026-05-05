import streamlit as st
import sqlite3
import pandas as pd
import os

from src.core.database import Database


def get_database():
    review_id = st.session_state.get("review_id", 1)
    return Database(review_id=review_id)


def get_prisma_stats():
    db = get_database()
    conn = sqlite3.connect(db.db_path)
    
    total_imported = pd.read_sql_query("SELECT COUNT(*) as count FROM articles", conn).iloc[0]['count']
    
    screened = pd.read_sql_query("""
        SELECT COUNT(DISTINCT article_id) as count FROM screening_decisions
    """, conn).iloc[0]['count']
    
    excluded_by_ec = pd.read_sql_query("""
        SELECT exclusion_reason, COUNT(*) as count 
        FROM screening_decisions 
        WHERE decision = 'exclude' AND exclusion_reason IS NOT NULL
        GROUP BY exclusion_reason
        ORDER BY count DESC
    """, conn)
    
    included_screening = pd.read_sql_query("""
        SELECT COUNT(DISTINCT article_id) as count 
        FROM screening_decisions 
        WHERE decision = 'include'
    """, conn).iloc[0]['count']
    
    final_included = pd.read_sql_query("""
        SELECT COUNT(*) as count 
        FROM final_decisions 
        WHERE final_decision = 'include'
    """, conn).iloc[0]['count']
    
    final_excluded = pd.read_sql_query("""
        SELECT COUNT(*) as count 
        FROM final_decisions 
        WHERE final_decision = 'exclude'
    """, conn).iloc[0]['count']
    
    qa_passed = pd.read_sql_query("""
        SELECT COUNT(*) as count 
        FROM quality_assessments 
        WHERE decision = 'include'
    """, conn).iloc[0]['count']
    
    qa_failed = pd.read_sql_query("""
        SELECT COUNT(*) as count 
        FROM quality_assessments 
        WHERE decision = 'exclude'
    """, conn).iloc[0]['count']
    
    pending_screening = total_imported - screened
    
    qa_pending = pd.read_sql_query("""
        SELECT COUNT(*) as count 
        FROM final_decisions f
        WHERE f.final_decision = 'include'
        AND NOT EXISTS (
            SELECT 1 FROM quality_assessments q WHERE q.article_id = f.article_id
        )
    """, conn).iloc[0]['count']
    
    conn.close()
    
    return {
        "total_imported": total_imported,
        "screened": screened,
        "pending_screening": pending_screening,
        "included_screening": included_screening,
        "excluded_screening": screened - included_screening,
        "final_included": final_included,
        "final_excluded": final_excluded,
        "qa_passed": qa_passed,
        "qa_failed": qa_failed,
        "qa_pending": qa_pending,
        "excluded_by_ec": excluded_by_ec
    }


def render_export_audit():
    st.header("Reporting & Export")
    st.caption("Quality control, audit trails, and publication-ready exports")
    
    db = get_database()
    
    if "export_data" not in st.session_state:
        st.session_state.export_data = {}
    
    st.subheader("Audit Dashboard")
    st.caption("Validate data integrity before export")
    
    prisma = get_prisma_stats()
    
    try:
        integrity = db.validate_traceability_integrity()
    except Exception as e:
        st.error("Critical validation failure in traceability check")
        st.exception(e)
        st.session_state.integrity = {"is_valid": False, "errors": [str(e)]}
        return
    
    conn = sqlite3.connect(db.db_path)
    
    articles_with_fragments = pd.read_sql_query("""
        SELECT DISTINCT article_id FROM fragments
    """, conn)
    articles_with_fragments_ids = set(articles_with_fragments["article_id"].tolist()) if not articles_with_fragments.empty else set()
    
    included_articles = pd.read_sql_query("""
        SELECT a.id, a.title FROM articles a
        JOIN final_decisions f ON a.id = f.article_id
        WHERE f.final_decision = 'include'
    """, conn)
    
    zero_extraction = []
    if not included_articles.empty:
        for _, row in included_articles.iterrows():
            if row['id'] not in articles_with_fragments_ids:
                zero_extraction.append({"id": row['id'], "title": row['title']})
    
    conn.close()
    
    has_issues = False
    
    if integrity.get("fragments_without_codes"):
        has_issues = True
        fragments_list = integrity["fragments_without_codes"]
        st.error(f"🚨 **Orphaned Fragments**: {len(fragments_list)} fragments have no codes assigned")
        with st.expander("View Orphaned Fragments"):
            for frag in fragments_list[:10]:
                if isinstance(frag, dict):
                    st.caption(f"- ID {frag.get('fragment_id', frag)}: {str(frag.get('fragment_text', ''))[:80]}...")
                else:
                    st.caption(f"- ID {frag}")
            if len(fragments_list) > 10:
                st.caption(f"... and {len(fragments_list) - 10} more")
    
    if integrity.get("codes_without_fragments"):
        st.warning(f"[WARN] **Orphaned Codes**: {len(integrity['codes_without_fragments'])} codes have no fragments linked")
    
    if integrity.get("themes_without_codes"):
        st.warning(f"[WARN] **Orphaned Themes**: {len(integrity['themes_without_codes'])} themes have no codes linked")
    
    if zero_extraction:
        has_issues = True
        st.warning(f"[WARN] **Coverage Gap**: {len(zero_extraction)} included articles have no fragments extracted")
        with st.expander("View Articles Needing Extraction"):
            for art in zero_extraction[:10]:
                st.caption(f"- {art['title'][:60]}...")
            if len(zero_extraction) > 10:
                st.caption(f"... and {len(zero_extraction) - 10} more")
    
    if not has_issues:
        st.success("[PASS] **Audit Passed**: No data integrity issues detected. Your research is ready for export!")
    
    st.divider()
    
    st.subheader("Publication Summary")
    st.caption("Copy-pasteable summary for your paper")
    
    with sqlite3.connect(db.db_path) as conn:
        total_articles = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        wl_count = conn.execute("SELECT COUNT(*) FROM articles WHERE literature_type = 'WL'").fetchone()[0]
        gl_count = conn.execute("SELECT COUNT(*) FROM articles WHERE literature_type = 'GL'").fetchone()[0]
        final_included = conn.execute("SELECT COUNT(*) FROM final_decisions WHERE final_decision = 'include'").fetchone()[0]
        themes_count = conn.execute("SELECT COUNT(*) FROM themes").fetchone()[0]
        codes_count = conn.execute("SELECT COUNT(*) FROM codes").fetchone()[0]
        fragments_count = conn.execute("SELECT COUNT(*) FROM fragments").fetchone()[0]
    
    summary_text = f"""This study analyzed {total_articles} articles ({wl_count} White Literature, {gl_count} Grey Literature). After systematic screening and quality assessment, {final_included} articles were included for analysis. The thematic synthesis process resulted in {themes_count} themes and {codes_count} unique codes, supported by {fragments_count} evidence fragments extracted from the primary sources."""
    
    st.text_area("Study Summary (for paper)", value=summary_text, height=100)
    
    st.caption("Copy the text above for use in your manuscript")
    
    st.divider()
    
    st.subheader("X-Marker Evidence Presence Matrix")
    st.caption("Track concept presence across sources (Evidence Cross-Tabulation)")
    
    with st.expander("Manage Concepts", expanded=False):
        new_concept = st.text_input("New Concept Name")
        concept_desc = st.text_area("Description")
        
        col_add, col_spacer = st.columns([1, 1])
        with col_add:
            add_clicked = st.button("➕ Add Concept", type="primary")
        
        if add_clicked and new_concept:
            try:
                db.create_concept(new_concept, concept_desc)
                st.success(f"Concept '{new_concept}' created")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to add concept: {str(e)}")
        
        concepts = db.get_concepts()
    
    if not concepts:
        st.info("No concepts defined. Create concepts above to track evidence presence.")
    else:
        st.markdown("#### Mark Presence")
        
        articles = pd.read_sql_query("""
            SELECT id, title, literature_type FROM articles 
            WHERE screening_status IN ('included', 'final_included')
        """, sqlite3.connect(db.db_path))
        
        if not articles.empty:
            selected_article = st.selectbox("Select Article", articles["id"], 
                                       format_func=lambda x: articles[articles["id"]==x]["title"].values[0][:50])
            
            current_marks = db.get_concept_presence(selected_article)
            
            st.caption(f"Checking presence for: {articles[articles['id']==selected_article]['title'].values[0][:60]}...")
            
            cols = st.columns(min(len(concepts), 4))
            for i, concept in enumerate(concepts):
                with cols[i % 4]:
                    is_checked = current_marks.get(concept[1], False)
                    if st.checkbox(concept[1], value=is_checked, key=f"mark_{selected_article}_{concept[0]}"):
                        try:
                            db.mark_concept_presence(selected_article, concept[0], True)
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
                    else:
                        try:
                            db.mark_concept_presence(selected_article, concept[0], False)
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
    
    st.divider()
    
    st.markdown("#### Concept Frequency")
    freq = db.compute_concept_frequency()
    if freq:
        freq_df = pd.DataFrame(freq)
        if not freq_df.empty:
            st.dataframe(freq_df, use_container_width=True)
    
    st.divider()
    
    st.markdown("#### X-Marker Matrix")
    matrix = db.get_X_marker_matrix()
    if not matrix.empty:
        st.dataframe(matrix, use_container_width=True)
        
        try:
            csv = matrix.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Download Matrix (.csv)",
                data=csv,
                file_name="x_marker_matrix.csv",
                mime="text/csv"
            )
        except Exception as e:
            st.error(f"Failed to generate CSV: {str(e)}")
    else:
        st.info("Mark concept presence above to generate matrix")
    
    st.divider()
    
    st.subheader("Publication-Ready Export")
    st.caption("Generate and download the complete research package")
    
    col_exp, col_status = st.columns([1, 1])
    
    with col_exp:
        generate_export = st.button(
            "📦 Generate Package",
            type="primary"
        )
    
    if generate_export:
        with st.spinner("Generating export files..."):
            try:
                export_dir = "research_export"
                os.makedirs(export_dir, exist_ok=True)
                
                conn = sqlite3.connect(db.db_path)
                
                articles_df = pd.read_sql_query("SELECT * FROM articles", conn)
                articles_df.to_csv(f"{export_dir}/articles.csv", index=False)
                
                decisions_df = pd.read_sql_query("SELECT * FROM screening_decisions", conn)
                decisions_df.to_csv(f"{export_dir}/screening_decisions.csv", index=False)
                
                final_df = pd.read_sql_query("SELECT * FROM final_decisions", conn)
                final_df.to_csv(f"{export_dir}/final_decisions.csv", index=False)
                
                qa_df = pd.read_sql_query("SELECT * FROM quality_assessments", conn)
                qa_df.to_csv(f"{export_dir}/quality_assessments.csv", index=False)
                
                fragments_df = pd.read_sql_query("SELECT * FROM fragments", conn)
                fragments_df.to_csv(f"{export_dir}/fragments.csv", index=False)
                
                codes_df = pd.read_sql_query("SELECT * FROM codes", conn)
                codes_df.to_csv(f"{export_dir}/codes.csv", index=False)
                
                themes_df = pd.read_sql_query("SELECT * FROM themes", conn)
                themes_df.to_csv(f"{export_dir}/themes.csv", index=False)
                
                conn.close()
                
                import zipfile
                with zipfile.ZipFile("research_package.zip", "w") as zipf:
                    for root, dirs, files in os.walk(export_dir):
                        for file in files:
                            zipf.write(os.path.join(root, file), file)
                
                with open("research_package.zip", "rb") as f:
                    st.download_button(
                        "📥 Download Package (.zip)",
                        data=f.read(),
                        file_name="research_package.zip",
                        mime="application/zip"
                    )
                
                st.success("Export package generated!")
            except Exception as e:
                st.error(f"Export failed: {str(e)}")