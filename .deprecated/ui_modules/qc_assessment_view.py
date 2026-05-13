"""
APOLLO QC Assessment Workspace - Forensic Terminal Aesthetic

Stage-specific workspace for Quality Criteria assessment.
WL and GL use SEPARATE QC frameworks.

Researcher assesses quality of papers that passed IC filtering.
"""
import streamlit as st
import uuid
from datetime import datetime
from typing import Dict
from src.ui.components import (
    terminal_header, section_header, status_badge, lit_type_badge,
    metric_tile, telemetry_panel, decision_card, progress_bar,
    stage_indicator, structured_card, criteria_panel, divider,
    operational_status, provenance_indicator
)
from src.ui.theme import COLORS, TYPOGRAPHY


def render_qc_assessment():
    """Render QC Assessment Workspace."""
    from src.core.dynamic_protocol import ProtocolState
    from src.core.screening_session import ScreeningSession

    terminal_header(
        "QC ASSESSMENT WORKSPACE",
        "Assess methodological quality using appropriate framework",
        status="ACTIVE"
    )
    divider()

    if "research_protocol" not in st.session_state or st.session_state.research_protocol is None:
        st.warning("⚠ No Research Protocol configured. Please go to 'Protocol Configuration' first.")
        return

    protocol = st.session_state.research_protocol

    if protocol.state == ProtocolState.DRAFT.value:
        st.warning("⚠ Protocol must be locked before assessment.")
        return

    render_protocol_info_banner(protocol)
    divider()

    if "apollo_session" not in st.session_state:
        st.session_state.apollo_session = ScreeningSession(
            session_id=str(uuid.uuid4())[:8],
            created_at=datetime.now().isoformat(),
            protocol_version=protocol.protocol_version,
            researcher_id="researcher_1"
        )
        st.session_state.apollo_session.stage = "qc"

    session = st.session_state.apollo_session

    if not session.articles:
        render_upload_section(session)
    else:
        render_assessment_workspace(session)


def render_protocol_info_banner(protocol):
    """Show protocol info in terminal-style banner."""
    summary = protocol.get_summary()

    st.markdown(f'''
    <div style="border:1px solid {COLORS['border_light']};background:{COLORS['bg_card']};padding:1rem;margin-bottom:1rem;">
        <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.6rem;color:{COLORS['cyan']};letter-spacing:0.15em;margin-bottom:0.75rem;">
            ▸ PROTOCOL TELEMETRY
        </div>
        <div style="display:grid;grid-template-columns:repeat(6, 1fr);gap:1rem;">
            <div><span style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['text_muted']};">VERSION</span><br><span style="font-family:{TYPOGRAPHY['mono']};font-size:0.9rem;color:{COLORS['text_primary']};">v{summary['version']}</span></div>
            <div><span style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['text_muted']};">WL QC</span><br><span style="font-family:{TYPOGRAPHY['mono']};font-size:0.9rem;color:{COLORS['cyan']};">{summary['wl_qc_enabled']}/{summary['wl_qc_count']}</span></div>
            <div><span style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['text_muted']};">GL QC</span><br><span style="font-family:{TYPOGRAPHY['mono']};font-size:0.9rem;color:{COLORS['cyan']};">{summary['gl_qc_enabled']}/{summary['gl_qc_count']}</span></div>
            <div><span style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['text_muted']};">WL THRESH</span><br><span style="font-family:{TYPOGRAPHY['mono']};font-size:0.9rem;color:{COLORS['text_secondary']};">{summary['wl_threshold']}</span></div>
            <div><span style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['text_muted']};">GL THRESH</span><br><span style="font-family:{TYPOGRAPHY['mono']};font-size:0.9rem;color:{COLORS['text_secondary']};">{summary['gl_threshold']}</span></div>
            <div><span style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['text_muted']};">HASH</span><br><span style="font-family:{TYPOGRAPHY['mono']};font-size:0.7rem;color:{COLORS['text_secondary']};">{summary['hash'][:12]}...</span></div>
        </div>
    </div>
    ''', unsafe_allow_html=True)


def render_upload_section(session):
    """Render upload section for QC assessment."""
    section_header("DATA INGESTION", "Upload IC-filtered papers for quality assessment")

    st.markdown(f'''
    <div style="border:1px solid {COLORS['border_light']};background:{COLORS['bg_card']};padding:1rem;margin:1rem 0;">
        <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['text_secondary']};margin-bottom:0.5rem;">
            FRAMEWORK SEPARATION
        </div>
        <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.7rem;color:{COLORS['text_muted']};line-height:1.6;">
            <span style="color:{COLORS['success']};">WL (White Literature)</span>: Scientific rigor assessment<br>
            <span style="color:{COLORS['warning']};">GL (Grey Literature)</span>: Trustworthiness assessment
        </div>
    </div>
    ''', unsafe_allow_html=True)

    uploaded_file = st.file_uploader(
        "Upload IC Results",
        type=["xlsx", "csv"],
        help="Upload papers for QC assessment",
        label_visibility="collapsed"
    )

    if uploaded_file:
        with st.spinner("Loading papers..."):
            articles = session.ingest_from_upload(uploaded_file, stage="qc")
            if articles:
                session.current_index = 0
                st.success(f"Loaded {len(articles)} papers. Ready for QC assessment.")
                st.rerun()
            else:
                st.error("Failed to load papers.")


def render_assessment_workspace(session):
    """Render the main QC assessment workspace."""
    from src.core.screening_session import ArticleReview

    articles = session.articles
    current_idx = session.current_index
    total = len(articles)
    assessed = session.qc_completed
    pending = total - assessed

    col_nav, col_stats, col_nav2 = st.columns([1, 2, 1])
    with col_nav:
        if st.button("◀ PREV", disabled=current_idx == 0):
            session.current_index = max(0, current_idx - 1)
            st.rerun()
    with col_stats:
        progress_bar(assessed, total, stage="QC")
    with col_nav2:
        if st.button("NEXT ▶", disabled=current_idx >= total - 1):
            session.current_index = min(total - 1, current_idx + 1)
            st.rerun()

    divider()

    if articles and 0 <= current_idx < total:
        article = articles[current_idx]
        render_assessment_card(article, current_idx, session)

    divider()

    if st.button("EXPORT QC RESULTS", type="primary"):
        export_qc_results(session)


def render_assessment_card(article, index: int, session):
    """Render a single article card for QC assessment with WL/GL framework."""
    from src.core.screening_session import ArticleReview
    if isinstance(article, ArticleReview):
        lit_type = article.get_literature_type()
        article_id = article.article_id
        metadata = article.metadata
    else:
        lit_type = article.get("literature_type", "WL")
        article_id = article.get("global_id", "N/A")
        metadata = article

    protocol = st.session_state.research_protocol

    st.markdown(f"""
    <div style="border:1px solid {COLORS['border_light']};background:{COLORS['bg_card']};padding:1rem;margin-bottom:1rem;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem;padding-bottom:0.75rem;border-bottom:1px solid {COLORS['border']};">
            <div style="display:flex;align-items:center;gap:1rem;">
                <span style="background:{COLORS['success'] if lit_type == 'WL' else COLORS['warning']};color:#000;padding:2px 8px;font-family:{TYPOGRAPHY['mono']};font-size:0.7rem;font-weight:600;">{lit_type}</span>
                <span style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['text_muted']};">INDEX: {index + 1:04d}</span>
            </div>
            <span style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['success']};">IC: {article.ic_stage if isinstance(article, ArticleReview) else metadata.get('ic_decision', 'INCLUDE')}</span>
        </div>
    """, unsafe_allow_html=True)

    st.markdown(f"### {article.title if isinstance(article, ArticleReview) else article.get('title', '')}")

    abstract = article.abstract if isinstance(article, ArticleReview) else article.get("abstract", "")
    if abstract and abstract != "nan":
        with st.expander("ABSTRACT", expanded=True):
            st.markdown(abstract)
    else:
        st.info("Abstract: _[NOT AVAILABLE]_")

    st.markdown("</div>", unsafe_allow_html=True)

    divider()

    if lit_type == "GL":
        render_gl_qc_framework(article, index, session, protocol)
    else:
        render_wl_qc_framework(article, index, session, protocol)

    divider()

    current_qc = article.qc_stage if isinstance(article, ArticleReview) else ""
    if current_qc:
        status_badge(current_qc.upper())
        st.markdown(f"Score: {article.qc_total if isinstance(article, ArticleReview) else metadata.get('qc_total', 0)}")
        if st.button("CLEAR"):
            if isinstance(article, ArticleReview):
                article.qc_stage = ""
                article.qc_notes = ""
                article.qc_timestamp = ""
                article.qc_scores = {}
                article.qc_total = 0
                session.qc_completed = max(0, session.qc_completed - 1)
            st.rerun()
    else:
        col_pass, col_fail = st.columns(2)
        with col_pass:
            if st.button("PASS QUALITY", type="primary", width="stretch"):
                if isinstance(article, ArticleReview):
                    article.qc_stage = "include"
                    article.qc_timestamp = datetime.now().isoformat()
                    session.qc_completed += 1
                st.rerun()
        with col_fail:
            if st.button("FAIL QUALITY", type="secondary", width="stretch"):
                if isinstance(article, ArticleReview):
                    article.qc_stage = "exclude"
                    article.qc_timestamp = datetime.now().isoformat()
                    session.qc_completed += 1
                st.rerun()


def render_wl_qc_framework(article, index: int, session, protocol):
    """Render WL QC framework assessment."""
    from src.core.screening_session import ArticleReview
    section_header("WHITE LITERATURE QC", "Scientific rigor framework: methodology, evidence, limitations")

    qc = protocol.qc

    if isinstance(article, ArticleReview):
        current_scores = article.qc_scores if hasattr(article, 'qc_scores') and article.qc_scores else {}
        current_qc = article.qc_stage or ""
    else:
        current_scores = article.get("qc_scores", {})
        current_qc = ""

    threshold = qc.wl_threshold
    st.markdown(f"**Threshold:** {threshold} (papers scoring below this are flagged)")

    enabled_criteria = [c for c in qc.wl_criteria.values() if c.enabled]

    if not enabled_criteria:
        st.warning("No WL QC criteria enabled in protocol.")
        return

    total_weight = sum(c.weight for c in enabled_criteria)
    max_score = total_weight

    new_scores = dict(current_scores)
    for criterion_id, criterion in qc.wl_criteria.items():
        if not criterion.enabled:
            continue

        score = new_scores.get(criterion_id, 0.5)
        new_score = st.slider(
            f"{criterion_id}: {criterion.description[:50]}...",
            min_value=0.0,
            max_value=1.0,
            value=float(score),
            step=0.5,
            key=f"qc_wl_{index}_{criterion_id}"
        )

        new_scores[criterion_id] = new_score

    new_total = sum(new_scores.values())

    if new_total < threshold:
        st.caption(f"Score ({new_total:.1f}) below threshold ({threshold})")
    else:
        st.caption(f"Score: {new_total:.1f}/{max_score:.1f}")

    if isinstance(article, ArticleReview):
        article.qc_scores = new_scores
        article.qc_total = new_total


def render_gl_qc_framework(article, index: int, session, protocol):
    """Render GL QC framework assessment."""
    from src.core.screening_session import ArticleReview
    section_header("GREY LITERATURE QC", "Trustworthiness framework: authority, transparency, relevance")

    qc = protocol.qc

    if isinstance(article, ArticleReview):
        current_scores = article.qc_scores if hasattr(article, 'qc_scores') and article.qc_scores else {}
        current_qc = article.qc_stage or ""
    else:
        current_scores = article.get("qc_scores", {})
        current_qc = ""

    threshold = qc.gl_threshold
    st.markdown(f"**Threshold:** {threshold} (papers scoring below this are flagged)")

    enabled_criteria = [c for c in qc.gl_criteria.values() if c.enabled]

    if not enabled_criteria:
        st.warning("No GL QC criteria enabled in protocol.")
        return

    total_weight = sum(c.weight for c in enabled_criteria)
    max_score = total_weight

    new_scores = dict(current_scores)
    for criterion_id, criterion in qc.gl_criteria.items():
        if not criterion.enabled:
            continue

        score = new_scores.get(criterion_id, 0.5)
        new_score = st.slider(
            f"{criterion_id}: {criterion.description[:50]}...",
            min_value=0.0,
            max_value=1.0,
            value=float(score),
            step=0.5,
            key=f"qc_gl_{index}_{criterion_id}"
        )

        new_scores[criterion_id] = new_score

    new_total = sum(new_scores.values())

    if new_total < threshold:
        st.caption(f"Score ({new_total:.1f}) below threshold ({threshold})")
    else:
        st.caption(f"Score: {new_total:.1f}/{max_score:.1f}")

    if isinstance(article, ArticleReview):
        article.qc_scores = new_scores
        article.qc_total = new_total


def export_qc_results(session):
    """Export QC assessment results."""
    import pandas as pd
    import json
    from src.core.screening_session import ArticleReview

    articles = session.articles

    results = []
    for i, article in enumerate(articles):
        if isinstance(article, ArticleReview):
            title = article.title
            abstract = article.abstract
            lit_type = article.get_literature_type()
            decision = article.qc_stage or "pending"
            qc_total = article.qc_total
            qc_scores = article.qc_scores if hasattr(article, 'qc_scores') and article.qc_scores else {}
        else:
            title = article.get("title", "")
            abstract = article.get("abstract", "")
            lit_type = article.get("literature_type", "WL")
            decision = article.get("qc_decision", "pending")
            qc_total = article.get("qc_total", 0)
            qc_scores = article.get("qc_scores", {})

        results.append({
            "Title": title,
            "Literature_Type": lit_type,
            "QC_Decision": decision.upper(),
            "QC_Score": qc_total,
            "QC_Scores": json.dumps(qc_scores, sort_keys=True) if qc_scores else "{}",
            "Abstract": abstract
        })

    df = pd.DataFrame(results)
    csv = df.to_csv(index=False)

    st.download_button(
        "Download QC Results (CSV)",
        data=csv,
        file_name="apollo_qc_assessment_results.csv",
        mime="text/csv"
    )

    passed = sum(1 for r in results if r["QC_Decision"] == "INCLUDE")
    failed = sum(1 for r in results if r["QC_Decision"] == "EXCLUDE")

    st.success(f"QC Assessment Complete: {passed} passed, {failed} failed quality")
