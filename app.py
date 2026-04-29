import streamlit as st
import pandas as pd
import json
import os
import sqlite3
import shutil
from datetime import datetime

# Importações do Core AIMS
from src.core import DatabaseManager, run_ingestion, run_conversion
from src.core.ai_handler import get_ai_suggestion
from src.core.snowballing import get_paper_references
from src.core.analytics import MLRAnalytics
from src.core.config_manager import load_config

# ==================== CONFIGURAÇÃO DA PÁGINA ====================
st.set_page_config(page_title="AIMS - AI-Powered MLR Pipeline", layout="wide", initial_sidebar_state="expanded")

def inject_custom_css():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        .stApp { background-color: #F8FAFC; font-family: 'Inter', sans-serif; }
        [data-testid="stSidebar"] { background-color: white !important; border-right: 1px solid #E2E8F0; }
        .abstract-box {
            font-size: 1.05rem; line-height: 1.7; color: #334155;
            background: white; padding: 1.5rem; border-radius: 8px; border: 1px solid #F1F5F9;
        }
        .badge { padding: 4px 12px; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; }
        .metric-card { background: white; padding: 1.2rem; border-radius: 10px; border: 1px solid #E2E8F0; }
    </style>
    """, unsafe_allow_html=True)

inject_custom_css()

# ==================== GESTÃO DE ESTADO E CONFIG ====================
config_mgr = load_config()
settings = {
    "project_name": config_mgr.get("project_name"),
    "research_questions": config_mgr.get("research_questions"),
    "inclusion_criteria": config_mgr.get("inclusion_criteria"),
    "exclusion_criteria": config_mgr.get("exclusion_criteria"),
    "extraction_fields": config_mgr.get("extraction_fields"),
    "quality_criteria": config_mgr.get("quality_criteria")
}

db = DatabaseManager()
analyzer = MLRAnalytics()

if "current_article_idx" not in st.session_state: st.session_state.current_article_idx = 0
if "ai_suggestion" not in st.session_state: st.session_state.ai_suggestion = None
if "reviewer_id" not in st.session_state: st.session_state.reviewer_id = "Reviewer_1"

# ==================== SIDEBAR ====================
with st.sidebar:
    st.title("🚀 AIMS Pipeline")
    st.caption("v2.1 | Research-Grade MLR")
    
    st.divider()
    st.subheader("👤 Reviewer Session")
    st.session_state.reviewer_id = st.text_input("Reviewer Name/ID", value=st.session_state.reviewer_id)
    st.info(f"Modo: Blind Review (Independent)")
    
    st.divider()
    page = st.radio("MAIN MENU", [
        "Dashboard", 
        "Import Hub", 
        "Screening", 
        "Consensus & Kappa", 
        "Enrichment (Snowballing)",
        "Evidence Synthesis",
        "Settings"
    ])

# ==================== PÁGINA: DASHBOARD ====================
if page == "Dashboard":
    st.title("📊 Project Insights")
    stats = db.get_stats()
    prisma = analyzer.get_prisma_data()
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Ingested", prisma['total_imported'])
    c2.metric("Excluded (Screening)", prisma['excluded_screening'])
    c3.metric("Excluded (Quality)", prisma['excluded_qc'])
    c4.metric("Final Included", prisma['final_included'])

    st.divider()
    st.subheader("PRISMA Flow Progress")
    progress_val = (prisma['final_included'] / prisma['total_imported']) if prisma['total_imported'] > 0 else 0
    st.progress(progress_val, text=f"{prisma['final_included']} papers reached Synthesis Phase")

# ==================== PÁGINA: IMPORT HUB ====================
elif page == "Import Hub":
    st.title("📥 Data Ingestion")
    lit_type = st.radio("Source Literature Type", ["WL (White)", "GL (Grey)"], horizontal=True)
    uploaded_files = st.file_uploader("Upload .bib, .ris, .csv", accept_multiple_files=True)
    
    if st.button("🚀 Process & Ingest", type="primary"):
        prefix = "wl" if "WL" in lit_type else "gl"
        raw_path = f"data/raw/{prefix}"
        os.makedirs(raw_path, exist_ok=True)
        
        for f in uploaded_files:
            with open(os.path.join(raw_path, f.name), "wb") as save_f:
                save_f.write(f.getbuffer())
        
        with st.spinner("Pipeline running..."):
            run_conversion(raw_path, f"data/processed/{prefix}")
            run_ingestion()
        st.success("Ingestion Complete!")
        st.balloons()

# ==================== PÁGINA: SCREENING (BLIND) ====================
elif page == "Screening":
    st.title("🔍 Literature Screening")
    st.caption(f"Reviewer: {st.session_state.reviewer_id} | Protocol: Title/Abstract Blind Review")
    
    # Busca apenas artigos que este revisor AINDA não decidiu
    query = """
        SELECT * FROM articles 
        WHERE id NOT IN (
            SELECT article_id FROM screening_decisions WHERE reviewer_id = ?
        ) AND status = 'imported'
    """
    with sqlite3.connect(db.db_path) as conn:
        pending_articles = pd.read_sql_query(query, conn, params=(st.session_state.reviewer_id,))

    if len(pending_articles) == 0:
        st.success("Queue empty! All assigned papers screened for this reviewer.")
    else:
        art = pending_articles.iloc[0]
        
        col_main, col_tools = st.columns([0.7, 0.3])
        with col_main:
            st.markdown(f"**[{art['source_id']}]**")
            st.subheader(art['title'])
            st.markdown(f"<div class='abstract-box'>{art['abstract']}</div>", unsafe_allow_html=True)
        
        with col_tools:
            with st.container(border=True):
                st.subheader("Decision")
                if st.button("✅ Include for Synthesis", use_container_width=True, type="primary"):
                    db.save_reviewer_decision(art['id'], st.session_state.reviewer_id, "included_screening")
                    st.rerun()
                if st.button("❌ Exclude Study", use_container_width=True):
                    db.save_reviewer_decision(art['id'], st.session_state.reviewer_id, "excluded")
                    st.rerun()
            
            if st.button("✨ Get AI Verdict"):
                with st.spinner("IA Analisando..."):
                    st.session_state.ai_suggestion = get_ai_suggestion(art['title'], art['abstract'], settings)
            
            if st.session_state.ai_suggestion:
                sug = st.session_state.ai_suggestion
                st.info(f"AI: {sug['decision'].upper()} ({sug['confidence']}%)\n\nReason: {sug['reasons'][0]}")

# ==================== PÁGINA: CONSENSUS & KAPPA ====================
elif page == "Consensus & Kappa":
    st.title("🤝 Consensus & Reconciliation")
    
    # 1. Merge de Bancos Externos
    with st.expander("📥 Import Decisions from Peer Reviewer"):
        uploaded_db = st.file_uploader("Upload Peer DB (.db)", type="db")
        if uploaded_db and st.button("Merge Peer Data"):
            with open("peer_temp.db", "wb") as f: f.write(uploaded_db.getbuffer())
            res = analyzer.merge_reviewer_decisions("peer_temp.db")
            st.success(res)

    # 2. Kappa Score
    metrics = analyzer.get_agreement_metrics()
    if metrics['n_shared'] > 0:
        c1, c2, c3 = st.columns(3)
        c1.metric("Cohen's Kappa (κ)", metrics['kappa'])
        c2.metric("Interpretation", metrics['interpretation'])
        c3.metric("Shared Articles", metrics['n_shared'])
    
    # 3. Resolução de Conflitos
    st.subheader("🚩 Conflicts to Resolve")
    conflicts = analyzer.get_conflicts()
    if conflicts.empty:
        st.success("No active conflicts! All decisions aligned.")
    else:
        st.dataframe(conflicts, use_container_width=True)
        with st.form("resolve_form"):
            art_id = st.number_input("Article ID from table", step=1)
            final_dec = st.radio("Final Consensus Decision", ["included_screening", "excluded"])
            rationale = st.text_input("Consensus Rationale")
            if st.form_submit_button("Apply Final Resolution"):
                analyzer.resolve_conflict(art_id, final_dec, rationale)
                st.success("Article status updated and finalized.")
                st.rerun()

# ==================== PÁGINA: ENRICHMENT ====================
elif page == "Enrichment (Snowballing)":
    st.title("🕸️ Snowballing Phase")
    st.caption("Backward Snowballing applied only to included White Literature (WL) seeds.")
    
    seeds = db.get_articles_by_status("included_screening")
    seeds = seeds[seeds['literature_type'] == 'WL']
    
    if seeds.empty:
        st.info("No WL seeds available yet. Complete Screening first.")
    else:
        target_id = st.selectbox("Select Seed Paper", seeds['source_id'].tolist())
        target_art = seeds[seeds['source_id'] == target_id].iloc[0]
        
        if st.button("🚀 Find References", type="primary"):
            with st.spinner("Graph Query..."):
                refs = get_paper_references(target_art['doi'])
                if refs:
                    db.upsert_mesh(refs)
                    st.success(f"Found {len(refs)} new papers. They are now in the Screening queue.")
                else: st.warning("No references found via API.")

# ==================== PÁGINA: SYNTHESIS & QUALITY ====================
elif page == "Evidence Synthesis":
    st.title("🧪 Synthesis & Quality Assessment")
    
    # Artigos que passaram pelo screening (ou consenso) e aguardam QA/Extração
    final_queue = db.get_articles_by_status("included_screening")
    
    if final_queue.empty:
        st.info("No articles ready for synthesis.")
    else:
        art_titles = [f"[{row['source_id']}] {row['title']}" for _, row in final_queue.iterrows()]
        selected = st.selectbox("Select Paper", art_titles)
        art_id_str = selected.split("]")[0].replace("[", "")
        art = final_queue[final_queue['source_id'] == art_id_str].iloc[0]
        
        with st.form("qa_form"):
            st.subheader(f"Quality Rubric ({art['literature_type']})")
            q_list = settings["quality_criteria"]["WL"] if art["literature_type"] == "WL" else settings["quality_criteria"]["GL"]
            
            scores = []
            for q in q_list:
                res = st.radio(q, ["Yes (1.0)", "Partially (0.5)", "No (0.0)"], horizontal=True)
                scores.append(float(res.split("(")[1].split(")")[0]))
            
            total_score = sum(scores)
            st.metric("Total Score", f"{total_score} / 4.0")
            
            st.divider()
            st.subheader("Data Extraction")
            extracted = {}
            for field in settings["extraction_fields"]:
                extracted[field] = st.text_area(field)
            
            if st.form_submit_button("Finalize Article"):
                if total_score < 2.0:
                    db.update_article_status(art['id'], "excluded_qc", f"Failed QC (Score: {total_score})")
                    st.error("Article EXCLUDED due to low quality threshold (< 2.0).")
                else:
                    # Salva extração no banco (necessário adicionar coluna extraction_data no DB)
                    db.update_article_status(art['id'], "included_final")
                    st.success("Article Included and Data Extracted!")
                st.rerun()

# ==================== PÁGINA: SETTINGS ====================
elif page == "Settings":
    st.title("⚙️ Config")
    st.json(settings)