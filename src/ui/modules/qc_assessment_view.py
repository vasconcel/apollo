"""
APOLLO QC Assessment Workspace

Stage-specific workspace for Quality Criteria assessment.
WL and GL use SEPARATE QC frameworks.

Researcher assesses quality of papers that passed IC filtering.
No EC or IC execution occurs here.
"""
import streamlit as st
from typing import Dict


def render_qc_assessment():
    """Render QC Assessment Workspace."""
    from src.core.dynamic_protocol import ProtocolState

    st.markdown("# QC Assessment Workspace")
    st.markdown("*Assess methodological quality using appropriate framework*")
    st.divider()

    if "research_protocol" not in st.session_state or st.session_state.research_protocol is None:
        st.warning("⚠️ No Research Protocol configured. Please go to 'Protocol Configuration' first.")
        return

    protocol = st.session_state.research_protocol

    if protocol.state == ProtocolState.DRAFT.value:
        st.warning("⚠️ Protocol must be locked before assessment.")
        return

    render_protocol_info_banner(protocol)
    st.divider()

    if "qc_session" not in st.session_state:
        st.session_state.qc_session = {
            "articles": [],
            "current_index": 0,
            "assessments": {},
            "loaded": False
        }

    if not st.session_state.qc_session["loaded"]:
        render_upload_section()
    else:
        render_assessment_workspace()


def render_protocol_info_banner(protocol):
    """Show protocol info in banner."""
    summary = protocol.get_summary()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Protocol", f"v{summary['version']}")
    with col2:
        st.metric("WL QC", f"{summary['wl_qc_enabled']}/{summary['wl_qc_count']}")
    with col3:
        st.metric("GL QC", f"{summary['gl_qc_enabled']}/{summary['gl_qc_count']}")
    with col4:
        st.caption(f"Hash: `{summary['hash']}`")

    col_t1, col_t2 = st.columns(2)
    with col_t1:
        st.caption(f"WL Threshold: {summary['wl_threshold']}")
    with col_t2:
        st.caption(f"GL Threshold: {summary['gl_threshold']}")


def render_upload_section():
    """Render upload section for QC assessment."""
    st.markdown("### Upload IC-Filtered Papers")
    st.info("""
    **Upload the results from IC Screening** (papers that were included).

    QC assessment uses DIFFERENT frameworks for WL and GL:
    - **WL (White Literature)**: Scientific rigor assessment
    - **GL (Grey Literature)**: Trustworthiness assessment

    Only papers relevant to your research scope will be quality-assessed.
    """)

    uploaded_file = st.file_uploader(
        "Upload IC Results",
        type=["xlsx", "csv"],
        help="Upload papers for QC assessment"
    )

    if uploaded_file:
        with st.spinner("Loading papers..."):
            articles = load_papers(uploaded_file)
            if articles:
                st.session_state.qc_session["articles"] = articles
                st.session_state.qc_session["current_index"] = 0
                st.session_state.qc_session["assessments"] = {}
                st.session_state.qc_session["loaded"] = True
                st.success(f"✅ Loaded {len(articles)} papers. Ready for QC assessment.")
                st.rerun()
            else:
                st.error("Failed to load papers.")


def load_papers(uploaded_file) -> list:
    """Load papers from file."""
    import pandas as pd

    import tempfile
    temp_path = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False).name

    with open(temp_path, "wb") as f:
        f.write(uploaded_file.getvalue())

    try:
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(temp_path)
        else:
            df = pd.read_excel(temp_path, sheet_name=0)

        articles = []
        for _, row in df.iterrows():
            ic_decision = str(row.get("IC_Decision", "INCLUDE"))
            if ic_decision.upper() != "INCLUDE":
                continue

            articles.append({
                "title": str(row.get("Title", row.get("title", ""))),
                "abstract": str(row.get("Abstract", row.get("abstract", ""))),
                "literature_type": str(row.get("Literature_Type", "WL")),
                "qc_scores": {},
                "qc_total": 0,
                "qc_decision": ""
            })

        return articles
    except Exception as e:
        st.error(f"Error loading file: {e}")
        return []
    finally:
        import os
        os.unlink(temp_path)


def render_assessment_workspace():
    """Render the main QC assessment workspace."""
    session = st.session_state.qc_session
    articles = session["articles"]
    current_idx = session["current_index"]
    assessments = session["assessments"]

    total = len(articles)
    assessed = sum(1 for a in assessments.values() if a.get("qc_decision"))
    pending = total - assessed

    col_nav, col_stats, col_nav2 = st.columns([1, 2, 1])
    with col_nav:
        if st.button("⬅️ Previous", disabled=current_idx == 0):
            session["current_index"] = max(0, current_idx - 1)
            st.rerun()
    with col_stats:
        st.markdown(f"**Progress:** {assessed}/{total} assessed | {pending} pending")
        progress = assessed / total if total > 0 else 0
        st.progress(progress)
    with col_nav2:
        if st.button("Next ➡️", disabled=current_idx >= total - 1):
            session["current_index"] = min(total - 1, current_idx + 1)
            st.rerun()

    st.divider()

    if articles and 0 <= current_idx < total:
        article = articles[current_idx]
        render_assessment_card(article, current_idx, assessments)


def render_assessment_card(article: Dict, index: int, assessments: Dict):
    """Render a single article card for QC assessment with WL/GL framework."""
    lit_type = article.get("literature_type", "WL")
    protocol = st.session_state.research_protocol

    col_type, col_id = st.columns([1, 3])
    with col_type:
        badge = "WL" if lit_type == "WL" else "GL"
        color = "#238636" if lit_type == "WL" else "#f0883e"
        st.markdown(f"<span style='background:{color};color:white;padding:2px 8px;border-radius:4px'>{badge}</span>",
                   unsafe_allow_html=True)
    with col_id:
        st.caption(f"IC Decision: {article.get('ic_decision', 'INCLUDE')}")

    st.markdown(f"### {article['title']}")

    abstract = article.get("abstract", "")
    if abstract and abstract != "nan":
        with st.expander("📄 Abstract"):
            st.markdown(abstract)

    st.divider()

    if lit_type == "GL":
        render_gl_qc_framework(article, index, assessments, protocol)
    else:
        render_wl_qc_framework(article, index, assessments, protocol)

    st.divider()

    current_assessment = assessments.get(index, {})
    if current_assessment.get("qc_decision"):
        st.success(f"QC Decision: **{current_assessment['qc_decision'].upper()}** (Score: {current_assessment.get('qc_total', 0)})")
        if st.button("🔄 Clear Assessment"):
            if index in assessments:
                del assessments[index]
            st.rerun()
    else:
        col_pass, col_fail = st.columns(2)
        with col_pass:
            if st.button("✅ Pass Quality", type="primary", use_container_width=True):
                assessments[index] = {
                    "qc_scores": current_assessment.get("qc_scores", {}),
                    "qc_total": current_assessment.get("qc_total", 0),
                    "qc_decision": "include"
                }
                st.rerun()
        with col_fail:
            if st.button("🚫 Fail Quality", type="secondary", use_container_width=True):
                assessments[index] = {
                    "qc_scores": current_assessment.get("qc_scores", {}),
                    "qc_total": current_assessment.get("qc_total", 0),
                    "qc_decision": "exclude"
                }
                st.rerun()

    st.divider()

    if st.button("📊 Export QC Results", type="primary"):
        export_qc_results(session)


def render_wl_qc_framework(article: Dict, index: int, assessments: Dict, protocol):
    """Render WL QC framework assessment."""
    st.markdown("#### White Literature (WL) Quality Assessment")
    st.caption("Scientific rigor framework: methodology, evidence, limitations")

    qc = protocol.qc
    current = assessments.get(index, {})
    current_scores = current.get("qc_scores", {})

    threshold = qc.wl_threshold
    st.markdown(f"**Threshold:** {threshold} (papers scoring below this are flagged)")

    enabled_criteria = [c for c in qc.wl_criteria.values() if c.enabled]

    if not enabled_criteria:
        st.warning("No WL QC criteria enabled in protocol.")
        return

    total_weight = sum(c.weight for c in enabled_criteria)
    max_score = total_weight

    for criterion_id, criterion in qc.wl_criteria.items():
        if not criterion.enabled:
            continue

        score = current_scores.get(criterion_id, 0.5)
        new_score = st.slider(
            f"{criterion_id}: {criterion.description[:50]}...",
            min_value=0.0,
            max_value=1.0,
            value=float(score),
            step=0.5,
            key=f"qc_wl_{index}_{criterion_id}"
        )

        new_scores = dict(current_scores)
        new_scores[criterion_id] = new_score

        new_total = sum(new_scores.values())

        if new_total < threshold:
            st.caption(f"⚠️ Current score ({new_total:.1f}) below threshold ({threshold})")
        else:
            st.caption(f"✓ Score: {new_total:.1f}/{max_score:.1f}")

        assessments[index] = {
            "qc_scores": new_scores,
            "qc_total": new_total,
            "qc_decision": current.get("qc_decision", "")
        }


def render_gl_qc_framework(article: Dict, index: int, assessments: Dict, protocol):
    """Render GL QC framework assessment."""
    st.markdown("#### Grey Literature (GL) Quality Assessment")
    st.caption("Trustworthiness framework: authority, transparency, relevance")

    qc = protocol.qc
    current = assessments.get(index, {})
    current_scores = current.get("qc_scores", {})

    threshold = qc.gl_threshold
    st.markdown(f"**Threshold:** {threshold} (papers scoring below this are flagged)")

    enabled_criteria = [c for c in qc.gl_criteria.values() if c.enabled]

    if not enabled_criteria:
        st.warning("No GL QC criteria enabled in protocol.")
        return

    total_weight = sum(c.weight for c in enabled_criteria)
    max_score = total_weight

    for criterion_id, criterion in qc.gl_criteria.items():
        if not criterion.enabled:
            continue

        score = current_scores.get(criterion_id, 0.5)
        new_score = st.slider(
            f"{criterion_id}: {criterion.description[:50]}...",
            min_value=0.0,
            max_value=1.0,
            value=float(score),
            step=0.5,
            key=f"qc_gl_{index}_{criterion_id}"
        )

        new_scores = dict(current_scores)
        new_scores[criterion_id] = new_score

        new_total = sum(new_scores.values())

        if new_total < threshold:
            st.caption(f"⚠️ Current score ({new_total:.1f}) below threshold ({threshold})")
        else:
            st.caption(f"✓ Score: {new_total:.1f}/{max_score:.1f}")

        assessments[index] = {
            "qc_scores": new_scores,
            "qc_total": new_total,
            "qc_decision": current.get("qc_decision", "")
        }


def export_qc_results(session: Dict):
    """Export QC assessment results."""
    import pandas as pd

    articles = session["articles"]
    assessments = session["assessments"]

    results = []
    for i, article in enumerate(articles):
        assessment = assessments.get(i, {})
        decision = assessment.get("qc_decision", "pending")
        results.append({
            "Title": article["title"],
            "Literature_Type": article["literature_type"],
            "QC_Decision": decision.upper(),
            "QC_Score": assessment.get("qc_total", 0),
            "QC_Scores": str(assessment.get("qc_scores", {})),
            "Abstract": article.get("abstract", "")
        })

    df = pd.DataFrame(results)
    csv = df.to_csv(index=False)

    st.download_button(
        "📥 Download QC Results (CSV)",
        data=csv,
        file_name="apollo_qc_assessment_results.csv",
        mime="text/csv"
    )

    passed = sum(1 for r in results if r["QC_Decision"] == "INCLUDE")
    failed = sum(1 for r in results if r["QC_Decision"] == "EXCLUDE")

    st.success(f"QC Assessment Complete: {passed} passed, {failed} failed quality")
