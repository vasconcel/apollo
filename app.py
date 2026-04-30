import streamlit as st
import pandas as pd
import sqlite3

# Core
from src.core.database import Database
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
consensus_engine = ConsensusEngine(db.db_path)
quality_engine = QualityEngine()

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
        "Synthesis (QC)"
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
    st.title("🤝 Consensus & Agreement")

    # ---------- KAPPA ----------
    df = load_decisions_dataframe(db.db_path)
    kappa, _ = prepare_kappa(df)

    if kappa is not None:
        st.metric("Cohen's Kappa", round(kappa, 3))
    else:
        st.warning("Not enough reviewers")

    st.divider()

    # ---------- AUTO CONSENSUS ----------
    if st.button("⚙️ Auto-resolve consensus"):
        n = consensus_engine.auto_resolve_consensus(db)
        st.success(f"{n} articles auto-resolved")

    st.divider()

    # ---------- CONFLICTS ----------
    st.subheader("🚩 Conflicts")

    conflicts = consensus_engine.detect_conflicts()

    if conflicts.empty:
        st.success("No conflicts 🎉")
    else:
        st.dataframe(conflicts, use_container_width=True)

        with st.form("resolve_conflict"):
            art_id = st.number_input("Article ID", step=1)
            decision = st.radio("Final Decision", ["include", "exclude"])
            notes = st.text_area("Resolution Notes")

            if st.form_submit_button("Resolve Conflict"):
                db.save_final_decision(
                    art_id,
                    decision,
                    st.session_state.reviewer_id,
                    notes
                )
                st.success("Conflict resolved")
                st.rerun()

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

# ==================== SYNTHESIS (QC) ====================
elif page == "Synthesis (QC)":
    st.title("🧪 Quality Assessment")

    conn = sqlite3.connect(db.db_path)

    # Apenas artigos com decisão final = include
    df = pd.read_sql_query("""
        SELECT a.*
        FROM articles a
        JOIN final_decisions f ON a.id = f.article_id
        WHERE f.final_decision = 'include'
    """, conn)

    conn.close()

    if df.empty:
        st.info("No articles ready for QC")
    else:
        selected = st.selectbox("Select article", df["title"])
        art = df[df["title"] == selected].iloc[0]

        with st.form("qa_form"):
            st.subheader(f"Quality Criteria ({art['literature_type']})")

            scores = {}

            if art["literature_type"] == "WL":
                q_list = settings["quality_criteria"]["WL"]
            else:
                q_list = settings["quality_criteria"]["GL"]

            for q in q_list:
                val = st.radio(q, [1.0, 0.5, 0.0], horizontal=True)
                scores[q] = val

            result = quality_engine.evaluate(scores)

            st.metric("Score", result["total_score"])
            st.metric("Decision", result["decision"])

            if st.form_submit_button("Save QC"):
                db.save_quality_assessment(
                    art["id"],
                    st.session_state.reviewer_id,
                    scores,
                    result["total_score"],
                    result["decision"]
                )

                if result["decision"] == "exclude":
                    st.error("Article EXCLUDED (QC < 2.0)")
                else:
                    st.success("Article PASSED QC")

                st.rerun()

# ==================== SETTINGS ====================
elif page == "Settings":
    st.title("⚙️ Settings")
    st.json(settings)