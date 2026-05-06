import streamlit as st
import pandas as pd
import sqlite3
import os
import zipfile


def render_export_audit_view():
    from src.core.database import Database
    
    @st.cache_resource
    def get_db():
        return Database(review_id=st.session_state.get("review_id", 1))
    
    db = get_db()
    
    st.header("Reporting & Export")
    st.caption("Quality control, audit trails, and publication-ready exports")
    
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
                
                export_results = db.export_all_research_artifacts(export_dir)
                
                st.session_state.export_data = {
                    "success": True,
                    "results": export_results,
                    "path": export_dir
                }
                st.rerun()
                
            except Exception as e:
                st.error(f"Export failed: {str(e)}")
    
    if st.session_state.get("export_data", {}).get("success"):
        export_results = st.session_state["export_data"]["results"]
        export_path = st.session_state["export_data"]["path"]
        
        with col_status:
            st.success(f"[PASS] Export complete! Generated {sum(export_results.values())} files")
        
        st.divider()
        
        st.markdown("### 📥 Download Export Files")
        
        export_files = {
            "traceability_matrix.csv": "Full traceability: Theme → Code → Fragment → Source",
            "fragments_with_sources.csv": "All evidence fragments with source metadata",
            "codes.csv": "Codebook with RQ associations",
            "themes.csv": "Theme definitions and RQ mappings"
        }
        
        for filename, description in export_files.items():
            filepath = os.path.join(export_path, filename)
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        file_content = f.read()
                    
                    col_dl, col_desc = st.columns([1, 2])
                    with col_dl:
                        st.download_button(
                            f"📥 {filename}",
                            data=file_content,
                            file_name=filename,
                            mime="text/csv",
                            width=True,
                            key=f"dl_{filename}"
                        )
                    with col_desc:
                        st.caption(description)
                except Exception as e:
                    st.warning(f"Could not load {filename}: {str(e)}")
        
        st.divider()
        
        st.markdown("###  Export Statistics")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Themes", export_results.get("themes", 0))
        with c2:
            st.metric("Codes", export_results.get("codes", 0))
        with c3:
            st.metric("Fragments", export_results.get("fragments_with_sources", 0))
        with c4:
            st.metric("Matrix Rows", export_results.get("traceability_matrix", 0))
        
        zip_path = f"{export_path}_package.zip"
        
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for filename in export_files.keys():
                    filepath = os.path.join(export_path, filename)
                    if os.path.exists(filepath):
                        zipf.write(filepath, filename)
            
            with open(zip_path, 'rb') as f:
                zip_data = f.read()
            
            st.divider()
            col_zip, col_spacer = st.columns([1, 1])
            with col_zip:
                st.download_button(
                    "📦 Download Full Replication Package (.zip)",
                    data=zip_data,
                    file_name="aims_research_package.zip",
                    mime="application/zip",
                    width=True
                )
        except Exception as e:
            st.warning(f"Could not create ZIP package: {str(e)}")
    else:
        with col_status:
            st.info("Click 'Generate Full Research Package' to create export files")
    
    st.divider()
    
    st.subheader("💻 System Health")
    
    db_healthy = os.path.exists(db.db_path)
    db_size = os.path.getsize(db.db_path) / 1024 if db_healthy else 0
    
    import os as os_module
    api_key = os_module.environ.get("GROQ_API_KEY")
    if not api_key:
        try:
            api_key = st.secrets.get("GROQ_API_KEY", "")
        except:
            pass
    api_healthy = bool(api_key)
    
    c1, c2 = st.columns(2)
    with c1:
        if db_healthy:
            st.success(f"[PASS] Database Connected ({db_size:.1f} KB)")
        else:
            st.error(" Database Not Found")
    with c2:
        if api_healthy:
            st.success("[PASS] Groq API Ready")
        else:
            st.warning("[WARN] Groq API Not Configured")
            st.caption("Configure GROQ_API_KEY environment variable for AI features")
    
    st.divider()
    
    with st.expander("Database Information"):
        st.markdown(f"**Database Path:** `{db.db_path}`")
        st.markdown(f"**Database Size:** {os.path.getsize(db.db_path) / 1024:.1f} KB" if os.path.exists(db.db_path) else "N/A")
    
    st.divider()
    
    st.subheader("Danger Zone")
    st.warning("These actions cannot be undone. Use with caution.")
    
    col_danger, col_check = st.columns([1, 1])
    with col_danger:
        reset_clicked = st.button("RESET Reset Database", type="primary")
    
    with col_check:
        confirm = st.checkbox("I understand this will delete ALL data")
    
    if reset_clicked and confirm:
        try:
            db_path = db.db_path
            del db
            
            if os.path.exists(db_path):
                os.remove(db_path)
                st.success("Database reset complete. Refresh the page to reinitialize.")
            else:
                st.error("Database file not found")
        except Exception as e:
            st.error(f"Reset failed: {e}")
    
    col_danger, col_confirm = st.columns([1, 1])
    with col_danger:
        st.caption("RESET This will permanently delete all data")
    with col_confirm:
        st.caption("Checked Required before action")


def get_prisma_stats():
    """Calculate PRISMA Flow Diagram statistics from database."""
    from src.core.database import Database
    
    @st.cache_resource
    def get_db():
        return Database(review_id=st.session_state.get("review_id", 1))
    
    db = get_db()
    review_id = st.session_state.get("review_id", 1)
    return db.get_prisma_stats(review_id)