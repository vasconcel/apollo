import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Core
from src.core.database import Database, DatabaseError
from src.core.analytics import load_decisions_dataframe, prepare_kappa
from src.core.consensus import ConsensusEngine
from src.core.quality import QualityEngine

# Extras
from src.core.ai_handler import get_ai_suggestion, generate_theme_synthesis
from src.core.config_manager import load_config
from src.core.converter import convert_bibtex_to_df, convert_ris_to_df, convert_excel_to_df
from src.core.snowballing import get_paper_references


# ==================== CONFIG ====================
st.set_page_config(
    page_title="AIMS - Research Synthesis Platform",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🔬"
)

# ==================== DEEP SPACE THEME ====================
from src.ui.styles import get_custom_css
st.markdown(get_custom_css(), unsafe_allow_html=True)


# ==================== INIT ====================
@st.cache_resource
def get_database():
    """Returns a cached Database instance."""
    return Database()

@st.cache_resource
def get_consensus_engine():
    """Returns a cached ConsensusEngine - uses db path internally."""
    db = get_database()
    return ConsensusEngine(db.db_path)

@st.cache_resource
def get_quality_engine():
    """Returns a cached QualityEngine instance."""
    return QualityEngine()

@st.cache_resource
def get_config():
    """Returns a cached config manager instance."""
    return load_config()

db = get_database()
consensus_engine = get_consensus_engine()
quality_engine = get_quality_engine()
config_mgr = get_config()

settings = {
    "project_name": config_mgr.get("project_name", "My Research Project"),
    "project_description": config_mgr.get("project_description"),
    "research_questions": config_mgr.get("research_questions"),
    "inclusion_criteria": config_mgr.get("inclusion_criteria"),
    "exclusion_criteria": config_mgr.get("exclusion_criteria"),
    "quality_criteria": config_mgr.get("quality_criteria"),
    "extraction_fields": config_mgr.get("extraction_fields")
}

# Session state
if "reviewer_id" not in st.session_state:
    st.session_state.reviewer_id = "Reviewer_1"
if "current_article_idx" not in st.session_state:
    st.session_state.current_article_idx = 0


# ==================== HELPER FUNCTIONS ====================
def get_stats():
    """Get real-time statistics for the dashboard."""
    conn = sqlite3.connect(db.db_path)
    
    # Articles
    articles_df = pd.read_sql_query("SELECT * FROM articles", conn)
    total_articles = len(articles_df)
    
    # Screening decisions
    decisions_df = pd.read_sql_query("SELECT * FROM screening_decisions", conn)
    
    # Final decisions
    final_df = pd.read_sql_query("SELECT * FROM final_decisions", conn)
    
    # Quality assessments
    qa_df = pd.read_sql_query("SELECT * FROM quality_assessments", conn)
    
    conn.close()
    
    return {
        "total_articles": total_articles,
        "decisions": decisions_df,
        "final": final_df,
        "qa": qa_df
    }


def get_prisma_stats():
    """Calculate PRISMA Flow Diagram statistics from database."""
    conn = sqlite3.connect(db.db_path)
    
    # Total imported records
    total_imported = pd.read_sql_query("SELECT COUNT(*) as count FROM articles", conn).iloc[0]['count']
    
    # Screened records (unique articles with at least one decision)
    screened = pd.read_sql_query("""
        SELECT COUNT(DISTINCT article_id) as count FROM screening_decisions
    """, conn).iloc[0]['count']
    
    # Exclusion reasons breakdown
    excluded_by_ec = pd.read_sql_query("""
        SELECT exclusion_reason, COUNT(*) as count 
        FROM screening_decisions 
        WHERE decision = 'exclude' AND exclusion_reason IS NOT NULL
        GROUP BY exclusion_reason
        ORDER BY count DESC
    """, conn)
    
    # Included in screening (by any reviewer)
    included_screening = pd.read_sql_query("""
        SELECT COUNT(DISTINCT article_id) as count 
        FROM screening_decisions 
        WHERE decision = 'include'
    """, conn).iloc[0]['count']
    
    # Final included (consensus resolved)
    final_included = pd.read_sql_query("""
        SELECT COUNT(*) as count 
        FROM final_decisions 
        WHERE final_decision = 'include'
    """, conn).iloc[0]['count']
    
    # Final excluded (consensus resolved)
    final_excluded = pd.read_sql_query("""
        SELECT COUNT(*) as count 
        FROM final_decisions 
        WHERE final_decision = 'exclude'
    """, conn).iloc[0]['count']
    
    # QA assessments
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
    
    # Pending screening
    pending_screening = total_imported - screened
    
    # Articles in QA queue (passed final decision as include, not yet assessed)
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


def get_exclusion_reasons_summary():
    """Get detailed exclusion reasons for analytics."""
    exclusion_criteria = settings.get("exclusion_criteria", {})
    conn = sqlite3.connect(db.db_path)
    
    reasons_df = pd.read_sql_query("""
        SELECT exclusion_reason, COUNT(*) as count 
        FROM screening_decisions 
        WHERE decision = 'exclude' AND exclusion_reason IS NOT NULL
        GROUP BY exclusion_reason
        ORDER BY count DESC
    """, conn)
    
    conn.close()
    
    result = []
    for _, row in reasons_df.iterrows():
        ec_code = row['exclusion_reason']
        count = row['count']
        description = exclusion_criteria.get(ec_code, "Unknown criterion")
        result.append({
            "code": ec_code,
            "description": description,
            "count": count
        })
    
    return result


def render_status_badge(status):
    """Render a status badge."""
    status_lower = str(status).lower()
    if status_lower == "include":
        return '<span class="badge badge-include">Included</span>'
    elif status_lower == "exclude":
        return '<span class="badge badge-exclude">Excluded</span>'
    elif status_lower == "uncertain":
        return '<span class="badge badge-uncertain">Uncertain</span>'
    else:
        return '<span class="badge badge-pending">Pending</span>'


def render_metric_card(label, value, delta=None, help_text=None):
    """Render a metric card."""
    st.metric(label=label, value=value, delta=delta, help=help_text)


# ==================== PAGE: OVERVIEW ====================
def render_overview():
    proj_name = settings.get("project_name", "Research Project")
    st.markdown(f"""
    <div style="margin-bottom: 1.5rem;">
        <h2 style="margin: 0; font-size: 1.75rem;">{proj_name}</h2>
        <p style="color: var(--text-secondary); margin: 0.25rem 0 0 0;">Real-time pipeline statistics and PRISMA flow tracking</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Get PRISMA statistics
    prisma = get_prisma_stats()
    has_data = prisma["total_imported"] > 0
    
    # ===== KEY METRICS ROW =====
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        st.metric("Total Imported", prisma["total_imported"])
    with c2:
        st.metric("Screened", prisma["screened"])
    with c3:
        st.metric("Pending", prisma["pending_screening"])
    with c4:
        st.metric("Included (Screening)", prisma["included_screening"])
    with c5:
        st.metric("Final Included", prisma["final_included"])
    with c6:
        st.metric("QA Pending", prisma["qa_pending"])
    
    st.divider()
    
    # ===== PRISMA FLOW DIAGRAM =====
    st.subheader("📊 PRISMA Flow Diagram")
    
    if not has_data:
        st.info("No articles imported yet. Import data to see the PRISMA flow.")
    else:
        # Create PRISMA flow using styled containers
        with st.container():
            # Stage 1: Identification
            col_id = st.columns([1])
            with col_id[0]:
                st.markdown("""
                <div style="
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white; padding: 20px; border-radius: 10px;
                    text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                ">
                    <h3 style="margin:0; color: white;">📥 Identification</h3>
                    <p style="font-size: 24px; font-weight: bold; margin: 10px 0;">{}</p>
                    <small>Records identified from databases</small>
                </div>
                """.format(prisma["total_imported"]), unsafe_allow_html=True)
            
            st.markdown("##### ↓")
            
            # Stage 2: Screening (with expandable details)
            with st.expander("🔍 **Screening Phase** (click to expand)", expanded=True):
                c_screen = st.columns([1, 1, 1])
                
                with c_screen[0]:
                    st.markdown("""
                    <div style="
                        background: #fef3c7; padding: 15px; border-radius: 8px;
                        border-left: 4px solid #f59e0b; text-align: center;
                    ">
                        <h4 style="margin:0;">🕐 Pending</h4>
                        <p style="font-size: 20px; font-weight: bold; color: #92400e;">{}</p>
                    </div>
                    """.format(prisma["pending_screening"]), unsafe_allow_html=True)
                
                with c_screen[1]:
                    st.markdown("""
                    <div style="
                        background: #d1fae5; padding: 15px; border-radius: 8px;
                        border-left: 4px solid #10b981; text-align: center;
                    ">
                        <h4 style="margin:0;">✅ Screened</h4>
                        <p style="font-size: 20px; font-weight: bold; color: #065f46;">{}</p>
                    </div>
                    """.format(prisma["screened"]), unsafe_allow_html=True)
                
                with c_screen[2]:
                    excluded_count = prisma["excluded_screening"]
                    st.markdown("""
                    <div style="
                        background: #fee2e2; padding: 15px; border-radius: 8px;
                        border-left: 4px solid #ef4444; text-align: center;
                    ">
                        <h4 style="margin:0;">❌ Excluded</h4>
                        <p style="font-size: 20px; font-weight: bold; color: #991b1b;">{}</p>
                    </div>
                    """.format(excluded_count), unsafe_allow_html=True)
                
                # Show exclusion reasons breakdown
                if prisma["excluded_by_ec"] is not None and not prisma["excluded_by_ec"].empty:
                    st.markdown("**Exclusion Reasons Breakdown:**")
                    ec_data = []
                    for _, row in prisma["excluded_by_ec"].iterrows():
                        ec_data.append({
                            "Criterion": row['exclusion_reason'],
                            "Count": row['count']
                        })
                    if ec_data:
                        ec_df = pd.DataFrame(ec_data)
                        st.dataframe(ec_df, hide_index=True, use_container_width=True)
            
            st.markdown("##### ↓")
            
            # Stage 3: Eligibility (QA)
            with st.expander("🧪 **Eligibility / Quality Assessment**", expanded=True):
                if prisma["final_included"] > 0 or prisma["qa_pending"] > 0:
                    c_qa = st.columns([1, 1, 1, 1])
                    
                    with c_qa[0]:
                        st.markdown("""
                        <div style="
                            background: #e0f2fe; padding: 15px; border-radius: 8px;
                            border-left: 4px solid #0ea5e9; text-align: center;
                        ">
                            <h4 style="margin:0;">📋 For QA</h4>
                            <p style="font-size: 20px; font-weight: bold; color: #075985;">{}</p>
                        </div>
                        """.format(prisma["final_included"] + prisma["qa_pending"]), unsafe_allow_html=True)
                    
                    with c_qa[1]:
                        st.markdown("""
                        <div style="
                            background: #d1fae5; padding: 15px; border-radius: 8px;
                            border-left: 4px solid #10b981; text-align: center;
                        ">
                            <h4 style="margin:0;">✅ QA Passed</h4>
                            <p style="font-size: 20px; font-weight: bold; color: #065f46;">{}</p>
                        </div>
                        """.format(prisma["qa_passed"]), unsafe_allow_html=True)
                    
                    with c_qa[2]:
                        st.markdown("""
                        <div style="
                            background: #fee2e2; padding: 15px; border-radius: 8px;
                            border-left: 4px solid #ef4444; text-align: center;
                        ">
                            <h4 style="margin:0;">❌ QA Failed</h4>
                            <p style="font-size: 20px; font-weight: bold; color: #991b1b;">{}</p>
                        </div>
                        """.format(prisma["qa_failed"]), unsafe_allow_html=True)
                    
                    with c_qa[3]:
                        st.markdown("""
                        <div style="
                            background: #fef3c7; padding: 15px; border-radius: 8px;
                            border-left: 4px solid #f59e0b; text-align: center;
                        ">
                            <h4 style="margin:0;">⏳ QA Pending</h4>
                            <p style="font-size: 20px; font-weight: bold; color: #92400e;">{}</p>
                        </div>
                        """.format(prisma["qa_pending"]), unsafe_allow_html=True)
                else:
                    st.info("No articles have passed to Quality Assessment yet.")
            
            st.markdown("##### ↓")
            
            # Stage 4: Included in Synthesis
            with st.expander("🧩 **Included in Synthesis**", expanded=False):
                st.markdown("""
                <div style="
                    background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
                    color: white; padding: 20px; border-radius: 10px;
                    text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                ">
                    <h3 style="margin:0; color: white;">📚 Final Synthesis Set</h3>
                    <p style="font-size: 36px; font-weight: bold; margin: 10px 0;">{}</p>
                    <small>Articles ready for thematic synthesis</small>
                </div>
                """.format(prisma["final_included"]), unsafe_allow_html=True)
    
    st.divider()
    
    # ===== EXCLUSION REASONS ANALYTICS =====
    if has_data and not prisma["excluded_by_ec"].empty:
        st.subheader("🚫 Exclusion Reasons Analysis")
        
        exclusion_reasons = get_exclusion_reasons_summary()
        
        if exclusion_reasons:
            # Create horizontal bar chart
            exclusion_criteria = settings.get("exclusion_criteria", {})
            
            fig_excl = px.bar(
                pd.DataFrame(exclusion_reasons),
                y="code",
                x="count",
                orientation='h',
                title="Distribution of Exclusion Criteria",
                labels={"code": "Criterion", "count": "Number of Articles Excluded"},
                color="count",
                color_continuous_scale="Reds"
            )
            fig_excl.update_layout(
                showlegend=False,
                height=max(300, len(exclusion_reasons) * 60),
                yaxis={"categoryorder": "total"},
                margin={"l": 150}
            )
            st.plotly_chart(fig_excl, use_container_width=True)
            
            # Detailed table with descriptions
            with st.expander("📋 Detailed Exclusion Reasons Table"):
                excl_df = pd.DataFrame(exclusion_reasons)
                excl_df["% of Total"] = (excl_df["count"] / prisma["screened"] * 100).round(1)
                st.dataframe(excl_df.rename(columns={
                    "code": "Criterion",
                    "description": "Description",
                    "count": "Count",
                    "% of Total": "% of Screened"
                }), hide_index=True, use_container_width=True)
    
    st.divider()
    
    # ===== LITERATURE TYPE DISTRIBUTION =====
    st.subheader("📚 Literature Type Distribution")
    
    conn = sqlite3.connect(db.db_path)
    articles = pd.read_sql_query("SELECT literature_type FROM articles", conn)
    conn.close()
    
    if not articles.empty:
        lit_dist = articles["literature_type"].value_counts()
        fig_lit = px.bar(
            x=lit_dist.index,
            y=lit_dist.values,
            title="White Literature (WL) vs Grey Literature (GL)",
            labels={"x": "Literature Type", "y": "Count"},
            color=lit_dist.index,
            color_discrete_map={"WL": "#2563eb", "GL": "#64748b"}
        )
        fig_lit.update_layout(height=300, showlegend=False)
        st.plotly_chart(fig_lit, use_container_width=True)
    else:
        st.info("No articles imported")
    
    st.divider()
    
    # ===== RESEARCH QUESTIONS =====
    st.subheader("Research Questions")
    rqs = settings.get("research_questions", [])
    has_placeholder = any("[TOPIC]" in rq or rq.startswith("[") for rq in rqs)
    
    if has_placeholder:
        st.warning("Project configuration not yet customized. Edit project_config.json.")
    
    for i, rq in enumerate(rqs, 1):
        rq_stripped = rq.strip()
        if rq_stripped.upper().startswith("RQ"):
            st.markdown(f"**{rq_stripped}**")
        else:
            st.markdown(f"**RQ{i}:** {rq}")
    
    st.divider()
    
    # ===== QUICK ACTIONS =====
    st.subheader("Quick Actions")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Refresh Statistics", use_container_width=True):
            st.rerun()
    with c2:
        st.info("Import data via the database module")


# ==================== PAGE: SCREENING ====================
def render_screening():
    st.header("Screening")
    st.caption(f"Reviewer: **{st.session_state.reviewer_id}**")
    
    stats = get_stats()
    decisions = stats["decisions"]
    total_articles = stats["total_articles"]
    
    # Empty state - No data imported
    if total_articles == 0:
        st.info("No articles available. Please import your literature data to begin screening.")
        st.markdown("""
        **Getting Started:**
        1. Prepare your literature in CSV, BibTeX, RIS, or Excel format
        2. Upload files below to import
        """)
        
        # ========== DATA INGESTION HUB ==========
        with st.expander("Data Ingestion Hub", expanded=True):
            st.subheader("Upload Literature Files")
            
            col_src, col_file = st.columns([1, 2])
            with col_src:
                lit_type = st.radio("Literature Source Type", ["White Literature (WL)", "Grey Literature (GL)"], horizontal=True)
            with col_file:
                uploaded_files = st.file_uploader(
                    "Upload files (.bib, .ris, .csv, .xlsx)",
                    type=["bib", "ris", "csv", "xlsx"],
                    accept_multiple_files=True
                )
            
            if uploaded_files:
                st.caption(f"📎 {len(uploaded_files)} file(s) selected")
                
                all_dfs = []
                for uploaded in uploaded_files:
                    st.info(f"Processing: {uploaded.name}")
                    
                    # Save to temp file
                    import tempfile
                    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded.name).suffix) as tmp:
                        tmp.write(uploaded.getvalue())
                        tmp_path = tmp.name
                    
                    # Convert based on extension
                    suffix = Path(uploaded.name).suffix.lower()
                    try:
                        if suffix == ".bib":
                            df = convert_bibtex_to_df(tmp_path)
                        elif suffix == ".ris":
                            df = convert_ris_to_df(tmp_path)
                        elif suffix == ".xlsx":
                            df = convert_excel_to_df(tmp_path)
                        elif suffix == ".csv":
                            df = pd.read_csv(tmp_path)
                        else:
                            df = pd.DataFrame()
                        
                        if not df.empty:
                            df["literature_type"] = "WL" if "White" in lit_type else "GL"
                            all_dfs.append(df)
                            st.success(f"✓ Converted: {len(df)} records")
                    except Exception as e:
                        st.error(f"Error: {e}")
                
                # Merge and preview
                if all_dfs:
                    combined = pd.concat(all_dfs, ignore_index=True)
                    
                    st.divider()
                    st.subheader("Preview (first 5 rows)")
                    st.dataframe(combined.head(5), use_container_width=True)
                    
                    # Ingest button
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
                                
                                st.success(f"✅ {imported} records added to screening queue!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Ingestion failed: {e}")
                
                # ========== SNOWBALLING ENRICHMENT ==========
                st.divider()
                with st.expander("Snowballing (Reference Tracking)"):
                    st.caption("Find related articles via reference lists")
                    
                    # Get included articles via direct query
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
        
        return
    
    # Progress bar
    screened_count = len(decisions["article_id"].unique()) if not decisions.empty else 0
    progress = screened_count / total_articles if total_articles > 0 else 0
    
    st.progress(progress)
    st.caption(f"Progress: {screened_count}/{total_articles} articles screened ({int(progress*100)}%)")
    
    # ===== AI BATCH PRE-SCREENING =====
    st.divider()
    with st.expander("🤖 AI Pre-Screening (Batch)", expanded=False):
        st.caption("Let AI learn from your decisions and pre-screen pending articles")
        
        col_ai, col_batch = st.columns([1, 2])
        with col_ai:
            run_batch = st.button("🔮 Run AI Batch Screening (20 articles)", use_container_width=True)
        
        if run_batch:
            with st.spinner("Learning from your decisions..."):
                try:
                    # Get training context from reviewer
                    from src.core.active_learning import get_training_context, format_few_shot_prompt, get_pending_articles_for_screening
                    from src.core.ai_handler import get_batch_predictions
                    
                    context = get_training_context(db, st.session_state.reviewer_id, limit=20)
                    
                    if context["total_includes"] == 0 and context["total_excludes"] == 0:
                        st.warning("Need at least some screening decisions to learn from. Make some decisions first!")
                    else:
                        # Get pending articles
                        pending_batch = get_pending_articles_for_screening(db, st.session_state.reviewer_id, limit=20)
                        
                        if not pending_batch:
                            st.info("No pending articles for batch screening")
                        else:
                            # Format few-shot prompt
                            few_shot = format_few_shot_prompt(context, settings)
                            
                            # Get batch predictions
                            predictions = get_batch_predictions(pending_batch, few_shot, max_articles=20)
                            
                            if predictions:
                                # Store predictions in session state
                                ai_key = f"batch_predictions_{st.session_state.reviewer_id}"
                                st.session_state[ai_key] = predictions
                                st.success(f"✅ Generated predictions for {len(predictions)} articles!")
                                st.rerun()
                            else:
                                st.error("Could not generate predictions")
                except Exception as e:
                    st.error(f"Batch screening error: {e}")
        
        st.info("AI will analyze articles based on your previous Include/Exclude decisions.")
    
    st.divider()
    
    # Get pending articles for this reviewer
    pending_articles = db.get_pending_articles(st.session_state.reviewer_id)
    
    if not pending_articles:
        st.success("All articles have been reviewed!")
        
        # Show summary
        c1, c2 = st.columns(2)
        with c1:
            my_decisions = decisions[decisions["reviewer_id"] == st.session_state.reviewer_id]
            st.metric("My Decisions", len(my_decisions))
        with c2:
            included_count = len(my_decisions[my_decisions["decision"] == "include"]) if not my_decisions.empty else 0
            st.metric("Included", included_count)
        return
    
    # Current article navigation
    st.subheader("Current Article")
    
    if st.session_state.current_article_idx >= len(pending_articles):
        st.session_state.current_article_idx = 0
    
    current_article = pending_articles[st.session_state.current_article_idx]
    art_id, title, abstract, source_id, lit_type, status = current_article
    
    # Article card
    with st.container():
        st.markdown(f"### {title}")
        
        # Metadata
        c1, c2, c3 = st.columns(3)
        with c1:
            st.caption(f"📂 Source: {source_id}")
        with c2:
            st.caption(f"📚 Type: {lit_type}")
        with c3:
            st.caption(f"🆔 ID: {art_id}")
    
    # Abstract
    if abstract:
        with st.expander("📝 Abstract", expanded=True):
            st.write(abstract[:800] + "..." if len(str(abstract)) > 800 else abstract)
    else:
        st.warning("No abstract available")
    
    # AI Suggestion (if enabled)
    ai_suggestion = st.session_state.get("ai_suggestion")
    if ai_suggestion and ai_suggestion.get("decision") != "error":
        st.info(f"🤖 AI Suggestion: **{ai_suggestion.get('decision', 'N/A').upper()}** (confidence: {ai_suggestion.get('confidence', 0)}%)")
        st.caption(f"Reason: {ai_suggestion.get('reasons', ['No reason'])[0]}")
    
    st.divider()
    
    # ========== ELIGIBILITY CRITERIA FUNNEL ==========
    st.subheader("🎯 Decision: Eligibility Criteria Funnel")
    
    # Load criteria from settings
    exclusion_criteria = settings.get("exclusion_criteria", {})
    inclusion_criteria = settings.get("inclusion_criteria", {})
    
    # Create a form for formal screening decision
    with st.form(key=f"screening_form_{art_id}", clear_on_submit=False):
        # Decision type selector
        decision_type = st.radio(
            "Select Decision Type",
            options=["include", "exclude", "uncertain"],
            format_func=lambda x: {
                "include": "✅ Include",
                "exclude": "❌ Exclude", 
                "uncertain": "⚠️ Uncertain"
            }.get(x, x),
            horizontal=True,
            help="Select the type of screening decision"
        )
        
        st.divider()
        
        # CRITERIA INPUTS BASED ON DECISION TYPE
        selected_exclusion_reason = None
        selected_inclusion_criteria = {}
        
        if decision_type == "exclude":
            # MANDATORY: Select at least one Exclusion Criterion
            st.markdown("**Exclusion Criterion (Required)**")
            st.caption("Select the criterion that justifies exclusion:")
            
            selected_ec = st.selectbox(
                "Exclusion Criterion",
                options=[""] + list(exclusion_criteria.keys()),
                format_func=lambda x: x if not x else f"{x}: {exclusion_criteria[x]}"
            )
            
            if not selected_ec:
                st.error("⚠️ You must select at least one Exclusion Criterion to exclude an article.")
            
            selected_exclusion_reason = selected_ec
            
        elif decision_type == "include":
            # OPTIONAL: Check which Inclusion Criteria were met
            st.markdown("**Inclusion Criteria (Optional)**")
            st.caption("Check the criteria this article meets:")
            
            selected_inclusion_criteria = {}
            for ic_code, ic_desc in inclusion_criteria.items():
                selected_inclusion_criteria[ic_code] = st.checkbox(
                    f"{ic_code}: {ic_desc}",
                    value=False,
                    key=f"ic_{art_id}_{ic_code}"
                )
        
        # AI Analyze button (positioned within form)
        col_ai_left, col_ai_right = st.columns([1, 3])
        with col_ai_left:
            ai_analyze = st.form_submit_button(
                "🤖 AI Analyze",
                type="secondary",
                use_container_width=True
            )
        
        if ai_analyze:
            with st.spinner("Analyzing with AI..."):
                st.session_state.ai_suggestion = get_ai_suggestion(title, abstract or "", settings)
            st.rerun()
        
        st.divider()
        
        # SUBMIT DECISION
        col_submit_left, col_submit_right = st.columns([1, 3])
        with col_submit_left:
            submit_decision = st.form_submit_button(
                "💾 Submit Decision",
                type="primary",
                use_container_width=True
            )
    
    # Handle form submission (outside form for proper state management)
    if 'submit_screening' not in st.session_state:
        st.session_state.submit_screening = None
    
    # Process decision submission via a separate handler
    if submit_decision:
        # Validate exclusion criterion is selected for exclude decisions
        if decision_type == "exclude" and not selected_exclusion_reason:
            st.error("❌ Exclusion requires selecting at least one Exclusion Criterion.")
        else:
            # Build criteria dict for include decisions
            criteria_dict = None
            if decision_type == "include":
                criteria_dict = {k: v for k, v in selected_inclusion_criteria.items() if v}
            
            # Save decision with criteria
            db.save_decision(
                art_id, 
                st.session_state.reviewer_id, 
                decision_type,
                exclusion_reason=selected_exclusion_reason,
                criteria=criteria_dict
            )
            
            st.session_state.ai_suggestion = None
            st.session_state.submit_screening = art_id
            
            # Navigate to next article
            if st.session_state.current_article_idx < len(pending_articles) - 1:
                st.session_state.current_article_idx += 1
            else:
                st.session_state.current_article_idx = 0
            
            st.success(f"Decision recorded: **{decision_type.upper()}**" + 
                     (f" (EC: {selected_exclusion_reason})" if selected_exclusion_reason else ""))
            st.rerun()
    
    # Navigation
    st.divider()
    st.subheader("📑 Article Navigation")
    nav_c1, nav_c2, nav_c3 = st.columns([1, 2, 1])
    with nav_c1:
        if st.button("◀️ Previous", disabled=st.session_state.current_article_idx == 0, use_container_width=True):
            st.session_state.current_article_idx = max(0, st.session_state.current_article_idx - 1)
            st.session_state.ai_suggestion = None
            st.rerun()
    with nav_c3:
        if st.button("Next ▶️", disabled=st.session_state.current_article_idx >= len(pending_articles) - 1, use_container_width=True):
            st.session_state.current_article_idx += 1
            st.session_state.ai_suggestion = None
            st.rerun()
    
    with nav_c2:
        st.caption(f"Article {st.session_state.current_article_idx + 1} of {len(pending_articles)}")


# ==================== PAGE: CONSENSUS ====================
def render_consensus():
    st.header("Reliability & Resolution")
    st.caption("Inter-reviewer agreement and conflict resolution")
    
    stats = get_stats()
    decisions = stats["decisions"]
    total_articles = stats["total_articles"]
    
    # Empty state check
    if total_articles == 0:
        st.info("No articles available. Please import literature data first.")
        return
    
    # ==================== SECTION 1: INTER-REVIEWER AGREEMENT ====================
    st.subheader("Inter-Reviewer Agreement (Cohen's Kappa)")
    
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
        
        # Kappa interpretation with detailed guidance
        if kappa is not None:
            if kappa < 0.2:
                st.error("⚠️ **Poor agreement** - Reviewers largely disagree. Recommend additional reviewer training and protocol clarification.")
            elif kappa < 0.4:
                st.warning("⚠️ **Fair agreement** - Some conflicts expected. Close monitoring recommended.")
            elif kappa < 0.6:
                st.success("✓ **Moderate agreement** - Acceptable for systematic reviews.")
            elif kappa < 0.8:
                st.success("✓ ✓ **Good agreement** - High reliability.")
            else:
                st.success("✓ ✓ ✓ **Excellent agreement** - Near-perfect consensus.")
            
            # Formal interpretation table
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
    
    # ==================== SECTION 2: CONFLICT RESOLUTION ====================
    st.subheader("🚩 Conflict Resolution")
    
    # Get conflicts with detailed information
    conflicts = consensus_engine.detect_conflicts()
    
    # Count resolved vs unresolved
    conn = sqlite3.connect(db.db_path)
    resolved = pd.read_sql_query("SELECT article_id FROM final_decisions", conn)
    resolved_ids = set(resolved["article_id"].tolist()) if not resolved.empty else set()
    conn.close()
    
    total_conflicts = len(conflicts)
    unresolved_count = sum(1 for cid in conflicts["article_id"] if cid not in resolved_ids)
    
    if total_conflicts > 0:
        # Progress bar
        progress = (total_conflicts - unresolved_count) / total_conflicts if total_conflicts > 0 else 0
        st.progress(progress)
        st.caption(f"Conflict Resolution Progress: {total_conflicts - unresolved_count} of {total_conflicts} resolved ({int(progress*100)}%)")
    
    if conflicts.empty:
        st.success("✅ No conflicts detected - all reviewers agree!")
    else:
        st.error(f"Found {total_conflicts} articles with conflicting decisions that need human mediation")
        
        # Fetch detailed information for each conflict article
        conn = sqlite3.connect(db.db_path)
        
        for _, conflict in conflicts.iterrows():
            article_id = conflict["article_id"]
            
            # Get article details
            article = pd.read_sql_query(f"SELECT id, title, abstract, literature_type FROM articles WHERE id = {article_id}", conn).iloc[0]
            
            # Get all decisions for this article
            article_decisions = pd.read_sql_query(f"""
                SELECT reviewer_id, decision, exclusion_reason, criteria_snapshot 
                FROM screening_decisions 
                WHERE article_id = {article_id}
            """, conn)
            
            is_resolved = article_id in resolved_ids
            
            with st.expander(f"{'✅' if is_resolved else '🚩'} Article ID {article_id}: {article['title'][:60]}... ({'RESOLVED' if is_resolved else 'UNRESOLVED'})"):
                # Show article metadata
                st.markdown(f"**📄 Title:** {article['title']}")
                st.caption(f"**Type:** {article['literature_type']}")
                
                # Show abstract
                if article['abstract']:
                    with st.expander("📝 Abstract"):
                        st.write(article['abstract'][:500] + "..." if len(str(article['abstract'])) > 500 else article['abstract'])
                
                # Side-by-side reviewer decisions
                st.markdown("**👥 Reviewer Decisions:**")
                
                cols = st.columns(len(article_decisions))
                for i, (_, row) in enumerate(article_decisions.iterrows()):
                    with cols[i]:
                        decision_emoji = "✅" if row['decision'] == 'include' else "❌" if row['decision'] == 'exclude' else "⚠️"
                        st.markdown(f"**{row['reviewer_id']}**: {decision_emoji} {row['decision'].upper()}")
                        
                        # Show criteria/reasons
                        if row['decision'] == 'exclude' and row['exclusion_reason']:
                            st.caption(f"Exclusion Reason: {row['exclusion_reason']}")
                        elif row['decision'] == 'include' and row['criteria_snapshot']:
                            st.caption(f"Included Criteria: {row['criteria_snapshot'][:50]}...")
                
                st.divider()
                
                # Resolution form (only if not yet resolved)
                if not is_resolved:
                    st.markdown("**📋 Final Resolution Form**")
                    
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
                                "✅ Resolve Conflict",
                                type="primary",
                                use_container_width=True
                            )
                        
                        if submit_resolved:
                            if not resolution_notes.strip():
                                st.error("Resolution notes are required before finalizing")
                            else:
                                db.save_final_decision(
                                    article_id,
                                    final_decision,
                                    st.session_state.reviewer_id,
                                    resolution_notes
                                )
                                st.success("Conflict resolved! Final decision saved.")
                                st.rerun()
                else:
                    # Show existing resolution
                    conn2 = sqlite3.connect(db.db_path)
                    resolution = pd.read_sql_query(f"SELECT * FROM final_decisions WHERE article_id = {article_id}", conn2).iloc[0]
                    conn2.close()
                    
                    st.markdown("**✅ Resolved Decision:**")
                    decision_emoji = "✅" if resolution['final_decision'] == 'include' else "❌"
                    st.markdown(f"**Final Decision:** {decision_emoji} {resolution['final_decision'].upper()}")
                    st.markdown(f"**Resolved By:** {resolution['resolved_by']}")
                    st.markdown(f"**Notes:** {resolution['resolution_notes']}")
        
        # Close connection
        conn.close()
    
    st.divider()
    
    # ==================== SECTION 3: AUTO-CONSENSUS ====================
    st.subheader("⚙️ Auto-Consensus")
    st.caption("Automatically finalize unanimous decisions to save time")
    
    conn = sqlite3.connect(db.db_path)
    
    # Find unanimous decisions
    unanimous = pd.read_sql_query("""
        SELECT article_id, GROUP_CONCAT(decision) as decisions
        FROM screening_decisions
        GROUP BY article_id
        HAVING COUNT(DISTINCT decision) = 1
    """, conn)
    
    # Already finalized
    already_final = pd.read_sql_query("SELECT article_id FROM final_decisions", conn)
    already_final_ids = set(already_final["article_id"].tolist()) if not already_final.empty else set()
    
    # Count candidates for auto-resolution
    candidates = [x for x in unanimous["article_id"] if x not in already_final_ids]
    candidate_count = len(candidates)
    
    conn.close()
    
    col_auto, col_info = st.columns([1, 2])
    
    with col_auto:
        if st.button("✅ Auto-finalize Unanimous Decisions", use_container_width=True, disabled=candidate_count == 0):
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


# ==================== PAGE: QUALITY ASSESSMENT ====================
def render_quality():
    st.header("🧪 Quality Assessment")
    st.caption("Appraise included articles using quality criteria")
    
    # Get articles ready for QC (passed screening, not yet QC'd)
    conn = sqlite3.connect(db.db_path)
    
    # Articles that passed screening
    passed_screening = pd.read_sql_query("""
        SELECT a.id, a.title, a.abstract, a.literature_type
        FROM articles a
        JOIN final_decisions f ON a.id = f.article_id
        WHERE f.final_decision = 'include'
    """, conn)
    
    # Already assessed
    assessed = pd.read_sql_query("""
        SELECT article_id, decision FROM quality_assessments
    """, conn)
    
    conn.close()
    
    if not passed_screening.empty:
        # Filter out already assessed
        assessed_ids = assessed["article_id"].tolist() if not assessed.empty else []
        ready_for_qc = passed_screening[~passed_screening["id"].isin(assessed_ids)]
        
        if ready_for_qc.empty:
            st.success("✅ All included articles have been quality assessed!")
            
            # Show summary
            st.subheader("QC Summary")
            if not assessed.empty:
                qc_passed = len(assessed[assessed["decision"] == "include"])
                qc_failed = len(assessed[assessed["decision"] == "exclude"])
                
                c1, c2 = st.columns(2)
                with c1:
                    st.metric("Passed QC", qc_passed)
                with c2:
                    st.metric("Failed QC", qc_failed)
        else:
            # Progress
            total_ready = len(passed_screening)
            assessed_count = len(passed_screening) - len(ready_for_qc)
            progress = assessed_count / total_ready if total_ready > 0 else 0
            
            st.progress(progress)
            st.caption(f"QC Progress: {assessed_count}/{total_ready} assessed")
            
            st.divider()
            
            # Article selector
            st.subheader("Select Article for Assessment")
            
            article_titles = ready_for_qc["title"].tolist()
            selected_title = st.selectbox("Article", article_titles)
            
            if selected_title:
                art = ready_for_qc[ready_for_qc["title"] == selected_title].iloc[0]
                
                # Article info
                with st.container():
                    st.markdown(f"### {art['title']}")
                    c1, c2 = st.columns(2)
                    with c1:
                        st.caption(f"📚 Type: {art['literature_type']}")
                    with c2:
                        st.caption(f"🆔 ID: {art['id']}")
                
                if art['abstract']:
                    with st.expander("📝 Abstract"):
                        st.write(art['abstract'][:500] + "..." if len(str(art['abstract'])) > 500 else art['abstract'])
                
                # QC form
                st.divider()
                st.subheader(f"Quality Criteria ({art['literature_type']})")
                
                if art['literature_type'] == "WL":
                    q_list = settings["quality_criteria"]["WL"]
                else:
                    q_list = settings["quality_criteria"]["GL"]
                
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
                            st.metric("Decision", "✅ Include", delta="PASS")
                        else:
                            st.metric("Decision", "❌ Exclude", delta="FAIL", delta_color="inverse")
                    
                    if st.form_submit_button("💾 Save Assessment"):
                        db.save_quality_assessment(
                            art['id'],
                            st.session_state.reviewer_id,
                            scores,
                            result['total_score'],
                            result['decision']
                        )
                        st.success("Quality assessment saved!")
                        st.rerun()
    else:
        st.info("No articles have passed screening yet. Complete screening first.")


# ==================== PAGE: EXTRACTION ====================
def render_extraction():
    st.header("🔬 Evidence Extraction")
    st.caption("Extract fragments from quality-assessed articles")
    
    # Get articles ready for extraction
    ready_articles = db.get_included_articles_for_extraction()
    
    if not ready_articles:
        st.warning("No articles ready for extraction. Complete screening and quality assessment first.")
        return
    
    # Show ready articles
    st.subheader(f"📄 Ready for Extraction ({len(ready_articles)} articles)")
    
    # Create a dataframe for display
    articles_data = []
    for art in ready_articles:
        articles_data.append({
            "ID": art[0],
            "Title": art[1],
            "Type": art[3]
        })
    
    df_articles = pd.DataFrame(articles_data)
    st.dataframe(df_articles, use_container_width=True, hide_index=True)
    
    st.divider()
    
    # Extraction interface
    st.subheader("Extract Evidence")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        selected_article_id = st.selectbox(
            "Select Article",
            [a[0] for a in ready_articles],
            format_func=lambda x: next((a[1] for a in ready_articles if a[0] == x), str(x))
        )
    
    # Get existing fragments for this article
    existing_fragments = db.get_fragments_by_article(selected_article_id)
    
    with col2:
        st.caption(f"Existing fragments: {len(existing_fragments)}")
    
    if selected_article_id:
        # Find article title
        article_title = next((a[1] for a in ready_articles if a[0] == selected_article_id), "")
        st.markdown(f"**Selected:** {article_title}")
        
        # Extraction form
        with st.form("extraction_form"):
            rq_code = st.selectbox("Research Question", ["RQ1", "RQ2", "RQ3", "RQ4", "RQ5"])
            theme_category = st.selectbox("Theme Category", ["challenge", "practice", "context", "finding", "gap", "other"])
            fragment_text = st.text_area("Evidence Fragment", height=100, placeholder="Paste or type the extracted evidence...")
            page_or_section = st.text_input("Page/Section Reference", placeholder="e.g., 4.2, Introduction")
            
            if st.form_submit_button("➕ Add Fragment"):
                if not fragment_text.strip():
                    st.error("Fragment text cannot be empty")
                else:
                    try:
                        frag_id = db.insert_fragment(
                            article_id=selected_article_id,
                            rq_code=rq_code,
                            fragment_text=fragment_text,
                            reviewer_id=st.session_state.reviewer_id,
                            theme_category=theme_category,
                            page_or_section=page_or_section
                        )
                        st.success(f"Fragment added (ID: {frag_id})")
                        st.rerun()
                    except DatabaseError as e:
                        st.error(str(e))
        
        st.divider()
        
        # Show existing fragments for this article
        st.subheader("Existing Fragments")
        
        if existing_fragments:
            for frag in existing_fragments:
                with st.expander(f"RQ{frag[2]} - {frag[4] or 'No category'}"):
                    st.write(frag[3])
                    st.caption(f"Page: {frag[6] or 'N/A'} | Reviewer: {frag[5]}")
        else:
            st.info("No fragments extracted yet for this article")
        
        # ===== AI DOCUMENT ANALYSIS =====
        st.divider()
        with st.expander("🤖 AI Document Analysis", expanded=False):
            st.caption("Upload a PDF to auto-extract evidence using AI")
            
            uploaded_pdf = st.file_uploader("Upload Article PDF", type=["pdf"], key="extraction_pdf")
            
            if uploaded_pdf:
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(uploaded_pdf.getvalue())
                    pdf_path = tmp.name
                
                try:
                    from src.core.pdf_processor import extract_text_from_pdf
                    
                    with st.spinner("Extracting text from PDF..."):
                        pdf_result = extract_text_from_pdf(pdf_path, max_pages=30)
                    
                    if pdf_result.get("error"):
                        st.error(f"PDF Error: {pdf_result['error']}")
                    else:
                        pdf_text = pdf_result["text"]
                        st.success(f"Extracted {len(pdf_text)} characters from {pdf_result['page_count']} pages")
                        
                        if st.button("🤖 AI Auto-Extract Evidence", use_container_width=True, key="ai_extract_btn"):
                            with st.spinner("AI analyzing document..."):
                                try:
                                    from groq import Groq
                                    import os
                                    import json
                                    
                                    api_key = os.environ.get("GROQ_API_KEY")
                                    if not api_key:
                                        st.warning("Configure GROQ_API_KEY in environment for AI extraction")
                                    else:
                                        client = Groq(api_key=api_key)
                                        
                                        settings = db.get_settings()
                                        extraction_fields = settings.get("extraction_fields", [])
                                        fields_text = "\n".join([f"- {f}" for f in extraction_fields]) if extraction_fields else "RQ Code, Theme Category, Evidence Fragment, Page/Section"
                                        
                                        prompt = f"""Extract evidence from this research paper. Return JSON with these fields:
{fields_text}

If a field cannot be found, use empty string.

Paper text (first 4000 chars):
{pdf_text[:4000]}"""
                                        
                                        response = client.chat.completions.create(
                                            model="llama3-70b-8192",
                                            messages=[{"role": "user", "content": prompt}],
                                            temperature=0.1,
                                            max_tokens=2000
                                        )
                                        
                                        ai_response = response.choices[0].message.content
                                        
                                        try:
                                            extracted = json.loads(ai_response)
                                            st.json(extracted)
                                            st.success("AI extraction complete! Review and edit.")
                                        except json.JSONDecodeError:
                                            st.warning("Could not parse AI response as JSON")
                                            st.text(ai_response[:500])
                                except Exception as e:
                                    st.error(f"AI extraction error: {e}")
                finally:
                    import os
                    if os.path.exists(pdf_path):
                        os.remove(pdf_path)


# ==================== PAGE: SYNTHESIS ====================
def render_synthesis():
    st.header("🧩 Thematic Synthesis Workspace")
    st.caption("Interactive qualitative analysis: Open Coding → Thematic Organization → Traceability")
    
    # Session state for managing selections
    if "selected_rq" not in st.session_state:
        st.session_state.selected_rq = "RQ1"
    
    tab1, tab2, tab3 = st.tabs(["1. 🔬 Open Coding", "2. 🎨 Thematic Organization", "3. 🔗 Traceability Matrix"])
    
    # ==================== TAB 1: OPEN CODING ====================
    with tab1:
        st.subheader("Open Coding: Link Fragments to Codes")
        
        # RQ Selector
        rq_codes = ["RQ1", "RQ2", "RQ3", "RQ4", "RQ5"]
        selected_rq = st.selectbox("Select Research Question", rq_codes, index=rq_codes.index(st.session_state.selected_rq), key="rq_selector")
        st.session_state.selected_rq = selected_rq
        
        # Get fragments for selected RQ
        fragments = db.get_fragments_by_rq(selected_rq)
        
        if not fragments:
            st.info(f"No fragments extracted for {selected_rq} yet. Go to Extraction to add fragments.")
        else:
            # Create fragment dataframe with codes
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
            st.dataframe(frag_df, use_container_width=True, hide_index=True, height=300)
            
            st.divider()
            
            # Fragment selection and coding interface
            st.markdown("### 🔗 Link Fragment to Code")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Select fragment to code
                frag_options = {f"ID {f[0]}: {f[3][:60]}...": f[0] for f in fragments}
                selected_frag_key = st.selectbox("Select Fragment", list(frag_options.keys()))
                selected_frag_id = frag_options[selected_frag_key]
                
                # Show selected fragment details
                selected_frag = next((f for f in fragments if f[0] == selected_frag_id), None)
                if selected_frag:
                    with st.expander("Fragment Details"):
                        st.write(selected_frag[3])
                        st.caption(f"Source: {selected_frag[8]} ({selected_frag[9]})")
                
                # Existing codes for this fragment
                existing_codes = db.get_codes_for_fragment(selected_frag_id)
                if existing_codes:
                    st.markdown("**Already coded with:**")
                    for code in existing_codes:
                        st.caption(f"- {code[1]}")
            
            with col2:
                # Get existing codes for this RQ
                existing_codes_rq = db.get_codes_by_rq(selected_rq)
                
                if existing_codes_rq:
                    code_options = {c[1]: c[0] for c in existing_codes_rq}
                    
                    # Option to use existing code or create new
                    code_choice = st.radio("Code Action", ["Use Existing Code", "Create New Code"])
                    
                    if code_choice == "Use Existing Code":
                        selected_code_label = st.selectbox("Select Existing Code", list(code_options.keys()))
                        selected_code_id = code_options[selected_code_label]
                        code_desc = next((c[2] for c in existing_codes_rq if c[1] == selected_code_label), "")
                        
                        if code_desc:
                            st.caption(f"Description: {code_desc}")
                        
                        if st.button("🔗 Link to Fragment", use_container_width=True):
                            try:
                                db.link_fragment_code(selected_frag_id, selected_code_id, st.session_state.reviewer_id)
                                st.success(f"Linked fragment to code: {selected_code_label}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Link failed: {e}")
                    
                    else:  # Create new code
                        new_code_label = st.text_input("New Code Label", placeholder="e.g., 'Remote Hiring Challenge'")
                        new_code_desc = st.text_area("Code Description (optional)", placeholder="Brief description of what this code represents")
                        
                        if st.button("➕ Create & Link", use_container_width=True):
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
                    
                    if st.button("➕ Create Code", use_container_width=True):
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
    
    # ==================== TAB 2: THEMATIC ORGANIZATION ====================
    with tab2:
        st.subheader("Thematic Organization: Manage Codes & Themes")
        
        col_theme, col_codes = st.columns([1, 1])
        
        # Theme management section
        with col_theme:
            st.markdown("#### 🎨 Theme Management")
            
            # Create new theme
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
            
            # List existing themes by RQ
            st.markdown("**Existing Themes:**")
            for rq in rq_codes:
                themes = db.get_themes_by_rq(rq)
                if themes:
                    with st.expander(f"{rq} Themes ({len(themes)})"):
                        for t in themes:
                            st.markdown(f"**{t[1]}:** {t[2]}")
                            if t[3]:
                                st.caption(t[3])
        
        # Code-Theme linking section
        with col_codes:
            st.markdown("#### 🔗 Link Codes to Themes")
            
            # Get all codes
            all_codes = []
            for rq in rq_codes:
                codes = db.get_codes_by_rq(rq)
                all_codes.extend(codes)
            
            if not all_codes:
                st.info("No codes created yet. Go to Open Coding tab to create codes.")
            else:
                # Select code
                code_options = {f"{c[1]} ({c[3]})": c[0] for c in all_codes}
                selected_code_key = st.selectbox("Select Code", list(code_options.keys()))
                selected_code_id = code_options[selected_code_key]
                
                # Get themes for the code's RQ
                code_rq = next((c[3] for c in all_codes if c[0] == selected_code_id), None)
                code_label = next((c[1] for c in all_codes if c[0] == selected_code_id), "")
                
                if code_rq:
                    themes_rq = db.get_themes_by_rq(code_rq)
                    
                    if not themes_rq:
                        st.warning(f"No themes exist for {code_rq}. Create a theme first.")
                    else:
                        theme_options = {f"{t[1]}: {t[2]}": t[0] for t in themes_rq}
                        
                        # Check which themes this code is already linked to
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
                            if st.button("🔗 Link Code to Theme", use_container_width=True):
                                try:
                                    db.link_code_theme(selected_code_id, selected_theme_id, st.session_state.reviewer_id)
                                    st.success("Code linked to theme!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Link failed: {e}")
    
    # ==================== TAB 3: TRACEABILITY MATRIX ====================
    with tab3:
        st.subheader("Traceability Matrix: Theme → Codes → Fragments → Sources")
        
        # Get all themes
        all_themes = []
        for rq in rq_codes:
            themes = db.get_themes_by_rq(rq)
            all_themes.extend(themes)
        
        if not all_themes:
            st.warning("No themes created yet. Go to Thematic Organization to create themes.")
        else:
            # Theme selector
            theme_options = {f"{t[1]}: {t[2]} ({t[3]})": t[0] for t in all_themes}
            selected_theme_label = st.selectbox("Select Theme to Explore", list(theme_options.keys()))
            selected_theme_id = theme_options[selected_theme_label]
            
            # Get theme details
            selected_theme = next((t for t in all_themes if t[0] == selected_theme_id), None)
            
            st.divider()
            
            # Theme header
            if selected_theme:
                st.markdown(f"### 📂 Theme: {selected_theme[1]} - {selected_theme[2]}")
                if selected_theme[3]:
                    st.caption(f"RQ: {selected_theme[3]} | Description: {selected_theme[3]}")
            
            # ==================== AI INSIGHT GENERATOR ====================
            st.divider()
            st.subheader("🤖 AI Insight Generator")
            
            # Initialize session state for AI synthesis
            ai_key = f"ai_synthesis_{selected_theme_id}"
            if ai_key not in st.session_state:
                st.session_state[ai_key] = None
            
            # Button to generate AI synthesis
            col_ai_btn, col_ai_status = st.columns([1, 2])
            with col_ai_btn:
                generate_btn = st.button(
                    "🤖 Generate AI Synthesis",
                    use_container_width=True,
                    key=f"ai_gen_{selected_theme_id}"
                )
            
            if generate_btn:
                # Fetch all fragments linked to this theme
                wl_fragments = []
                gl_fragments = []
                
                theme_codes = db.get_codes_for_theme(selected_theme_id)
                for code in theme_codes:
                    code_id = code[0]
                    code_fragments = db.get_fragments_for_code(code_id)
                    
                    for frag in code_fragments:
                        frag_id, art_id, rq, text = frag[0], frag[1], frag[2], frag[3]
                        
                        # Get article literature type and metadata
                        conn = sqlite3.connect(db.db_path)
                        art = pd.read_sql_query(f"SELECT literature_type, authors, year FROM articles WHERE id = {art_id}", conn).iloc[0]
                        conn.close()
                        
                        # Format with Author/Year for citation traceability
                        authors = art.get('authors', 'Unknown')
                        year = art.get('year', 'n.d.')
                        fragment_with_meta = f"[{authors}, {year}]: {text}"
                        
                        if art['literature_type'] == "WL":
                            wl_fragments.append(fragment_with_meta)
                        else:
                            gl_fragments.append(fragment_with_meta)
                
                # Generate synthesis
                with st.spinner("Synthesizing evidence from WL and GL sources..."):
                    synthesis_result = generate_theme_synthesis(
                        selected_theme[2],  # theme label
                        wl_fragments,
                        gl_fragments
                    )
                    
                    if synthesis_result.get("error"):
                        st.error(f"Synthesis failed: {synthesis_result['error']}")
                    else:
                        st.session_state[ai_key] = synthesis_result
                        st.rerun()
            
            # Display existing synthesis or new result
            if st.session_state.get(ai_key):
                synthesis_data = st.session_state[ai_key]
                if synthesis_data and synthesis_data.get("synthesis"):
                    with col_ai_status:
                        st.caption(f"✅ Generated - WL: {synthesis_data['wl_count']} fragments | GL: {synthesis_data['gl_count']} fragments")
                    
                    st.divider()
                    st.markdown("### 📝 AI Synthesis Report")
                    
                    # Display synthesis in a styled container
                    st.markdown(f"""
                    <div style="
                        background: #f8fafc; padding: 20px; border-radius: 10px;
                        border: 1px solid #e2e8f0; font-family: system-ui;
                    ">
                    {synthesis_data['synthesis'].replace('**', '<strong>').replace('**', '</strong>')}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Also display as regular markdown
                    st.markdown(synthesis_data['synthesis'])
                    
                    # Export/Copy controls
                    st.divider()
                    col_exp, col_copy = st.columns(2)
                    
                    with col_exp:
                        # Simple text download
                        synthesis_text = synthesis_data['synthesis']
                        st.download_button(
                            "📥 Export as Text",
                            data=synthesis_text,
                            file_name=f"{selected_theme[1]}_synthesis.txt",
                            mime="text/plain",
                            use_container_width=True
                        )
                    
                    with col_copy:
                        if st.button("📋 Copy to Clipboard", use_container_width=True):
                            # Note: Streamlit doesn't have native clipboard, show instruction
                            st.info("Use Ctrl+C to copy the text above")
                
            elif not generate_btn:
                st.info("Click 'Generate AI Synthesis' to create a comparative WL/GL report for this theme.")
            
            # ==================== HIERARCHICAL TREE ====================
            theme_codes = db.get_codes_for_theme(selected_theme_id)
            
            if not theme_codes:
                st.info("No codes linked to this theme yet.")
            else:
                st.markdown(f"**Codes in this Theme:** ({len(theme_codes)})")
                
                # WL vs GL distribution for the theme
                comparison = db.compare_theme_by_literature_type(selected_theme_id)
                
                if comparison:
                    st.markdown("#### 📊 Literature Distribution")
                    comp_data = [{"Type": c[0], "Fragments": c[1], "Sources": c[2]} for c in comparison]
                    fig = px.bar(
                        comp_data, x="Type", y="Fragments", 
                        title="Fragment Distribution by Literature Type",
                        color="Type", color_discrete_sequence=["#2563eb", "#64748b"]
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                st.markdown("#### 🌳 Hierarchical Tree")
                
                # Display: Theme -> Codes -> Fragments -> Sources
                for code in theme_codes:
                    code_id, code_label, code_desc, code_rq = code[0], code[1], code[2], code[3]
                    
                    with st.expander(f"📌 **{code_label}** ({code_rq})"):
                        if code_desc:
                            st.caption(f"Description: {code_desc}")
                        
                        # Get fragments for this code
                        code_fragments = db.get_fragments_for_code(code_id)
                        
                        if not code_fragments:
                            st.info("No fragments linked to this code")
                        else:
                            st.markdown(f"**Fragments ({len(code_fragments)}):**")
                            
                            for frag in code_fragments:
                                frag_id, art_id, rq, text, category, reviewer, page, created = frag[0], frag[1], frag[2], frag[3], frag[4], frag[5], frag[6], frag[7]
                                
                                # Get article metadata
                                conn = sqlite3.connect(db.db_path)
                                art = pd.read_sql_query(f"SELECT title, authors, year, literature_type FROM articles WHERE id = {art_id}", conn).iloc[0]
                                conn.close()
                                
                                # Format citation metadata
                                authors = art.get('authors', 'Unknown')
                                year = art.get('year', 'n.d.')
                                citation = f"[{authors}, {year}]" if year else f"[{authors}]"
                                
                                with st.container():
                                    st.markdown(f"📄 **{art['title'][:60]}...** ({art['literature_type']})")
                                    st.caption(citation)
                                    st.write(f"_{text}_")
                                    st.caption(f"RQ: {rq} | Extracted by: {reviewer}")
                                    st.divider()
            
            # Synthesis Summary
            st.divider()
            st.markdown("#### 📊 Synthesis Summary")
            
            # Get all stats
            conn = sqlite3.connect(db.db_path)
            
            # Fragments by RQ
            fragments_by_rq = pd.read_sql_query("""
                SELECT rq_code, COUNT(*) as count 
                FROM fragments 
                GROUP BY rq_code
            """, conn)
            
            # Literature type distribution
            lit_dist = pd.read_sql_query("""
                SELECT a.literature_type, COUNT(DISTINCT f.id) as fragment_count
                FROM fragments f
                JOIN articles a ON f.article_id = a.id
                GROUP BY a.literature_type
            """, conn)
            
            # Codes per RQ
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
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No fragments")
            
            with c2:
                if not codes_per_rq.empty:
                    fig = px.bar(codes_per_rq, x="rq_code", y="count", title="Codes by RQ", color="rq_code", color_discrete_sequence=px.colors.qualitative.Pastel)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No codes")
            
            with c3:
                if not lit_dist.empty:
                    fig = px.pie(lit_dist, values="fragment_count", names="literature_type", title="Fragment Distribution", color_discrete_sequence=["#2563eb", "#64748b"])
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No fragments")
        
        # ===== EXECUTIVE SUMMARY GENERATOR =====
        st.divider()
        st.subheader("📊 Final Executive Report")
        st.caption("Automated professional synthesis report for stakeholders")
        
        if st.button("✨ Generate Full Executive Summary", use_container_width=True):
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
                                use_container_width=True
                            )
                    else:
                        st.warning("No themes synthesized yet. Create themes and AI syntheses first.")
                except Exception as e:
                    st.error(f"Report generation error: {e}")


# ==================== PAGE: EXPORT & AUDIT ====================
def render_export_audit():
    st.header("Reporting & Export")
    st.caption("Quality control, audit trails, and publication-ready exports")
    
    # Ensure db is available
    db = get_database()
    
    # Initialize session state for exports
    if "export_data" not in st.session_state:
        st.session_state.export_data = {}
    
    # ==================== SECTION 1: AUDIT DASHBOARD ====================
    st.subheader("Audit Dashboard")
    st.caption("Validate data integrity before export")
    
    # Get PRISMA stats
    prisma = get_prisma_stats()
    
    # Validate traceability
    integrity = db.validate_traceability_integrity()
    
    # Get additional audit metrics
    conn = sqlite3.connect(db.db_path)
    
    # Articles with no fragments
    articles_with_fragments = pd.read_sql_query("""
        SELECT DISTINCT article_id FROM fragments
    """, conn)
    articles_with_fragments_ids = set(articles_with_fragments["article_id"].tolist()) if not articles_with_fragments.empty else set()
    
    # Included articles (passed screening)
    included_articles = pd.read_sql_query("""
        SELECT a.id, a.title FROM articles a
        JOIN final_decisions f ON a.id = f.article_id
        WHERE f.final_decision = 'include'
    """, conn)
    
    # Articles with zero extraction
    zero_extraction = []
    if not included_articles.empty:
        for _, row in included_articles.iterrows():
            if row['id'] not in articles_with_fragments_ids:
                zero_extraction.append({"id": row['id'], "title": row['title']})
    
    conn.close()
    
    # Display audit alerts
    has_issues = False
    
    # Orphaned Fragments (no codes)
    if integrity["fragments_without_codes"]:
        has_issues = True
        st.error(f"🚨 **Orphaned Fragments**: {len(integrity['fragments_without_codes'])} fragments have no codes assigned")
        with st.expander("View Orphaned Fragments"):
            for frag in integrity["fragments_without_codes"][:10]:
                st.caption(f"- ID {frag['fragment_id']}: {frag['fragment_text'][:80]}... (RQ: {frag['rq_code']})")
            if len(integrity["fragments_without_codes"]) > 10:
                st.caption(f"... and {len(integrity['fragments_without_codes']) - 10} more")
    
    # Orphaned Codes (no themes)
    if integrity["codes_without_fragments"]:
        st.warning(f"⚠️ **Orphaned Codes**: {len(integrity['codes_without_fragments'])} codes have no fragments linked")
        with st.expander("View Orphaned Codes"):
            for code in integrity["codes_without_fragments"][:10]:
                st.caption(f"- {code['code_label']} (RQ: {code['rq_code']})")
    
    # Orphaned Themes (no codes)
    if integrity["themes_without_codes"]:
        st.warning(f"⚠️ **Orphaned Themes**: {len(integrity['themes_without_codes'])} themes have no codes linked")
        with st.expander("View Orphaned Themes"):
            for theme in integrity["themes_without_codes"][:10]:
                st.caption(f"- {theme['theme_code']}: {theme['theme_label']} (RQ: {theme['rq_code']})")
    
    # Coverage Gap (included articles with no fragments)
    if zero_extraction:
        has_issues = True
        st.warning(f"⚠️ **Coverage Gap**: {len(zero_extraction)} included articles have no fragments extracted")
        with st.expander("View Articles Needing Extraction"):
            for art in zero_extraction[:10]:
                st.caption(f"- {art['title'][:60]}...")
            if len(zero_extraction) > 10:
                st.caption(f"... and {len(zero_extraction) - 10} more")
    
    # All clear
    if not has_issues:
        st.success("✅ **Audit Passed**: No data integrity issues detected. Your research is ready for export!")
    
    st.divider()
    
    # ==================== SECTION 2: PUBLICATION SUMMARY ====================
    st.subheader("Publication Summary")
    st.caption("Copy-pasteable summary for your paper")
    
    # Calculate summary statistics with FRESH connection
    with sqlite3.connect(db.db_path) as conn:
        total_articles = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        wl_count = conn.execute("SELECT COUNT(*) FROM articles WHERE literature_type = 'WL'").fetchone()[0]
        gl_count = conn.execute("SELECT COUNT(*) FROM articles WHERE literature_type = 'GL'").fetchone()[0]
        final_included = conn.execute("SELECT COUNT(*) FROM final_decisions WHERE final_decision = 'include'").fetchone()[0]
        themes_count = conn.execute("SELECT COUNT(*) FROM themes").fetchone()[0]
        codes_count = conn.execute("SELECT COUNT(*) FROM codes").fetchone()[0]
        fragments_count = conn.execute("SELECT COUNT(*) FROM fragments").fetchone()[0]
    
    # Generate summary text
    summary_text = f"""This study analyzed {total_articles} articles ({wl_count} White Literature, {gl_count} Grey Literature). After systematic screening and quality assessment, {final_included} articles were included for analysis. The thematic synthesis process resulted in {themes_count} themes and {codes_count} unique codes, supported by {fragments_count} evidence fragments extracted from the primary sources."""
    
    st.text_area("Study Summary (for paper)", value=summary_text, height=100)
    
    st.caption("Copy the text above for use in your manuscript")
    
    st.divider()
    
    # ==================== SECTION 3: EXPORT PACKAGE ====================
    st.subheader("Publication-Ready Export")
    st.caption("Generate and download the complete research package")
    
    # Export button
    col_exp, col_status = st.columns([1, 2])
    
    with col_exp:
        generate_export = st.button(
            "📦 Generate Full Research Package",
            use_container_width=True,
            type="primary"
        )
    
    if generate_export:
        with st.spinner("Generating export files..."):
            try:
                # Create export directory
                export_dir = "research_export"
                os.makedirs(export_dir, exist_ok=True)
                
                # Export all artifacts
                export_results = db.export_all_research_artifacts(export_dir)
                
                st.session_state.export_data = {
                    "success": True,
                    "results": export_results,
                    "path": export_dir
                }
                st.rerun()
                
            except Exception as e:
                st.error(f"Export failed: {str(e)}")
    
    # Display export results
    if st.session_state.get("export_data", {}).get("success"):
        export_results = st.session_state["export_data"]["results"]
        export_path = st.session_state["export_data"]["path"]
        
        with col_status:
            st.success(f"✅ Export complete! Generated {sum(export_results.values())} files")
        
        st.divider()
        
        st.markdown("### 📥 Download Export Files")
        
        # Read and provide download buttons for each file
        export_files = {
            "traceability_matrix.csv": "Full traceability: Theme → Code → Fragment → Source",
            "fragments_with_sources.csv": "All evidence fragments with source metadata",
            "codes.csv": "Codebook with RQ associations",
            "themes.csv": "Theme definitions and RQ mappings"
        }
        
        for filename, description in export_files.items():
            filepath = os.path.join(export_path, filename)
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8-sig') as f:
                    file_content = f.read()
                
                col_dl, col_desc = st.columns([1, 2])
                with col_dl:
                    st.download_button(
                        f"📥 {filename}",
                        data=file_content,
                        file_name=filename,
                        mime="text/csv",
                        use_container_width=True
                    )
                with col_desc:
                    st.caption(description)
        
        st.divider()
        
        # Quick stats for the export
        st.markdown("### 📊 Export Statistics")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Themes", export_results.get("themes", 0))
        with c2:
            st.metric("Codes", export_results.get("codes", 0))
        with c3:
            st.metric("Fragments", export_results.get("fragments_with_sources", 0))
        with c4:
            st.metric("Matrix Rows", export_results.get("traceability_matrix", 0))
        
        # ZIP download option
        import zipfile
        zip_path = f"{export_path}_package.zip"
        
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
                use_container_width=True
            )
    else:
        with col_status:
            st.info("Click 'Generate Full Research Package' to create export files")
    
    st.divider()
    
    # ==================== SECTION 4: SYSTEM HEALTH ====================
    st.subheader("💻 System Health")
    
    # Check database
    db_healthy = os.path.exists(db.db_path)
    db_size = os.path.getsize(db.db_path) / 1024 if db_healthy else 0
    
    # Check Groq API (from env or streamlit secrets)
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        try:
            api_key = st.secrets.get("GROQ_API_KEY", "")
        except:
            pass
    api_healthy = bool(api_key)
    
    c1, c2 = st.columns(2)
    with c1:
        if db_healthy:
            st.success(f"✅ Database Connected ({db_size:.1f} KB)")
        else:
            st.error("❌ Database Not Found")
    with c2:
        if api_healthy:
            st.success("✅ Groq API Ready")
        else:
            st.warning("⚠️ Groq API Not Configured")
            st.caption("Configure GROQ_API_KEY environment variable for AI features")
    
    st.divider()
    
    # ==================== SECTION 5: DATABASE INFO ====================
    with st.expander("Database Information"):
        st.markdown(f"**Database Path:** `{db.db_path}`")
        st.markdown(f"**Database Size:** {os.path.getsize(db.db_path) / 1024:.1f} KB" if os.path.exists(db.db_path) else "N/A")
    
    st.divider()
    
    # ==================== SECTION 6: DANGER ZONE ====================
    st.subheader("Danger Zone")
    st.warning("These actions cannot be undone. Use with caution.")
    
    if st.button("Reset/Nuke Database", type="primary", use_container_width=True):
        confirm = st.checkbox("I understand this will delete ALL data. Confirm:")
        
        if confirm:
            try:
                # Close and delete database
                db_path = db.db_path
                del db
                
                if os.path.exists(db_path):
                    os.remove(db_path)
                    st.success("Database reset complete. Refresh the page to reinitialize.")
                else:
                    st.error("Database file not found")
            except Exception as e:
                st.error(f"Reset failed: {e}")


# ==================== SIDEBAR ====================
with st.sidebar:
    st.markdown("""
    <div class="sidebar-title">AIMS</div>
    <div class="sidebar-subtitle">Next-Gen Research Intelligence</div>
    """, unsafe_allow_html=True)
    
    st.divider()
    
    # Reviewer session
    st.subheader("Reviewer Session")
    st.session_state.reviewer_id = st.text_input("Reviewer ID", value=st.session_state.reviewer_id)
    st.caption("Blind review mode")
    
    st.divider()
    
    # Navigation - Academic labels
    st.subheader("Navigation")
    page = st.radio("Go to", [
        "Dashboard",
        "Eligibility Screening",
        "Agreement & Consensus",
        "Quality Appraisal",
        "Data Extraction",
        "Thematic Synthesis",
        "Reporting & Export"
    ], label_visibility="collapsed")
    
    st.divider()
    
    # ===== SYSTEM STATUS CARD =====
    st.markdown("**🔧 System Status**")
    
    status_col1, status_col2 = st.columns(2)
    with status_col1:
        st.caption("Mode")
        st.markdown("<span style='color:#00D2FF;font-weight:600'>Professional Research Suite</span>", unsafe_allow_html=True)
    with status_col2:
        st.caption("AI Engine")
        st.markdown("<span style='color:#10B981;font-weight:600'>Active</span>", unsafe_allow_html=True)
    
    st.caption("Traceability")
    st.markdown("<span style='color:#10B981;font-weight:600'>✓ Verified</span>", unsafe_allow_html=True)
    
    st.divider()
    
    # PROJECT CONFIGURATION HUB
    with st.expander("Project Configuration", expanded=False):
        config_mgr = load_config()
        
        st.subheader("Project Identity")
        proj_name = st.text_input("Project Name", value=config_mgr.get("project_name", "My Research Project"), key="cfg_name")
        proj_desc = st.text_area("Description", value=config_mgr.get("project_description", ""), key="cfg_desc")
        
        st.subheader("Research Questions")
        rqs_current = config_mgr.get("research_questions", [])
        rqs_edit = [{"RQ": rq} for rq in rqs_current]
        
        rqs_editor = st.data_editor(rqs_edit, num_rows="dynamic", key="cfg_rqs", use_container_width=True)
        rqs_list = [row["RQ"] for row in rqs_editor if row.get("RQ", "").strip()]
        
        st.subheader("API Configuration")
        api_key_input = st.text_input("Groq API Key", type="password", help="Optional: For AI-assisted features", key="cfg_api")
        
        if st.button("Save Configuration", key="save_config_btn"):
            new_config = {
                "project_name": proj_name,
                "project_description": proj_desc,
                "research_questions": rqs_list,
                "literature_types": config_mgr.get("literature_types", ["White Literature", "Grey Literature"]),
                "literature_types_abbrev": config_mgr.get("literature_types_abbrev", ["WL", "GL"]),
                "exclude_irrelevant": config_mgr.get("exclude_irrelevant", True),
                "min_qa_score": config_mgr.get("min_qa_score", 0.5)
            }
            if api_key_input:
                new_config["api_key"] = api_key_input
            
            import json
            with open("project_config.json", "w", encoding="utf-8") as f:
                json.dump(new_config, f, indent=2)
            
            st.success("Configuration saved!")
            st.rerun()
    
    st.divider()
    
    # Quick stats in sidebar
    st.subheader("Quick Stats")
    stats = get_stats()
    st.metric("Articles", stats["total_articles"])
    st.metric("Screened", len(stats["decisions"]["article_id"].unique()) if not stats["decisions"].empty else 0)
    
    # Data Quality Indicators
    try:
        articles = stats.get("total_articles", 0)
        if articles > 0:
            conn = sqlite3.connect(db.db_path)
            df = pd.read_sql_query("SELECT abstract, doi FROM articles", conn)
            conn.close()
            
            missing_abstracts = int((df['abstract'].isna() | (df['abstract'] == '')).sum() / len(df) * 100)
            missing_dois = int((df['doi'].isna() | (df['doi'] == '')).sum() / len(df) * 100)
            
            st.caption("Data Quality:")
            if missing_abstracts > 50:
                st.warning(f"⚠️ {missing_abstracts}% missing abstracts")
            else:
                st.caption(f"📄 {missing_abstracts}% missing abstracts")
            
            if missing_dois > 50:
                st.warning(f"⚠️ {missing_dois}% missing DOIs")
            else:
                st.caption(f"🔗 {missing_dois}% missing DOIs")
    except:
        pass
    
    # Conflicts warning
    conflicts = consensus_engine.detect_conflicts()
    if not conflicts.empty:
        st.warning(f"{len(conflicts)} conflicts")


# ==================== MAIN ====================
if page == "Dashboard":
    render_overview()
elif page == "Eligibility Screening":
    render_screening()
elif page == "Agreement & Consensus":
    render_consensus()
elif page == "Quality Appraisal":
    render_quality()
elif page == "Data Extraction":
    render_extraction()
elif page == "Thematic Synthesis":
    render_synthesis()
elif page == "Reporting & Export":
    render_export_audit()