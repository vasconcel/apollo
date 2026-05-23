import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import streamlit as st
import pandas as pd
import plotly.express as px
import json
import config

MASTER_FILE = "data/master_table.csv"

try:
    from groq import Groq
    from dotenv import load_dotenv
    load_dotenv()
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False


def inject_css():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

        html, body, .stApp {
            font-family: 'Inter', sans-serif !important;
        }

        .card {
            background: var(--secondary-background-color);
            border-radius: 12px;
            padding: 20px;
            border: 1px solid rgba(128,128,128,0.2);
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
            margin-bottom: 16px;
        }

        .article-title {
            font-size: 1.25rem;
            font-weight: 700;
            color: var(--text-color);
            line-height: 1.4;
            margin-bottom: 8px;
        }

        .article-meta {
            color: var(--tag-color-default);
            font-size: 0.9rem;
            margin-bottom: 12px;
        }

        .abstract-box {
            background: var(--secondary-background-color);
            border-left: 4px solid #6366F1;
            border-radius: 8px;
            padding: 14px;
            color: var(--text-color);
            line-height: 1.6;
            font-size: 0.9rem;
            opacity: 0.9;
        }

        .ai-bubble {
            background: #EFF6FF;
            border: 1px solid #BFDBFE;
            border-radius: 12px;
            padding: 14px;
            color: #1E40AF;
        }

        @media (prefers-color-scheme: dark) {
            .ai-bubble {
                background: #1E3A5F;
                border-color: #1E40AF;
                color: #BFDBFE;
            }
        }

        .badge {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 20px;
            font-weight: 500;
            font-size: 0.8rem;
        }

        .badge-eligible { background: #DCFCE7; color: #166534; }
        .badge-excluded { background: #FEE2E2; color: #991B1B; }
        .badge-raw { background: #F1F5F9; color: #475569; }

        @media (prefers-color-scheme: dark) {
            .badge-eligible { background: #166534; color: #DCFCE7; }
            .badge-excluded { background: #991B1B; color: #FEE2E2; }
            .badge-raw { background: #475569; color: #F1F5F9; }
        }

        .progress-label {
            font-weight: 600;
            color: var(--text-color);
        }
    </style>
    """, unsafe_allow_html=True)


def get_api_key() -> str:
    env_key = os.environ.get('GROQ_API_KEY', '')
    session_key = st.session_state.get('api_key', '')
    return session_key if session_key else env_key


def get_ai_triage_suggestion(title: str, abstract: str) -> dict:
    api_key = get_api_key()

    if not api_key or not GROQ_AVAILABLE:
        return {'suggestion': 'error', 'reason': 'Configure API Key no sidebar.', 'criteria': ''}

    exclusion_criteria = '\n'.join([f"{k}: {v}" for k, v in config.EXCLUSION_CRITERIA.items()])
    inclusion_criteria = '\n'.join([f"{k}: {v}" for k, v in config.INCLUSION_CRITERIA.items()])

    system_prompt = f"""Você é assistente de triagem para SLR em Engenharia de Software.

CRITÉRIOS DE EXCLUSÃO (EC):
{exclusion_criteria}

CRITÉRIOS DE INCLUSÃO (IC):
{inclusion_criteria}

Retorne JSON: {{"suggestion": "eligible"/"excluded", "reason": "justificativa", "criteria": "código"}}"""

    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.1-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Título: {title}\n\nAbstract: {abstract}"}
            ],
            temperature=0.3,
            max_tokens=300
        )
        content = response.choices[0].message.content.strip()
        content = content.replace('```json', '').replace('```', '').strip()
        return json.loads(content)
    except Exception as e:
        return {'suggestion': 'error', 'reason': f"Erro: {str(e)[:40]}", 'criteria': ''}


def load_master_table() -> pd.DataFrame:
    if not os.path.exists(MASTER_FILE):
        return pd.DataFrame()

    try:
        df = pd.read_csv(MASTER_FILE, encoding='utf-8')
    except Exception:
        return pd.DataFrame()

    required_cols = ['title', 'abstract', 'year', 'source', 'status', 'ec_reason', 'ic_pass', 'doi',
                 'authors', 'keywords', 'journal', 'volume', 'issue', 'pages', 'url']
    for col in required_cols:
        if col not in df.columns:
            df[col] = ''

    df['status'] = df['status'].fillna('raw').astype(str)
    df['ec_reason'] = df['ec_reason'].fillna('').astype(str)
    df['ic_pass'] = df['ic_pass'].fillna('False').astype(str)
    df['title'] = df['title'].fillna('').astype(str)
    df['abstract'] = df['abstract'].fillna('').astype(str)
    df['source'] = df['source'].fillna('unknown').astype(str)
    df['doi'] = df['doi'].fillna('').astype(str)
    df['year'] = df['year'].fillna(0).astype(str)
    df['authors'] = df['authors'].fillna('').astype(str)

    return df


def save_master_table(df: pd.DataFrame):
    df.to_csv(MASTER_FILE, index=False, encoding='utf-8')


def prepare_year(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['year_clean'] = df['year'].astype(str).str.strip().str.extract(r'(\d{4})', expand=False)
    df['year_int'] = pd.to_numeric(df['year_clean'], errors='coerce').fillna(0).astype(int)
    return df


def tab_overview(df: pd.DataFrame):
    st.header("📊 Overview")
    st.markdown("---")

    if df.empty:
        st.warning("Nenhum dado. Execute ingestion.")
        return

    total = len(df)
    wl = len(df[df['source'].isin(['wl', 'raw/wl'])])
    gl = len(df[df['source'].isin(['gl', 'raw/gl'])])

    c1, c2, c3 = st.columns(3)
    c1.metric("Total", total)
    c2.metric("WoS/Scopus", wl)
    c3.metric("Google Scholar", gl)

    st.markdown("---")

    df = prepare_year(df)
    valid = df[(df['year_int'] >= 2015) & (df['year_int'] <= 2025) & (df['year_int'] > 0)]

    if not valid.empty:
        by_year = valid.groupby('year_int').size().reset_index(name='count')
        fig = px.bar(by_year, x='year_int', y='count', title="Publicações por Ano (2015-2025)",
                   color='count', color_continuous_scale='Blues')
        fig.update_layout(
            template="plotly_white",
            font_family='Inter',
            xaxis_title="Ano",
            yaxis_title="Quantidade"
        )
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("Sem dados de ano.")


def tab_screening(df: pd.DataFrame):
    st.header("🔬 Screening")
    st.markdown("---")

    if df.empty:
        st.warning("Nenhum dado.")
        return

    pending = df[df['status'] == 'raw']

    if pending.empty:
        st.success("✅ Triagem concluída!")
        eligible = len(df[df['status'] == 'eligible'])
        excluded = len(df[df['status'] == 'excluded'])
        st.write(f"**Total:** {len(df)} | **Incluídos:** {eligible} | **Excluídos:** {excluded}")
        return

    idx = pending.index[0]
    article = df.loc[idx]
    total = len(df)
    current = total - len(pending) + 1
    percent = int((current / total) * 100)

    st.markdown(f"**Progresso:** {current}/{total} ({percent}%)")
    st.progress(percent / 100)

    with st.container():
        st.markdown(f"""
        <div class="card">
            <h3 class="article-title">{article.get('title', 'Sem título')}</h3>
            <p class="article-meta">📅 {article.get('year', 'N/A')} | 📂 {article.get('source', 'N/A')}</p>
        </div>
        """, unsafe_allow_html=True)

    abstract = article.get('abstract', '')
    if abstract:
        st.markdown(f"""
        <div class="abstract-box">
            <b>Abstract:</b><br><br>
            {abstract[:800]}{'...' if len(abstract) > 800 else ''}
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("Abstract indisponível.")

    ai_result = st.session_state.get('ai_result')
    if ai_result and ai_result.get('suggestion') != 'error':
        st.markdown(f"""
        <div class="ai-bubble">
            <b>🤖 IA:</b> {ai_result.get('reason')}<br>
            <small>Critério: {ai_result.get('criteria')}</small>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    col_ec, col_ic = st.columns(2)

    with col_ec:
        st.subheader("🚫 Exclusão (EC)")
        ec_selected = []
        default_ec = [ai_result.get('criteria', '')] if ai_result and ai_result.get('criteria', '').startswith('EC') else []
        for code, desc in config.EXCLUSION_CRITERIA.items():
            if st.checkbox(f"**{code}:** {desc}", key=f"ec_{code}", value=code in default_ec):
                ec_selected.append(code)

    with col_ic:
        st.subheader("✅ Inclusão (IC)")
        ic_selected = []
        default_ic = [ai_result.get('criteria', '')] if ai_result and ai_result.get('criteria', '').startswith('IC') else []
        for code, desc in config.INCLUSION_CRITERIA.items():
            if st.checkbox(f"**{code}:** {desc}", key=f"ic_{code}", value=code in default_ic):
                ic_selected.append(code)

    st.markdown("---")

    c1, c2 = st.columns([2, 1])
    with c1:
        btn = st.button("🤖 Analisar IA", type="secondary", width="stretch")
        if btn:
            with st.spinner("Analisando..."):
                result = get_ai_triage_suggestion(article.get('title', ''), abstract)
                st.session_state['ai_result'] = result
            st.rerun()
    with c2:
        save_btn = st.button("💾 Salvar", type="primary", width="stretch")

    if save_btn:
        if ec_selected:
            new_status = 'excluded'
            reason = '; '.join(ec_selected)
        elif ic_selected:
            new_status = 'eligible'
            reason = ''
        else:
            new_status = 'raw'
            reason = ''

        if new_status != 'raw':
            df.loc[idx, 'status'] = new_status
            df.loc[idx, 'ec_reason'] = reason
            df.loc[idx, 'ic_pass'] = 'True' if new_status == 'eligible' else 'False'
            save_master_table(df)
            st.session_state.pop('ai_result', None)
            st.rerun()
        else:
            st.warning("Selecione um critério.")


def tab_dataset(df: pd.DataFrame):
    st.header("📂 Dataset Explorer")
    st.markdown("---")

    if df.empty:
        st.warning("Nenhum dado.")
        return

    df = prepare_year(df)

    with st.container():
        c1, c2, c3 = st.columns(3)
        with c1:
            src = ["Todos"] + sorted([str(s) for s in df['source'].unique()])
            src_filter = st.selectbox("Fonte", src)
        with c2:
            search = st.text_input("Buscar título", "")
        with c3:
            min_y = int(df['year_int'].min()) if df['year_int'].min() > 0 else 2015
            max_y = int(df['year_int'].max()) if df['year_int'].max() > 0 else 2025
            year_rng = st.slider("Ano", min_y, max_y, (min_y, max_y))

        c4, c5 = st.columns(2)
        with c4:
            stat = ["Todos"] + sorted([str(s) for s in df['status'].unique()])
            stat_filter = st.selectbox("Status", stat)
        with c5:
            doi_opts = ["Todos", "Com DOI", "Sem DOI"]
            doi_filter = st.selectbox("DOI", doi_opts)

    fdf = df.copy()

    if src_filter != "Todos":
        fdf = fdf[fdf['source'].astype(str) == src_filter]
    if search:
        fdf = fdf[fdf['title'].astype(str).str.contains(search, case=False, na=False)]
    if fdf['year_int'].notna().any():
        fdf = fdf[(fdf['year_int'] >= year_rng[0]) & (fdf['year_int'] <= year_rng[1])]
    if stat_filter != "Todos":
        fdf = fdf[fdf['status'].astype(str) == stat_filter]
    if doi_filter == "Com DOI":
        fdf = fdf[fdf['doi'].astype(str).str.strip() != '']
    elif doi_filter == "Sem DOI":
        fdf = fdf[(fdf['doi'].astype(str).str.strip() == '') | (fdf['doi'].isna())]

    def status_badge(s):
        s = str(s)
        if s == 'eligible':
            return '🟢 Eligible'
        elif s == 'excluded':
            return '🔴 Excluded'
        return '🟡 Pendente'

    fdf['Status'] = fdf['status'].apply(status_badge)

    cols = ['title', 'year_int', 'authors', 'source', 'Status', 'doi']
    cols = [c for c in cols if c in fdf.columns]
    disp = fdf[cols].rename(columns={'year_int': 'year'})

    st.markdown("---")
    st.markdown(f"**Exibindo {len(disp)} de {len(df)} registros**")

    st.dataframe(
        disp,
        column_config={
            "title": st.column_config.TextColumn("Título", width="large"),
            "authors": st.column_config.TextColumn("Autores", width="medium"),
            "doi": st.column_config.TextColumn("DOI", width="small"),
        },
        width="stretch",
        height=500,
        hide_index=True
    )

    csv = fdf.to_csv(index=False, encoding='utf-8')
    st.download_button("📥 Exportar CSV", data=csv, file_name="filtered.csv", mime="text/csv")


def main():
    inject_css()
    st.set_page_config(page_title="RS-SE-MLR Pipeline", layout="wide", page_icon="📚")

    with st.sidebar:
        st.title("⚙️ Config")
        api_key = st.text_input("GROQ API Key", type="password", key="api_sidebar")
        if api_key:
            st.session_state['api_key'] = api_key
        if not GROQ_AVAILABLE:
            st.warning("pip install groq")
        st.markdown("---")
        st.caption("**Legenda:** 🟢 Eligible | 🔴 Excluded | 🟡 Pendente")

    st.title("📚 RS-SE-MLR Pipeline")
    st.caption("Recruitment & Selection in SE - SLR")

    df = load_master_table()

    tab1, tab2, tab3 = st.tabs(["📊 Overview", "🔬 Screening", "📂 Dataset"])

    with tab1:
        tab_overview(df)
    with tab2:
        tab_screening(df)
    with tab3:
        tab_dataset(df)


if __name__ == "__main__":
    main()