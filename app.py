import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import plotly.graph_objects as go

# Core
from src.core.database import Database, DatabaseError
from src.core.analytics import load_decisions_dataframe, prepare_kappa
from src.core.consensus import ConsensusEngine
from src.core.quality import QualityEngine

# Extras
from src.core.ai_handler import get_ai_suggestion
from src.core.config_manager import load_config


# ==================== CONFIG ====================
st.set_page_config(
    page_title="AIMS - AI-Powered MLR Pipeline",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🔬"
)

# Custom CSS for modern look
st.markdown("""
<style>
    .block-container {padding-top: 2rem; padding-bottom: 2rem;}
    .stMetric {background: #f0f2f6; padding: 1rem; border-radius: 0.5rem;}
    .metric-card {background: #ffffff; border: 1px solid #e0e0e0; padding: 1rem; border-radius: 0.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1);}
    .section-header {font-size: 1.5rem; font-weight: 600; margin-bottom: 1rem; color: #1f2937;}
    .badge {padding: 0.25rem 0.75rem; border-radius: 1rem; font-size: 0.875rem; font-weight: 500;}
    .badge-include {background: #d1fae5; color: #065f46;}
    .badge-exclude {background: #fee2e2; color: #991b1b;}
    .badge-pending {background: #fef3c7; color: #92400e;}
    .badge-uncertain {background: #e0e7ff; color: #3730a3;}
</style>
""", unsafe_allow_html=True)


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
    st.header("📊 Overview")
    st.caption("Real-time pipeline statistics and progress tracking")
    
    stats = get_stats()
    decisions = stats["decisions"]
    final = stats["final"]
    qa = stats["qa"]
    
    # Key metrics row
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("Total Articles", stats["total_articles"])
    with c2:
        screened = len(decisions["article_id"].unique()) if not decisions.empty else 0
        st.metric("Screened", screened)
    with c3:
        included = len(final[final["final_decision"] == "include"]) if not final.empty else 0
        st.metric("Included", included)
    with c4:
        excluded_final = len(final[final["final_decision"] == "exclude"]) if not final.empty else 0
        st.metric("Excluded (Final)", excluded_final)
    with c5:
        pending = stats["total_articles"] - screened
        st.metric("Pending", pending)
    
    st.divider()
    
    # Charts row
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.subheader("Screening Progress")
        if not decisions.empty:
            # Decision distribution
            decision_counts = decisions["decision"].value_counts()
            fig_pie = px.pie(
                values=decision_counts.values,
                names=decision_counts.index,
                title="Decision Distribution",
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            fig_pie.update_layout(showlegend=True, height=300)
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No screening decisions yet")
    
    with col_right:
        st.subheader("Literature Type Distribution")
        conn = sqlite3.connect(db.db_path)
        articles = pd.read_sql_query("SELECT literature_type FROM articles", conn)
        conn.close()
        
        if not articles.empty:
            lit_dist = articles["literature_type"].value_counts()
            fig_bar = px.bar(
                x=lit_dist.index,
                y=lit_dist.values,
                title="White vs Grey Literature",
                labels={"x": "Type", "y": "Count"},
                color=lit_dist.values,
                color_continuous_scale="Blues"
            )
            fig_bar.update_layout(height=300, showlegend=False)
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("No articles imported")
    
    st.divider()
    
    # Research Questions overview
    st.subheader("Research Questions")
    rqs = settings["research_questions"]
    for i, rq in enumerate(rqs, 1):
        st.markdown(f"**RQ{i}:** {rq}")
    
    st.divider()
    
    # Quick actions
    st.subheader("Quick Actions")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("📥 Import Data", use_container_width=True):
            st.info("Use the Data Exchange section to import CSV files")
    with c2:
        if st.button("🔄 Refresh Stats", use_container_width=True):
            st.rerun()
    with c3:
        if st.button("📊 Generate Report", use_container_width=True):
            st.info("Report generation coming soon")


# ==================== PAGE: SCREENING ====================
def render_screening():
    st.header("🔍 Screening")
    st.caption(f"Reviewer: **{st.session_state.reviewer_id}** | Blind review mode enabled")
    
    stats = get_stats()
    decisions = stats["decisions"]
    
    # Progress bar
    total = stats["total_articles"]
    screened_count = len(decisions["article_id"].unique()) if not decisions.empty else 0
    progress = screened_count / total if total > 0 else 0
    
    st.progress(progress)
    st.caption(f"Progress: {screened_count}/{total} articles screened ({int(progress*100)}%)")
    
    st.divider()
    
    # Get pending articles for this reviewer
    pending_articles = db.get_pending_articles(st.session_state.reviewer_id)
    
    if not pending_articles:
        st.success("✅ All articles have been reviewed!")
        
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
    st.subheader("📄 Current Article")
    
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
    
    # Action buttons
    st.subheader("Decision")
    
    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        if st.button("✅ Include", key=f"inc_{art_id}", use_container_width=True):
            db.save_decision(art_id, st.session_state.reviewer_id, "include")
            st.session_state.ai_suggestion = None
            if st.session_state.current_article_idx < len(pending_articles) - 1:
                st.session_state.current_article_idx += 1
            else:
                st.session_state.current_article_idx = 0
            st.rerun()
    
    with c2:
        if st.button("❌ Exclude", key=f"exc_{art_id}", use_container_width=True):
            db.save_decision(art_id, st.session_state.reviewer_id, "exclude")
            st.session_state.ai_suggestion = None
            if st.session_state.current_article_idx < len(pending_articles) - 1:
                st.session_state.current_article_idx += 1
            else:
                st.session_state.current_article_idx = 0
            st.rerun()
    
    with c3:
        if st.button("⚠️ Uncertain", key=f"unc_{art_id}", use_container_width=True):
            db.save_decision(art_id, st.session_state.reviewer_id, "uncertain")
            st.session_state.ai_suggestion = None
            if st.session_state.current_article_idx < len(pending_articles) - 1:
                st.session_state.current_article_idx += 1
            else:
                st.session_state.current_article_idx = 0
            st.rerun()
    
    with c4:
        if st.button("🤖 AI Analyze", key=f"ai_{art_id}", use_container_width=True, type="secondary"):
            with st.spinner("Analyzing with AI..."):
                st.session_state.ai_suggestion = get_ai_suggestion(title, abstract or "", settings)
            st.rerun()
    
    # Navigation
    st.divider()
    nav_c1, nav_c2, nav_c3 = st.columns([1, 2, 1])
    with nav_c1:
        if st.button("◀️ Previous", disabled=st.session_state.current_article_idx == 0):
            st.session_state.current_article_idx = max(0, st.session_state.current_article_idx - 1)
            st.session_state.ai_suggestion = None
            st.rerun()
    with nav_c3:
        if st.button("Next ▶️", disabled=st.session_state.current_article_idx >= len(pending_articles) - 1):
            st.session_state.current_article_idx += 1
            st.session_state.ai_suggestion = None
            st.rerun()
    
    with nav_c2:
        st.caption(f"Article {st.session_state.current_article_idx + 1} of {len(pending_articles)}")


# ==================== PAGE: CONSENSUS ====================
def render_consensus():
    st.header("🤝 Consensus & Agreement")
    st.caption("Inter-reviewer agreement and conflict resolution")
    
    stats = get_stats()
    decisions = stats["decisions"]
    
    # Kappa calculation
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
        
        # Kappa interpretation
        if kappa is not None:
            if kappa < 0.2:
                st.warning("⚠️ Poor agreement - consider additional reviewer training")
            elif kappa < 0.4:
                st.info("ℹ️ Fair agreement - some conflicts expected")
            elif kappa < 0.6:
                st.success("✓ Moderate agreement")
            elif kappa < 0.8:
                st.success("✓ Good agreement")
            else:
                st.success("✓ Excellent agreement")
    else:
        st.warning("Not enough data for kappa calculation. Need at least 2 reviewers with overlapping articles.")
    
    st.divider()
    
    # Conflicts detection
    st.subheader("🚩 Conflicts")
    
    conflicts = consensus_engine.detect_conflicts()
    
    if conflicts.empty:
        st.success("✅ No conflicts detected - all reviewers agree!")
    else:
        st.error(f"Found {len(conflicts)} articles with conflicting decisions")
        
        # Display conflicts
        for _, conflict in conflicts.iterrows():
            with st.expander(f"Article ID: {conflict['article_id']} - {conflict['title'][:50]}..."):
                decisions_str = conflict['decisions'].split(',')
                for d in decisions_str:
                    reviewer, decision = d.split(':')
                    st.write(f"  **{reviewer}**: {decision}")
                
                # Resolution form
                with st.form(f"resolve_{conflict['article_id']}"):
                    c1, c2 = st.columns(2)
                    with c1:
                        final_decision = st.radio("Final Decision", ["include", "exclude"], key=f"fd_{conflict['article_id']}")
                    with c2:
                        notes = st.text_input("Resolution Notes", key=f"notes_{conflict['article_id']}")
                    
                    if st.form_submit_button("Resolve Conflict"):
                        db.save_final_decision(
                            conflict['article_id'],
                            final_decision,
                            st.session_state.reviewer_id,
                            notes
                        )
                        st.success("Conflict resolved!")
                        st.rerun()
    
    st.divider()
    
    # Auto-resolve section
    st.subheader("⚙️ Auto-Resolution")
    
    if st.button("Auto-Resolve Consensus (Same Decisions)"):
        count = consensus_engine.auto_resolve_consensus(db)
        st.success(f"Auto-resolved {count} articles")
        st.rerun()
    
    st.caption("This will automatically finalize decisions for articles where all reviewers have the same decision.")


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


# ==================== PAGE: SYNTHESIS ====================
def render_synthesis():
    st.header("🧩 Synthesis & Traceability")
    st.caption("Explore themes, codes, and evidence traceability")
    
    tab1, tab2, tab3 = st.tabs(["🔍 Traceability Explorer", "🎨 Theme Explorer", "📊 Synthesis Summary"])
    
    with tab1:
        st.subheader("Traceability: RQ → Fragments → Sources")
        
        # RQ selector
        rq_code = st.selectbox("Select Research Question", ["RQ1", "RQ2", "RQ3", "RQ4", "RQ5"])
        
        # Get fragments for this RQ
        fragments = db.get_fragments_by_rq(rq_code)
        
        if not fragments:
            st.info(f"No fragments extracted for {rq_code} yet")
        else:
            st.caption(f"Found {len(fragments)} fragments")
            
            # Group by source
            for frag in fragments:
                frag_id, art_id, rq, text, category, reviewer, page, created, art_title, lit_type = frag
                
                with st.expander(f"📄 {art_title[:60]}... ({lit_type})"):
                    st.markdown(f"**RQ:** {rq}")
                    st.markdown(f"**Category:** {category or 'N/A'}")
                    st.markdown(f"**Fragment:** {text}")
                    st.caption(f"Page: {page or 'N/A'} | Extracted by: {reviewer}")
    
    with tab2:
        st.subheader("Theme Explorer: Theme → Codes → Fragments → Sources")
        
        # Get all themes
        all_themes = []
        for rq in ["RQ1", "RQ2", "RQ3", "RQ4", "RQ5"]:
            themes = db.get_themes_by_rq(rq)
            all_themes.extend(themes)
        
        if not all_themes:
            st.info("No themes created yet. Create themes in the Extraction section.")
        else:
            theme_options = {f"{t[1]}: {t[2]}": t[0] for t in all_themes}
            selected_theme_label = st.selectbox("Select Theme", list(theme_options.keys()))
            selected_theme_id = theme_options[selected_theme_label]
            
            # Get fragments for this theme
            theme_fragments = db.get_theme_fragments_with_sources(selected_theme_id)
            
            if not theme_fragments:
                st.info("No fragments linked to this theme")
            else:
                st.caption(f"Found {len(theme_fragments)} fragments")
                
                # WL vs GL comparison
                comparison = db.compare_theme_by_literature_type(selected_theme_id)
                
                if comparison:
                    st.subheader("WL vs GL Distribution")
                    comp_data = [{"Type": c[0], "Fragments": c[1], "Sources": c[2]} for c in comparison]
                    fig = px.bar(comp_data, x="Type", y="Fragments", title="Fragment Distribution by Literature Type", color="Type", color_discrete_sequence=["#2563eb", "#64748b"])
                    st.plotly_chart(fig, use_container_width=True)
                
                st.divider()
                
                # Display fragments
                for tf in theme_fragments:
                    text, rq, source_id, source_title, lit_type, theme_code, theme_label = tf
                    with st.container():
                        st.markdown(f"**Source:** {source_title[:50]}... ({lit_type})")
                        st.write(f"_{text}_")
                        st.caption(f"RQ: {rq} | Theme: {theme_code}")
                        st.divider()
    
    with tab3:
        st.subheader("Synthesis Summary")
        
        # Get all stats
        conn = sqlite3.connect(db.db_path)
        
        # Fragments by RQ
        fragments_df = pd.read_sql_query("SELECT rq_code, COUNT(*) as count FROM fragments GROUP BY rq_code", conn)
        
        # Literature type distribution
        lit_dist = pd.read_sql_query("""
            SELECT a.literature_type, COUNT(DISTINCT f.id) as fragment_count
            FROM fragments f
            JOIN articles a ON f.article_id = a.id
            GROUP BY a.literature_type
        """, conn)
        
        conn.close()
        
        # Display
        c1, c2 = st.columns(2)
        
        with c1:
            if not fragments_df.empty:
                fig = px.bar(fragments_df, x="rq_code", y="count", title="Fragments by Research Question", color="rq_code", color_discrete_sequence=px.colors.qualitative.Set2)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No fragments extracted")
        
        with c2:
            if not lit_dist.empty:
                fig = px.pie(lit_dist, values="fragment_count", names="literature_type", title="Fragment Distribution by Literature Type", color_discrete_sequence=["#2563eb", "#64748b"])
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No fragments extracted")


# ==================== SIDEBAR ====================
with st.sidebar:
    st.title("🔬 AIMS")
    st.caption("AI-Powered MLR Pipeline")
    
    st.divider()
    
    # Reviewer session
    st.subheader("👤 Reviewer Session")
    st.session_state.reviewer_id = st.text_input("Reviewer ID", value=st.session_state.reviewer_id)
    st.caption("Blind review mode")
    
    st.divider()
    
    # Navigation
    st.subheader("📋 Navigation")
    page = st.radio("Go to", [
        "Overview",
        "Screening",
        "Consensus",
        "Quality Assessment",
        "Extraction",
        "Synthesis"
    ], label_visibility="collapsed")
    
    st.divider()
    
    # Quick stats in sidebar
    st.subheader("📊 Quick Stats")
    stats = get_stats()
    st.metric("Articles", stats["total_articles"])
    st.metric("Screened", len(stats["decisions"]["article_id"].unique()) if not stats["decisions"].empty else 0)
    
    # Conflicts warning
    conflicts = consensus_engine.detect_conflicts()
    if not conflicts.empty:
        st.warning(f"⚠️ {len(conflicts)} conflicts")


# ==================== MAIN ====================
if page == "Overview":
    render_overview()
elif page == "Screening":
    render_screening()
elif page == "Consensus":
    render_consensus()
elif page == "Quality Assessment":
    render_quality()
elif page == "Extraction":
    render_extraction()
elif page == "Synthesis":
    render_synthesis()