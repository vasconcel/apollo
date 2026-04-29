import streamlit as st
import json
import os
import shutil
import plotly.graph_objects as go
import sqlite3
from src.core import DatabaseManager, run_ingestion
from src.core.ai_handler import get_ai_suggestion
from src.core.snowballing import get_paper_references

# ==================== CONFIGURAÇÃO DA PÁGINA ====================
st.set_page_config(page_title="AIMS - AI-Powered MLR", layout="wide")

def inject_custom_css():
    """Injeta CSS customizado para um visual profissional SaaS (Inter & Slate/Indigo)."""
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        
        /* Fundo principal e Tipografia */
        .stApp {
            background-color: #F8FAFC;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        }
        
        /* Menu Lateral */
        [data-testid="stSidebar"] > div:first-child {
            background-color: #F8FAFC;
            border-right: 1px solid #E2E8F0;
        }
        [data-testid="stSidebar"] * {
            color: #334155 !important;
        }
        
        /* Containers e Cards */
        [data-testid="stContainer"] {
            background-color: white;
            border: 1px solid #E2E8F0;
            border-radius: 8px;
            padding: 1.5rem;
            box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
        }
        
        /* Cabeçalhos e Métricas */
        [data-testid="stHeader"] {
            background-color: transparent;
        }
        [data-testid="stMetricValue"] {
            color: #4F46E5 !important;
            font-weight: 700;
        }
        
        /* Texto do Resumo (Abstract) */
        .abstract-text {
            line-height: 1.8;
            color: #475569;
            font-size: 0.95rem;
            text-align: justify;
        }
        
        /* Estilo dos Radio Buttons (Quality Assessment) */
        .stRadio > div > div > label {
            background-color: #F1F5F9;
            border: 1px solid #CBD5E1;
            border-radius: 6px;
            padding: 0.5rem 1rem;
            margin: 0.25rem;
            cursor: pointer;
            transition: all 0.2s;
            font-size: 0.875rem;
        }
        .stRadio > div > div > label:hover {
            background-color: #E2E8F0;
        }
        .stRadio > div > div > label[data-selected="true"] {
            background-color: #4F46E5;
            color: white;
            border-color: #4F46E5;
        }
        
        /* Botões */
        button {
            border-radius: 8px !important;
            font-weight: 500 !important;
            font-family: 'Inter', sans-serif !important;
        }
        
        /* Badges de Qualidade */
        .quality-badge {
            display: inline-block;
            padding: 0.75rem 1.25rem;
            border-radius: 6px;
            font-weight: 600;
            margin-top: 1rem;
            font-size: 0.9rem;
            width: 100%;
            text-align: center;
        }
        .quality-pass {
            background-color: #EEF2FF;
            color: #4338CA;
            border: 1px solid #C7D2FE;
        }
        .quality-fail {
            background-color: #F1F5F9;
            color: #475569;
            border: 1px solid #CBD5E1;
        }
    </style>
    """, unsafe_allow_html=True)

inject_custom_css()

# ==================== ESTADO DA SESSÃO E CONFIGURAÇÃO ====================
if "current_article_idx" not in st.session_state: st.session_state.current_article_idx = 0
if "ingestion_running" not in st.session_state: st.session_state.ingestion_running = False
if "ai_suggestion" not in st.session_state: st.session_state.ai_suggestion = None
if "last_article_id" not in st.session_state: st.session_state.last_article_id = None

# Carregamento Dinâmico do Config (Garante Genericidade)
config_path = "project_config.json"
project_config = {}
if os.path.exists(config_path):
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            project_config = json.load(f)
    except Exception as e:
        st.error(f"Erro ao ler config: {e}")

# Valores Padrão em caso de ausência no JSON (Genéricos)
EXTRACTION_FIELDS = project_config.get("extraction_fields", [
    "Context / Objective",
    "Methodology / Approach",
    "Key Findings / Practices",
    "Limitations / Frictions"
])
QUALITY_CRITERIA_WL = project_config.get("quality_criteria", {}).get("WL", [
    "WL-Q1: Clear research context and objectives",
    "WL-Q2: Appropriate methodology and analysis",
    "WL-Q3: Sufficient data support and evidence",
    "WL-Q4: Acknowledged limitations and constraints"
])
QUALITY_CRITERIA_GL = project_config.get("quality_criteria", {}).get("GL", [
    "GL-Q1: Demonstrated expertise and credibility",
    "GL-Q2: Transparent methodology and documentation",
    "GL-Q3: Relevant artifacts and deliverables",
    "GL-Q4: Balanced trade-offs and considerations"
])


# ==================== NAVEGAÇÃO ====================
page = st.sidebar.radio(
    "Navigation",
    ["Dashboard", "Import & Ingestion", "Screening", "Evidence Synthesis", "Project Settings"],
    index=0
)

# ==================== DASHBOARD TAB ====================
if page == "Dashboard":
    st.title("PRISMA Dashboard")
    st.divider()

    db = DatabaseManager()
    stats = db.get_stats()

    if stats["total"] == 0:
        st.warning("No data found. Please run the ingestion pipeline first.")
    else:
        with st.container(border=True):
            col1, col2, col3 = st.columns(3)
            with col1: st.metric("Total Articles", stats["total"])
            with col2: st.metric("White Literature (WL)", stats["wl_count"])
            with col3: st.metric("Grey Literature (GL)", stats["gl_count"])

        st.divider()
        st.subheader("PRISMA Flow Diagram")
        
        status_breakdown = stats.get("status_breakdown", {})
        deduplicated = status_breakdown.get("deduplicated", stats["total"])
        excluded = status_breakdown.get("excluded", 0)
        included = max(deduplicated - excluded, 0)

        # Cores customizadas baseadas na paleta Indigo/Emerald/Rose
        fig = go.Figure(go.Sankey(
            node=dict(
                pad=15, thickness=20, line=dict(color="black", width=0.5),
                label=["Input", "Deduplicated", "Included", "Excluded"],
                color=["#4F46E5", "#4F46E5", "#10B981", "#EF4444"]
            ),
            link=dict(
                source=[0, 1, 1],
                target=[1, 2, 3],
                value=[deduplicated, included, excluded],
                color=["#C7D2FE", "#D1FAE5", "#FECACA"]
            )
        ))
        fig.update_layout(font_size=12, margin=dict(t=20, b=20, l=20, r=20))
        st.plotly_chart(fig, use_container_width=True)


# ==================== IMPORT & INGESTION TAB ====================
elif page == "Import & Ingestion":
    st.title("Import & Ingestion")
    st.divider()

    def count_csv_files(directory):
        count = 0
        if os.path.exists(directory):
            for root, _, files in os.walk(directory):
                count += sum(1 for f in files if f.endswith(".csv"))
        return count

    col1, col2 = st.columns(2)
    with col1: st.metric("Raw CSV Files", count_csv_files("data/raw"))
    with col2: st.metric("Processed CSV Files", count_csv_files("data/processed"))

    st.divider()

    if st.button("Run Ingestion Pipeline", type="primary"):
        if not st.session_state.ingestion_running:
            st.session_state.ingestion_running = True
            template_path = "project_config_template.json"
            
            if not os.path.exists(config_path) and os.path.exists(template_path):
                shutil.copy(template_path, config_path)
                st.toast("Initialized project_config.json from template")
            
            with st.spinner("Running batch ingestion (Deduplication & DB Build)..."):
                try:
                    run_ingestion()
                    st.success("Ingestion completed successfully!")
                    st.session_state.current_article_idx = 0
                except Exception as e:
                    st.error(f"Ingestion failed: {str(e)}")
                finally:
                    st.session_state.ingestion_running = False


# ==================== SCREENING TAB ====================
elif page == "Screening":
    st.title("Screening")
    st.divider()

    db = DatabaseManager()
    imported_articles = db.get_articles_by_status("imported")

    if len(imported_articles) == 0:
        st.session_state.current_article_idx = 0
        st.session_state.ai_suggestion = None
        st.info("No articles to screen. All imported articles have been processed.")
    else:
        if st.session_state.current_article_idx >= len(imported_articles):
            st.session_state.current_article_idx = max(0, len(imported_articles) - 1)
        
        idx = st.session_state.current_article_idx
        current_article = imported_articles.iloc[idx]

        if st.session_state.last_article_id != current_article["id"]:
            st.session_state.ai_suggestion = None
            st.session_state.last_article_id = current_article["id"]

        with st.expander("View Eligibility Criteria", expanded=False):
            st.subheader("Inclusion Criteria")
            for cid, ctext in project_config.get("inclusion_criteria", {}).items():
                st.markdown(f"**{cid}:** {ctext}")
            st.subheader("Exclusion Criteria")
            for cid, ctext in project_config.get("exclusion_criteria", {}).items():
                st.markdown(f"**{cid}:** {ctext}")

        # Layout Principal (Leitura vs Ferramentas)
        col_left, col_right = st.columns([3, 1])

        with col_left:
            with st.container(border=True):
                st.markdown(f"### {current_article.get('title', 'No Title')}")
                st.caption(f"**Authors:** {current_article.get('authors', 'N/A')} | **Year:** {current_article.get('year', 'N/A')} | **Type:** {current_article.get('literature_type', 'N/A')}")
                st.divider()
                st.markdown("**Abstract**")
                abstract_text = current_article.get("abstract", "No abstract available.")
                st.markdown(f'<div class="abstract-text">{abstract_text}</div>', unsafe_allow_html=True)

        with col_right:
            st.subheader("Tools")
            
            # AI Screening
            if st.button("Ask AI Assistant", use_container_width=True):
                with st.spinner("Analyzing..."):
                    criteria_dict = {
                        "inclusion_criteria": project_config.get("inclusion_criteria", {}),
                        "exclusion_criteria": project_config.get("exclusion_criteria", {})
                    }
                    st.session_state.ai_suggestion = get_ai_suggestion(
                        current_article.get("title", ""), 
                        current_article.get("abstract", ""), 
                        criteria_dict
                    )
            
            # Snowballing
            doi = current_article.get("doi", "")
            if doi and str(doi).strip():
                if st.button("Perform Snowballing", use_container_width=True):
                    with st.spinner("Fetching references via API..."):
                        references = get_paper_references(doi)
                        if references:
                            db.upsert_mesh(references)
                            st.toast(f"Success: Added {len(references)} references via Snowballing.")
                        else:
                            st.warning("No references found or API timeout.")
            else:
                st.button("Perform Snowballing", disabled=True, use_container_width=True, help="DOI missing.")

            if st.session_state.ai_suggestion:
                res = st.session_state.ai_suggestion
                if "error" in res:
                    st.error(f"AI Error: {res['error']}")
                else:
                    st.info(f"**Decision:** {res.get('decision', 'N/A').upper()}\n\n**Reason:** {res.get('reason', '')}")

        st.divider()
        st.subheader("Manual Decision")
        
        dec_col1, dec_col2, dec_col3 = st.columns(3)
        with dec_col1:
            if st.button("✅ Include", use_container_width=True, type="primary"):
                db.update_article_status(current_article["id"], "included_screening")
                st.session_state.current_article_idx = min(idx + 1, len(imported_articles) - 1)
                st.rerun()
        with dec_col2:
            if st.button("❌ Exclude", use_container_width=True):
                db.update_article_status(current_article["id"], "excluded")
                st.session_state.current_article_idx = min(idx + 1, len(imported_articles) - 1)
                st.rerun()
        with dec_col3:
            if st.button("⏭️ Skip", use_container_width=True):
                st.session_state.current_article_idx = min(idx + 1, len(imported_articles) - 1)
                st.rerun()
                
        st.caption(f"Article {idx + 1} of {len(imported_articles)}")


# ==================== EVIDENCE SYNTHESIS TAB ====================
elif page == "Evidence Synthesis":
    st.title("Evidence Synthesis")
    st.divider()

    db = DatabaseManager()
    included_articles = db.get_articles_by_status("included_screening")

    if len(included_articles) == 0:
        st.info("No articles available for evidence synthesis. Please complete the screening process.")
    else:
        st.subheader(f"Included Articles ({len(included_articles)})")
        
        # Seleção de artigo
        article_options = [f"{row['title'][:70]}..." if len(row["title"]) > 70 else row["title"] for _, row in included_articles.iterrows()]
        selected_idx = st.selectbox("Select Article to Synthesize", range(len(article_options)), format_func=lambda i: article_options[i])
        selected_article = included_articles.iloc[selected_idx]

        st.markdown(f"### {selected_article['title']}")
        st.caption(f"**Type:** {selected_article.get('literature_type', 'N/A')} | **Source:** {selected_article.get('source', 'N/A')}")
        st.divider()

        with st.form("evidence_form"):
            # 1. Campos de Extração Dinâmicos
            st.subheader("Data Extraction")
            extraction_data = {}
            for field in EXTRACTION_FIELDS:
                extraction_data[field] = st.text_area(field, height=80, key=f"ext_{field}")

            # 2. Avaliação de Qualidade Dinâmica (Dual-Rubric)
            st.divider()
            st.subheader("Quality Assessment")
            
            lit_type = selected_article.get("literature_type", "WL")
            if lit_type not in ["WL", "GL"]:
                lit_type = "WL"  # Fallback caso seja PENDING ou incorreto

            criteria_list = QUALITY_CRITERIA_WL if lit_type == "WL" else QUALITY_CRITERIA_GL
            st.write(f"**Applying {lit_type} Quality Criteria Framework**")
            
            score_map = {"Yes (1.0)": 1.0, "Partially (0.5)": 0.5, "No (0)": 0.0}
            total_score = 0.0
            
            for idx, criterion in enumerate(criteria_list):
                ans = st.radio(criterion, ["Yes (1.0)", "Partially (0.5)", "No (0)"], key=f"qa_{idx}", horizontal=True)
                total_score += score_map[ans]

            # Indicador Visual de Pass/Fail
            if total_score >= 2.0:
                score_display = f'<div class="quality-badge quality-pass">✓ Verified Evidence (Score: {total_score:.1f} / 4.0)</div>'
            else:
                score_display = f'<div class="quality-badge quality-fail">✗ Low Quality / Exclude (Score: {total_score:.1f} / 4.0)</div>'
            
            st.markdown(score_display, unsafe_allow_html=True)
            st.write("") # Spacing

            submitted = st.form_submit_button("Save Evidence & Finalize", type="primary")
            if submitted:
                article_id = selected_article["id"]
                
                # Salva os dados independentemente de passar ou falhar
                with sqlite3.connect(db.db_path) as conn:
                    conn.execute(
                        "UPDATE articles SET ic_results = ?, quality_score = ? WHERE id = ?",
                        (json.dumps(extraction_data), total_score, article_id)
                    )
                    conn.commit()
                
                # Atualiza o status baseado na nota
                if total_score >= 2.0:
                    db.update_article_status(article_id, "included_final")
                    st.success("Evidence saved successfully! Moved to Included Final.")
                else:
                    db.update_article_status(article_id, "excluded", exclusion_reason="Failed Quality Assessment")
                    st.warning("Article excluded due to low quality score.")
                
                st.rerun()


# ==================== PROJECT SETTINGS TAB ====================
elif page == "Project Settings":
    st.title("Project Configuration")
    st.divider()

    if not os.path.exists(config_path):
        st.warning("`project_config.json` not found in root directory.")
        if st.button("Initialize Default Config"):
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(project_config, f, indent=4)
            st.success("Configuration created successfully!")
            st.rerun()
    else:
        st.write("Current active configuration driving the system behavior (read-only view):")
        st.json(project_config)