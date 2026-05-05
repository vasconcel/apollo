import streamlit as st
import sqlite3
import pandas as pd
import json
import tempfile
from pathlib import Path

from src.core.database import Database
from src.core.workflow import ReviewStage, is_valid_transition
from src.core.ai_handler import get_ai_suggestion
from src.core.converter import convert_bibtex_to_df, convert_ris_to_df, convert_excel_to_df, convert_wos_txt_to_df
from src.core.snowballing import get_paper_references
from src.core.gl_handler import process_gl_ingestion


def get_database():
    """Returns a cached Database instance with current review_id."""
    review_id = st.session_state.get("review_id", 1)
    return Database(review_id=review_id)


def require_stage(required_stage: ReviewStage) -> bool:
    """Block page access if current stage doesn't permit it."""
    db = get_database()
    current = ReviewStage(db.get_current_stage())
    
    if current != required_stage:
        st.error(f"[LOCKED] This section requires '{required_stage.value}' stage")
        st.info(f"Workflow: {db.get_stage_prompt()}")
        return False
    return True


def get_stats():
    """Get real-time statistics for the dashboard."""
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


def get_settings():
    """Get project settings."""
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


def render_screening():
    """Screening module with AI Pre-screening activation."""
    st.header("Screening")
    st.caption(f"Reviewer: **{st.session_state.get('reviewer_id', 'Reviewer_1')}**")
    
    db = get_database()
    if not require_stage(ReviewStage.SCREENING):
        return
    
    stats = get_stats()
    decisions = stats["decisions"]
    total_articles = stats["total_articles"]
    settings = get_settings()
    
    if total_articles == 0:
        st.info("No articles available. Please import your literature data to begin screening.")
        st.markdown("""
        **Getting Started:**
        1. Prepare your literature in CSV, BibTeX, RIS, or Excel format
        2. Upload files below to import
        """)
        
        with st.expander("Data Ingestion Hub", expanded=True):
            st.subheader("Upload Literature Files")
            
            col_src, col_file = st.columns([1, 2])
            with col_src:
                lit_type = st.radio("Literature Source Type", ["White Literature (WL)", "Grey Literature (GL)"], horizontal=True)
            with col_file:
                uploaded_files = st.file_uploader(
                    "Upload files (any format: .bib, .ris, .csv, .xlsx, .txt, or no extension)",
                    accept_multiple_files=True
                )
                
                st.caption("💡 Tip: Files with no extension (ACM exports) are auto-detected as BibTeX")
            
            if uploaded_files:
                st.caption(f"📎 {len(uploaded_files)} file(s) selected")
                
                all_dfs = []
                for uploaded in uploaded_files:
                    st.info(f"Processing: {uploaded.name}")
                    
                    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded.name).suffix) as tmp:
                        tmp.write(uploaded.getvalue())
                        tmp_path = tmp.name
                    
                    suffix = Path(uploaded.name).suffix.lower()
                    
                    if not suffix or suffix not in [".bib", ".ris", ".xlsx", ".csv", ".txt"]:
                        suffix = ".bib"
                    
                    try:
                        if suffix == ".bib":
                            try:
                                df = convert_bibtex_to_df(tmp_path)
                            except Exception as bib_error:
                                st.warning(f"Not BibTeX format, skipping: {bib_error}")
                                df = pd.DataFrame()
                        elif suffix == ".ris":
                            df = convert_ris_to_df(tmp_path)
                        elif suffix == ".xlsx":
                            df = convert_excel_to_df(tmp_path)
                        elif suffix == ".csv":
                            df = pd.read_csv(tmp_path)
                        elif suffix == ".txt":
                            df = convert_wos_txt_to_df(tmp_path)
                        else:
                            df = pd.DataFrame()
                        
                        if not df.empty:
                            df["literature_type"] = "WL" if "White" in lit_type else "GL"
                            all_dfs.append(df)
                            st.success(f"[OK] Converted: {len(df)} records")
                    except Exception as e:
                        st.error(f"Error: {e}")
                
                if all_dfs:
                    combined = pd.concat(all_dfs, ignore_index=True)
                    
                    st.divider()
                    st.subheader("Preview (first 5 rows)")
                    st.dataframe(combined.head(5))
                    
                    if st.button("Import to Screening Queue", type="primary"):
                        with st.spinner("Ingesting..."):
                            try:
                                initial_count = db.count_articles()
                                
                                for _, row in combined.iterrows():
                                    db.add_article({
                                        "title": str(row.get("title", "")),
                                        "authors": str(row.get("authors", "")),
                                        "year": row.get("year"),
                                        "abstract": str(row.get("abstract", "")),
                                        "doi": str(row.get("doi", "")),
                                        "url": str(row.get("url", "")),
                                        "source": str(row.get("source", "") or row.get("source_title", "")),
                                        "literature_type": row.get("literature_type", "WL")
                                    })
                                
                                final_count = db.count_articles()
                                imported = final_count - initial_count
                                
                                st.success(f"[PASS] {imported} records added to screening queue!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Ingestion failed: {e}")
                
                st.divider()
                with st.expander("Snowballing (Reference Tracking)"):
                    st.caption("Find related articles via reference lists")
                    
                    conn = sqlite3.connect(db.db_path)
                    included = pd.read_sql_query("""
                        SELECT a.id, a.title, a.authors, a.doi, a.year
                        FROM articles a
                        INNER JOIN final_decisions fd ON a.id = fd.article_id
                        WHERE fd.final_decision = 'include'
                        ORDER BY a.year DESC
                        LIMIT 50
                    """, conn)
                    conn.close()
                    
                    if not included.empty:
                        inc_options = [f"{row['title'][:60]}..." if len(str(row['title'])) > 60 else str(row['title']) for _, row in included.iterrows()]
                        inc_dict = {f"{row['title'][:60]}..." if len(str(row['title'])) > 60 else str(row['title']): row["id"] for _, row in included.iterrows()}
                        
                        selected = st.selectbox("Select Included Article", inc_options)
                        if st.button("Find References", disabled=not selected):
                            with st.spinner("Searching..."):
                                try:
                                    art_id = inc_dict[selected]
                                    article = db.get_article_by_id(art_id)
                                    doi = article.get("doi", "") if article else ""
                                    
                                    if doi:
                                        refs = get_paper_references(doi)
                                        st.success(f"Found {len(refs)} references")
                                        
                                        if refs and st.button("Add References to Queue"):
                                            for ref in refs:
                                                db.add_article({
                                                    "title": ref.get("title", ""),
                                                    "authors": ref.get("authors", ""),
                                                    "year": ref.get("year"),
                                                    "doi": ref.get("doi", ""),
                                                    "literature_type": "WL"
                                                })
                                            st.success("References added!")
                                            st.rerun()
                                    else:
                                        st.warning("No DOI available for this article")
                                except Exception as e:
                                    st.error(f"Error: {e}")
                    else:
                        st.info("No included articles yet")
        
        st.divider()
        with st.expander("📥 GL Ingestion (Grey Literature)", expanded=False):
            st.markdown("""
            **Grey Literature Ingestion Module**
            
            Import Grey Literature from TSV files. Each URL is scraped and evaluated for thematic saturation.
            Based on Garousi et al. (2019) MLR Protocol.
            """)
            
            gl_file = st.file_uploader(
                "Upload TSV file (columns: Position, Title, URL)",
                type=["txt", "tsv"]
            )
            
            if gl_file:
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".tsv") as tmp:
                        tmp.write(gl_file.getvalue())
                        tmp_path = tmp.name
                    
                    df = pd.read_csv(tmp_path, sep='\t')
                    
                    if not {'Position', 'Title', 'URL'}.issubset(df.columns):
                        st.error("TSV must contain columns: Position, Title, URL")
                    else:
                        st.dataframe(df.head(), use_container_width=True)
                        st.caption(f"Ready to process {len(df)} URLs")
                        
                        if st.button("Execute Process GL Ingestion", type="primary"):
                            kb = db.get_project_knowledge_base()
                            
                            research_questions = [rq[1] for rq in db.get_research_questions()]
                            project_themes = kb.get("themes_summary", "")
                            
                            progress_bar = st.progress(0)
                            status_text = st.empty()
                            
                            def update_progress(current, total, status):
                                progress_bar.progress(current / total)
                                status_text.caption(status)
                            
                            try:
                                results = process_gl_ingestion(
                                    df,
                                    project_themes,
                                    research_questions,
                                    progress_callback=update_progress
                                )
                                
                                new_count = 0
                                saturated_count = 0
                                
                                for result in results:
                                    if result["status"] == "processed":
                                        notes_json = json.dumps({
                                            "is_new": result["saturation"].get("is_new"),
                                            "reasoning": result["saturation"].get("reasoning", ""),
                                            "suggested_tags": result["saturation"].get("suggested_tags", [])
                                        })
                                        
                                        article_id = db.add_gl_article(
                                            title=result["title"],
                                            url=result["url"],
                                            ingestion_notes=notes_json,
                                            abstract=result["content"][:500] if result["content"] else None
                                        )
                                        if article_id:
                                            new_count += 1
                                    else:
                                        saturated_count += 1
                            finally:
                                progress_bar.empty()
                                status_text.empty()
                            
                            st.success(f"[PASS] GL Ingestion Complete!")
                            st.markdown(f"""
                            - **New articles imported:** {new_count}
                            - **Thematic saturation reached:** {saturated_count}
                            """)
                            
                            if results:
                                results_df = pd.DataFrame([
                                    {
                                        "Title": r["title"][:60] + ("..." if len(r["title"]) > 60 else ""),
                                        "URL": r["url"][:50] + ("..." if len(r["url"]) > 50 else ""),
                                        "Status": r["status"].title(),
                                        "Is New": "Yes" if r["saturation"].get("is_new") else "No",
                                        "Reasoning": r["saturation"].get("reasoning", "")[:100]
                                    }
                                    for r in results
                                ])
                                
                                with st.expander(f" GL Ingestion Details ({len(results)} articles)", expanded=True):
                                    st.dataframe(results_df, use_container_width=True)
                            
                            st.rerun()
                            
                except Exception as e:
                    st.error(f"Error processing GL ingestion: {e}")
        
        return
    
    screened_count = len(decisions["article_id"].unique()) if not decisions.empty else 0
    progress = screened_count / total_articles if total_articles > 0 else 0
    
    st.progress(progress)
    st.caption(f"Progress: {screened_count}/{total_articles} articles screened ({int(progress*100)}%)")
    
    st.divider()
    with st.expander("🤖 AI Pre-Screening (Batch)", expanded=False):
        st.caption("Let AI learn from your decisions and pre-screen pending articles")
        
        col_ai, col_batch = st.columns([1, 2])
        with col_ai:
            run_batch = st.button("🔮 Run AI Batch Screening (20 articles)", width=True)
        
        if run_batch:
            with st.spinner("Learning from your decisions..."):
                try:
                    from src.core.active_learning import get_training_context, format_few_shot_prompt, get_pending_articles_for_screening
                    from src.core.ai_handler import get_batch_predictions
                    
                    reviewer_id = st.session_state.get("reviewer_id", "Reviewer_1")
                    context = get_training_context(db, reviewer_id, limit=20)
                    
                    if context["total_includes"] == 0 and context["total_excludes"] == 0:
                        st.warning("Need at least some screening decisions to learn from. Make some decisions first!")
                    else:
                        pending_batch = get_pending_articles_for_screening(db, reviewer_id, limit=20)
                        
                        if not pending_batch:
                            st.info("No pending articles for batch screening")
                        else:
                            few_shot = format_few_shot_prompt(context, settings)
                            
                            predictions = get_batch_predictions(pending_batch, few_shot, max_articles=20)
                            
                            if predictions:
                                ai_key = f"batch_predictions_{reviewer_id}"
                                st.session_state[ai_key] = predictions
                                st.success(f"[PASS] Generated predictions for {len(predictions)} articles!")
                                st.rerun()
                            else:
                                st.error("Could not generate predictions")
                except Exception as e:
                    st.error(f"Batch screening error: {e}")
        
        st.info("AI will analyze articles based on your previous Include/Exclude decisions.")
        
        st.info("🤖 **AI Pre-Screening Active**: AI-powered batch screening is enabled and ready to assist with screening decisions based on your prior judgments.")
    
    st.divider()
    
    pending_articles = db.get_pending_articles(st.session_state.get("reviewer_id", "Reviewer_1"))
    
    if not pending_articles:
        st.success("All articles have been reviewed!")
        
        c1, c2 = st.columns(2)
        with c1:
            my_decisions = decisions[decisions["reviewer_id"] == st.session_state.get("reviewer_id", "Reviewer_1")]
            st.metric("My Decisions", len(my_decisions))
        with c2:
            included_count = len(my_decisions[my_decisions["decision"] == "include"]) if not my_decisions.empty else 0
            st.metric("Included", included_count)
        return
    
    if st.session_state.get("current_article_idx", 0) >= len(pending_articles):
        st.session_state.current_article_idx = 0
    
    current_article = pending_articles[st.session_state.get("current_article_idx", 0)]
    art_id, title, abstract, source_id, lit_type, status = current_article
    
    with st.container():
        st.markdown('<div class="ais-card">', unsafe_allow_html=True)
        st.markdown(f"### {title}")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.caption(f"📂 Source: {source_id}")
        with c2:
            lit_badge = "📚 WL" if lit_type == "WL" else "📥 GL"
            st.caption(f"{lit_badge} Type: {lit_type}")
        with c3:
            st.caption(f"🆔 ID: {art_id}")
        
        if abstract:
            with st.expander("📝 Abstract", expanded=True):
                st.write(abstract[:1000] + "..." if len(str(abstract)) > 1000 else abstract)
        else:
            st.warning("No abstract available")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    ai_suggestion = st.session_state.get("ai_suggestion")
    if ai_suggestion and ai_suggestion.get("decision") != "error":
        st.info(f"[AI] Suggestion: **{ai_suggestion.get('decision', 'N/A').upper()}** (confidence: {ai_suggestion.get('confidence', 0)}%)")
        st.caption(f"Reason: {ai_suggestion.get('reasons', ['No reason'])[0]}")
    
    st.divider()
    
    st.subheader(" Decision: Eligibility Criteria Funnel")
    
    exclusion_criteria = settings.get("exclusion_criteria", {})
    inclusion_criteria = settings.get("inclusion_criteria", {})
    
    st.markdown('<div class="ais-card">', unsafe_allow_html=True)
    
    with st.form(key=f"screening_form_{art_id}", clear_on_submit=False):
        decision_type = st.radio(
            "Select Decision Type",
            options=["include", "exclude", "uncertain"],
            format_func=lambda x: {
                "include": "[PASS] Include",
                "exclude": " Exclude", 
                "uncertain": "[WARN] Uncertain"
            }.get(x, x),
            horizontal=True,
            help="Select the type of screening decision"
        )
        
        st.divider()
        
        selected_exclusion_reason = None
        selected_inclusion_criteria = {}
        
        if decision_type == "exclude":
            st.markdown("**Exclusion Criterion (Required)**")
            st.caption("Select the criterion that justifies exclusion:")
            
            selected_ec = st.selectbox(
                "Exclusion Criterion",
                options=[""] + list(exclusion_criteria.keys()),
                format_func=lambda x: x if not x else f"{x}: {exclusion_criteria[x]}"
            )
            
            if not selected_ec:
                st.error("[WARN] You must select at least one Exclusion Criterion to exclude an article.")
            
            selected_exclusion_reason = selected_ec
            
        elif decision_type == "include":
            st.markdown("**Inclusion Criteria (Optional)**")
            st.caption("Check the criteria this article meets:")
            
            selected_inclusion_criteria = {}
            for ic_code, ic_desc in inclusion_criteria.items():
                selected_inclusion_criteria[ic_code] = st.checkbox(
                    f"{ic_code}: {ic_desc}",
                    value=False,
                    key=f"ic_{art_id}_{ic_code}"
                )
        
        col_ai_left, col_ai_right = st.columns([1, 3])
        with col_ai_left:
            ai_analyze = st.form_submit_button(
                "🤖 AI Analyze",
                type="secondary",
                width=True
            )
        
        if ai_analyze:
            with st.spinner("Analyzing with AI..."):
                st.session_state.ai_suggestion = get_ai_suggestion(title, abstract or "", settings)
            st.rerun()
        
        st.divider()
        
        col_submit_left, col_submit_right = st.columns([1, 3])
        with col_submit_left:
            submit_decision = st.form_submit_button(
                "💾 Submit Decision",
                type="primary",
                width=True
            )
    
    if 'submit_screening' not in st.session_state:
        st.session_state.submit_screening = None
    
    if submit_decision:
        if decision_type == "exclude" and not selected_exclusion_reason:
            st.error(" Exclusion requires selecting at least one Exclusion Criterion.")
        else:
            criteria_dict = None
            if decision_type == "include":
                criteria_dict = {k: v for k, v in selected_inclusion_criteria.items() if v}
            
            db.save_decision(
                art_id, 
                st.session_state.get("reviewer_id", "Reviewer_1"), 
                decision_type,
                exclusion_reason=selected_exclusion_reason,
                criteria=criteria_dict
            )
            
            st.session_state.ai_suggestion = None
            st.session_state.submit_screening = art_id
            
            current_idx = st.session_state.get("current_article_idx", 0)
            if current_idx < len(pending_articles) - 1:
                st.session_state.current_article_idx = current_idx + 1
            else:
                st.session_state.current_article_idx = 0
            
            st.success(f"Decision recorded: **{decision_type.upper()}**" + 
                     (f" (EC: {selected_exclusion_reason})" if selected_exclusion_reason else ""))
            st.rerun()
    
    st.divider()
    st.subheader("📑 Article Navigation")
    nav_c1, nav_c2, nav_c3 = st.columns([1, 2, 1])
    current_idx = st.session_state.get("current_article_idx", 0)
    with nav_c1:
        if st.button("Previous", disabled=current_idx == 0, width=True):
            st.session_state.current_article_idx = max(0, current_idx - 1)
            st.session_state.ai_suggestion = None
            st.rerun()
    with nav_c3:
        if st.button("Next", disabled=current_idx >= len(pending_articles) - 1, width=True):
            st.session_state.current_article_idx = current_idx + 1
            st.session_state.ai_suggestion = None
            st.rerun()
    
    with nav_c2:
        st.caption(f"Article {current_idx + 1} of {len(pending_articles)}")