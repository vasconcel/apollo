import streamlit as st
import pandas as pd
import json
import os
import sqlite3
import plotly.graph_objects as go
from datetime import datetime

# Importações do Core
from src.core import DatabaseManager, run_ingestion, run_conversion
from src.core.ai_handler import get_ai_suggestion
from src.core.snowballing import get_paper_references

# Agente de Insights (Placeholder, caso ainda não implementado)
try:
    from src.core.insights_agent import ask_data_agent
except ImportError:
    def ask_data_agent(q, db=None): return "Agent module not found. Please implement insights_agent.py"

# ==================== CONFIGURAÇÃO DA PÁGINA ====================
st.set_page_config(page_title="AIMS - AI-Powered MLR", layout="wide", initial_sidebar_state="expanded")

def inject_custom_css():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        
        .stApp { background-color: #F8FAFC; font-family: 'Inter', sans-serif; }
        
        /* Sidebar Professional Look */
        [data-testid="stSidebar"] { background-color: white !important; border-right: 1px solid #E2E8F0; }
        
        /* Card-like containers */
        div[data-testid="stVerticalBlock"] > div > div[data-testid="stContainer"] {
            background-color: white;
            border: 1px solid #E2E8F0;
            border-radius: 12px;
            padding: 2rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }

        /* Abstract Box */
        .abstract-box {
            font-size: 1.05rem;
            line-height: 1.7;
            color: #334155;
            background: white;
            padding: 1.5rem;
            border-radius: 8px;
            border: 1px solid #F1F5F9;
        }

        /* Buttons */
        .stButton>button {
            border-radius: 8px;
            transition: all 0.2s;
        }
        
        /* Badge styling */
        .badge {
            padding: 4px 12px;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
        }
    </style>
    """, unsafe_allow_html=True)

inject_custom_css()

# ==================== GESTÃO DE CONFIGURAÇÃO ====================
CONFIG_PATH = "project_config.json"

def load_settings():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    # Default alinhado ao protocolo (Garousi et al.)
    return {
        "project_name": "SE R&S Multivocal Literature Review",
        "research_questions": ["RQ1: Distribution & Nature", "RQ2: Pipeline Conceptualization", "RQ3: Challenges & Frictions", "RQ4: Practices & Design Principles", "RQ5: WL/GL Divergence"],
        "inclusion_criteria": {"IC1": "Relevant to SE R&S"},
        "exclusion_criteria": {"EC1": "Not in English"},
        "extraction_fields": ["Extracted Context", "Pipeline Stages Addressed (RQ2)", "Identified Challenges (RQ3)", "Practices (RQ4)", "WL/GL Divergence (RQ5)"],
        "quality_criteria": {
            "WL": ["WL-Q1: Clear context?", "WL-Q2: Valid methodology?", "WL-Q3: Data supported?", "WL-Q4: Limitations discussed?"],
            "GL": ["GL-Q1: Author expertise?", "GL-Q2: Transparent source?", "GL-Q3: Operational artifacts?", "GL-Q4: Beyond marketing?"]
        }
    }

settings = load_settings()

# ==================== ESTADO DA SESSÃO ====================
if "current_article_idx" not in st.session_state: st.session_state.current_article_idx = 0
if "ai_suggestion" not in st.session_state: st.session_state.ai_suggestion = None
if "chat_history" not in st.session_state: st.session_state.chat_history = []

# ==================== SIDEBAR NAVEGAÇÃO ====================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2103/2103633.png", width=50)
    st.title("AIMS Pipeline")
    st.caption("v2.0 | Protocol-Aligned MLR")
    st.divider()
    page = st.radio("MAIN MENU", [
        "Dashboard", 
        "Import Hub", 
        "Screening", 
        "Enrichment (Snowballing)", 
        "Evidence Synthesis", 
        "AI Insights (Beta)", 
        "Settings"
    ])

# ==================== DASHBOARD ====================
if page == "Dashboard":
    st.title("📊 Project Insights")
    db = DatabaseManager()
    stats = db.get_stats()
    
    if stats["total"] == 0:
        st.info("Start by importing your literature files in the Import Hub.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Sources", stats["total"])
        c2.metric("Academic (WL)", stats["wl_count"])
        c3.metric("Practitioner (GL)", stats["gl_count"])
        
        # Consolida status processados
        status_b = stats.get("status_breakdown", {})
        processed = status_b.get("excluded", 0) + status_b.get("included_screening", 0) + status_b.get("excluded_qc", 0) + status_b.get("included_final", 0)
        c4.metric("Processed", processed)

        st.divider()
        col_left, col_right = st.columns([2, 1])
        
        with col_left:
            st.subheader("Process Flow (PRISMA)")
            st.info("Sankey visualization reflects: Imported → Screened → QA Excluded → Final Synthesis")
            # Para visualização real do PRISMA, você usará Plotly Sankey Graph aqui.
            
        with col_right:
            st.subheader("Data Health")
            with sqlite3.connect(db.db_path) as conn:
                no_abs = conn.execute("SELECT COUNT(*) FROM articles WHERE abstract IS NULL OR abstract = ''").fetchone()[0]
            coverage = ((stats['total']-no_abs)/stats['total']*100) if stats['total'] > 0 else 0
            st.progress(coverage/100, text=f"Abstract Coverage: {coverage:.1f}%")

# ==================== IMPORT HUB ====================
elif page == "Import Hub":
    st.title("📥 Import Hub")
    st.markdown("Upload your raw search results. The pipeline will automatically convert, clean, assign Source IDs and deduplicate.")
    
    with st.container(border=True):
        uploaded_files = st.file_uploader(
            "Drop .bib, .ris, .csv, .xlsx or .txt files", 
            type=['bib', 'ris', 'csv', 'xlsx', 'txt'],
            accept_multiple_files=True
        )
        
        lit_type = st.radio("Literature Type", ["White Literature (WL)", "Grey Literature (GL)"], horizontal=True)
        source_prefix = "wl" if "White" in lit_type else "gl"
        
        st.divider()

        if st.button("🚀 Process & Ingest", type="primary", use_container_width=True):
            if not uploaded_files:
                st.warning("Please upload at least one file first.")
            else:
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                try:
                    with st.spinner("Executing Pipeline..."):
                        status_text.text("Step 1/3: Saving uploaded files...")
                        raw_path = f"data/raw/{source_prefix}"
                        os.makedirs(raw_path, exist_ok=True)
                        
                        for f in uploaded_files:
                            with open(os.path.join(raw_path, f.name), "wb") as save_f:
                                save_f.write(f.getbuffer())
                        progress_bar.progress(33)

                        status_text.text("Step 2/3: Converting formats to standard CSV...")
                        processed_path = f"data/processed/{source_prefix}"
                        run_conversion(raw_path, processed_path)
                        progress_bar.progress(66)

                        status_text.text("Step 3/3: Deduplicating and writing to Database...")
                        run_ingestion() 
                        
                        progress_bar.progress(100)
                        status_text.text("Ingestion completed successfully!")
                        st.success(f"Done! Processed {len(uploaded_files)} files.")
                        st.balloons()
                        
                except Exception as e:
                    st.error(f"An error occurred during ingestion: {str(e)}")

# ==================== SCREENING ====================
elif page == "Screening":
    st.title("🔍 Literature Screening")
    db = DatabaseManager()
    articles = db.get_articles_by_status("imported")
    
    if len(articles) == 0:
        st.success("All articles have been screened!")
    else:
        if st.session_state.current_article_idx >= len(articles):
            st.session_state.current_article_idx = 0
            
        art = articles.iloc[st.session_state.current_article_idx]
        # Pega o Source ID gerado no banco (Ex: WL-001)
        source_id = art.get('source_id', f"ID: {art['id']}")
        
        col_main, col_utility = st.columns([0.68, 0.32])
        
        with col_main:
            st.markdown(f"### [{source_id}] {art['title']}")
            st.caption(f"Authors: {art['authors']} | Year: {art['year']} | Type: {art['literature_type']}")
            st.divider()
            st.markdown("#### Abstract")
            st.markdown(f"<div class='abstract-box'>{art['abstract']}</div>", unsafe_allow_html=True)
            
        with col_utility:
            st.subheader("🛠️ Decisions")
            with st.container(border=True):
                c1, c2, c3 = st.columns(3)
                if c1.button("✅ Include", use_container_width=True, type="primary"):
                    db.update_article_status(art['id'], "included_screening")
                    st.session_state.current_article_idx += 1
                    st.session_state.ai_suggestion = None
                    st.rerun()
                if c2.button("❌ Exclude", use_container_width=True):
                    db.update_article_status(art['id'], "excluded")
                    st.session_state.current_article_idx += 1
                    st.session_state.ai_suggestion = None
                    st.rerun()
                if c3.button("⏭️ Skip", use_container_width=True):
                    st.session_state.current_article_idx += 1
                    st.session_state.ai_suggestion = None
                    st.rerun()

            st.divider()
            
            if st.button("✨ Ask AI Verdict", use_container_width=True):
                with st.spinner("Analyzing against GQM criteria..."):
                    st.session_state.ai_suggestion = get_ai_suggestion(art['title'], art['abstract'], settings)
            
            if st.session_state.ai_suggestion:
                sug = st.session_state.ai_suggestion
                if "error" in sug.get("decision", ""):
                    st.error(f"AI Error: {sug.get('reasons', ['Unknown error'])[0]}")
                else:
                    color = "#10B981" if sug['decision'].lower() == "include" else "#EF4444"
                    st.markdown(f"""
                    <div style="background: white; border: 1px solid #E2E8F0; border-radius: 8px; padding: 15px;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <strong style="color:{color}; font-size: 1.1rem;">Verdict: {sug['decision'].upper()}</strong>
                            <span style="background: #F1F5F9; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem;">Confidence: {sug.get('confidence', 0)}%</span>
                        </div>
                        <hr style="margin: 10px 0;">
                        <ul style="padding-left: 20px; font-size: 0.85rem; color: #475569;">
                            {"".join([f"<li>{r}</li>" for f in sug.get('reasons', [])])}
                        </ul>
                        <div style="margin-top: 10px;">
                            {" ".join([f"<span class='badge' style='background:#EEF2FF; color:#4338CA; margin-right:4px;'>{c}</span>" for c in sug.get('matched_criteria', [])])}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            
            st.caption(f"Progress: {st.session_state.current_article_idx + 1} / {len(articles)}")

# ==================== ENRICHMENT (SNOWBALLING) ====================
elif page == "Enrichment (Snowballing)":
    st.title("🕸️ Protocol Enrichment (Snowballing)")
    st.markdown("Per methodology: Backward and forward snowballing is applied **only** to included White Literature (WL) studies.")
    
    db = DatabaseManager()
    included_wl = db.get_articles_by_status("included_screening")
    included_wl = included_wl[included_wl['literature_type'] == 'WL']
    
    if len(included_wl) == 0:
        st.info("No White Literature marked as 'Included' in Screening yet.")
    else:
        st.dataframe(included_wl[['source_id', 'title', 'doi', 'year']], use_container_width=True)
        
        display_options = [f"[{row.get('source_id', row['id'])}] {row['title']}" for _, row in included_wl.iterrows()]
        selected_option = st.selectbox("Select Study to apply Snowballing:", display_options)
        
        # Pega a linha selecionada baseada no selectbox
        idx = display_options.index(selected_option)
        target_art = included_wl.iloc[idx]
        
        if st.button("🚀 Execute Snowballing", type="primary", disabled=not target_art['doi']):
            with st.spinner("Querying Semantic Scholar Graph for References/Citations..."):
                refs = get_paper_references(target_art['doi'])
                if refs:
                    db.upsert_mesh(refs) # Insere como PENDING e imported
                    st.success(f"Found {len(refs)} new references! Sent to the Import Hub/Screening queue.")
                    st.balloons()
                else:
                    st.warning("No references found or invalid DOI.")

# ==================== EVIDENCE SYNTHESIS ====================
elif page == "Evidence Synthesis":
    st.title("🧪 Evidence Synthesis & Quality Assessment")
    st.markdown("Apply the dual-rubric QA protocol and extract data mapped to your RQs.")
    
    db = DatabaseManager()
    included = db.get_articles_by_status("included_screening")
    
    if len(included) == 0:
        st.warning("No articles in the queue for extraction.")
    else:
        display_options = [f"[{row.get('source_id', row['id'])}] {row['title']}" for _, row in included.iterrows()]
        selected_option = st.selectbox("Select Study for Extraction & QA", display_options)
        
        idx = display_options.index(selected_option)
        art = included.iloc[idx]
        
        st.divider()
        st.subheader(f"Dual-Rubric Quality Assessment ({art['literature_type']})")
        st.caption("Studies scoring below 2.0 will be blocked from extraction per protocol.")
        
        q_list = settings["quality_criteria"]["WL"] if art["literature_type"] == "WL" else settings["quality_criteria"]["GL"]
        
        scores = []
        for q in q_list:
            res = st.radio(q, ["Yes (1.0)", "Partially (0.5)", "No (0.0)"], horizontal=True, key=f"qa_{art['id']}_{q}")
            scores.append(float(res.split("(")[1].split(")")[0]))
        
        total_score = sum(scores)
        
        c1, c2 = st.columns([1, 3])
        c1.metric("Total Quality Score", f"{total_score} / 4.0")
        
        with c2:
            if total_score < 2.0:
                st.error("🚨 Threshold Not Met: Study scored below 2.0 and must be excluded.")
                if st.button("Exclude Study (Failed QA)", type="primary"):
                    db.update_article_status(art['id'], "excluded_qc", f"Failed QA Score: {total_score}")
                    with sqlite3.connect(db.db_path) as conn:
                        conn.execute("UPDATE articles SET quality_score = ? WHERE id = ?", (total_score, art['id']))
                    st.rerun()
            else:
                st.success("✅ Threshold Met: Study is eligible for extraction.")
        
        # Só exibe o form de extração se a nota for >= 2.0
        if total_score >= 2.0:
            st.divider()
            with st.form("extraction_form"):
                st.subheader("Data Extraction (GQM Aligned)")
                ext_data = {}
                for field in settings["extraction_fields"]:
                    ext_data[field] = st.text_area(field, height=100)
                
                if st.form_submit_button("💾 Save Extraction & Mark as Final", type="primary"):
                    with sqlite3.connect(db.db_path) as conn:
                        conn.execute("UPDATE articles SET status = 'included_final', quality_score = ?, extraction_data = ? WHERE id = ?", 
                                     (total_score, json.dumps(ext_data), art['id']))
                    st.success("Evidence finalized successfully!")
                    st.rerun()

# ==================== AI INSIGHTS ====================
elif page == "AI Insights (Beta)":
    st.title("🤖 AI Research Agent")
    st.markdown("Ask questions about your **included** dataset. The agent interprets the synthesized data.")
    
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
    if prompt := st.chat_input("Ex: What are the main challenges reported by Grey Literature?"):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("Analyzing database..."):
                response = ask_data_agent(prompt)
                st.markdown(response)
                st.session_state.chat_history.append({"role": "assistant", "content": response})

# ==================== SETTINGS ====================
elif page == "Settings":
    st.title("⚙️ Project Configuration")
    st.markdown("Protocol Definitions (GQM, Elegibility & QA Criteria).")
    
    with st.container(border=True):
        st.subheader("Project Identity")
        project_name = st.text_input("Project Name", value=settings.get("project_name", ""))
        project_desc = st.text_area("Description", value=settings.get("description", ""))

    st.divider()
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("✅ Inclusion Criteria")
        raw_ic = settings.get("inclusion_criteria", {})
        ic_data = [{"ID": k, "Description": v} for k, v in raw_ic.items()]
        edited_ic = st.data_editor(ic_data, num_rows="dynamic", use_container_width=True, key="ic_edit")
        
    with col2:
        st.subheader("❌ Exclusion Criteria")
        raw_ec = settings.get("exclusion_criteria", {})
        ec_data = [{"ID": k, "Description": v} for k, v in raw_ec.items()]
        edited_ec = st.data_editor(ec_data, num_rows="dynamic", use_container_width=True, key="ec_edit")

    st.divider()
    col3, col4 = st.columns(2)
    
    with col3:
        st.subheader("🔬 Research Questions (RQs)")
        raw_rq = settings.get("research_questions", [])
        rq_data = [{"RQ": q} for q in raw_rq]
        edited_rq = st.data_editor(rq_data, num_rows="dynamic", use_container_width=True, key="rq_edit")
        
    with col4:
        st.subheader("📋 Extraction Fields")
        raw_ext = settings.get("extraction_fields", [])
        ext_data = [{"Field": f} for f in raw_ext]
        edited_ext = st.data_editor(ext_data, num_rows="dynamic", use_container_width=True, key="ext_edit")

    st.divider()
    if st.button("💾 Save Settings", type="primary", use_container_width=True):
        new_settings = {
            "project_name": project_name,
            "description": project_desc,
            "inclusion_criteria": {item["ID"]: item["Description"] for item in edited_ic if item.get("ID")},
            "exclusion_criteria": {item["ID"]: item["Description"] for item in edited_ec if item.get("ID")},
            "research_questions": [item["RQ"] for item in edited_rq if item.get("RQ")],
            "extraction_fields": [item["Field"] for item in edited_ext if item.get("Field")],
            "quality_criteria": settings.get("quality_criteria"),
            "column_aliases": settings.get("column_aliases", {}),
            "source_columns": settings.get("source_columns", ["title", "year", "abstract", "doi", "authors"])
        }
        
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(new_settings, f, indent=4, ensure_ascii=False)
            
        st.success("Configuration updated per protocol!")
        st.balloons()
        st.rerun()