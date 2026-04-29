import streamlit as st
import pandas as pd
import os
import sqlite3

# Core atualizado
from src.core.database import Database
from src.core.analytics import load_decisions_dataframe, prepare_kappa, find_conflicts

# Mantidos do seu sistema
from src.core.ai_handler import get_ai_suggestion
from src.core.config_manager import load_config

# ==================== CONFIG ====================
st.set_page_config(
    page_title="AIMS - AI-Powered MLR Pipeline",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== INIT ====================
config_mgr = load_config()

settings = {
    "research_questions": config_mgr.get("research_questions"),
    "inclusion_criteria": config_mgr.get("inclusion_criteria"),
    "exclusion_criteria": config_mgr.get("exclusion_criteria"),
    "quality_criteria": config_mgr.get("quality_criteria"),
    "extraction_fields": config_mgr.get("extraction_fields")
}

db = Database()

if "reviewer_id" not in st.session_state:
    st.session_state.reviewer_id = "Reviewer_1"

if "ai_suggestion" not in st.session_state:
    st.session_state.ai_suggestion = None

# ==================== SIDEBAR ====================
with st.sidebar:
    st.title("🚀 AIMS Pipeline")

    st.divider()
    st.subheader("👤 Reviewer Session")

    st.session_state.reviewer_id = st.text_input(
        "Reviewer ID",
        value=st.session_state.reviewer_id
    )

    st.caption("Blind Review Enabled")

    st.divider()
    page = st.radio("MENU", [
        "Dashboard",
        "Screening",
        "Consensus & Kappa",
        "Export / Import",
        "Synthesis"
    ])

# ==================== DASHBOARD ====================
if page == "Dashboard":
    st.title("📊 Dashboard")

    df = load_decisions_dataframe(db.db_path)

    total = len(df)
    included = len(df[df["decision"] == "include"])
    excluded = len(df[df["decision"] == "exclude"])

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Decisions", total)
    c2.metric("Included", included)
    c3.metric("Excluded", excluded)

# ==================== SCREENING ====================
elif page == "Screening":
    st.title("🔍 Screening")
    st.caption(f"Reviewer: {st.session_state.reviewer_id}")

    articles = db.get_pending_articles(st.session_state.reviewer_id)

    if not articles:
        st.success("No pending articles 🎉")

    for art in articles:
        art_id, title, abstract, source_id, lit_type, status = art

        st.markdown(f"### {title}")
        st.write(abstract)

        col1, col2, col3 = st.columns(3)

        if col1.button("✅ Include", key=f"inc_{art_id}"):
            db.save_decision(art_id, st.session_state.reviewer_id, "include")
            st.rerun()

        if col2.button("❌ Exclude", key=f"exc_{art_id}"):
            db.save_decision(art_id, st.session_state.reviewer_id, "exclude")
            st.rerun()

        if col3.button("⚠️ Uncertain", key=f"unc_{art_id}"):
            db.save_decision(art_id, st.session_state.reviewer_id, "uncertain")
            st.rerun()

        # AI Assist
        if st.button("✨ AI Suggestion", key=f"ai_{art_id}"):
            with st.spinner("Analyzing..."):
                st.session_state.ai_suggestion = get_ai_suggestion(
                    title,
                    abstract,
                    settings
                )

        if st.session_state.ai_suggestion:
            sug = st.session_state.ai_suggestion
            st.info(f"{sug['decision']} ({sug['confidence']}%)")

        st.divider()

# ==================== CONSENSUS ====================
elif page == "Consensus & Kappa":
    st.title("🤝 Consensus & Kappa")

    df = load_decisions_dataframe(db.db_path)
    kappa, pivot = prepare_kappa(df)

    if kappa is not None:
        st.metric("Cohen's Kappa", round(kappa, 3))
    else:
        st.warning("Not enough reviewers")

    st.divider()

    st.subheader("🚩 Conflicts")

    conflicts = find_conflicts(db.db_path)

    if conflicts.empty:
        st.success("No conflicts 🎉")
    else:
        st.dataframe(conflicts)

# ==================== EXPORT / IMPORT ====================
elif page == "Export / Import":
    st.title("📤 Data Exchange")

    st.subheader("Export")

    if st.button("Export My Decisions"):
        path = f"decisions_{st.session_state.reviewer_id}.csv"
        db.export_decisions_csv(path, st.session_state.reviewer_id)
        st.success(f"Saved: {path}")

    st.subheader("Import")

    uploaded = st.file_uploader("Upload CSV")

    if uploaded:
        with open("temp.csv", "wb") as f:
            f.write(uploaded.read())

        db.import_decisions_csv("temp.csv")
        st.success("Imported successfully")

# ==================== SYNTHESIS ====================
elif page == "Synthesis":
    st.title("🧪 Quality Assessment")

    conn = sqlite3.connect(db.db_path)
    df = pd.read_sql_query("SELECT * FROM articles", conn)
    conn.close()

    if df.empty:
        st.info("No articles available")
    else:
        selected = st.selectbox("Select article", df["title"])

        art = df[df["title"] == selected].iloc[0]

        with st.form("qa_form"):
            st.subheader("Quality Criteria")

            q_list = settings["quality_criteria"]["WL"]

            scores = []
            for q in q_list:
                res = st.radio(q, ["1", "0.5", "0"])
                scores.append(float(res))

            total = sum(scores)
            st.metric("Score", total)

            if st.form_submit_button("Apply"):
                if total < 2.0:
                    st.error("Excluded (<2.0)")
                else:
                    st.success("Included")

# ==================== SETTINGS ====================
elif page == "Settings":
    st.title("⚙️ Settings")
    st.json(settings)