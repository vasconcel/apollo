import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from src.core.workflow import ReviewStage
from src.core.ai_handler import generate_theme_synthesis


def render_synthesis_view():
    from src.core.database import Database
    
    @st.cache_resource
    def get_db():
        return Database(review_id=st.session_state.get("review_id", 1))
    
    db = get_db()
    review_id = st.session_state.get("review_id", 1)
    
    st.header("🧩 Thematic Synthesis Workspace")
    st.caption("Interactive qualitative analysis: Open Coding → Thematic Organization → Traceability")
    
    if not require_stage(ReviewStage.SYNTHESIS, db):
        return
    
    try:
        integrity = db.validate_traceability_integrity()
    except Exception as e:
        st.error("Critical validation failure")
        st.exception(e)
        integrity = {"is_valid": False, "errors": [str(e)]}
    
    if not integrity.get("is_valid"):
        st.error("[WARN] Traceability integrity issues detected:")
        issues = integrity.get("issues", [])
        for issue in issues[:5]:
            st.caption(f"- {issue}")
        st.warning("Fix issues before proceeding. All themes → codes → fragments → sources must be connected.")
    
    if "selected_rq" not in st.session_state:
        st.session_state.selected_rq = "RQ1"
    
    tab1, tab2, tab3 = st.tabs(["1.  Open Coding", "2.  Thematic Organization", "3. 🔗 Traceability Matrix"])
    
    rq_codes = ["RQ1", "RQ2", "RQ3", "RQ4", "RQ5"]
    
    with tab1:
        st.subheader("Open Coding: Link Fragments to Codes")
        
        selected_rq = st.selectbox("Select Research Question", rq_codes, index=rq_codes.index(st.session_state.selected_rq), key="rq_selector")
        st.session_state.selected_rq = selected_rq
        
        fragments = db.get_fragments_by_rq(selected_rq, review_id)
        
        if not fragments:
            st.info(f"No fragments extracted for {selected_rq} yet. Go to Extraction to add fragments.")
        else:
            frag_data = []
            for frag in fragments:
                frag_id, art_id, rq, text, category, reviewer, page, created, art_title, lit_type = frag
                codes = db.get_codes_for_fragment(frag_id)
                code_labels = ", ".join([c[1] for c in codes]) if codes else "—"
                frag_data.append({
                    "ID": frag_id,
                    "Article": art_title[:50] + "..." if len(art_title) > 50 else art_title,
                    "Type": lit_type,
                    "Fragment": text[:100] + "..." if len(text) > 100 else text,
                    "Codes": code_labels
                })
            
            frag_df = pd.DataFrame(frag_data)
            st.dataframe(frag_df, use_container_width=True, height=300)
            
            st.divider()
            
            st.markdown("### 🔗 Link Fragment to Code")
            
            col1, col2 = st.columns(2)
            
            with col1:
                frag_options = {f"ID {f[0]}: {f[3][:60]}...": f[0] for f in fragments}
                selected_frag_key = st.selectbox("Select Fragment", list(frag_options.keys()))
                selected_frag_id = frag_options[selected_frag_key]
                
                selected_frag = next((f for f in fragments if f[0] == selected_frag_id), None)
                if selected_frag:
                    with st.expander("Fragment Details"):
                        st.write(selected_frag[3])
                        st.caption(f"Source: {selected_frag[8]} ({selected_frag[9]})")
                
                existing_codes = db.get_codes_for_fragment(selected_frag_id)
                if existing_codes:
                    st.markdown("**Already coded with:**")
                    for code in existing_codes:
                        st.caption(f"- {code[1]}")
            
            with col2:
                existing_codes_rq = db.get_codes_by_rq(selected_rq, review_id)
                
                if existing_codes_rq:
                    code_options = {c[1]: c[0] for c in existing_codes_rq}
                    
                    code_choice = st.radio("Code Action", ["Use Existing Code", "Create New Code"])
                    
                    if code_choice == "Use Existing Code":
                        selected_code_label = st.selectbox("Select Existing Code", list(code_options.keys()))
                        selected_code_id = code_options[selected_code_label]
                        code_desc = next((c[2] for c in existing_codes_rq if c[1] == selected_code_label), "")
                        
                        if code_desc:
                            st.caption(f"Description: {code_desc}")
                        
                        if st.button("🔗 Link to Fragment", width=True):
                            try:
                                db.link_fragment_code(selected_frag_id, selected_code_id, st.session_state.reviewer_id)
                                st.success(f"Linked fragment to code: {selected_code_label}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Link failed: {e}")
                    
                    else:
                        new_code_label = st.text_input("New Code Label", placeholder="e.g., 'Remote Hiring Challenge'")
                        new_code_desc = st.text_area("Code Description (optional)", placeholder="Brief description of what this code represents")
                        
                        if st.button("➕ Create & Link", width=True):
                            if not new_code_label.strip():
                                st.error("Code label is required")
                            else:
                                try:
                                    new_code_id = db.create_code(
                                        new_code_label.strip(),
                                        selected_rq,
                                        st.session_state.reviewer_id,
                                        new_code_desc if new_code_desc.strip() else None
                                    )
                                    db.link_fragment_code(selected_frag_id, new_code_id, st.session_state.reviewer_id)
                                    st.success(f"Created and linked code: {new_code_label}")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Failed: {e}")
                else:
                    st.info(f"No codes exist for {selected_rq} yet. Create one!")
                    new_code_label = st.text_input("New Code Label", placeholder="e.g., 'Remote Hiring Challenge'")
                    new_code_desc = st.text_area("Code Description (optional)", placeholder="Brief description")
                    
                    if st.button("➕ Create Code", width=True):
                        if not new_code_label.strip():
                            st.error("Code label is required")
                        else:
                            try:
                                new_code_id = db.create_code(
                                    new_code_label.strip(),
                                    selected_rq,
                                    st.session_state.reviewer_id,
                                    new_code_desc if new_code_desc.strip() else None
                                )
                                db.link_fragment_code(selected_frag_id, new_code_id, st.session_state.reviewer_id)
                                st.success(f"Created code and linked to fragment!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed: {e}")
    
    with tab2:
        st.subheader("Thematic Organization: Manage Codes & Themes")
        
        col_theme, col_codes = st.columns([1, 1])
        
        with col_theme:
            st.markdown("####  Theme Management")
            
            with st.expander("➕ Create New Theme", expanded=False):
                with st.form("create_theme_form"):
                    new_theme_code = st.text_input("Theme Code", placeholder="e.g., THEME-1")
                    new_theme_label = st.text_input("Theme Label", placeholder="e.g., Hiring Challenges")
                    new_theme_rq = st.selectbox("Research Question", rq_codes)
                    new_theme_desc = st.text_area("Description (optional)")
                    
                    if st.form_submit_button("Create Theme"):
                        if not new_theme_code.strip() or not new_theme_label.strip():
                            st.error("Theme code and label are required")
                        else:
                            try:
                                theme_id = db.create_theme(
                                    new_theme_code.strip().upper(),
                                    new_theme_label.strip(),
                                    new_theme_rq,
                                    new_theme_desc.strip() if new_theme_desc.strip() else None
                                )
                                st.success(f"Theme created: {new_theme_label}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed: {e}")
            
            st.markdown("**Existing Themes:**")
            for rq in rq_codes:
                themes = db.get_themes_by_rq(rq, review_id)
                if themes:
                    with st.expander(f"{rq} Themes ({len(themes)})"):
                        for t in themes:
                            st.markdown(f"**{t[1]}:** {t[2]}")
                            if t[3]:
                                st.caption(t[3])
        
        with col_codes:
            st.markdown("#### 🔗 Link Codes to Themes")
            
            all_codes = []
            for rq in rq_codes:
                codes = db.get_codes_by_rq(rq, review_id)
                all_codes.extend(codes)
            
            if not all_codes:
                st.info("No codes created yet. Go to Open Coding tab to create codes.")
            else:
                code_options = {f"{c[1]} ({c[3]})": c[0] for c in all_codes}
                selected_code_key = st.selectbox("Select Code", list(code_options.keys()))
                selected_code_id = code_options[selected_code_key]
                
                code_rq = next((c[3] for c in all_codes if c[0] == selected_code_id), None)
                code_label = next((c[1] for c in all_codes if c[0] == selected_code_id), "")
                
                if code_rq:
                    themes_rq = db.get_themes_by_rq(code_rq, review_id)
                    
                    if not themes_rq:
                        st.warning(f"No themes exist for {code_rq}. Create a theme first.")
                    else:
                        theme_options = {f"{t[1]}: {t[2]}": t[0] for t in themes_rq}
                        
                        linked_themes = db.get_themes_for_code(selected_code_id)
                        linked_theme_ids = [t[0] for t in linked_themes]
                        
                        st.markdown(f"**Code:** {code_label}")
                        st.caption(f"RQ: {code_rq}")
                        
                        if linked_themes:
                            st.markdown("**Currently linked to:**")
                            for lt in linked_themes:
                                st.caption(f"- {lt[1]}: {lt[2]}")
                        
                        st.markdown("**Link to Theme:**")
                        selected_theme_label = st.selectbox("Select Theme", list(theme_options.keys()))
                        selected_theme_id = theme_options[selected_theme_label]
                        
                        if selected_theme_id in linked_theme_ids:
                            st.info("This code is already linked to this theme")
                        else:
                            if st.button("🔗 Link Code to Theme", width=True):
                                try:
                                    db.link_code_theme(selected_code_id, selected_theme_id, st.session_state.reviewer_id)
                                    st.success("Code linked to theme!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Link failed: {e}")
    
    with tab3:
        st.subheader("🔗 Traceability Matrix: Theme → Codes → Fragments → Sources")
        
        all_themes = []
        for rq in rq_codes:
            themes = db.get_themes_by_rq(rq, review_id)
            all_themes.extend(themes)
        
        if not all_themes:
            st.warning("No themes created yet. Go to Thematic Organization to create themes.")
        else:
            theme_options = {f"{t[1]}: {t[2]} ({t[3]})": t[0] for t in all_themes}
            selected_theme_label = st.selectbox("Select Theme to Explore", list(theme_options.keys()))
            selected_theme_id = theme_options[selected_theme_label]
            
            st.divider()
            
            with st.expander(" Traceability Inspector", expanded=True):
                lineage = db.get_theme_lineage(selected_theme_id)
                
                if lineage["theme"]:
                    st.markdown(f"### 📂 {lineage['theme']['label']}")
                    st.caption(f"Synthesis: {lineage['theme']['synthesis'] or 'No AI synthesis yet'}")
                    
                    st.markdown("#### Codes Linked")
                    if lineage["codes"]:
                        for code in lineage["codes"]:
                            st.markdown(f"- **{code['label']}**: {code['description'] or 'No description'}")
                    else:
                        st.warning("No codes linked")
                    
                    st.markdown("#### Fragments Linked")
                    if lineage["fragments"]:
                        st.markdown(f"_{len(lineage['fragments'])} fragments from {len(lineage['sources'])} sources_")
                    else:
                        st.warning("No fragments linked")
                    
                    st.markdown("#### Evidence Sources")
                    if lineage["sources"]:
                        for src in lineage["sources"]:
                            st.caption(f"- {src['title'][:50]}... ({src['year']}) by {src['authors'][:30]}")
                    else:
                        st.warning("No sources traced")
                    
                    st.divider()
                    st.metric("Traceability Score", f"{len(lineage['fragments'])} frags / {len(lineage['sources'])} sources")
            
            selected_theme = next((t for t in all_themes if t[0] == selected_theme_id), None)
            
            st.divider()
            
            if selected_theme:
                st.markdown(f"### Theme: {selected_theme[1]} - {selected_theme[2]}")
                
                dist = db.compute_theme_source_distribution(selected_theme_id)
                classification = db.classify_theme(selected_theme_id)
                
                col_wl, col_gl, col_class = st.columns(3)
                with col_wl:
                    st.metric("WL Sources", dist["wl_count"])
                with col_gl:
                    st.metric("GL Sources", dist["gl_count"])
                with col_class:
                    if classification == "convergent":
                        st.success(f"Classification: Convergent")
                    elif classification == "academic_only":
                        st.warning(f"Classification: Academic Only")
                    elif classification == "practitioner_only":
                        st.info(f"Classification: Practitioner Only")
                    else:
                        st.error(f"Classification: Unclassified")
                
                if dist["wl_count"] > 0 and dist["gl_count"] > 0:
                    st.info("Triangulation opportunity: Both WL and GL sources present")
                elif dist["wl_count"] == 0 and dist["gl_count"] > 0:
                    st.warning("Gap: No academic literature evidence")
                elif dist["wl_count"] > 0 and dist["gl_count"] == 0:
                    st.warning("Gap: No gray literature evidence")
            
            st.divider()
            st.subheader("🤖 AI Insight Generator")
            
            ai_key = f"ai_synthesis_{selected_theme_id}"
            if ai_key not in st.session_state:
                st.session_state[ai_key] = None
            
            col_ai_btn, col_ai_status = st.columns([1, 2])
            with col_ai_btn:
                generate_btn = st.button(
                    "🤖 Generate AI Synthesis",
                    width=True,
                    key=f"ai_gen_{selected_theme_id}"
                )
            
            if generate_btn:
                wl_fragments = []
                gl_fragments = []
                
                theme_codes = db.get_codes_for_theme(selected_theme_id)
                for code in theme_codes:
                    code_id = code[0]
                    code_fragments = db.get_fragments_for_code(code_id)
                    
                    for frag in code_fragments:
                        frag_id, art_id, rq, text = frag[0], frag[1], frag[2], frag[3]
                        
                        conn = sqlite3.connect(db.db_path)
                        art = pd.read_sql_query(f"SELECT literature_type, authors, year FROM articles WHERE id = {art_id}", conn).iloc[0]
                        conn.close()
                        
                        authors = art.get('authors', 'Unknown')
                        year = art.get('year', 'n.d.')
                        fragment_with_meta = f"[{authors}, {year}]: {text}"
                        
                        if art['literature_type'] == "WL":
                            wl_fragments.append(fragment_with_meta)
                        else:
                            gl_fragments.append(fragment_with_meta)
                
                with st.spinner("Synthesizing evidence from WL and GL sources..."):
                    synthesis_result = generate_theme_synthesis(
                        selected_theme[2],
                        wl_fragments,
                        gl_fragments
                    )
                    
                    if synthesis_result.get("error"):
                        st.error(f"Synthesis failed: {synthesis_result['error']}")
                    else:
                        st.session_state[ai_key] = synthesis_result
                        st.rerun()
            
            if st.session_state.get(ai_key):
                synthesis_data = st.session_state[ai_key]
                if synthesis_data and synthesis_data.get("synthesis"):
                    with col_ai_status:
                        st.caption(f"[PASS] Generated - WL: {synthesis_data['wl_count']} fragments | GL: {synthesis_data['gl_count']} fragments")
                    
                    st.divider()
                    st.markdown("### 📝 AI Synthesis Report")
                    
                    st.markdown(f"""
                    <div style="
                        background: #f8fafc; padding: 20px; border-radius: 10px;
                        border: 1px solid #e2e8f0; font-family: system-ui;
                    ">
                    {synthesis_data['synthesis'].replace('**', '<strong>').replace('**', '</strong>')}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.markdown(synthesis_data['synthesis'])
                    
                    st.divider()
                    col_exp, col_copy = st.columns(2)
                    
                    with col_exp:
                        synthesis_text = synthesis_data['synthesis']
                        st.download_button(
                            "📥 Export as Text",
                            data=synthesis_text,
                            file_name=f"{selected_theme[1]}_synthesis.txt",
                            mime="text/plain",
                            width=True
                        )
                    
                    with col_copy:
                        if st.button("Copy to Clipboard", width=True):
                            st.info("Use Ctrl+C to copy the text above")
            
            elif not generate_btn:
                st.info("Click 'Generate AI Synthesis' to create a comparative WL/GL report for this theme.")
            
            theme_codes = db.get_codes_for_theme(selected_theme_id)
            
            if not theme_codes:
                st.info("No codes linked to this theme yet.")
            else:
                st.markdown(f"**Codes in this Theme:** ({len(theme_codes)})")
                
                comparison = db.compare_theme_by_literature_type(selected_theme_id)
                
                if comparison:
                    st.markdown("####  Literature Distribution")
                    comp_data = [{"Type": c[0], "Fragments": c[1], "Sources": c[2]} for c in comparison]
                    fig = px.bar(
                        comp_data, x="Type", y="Fragments", 
                        title="Fragment Distribution by Literature Type",
                        color="Type", color_discrete_sequence=["#2563eb", "#64748b"]
                    )
                    st.plotly_chart(fig, width=True)
                
                st.markdown("#### 🌳 Hierarchical Tree")
                
                for code in theme_codes:
                    code_id, code_label, code_desc, code_rq = code[0], code[1], code[2], code[3]
                    
                    with st.expander(f"📌 **{code_label}** ({code_rq})"):
                        if code_desc:
                            st.caption(f"Description: {code_desc}")
                        
                        code_fragments = db.get_fragments_for_code(code_id)
                        
                        if not code_fragments:
                            st.info("No fragments linked to this code")
                        else:
                            st.markdown(f"**Fragments ({len(code_fragments)}):**")
                            
                            for frag in code_fragments:
                                frag_id, art_id, rq, text, category, reviewer, page, created = frag[0], frag[1], frag[2], frag[3], frag[4], frag[5], frag[6], frag[7]
                                
                                conn = sqlite3.connect(db.db_path)
                                art = pd.read_sql_query(f"SELECT title, authors, year, literature_type FROM articles WHERE id = {art_id}", conn).iloc[0]
                                conn.close()
                                
                                authors = art.get('authors', 'Unknown')
                                year = art.get('year', 'n.d.')
                                citation = f"[{authors}, {year}]" if year else f"[{authors}]"
                                
                                with st.container():
                                    st.markdown(f"📄 **{art['title'][:60]}...** ({art['literature_type']})")
                                    st.caption(citation)
                                    st.write(f"_{text}_")
                                    st.caption(f"RQ: {rq} | Extracted by: {reviewer}")
                                    st.divider()
            
            st.divider()
            st.markdown("####  Synthesis Summary")
            
            conn = sqlite3.connect(db.db_path)
            
            fragments_by_rq = pd.read_sql_query("""
                SELECT rq_code, COUNT(*) as count 
                FROM fragments 
                GROUP BY rq_code
            """, conn)
            
            lit_dist = pd.read_sql_query("""
                SELECT a.literature_type, COUNT(DISTINCT f.id) as fragment_count
                FROM fragments f
                JOIN articles a ON f.article_id = a.id
                GROUP BY a.literature_type
            """, conn)
            
            codes_per_rq = pd.read_sql_query("""
                SELECT rq_code, COUNT(*) as count 
                FROM codes 
                GROUP BY rq_code
            """, conn)
            
            conn.close()
            
            c1, c2, c3 = st.columns(3)
            
            with c1:
                if not fragments_by_rq.empty:
                    fig = px.bar(fragments_by_rq, x="rq_code", y="count", title="Fragments by RQ", color="rq_code", color_discrete_sequence=px.colors.qualitative.Set2)
                    st.plotly_chart(fig, width=True)
                else:
                    st.info("No fragments")
            
            with c2:
                if not codes_per_rq.empty:
                    fig = px.bar(codes_per_rq, x="rq_code", y="count", title="Codes by RQ", color="rq_code", color_discrete_sequence=px.colors.qualitative.Pastel)
                    st.plotly_chart(fig, width=True)
                else:
                    st.info("No codes")
            
            with c3:
                if not lit_dist.empty:
                    fig = px.pie(lit_dist, values="fragment_count", names="literature_type", title="Fragment Distribution", color_discrete_sequence=["#2563eb", "#64748b"])
                    st.plotly_chart(fig, width=True)
                else:
                    st.info("No fragments")
    
    st.divider()
    st.subheader(" Final Executive Report")
    st.caption("Automated professional synthesis report for stakeholders")
    
    if st.button("✨ Generate Full Executive Summary", width=True):
        with st.spinner("Generating comprehensive report..."):
            try:
                from src.core.synthesis_aggregator import generate_executive_summary
                
                report, has_content = generate_executive_summary(db)
                
                if has_content:
                    st.markdown(report)
                    
                    col_dl, col_preview = st.columns(2)
                    with col_dl:
                        st.download_button(
                            label="📥 Download Report (.md)",
                            data=report,
                            file_name="executive_summary.md",
                            mime="text/markdown",
                            width=True
                        )
                else:
                    st.warning("No themes synthesized yet. Create themes and AI syntheses first.")
            except Exception as e:
                st.error(f"Report generation error: {e}")


def require_stage(required_stage: ReviewStage, db) -> bool:
    """Block page access if current stage doesn't permit it."""
    current = ReviewStage(db.get_current_stage())
    
    if current != required_stage:
        st.error(f"[LOCKED] This section requires '{required_stage.value}' stage")
        st.info(f"Workflow: {db.get_stage_prompt()}")
        return False
    return True