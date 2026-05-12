"""
APOLLO IC Screening Workspace - Forensic Terminal Aesthetic

Stage-specific workspace for Inclusion Criteria screening.
ONLY IC criteria are visible/applicable in this workspace.

Researcher screens papers that passed EC filtering.
"""
import streamlit as st
import uuid
from datetime import datetime
from typing import Dict, Optional
from src.ui.components import (
    terminal_header, section_header, status_badge, lit_type_badge,
    metric_tile, telemetry_panel, decision_card, progress_bar,
    stage_indicator, structured_card, terminal_stream, code_block,
    criteria_panel, divider, operational_status, provenance_indicator
)
from src.ui.theme import COLORS, TYPOGRAPHY


def render_ic_screening():
    """Render IC Screening Workspace."""
    from src.core.dynamic_protocol import ProtocolState
    from src.core.screening_session import ScreeningSession

    terminal_header(
        "IC SCREENING WORKSPACE",
        "Apply Inclusion Criteria to assess methodological relevance",
        status="ACTIVE"
    )
    divider()

    if "research_protocol" not in st.session_state or st.session_state.research_protocol is None:
        st.warning("⚠ No Research Protocol configured. Please go to 'Protocol Configuration' first.")
        return

    protocol = st.session_state.research_protocol

    if protocol.state == ProtocolState.DRAFT.value:
        st.warning("⚠ Protocol must be locked before screening.")
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
        st.session_state.apollo_session.stage = "ic"

    session = st.session_state.apollo_session

    if not session.articles:
        render_upload_section(session)
    else:
        render_screening_workspace(session)


def render_protocol_info_banner(protocol):
    """Show protocol info in terminal-style banner."""
    summary = protocol.get_summary()
    
    st.markdown(f'''
    <div style="border:1px solid {COLORS['border_light']};background:{COLORS['bg_card']};padding:1rem;margin-bottom:1rem;">
        <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.6rem;color:{COLORS['cyan']};letter-spacing:0.15em;margin-bottom:0.75rem;">
            ▸ PROTOCOL TELEMETRY
        </div>
        <div style="display:grid;grid-template-columns:repeat(4, 1fr);gap:1rem;">
            <div><span style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['text_muted']};">VERSION</span><br><span style="font-family:{TYPOGRAPHY['mono']};font-size:0.9rem;color:{COLORS['text_primary']};">v{summary['version']}</span></div>
            <div><span style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['text_muted']};">IC CRITERIA</span><br><span style="font-family:{TYPOGRAPHY['mono']};font-size:0.9rem;color:{COLORS['cyan']};">{summary['ic_enabled']}/{summary['ic_count']}</span></div>
            <div><span style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['text_muted']};">STATUS</span><br><span style="font-family:{TYPOGRAPHY['mono']};font-size:0.9rem;color:{COLORS['success']};">ACTIVE</span></div>
            <div><span style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['text_muted']};">HASH</span><br><span style="font-family:{TYPOGRAPHY['mono']};font-size:0.7rem;color:{COLORS['text_secondary']};">{summary['hash'][:16]}...</span></div>
        </div>
    </div>
    ''', unsafe_allow_html=True)


def render_upload_section(session):
    """Render upload section for IC screening."""
    section_header("DATA INGESTION", "Upload EC-filtered papers for IC screening")

    st.markdown(f'''
    <div style="border:1px solid {COLORS['border_light']};background:{COLORS['bg_card']};padding:1rem;margin:1rem 0;">
        <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['text_secondary']};margin-bottom:0.5rem;">
            INPUT REQUIREMENT
        </div>
        <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.7rem;color:{COLORS['text_muted']};line-height:1.6;">
            Upload results from EC Screening (papers that passed EC filtering).
            Only IC criteria will be applied in this workspace.
        </div>
    </div>
    ''', unsafe_allow_html=True)

    uploaded_file = st.file_uploader(
        "Upload EC Results or ATLAS File",
        type=["xlsx", "csv"],
        help="Upload papers for IC screening",
        label_visibility="collapsed"
    )

    if uploaded_file:
        with st.spinner("Loading papers..."):
            articles = session.ingest_from_upload(uploaded_file, stage="ic")
            if articles:
                session.current_index = 0
                st.success(f"Loaded {len(articles)} papers. Ready for IC screening.")
                st.rerun()
            else:
                st.error("Failed to load papers.")


def render_screening_workspace(session):
    """Render the main IC screening workspace."""
    from src.core.screening_session import ArticleReview

    articles = session.articles
    current_idx = session.current_index
    total = len(articles)
    reviewed = session.ic_completed
    pending = total - reviewed

    col_nav, col_stats, col_nav2 = st.columns([1, 2, 1])
    with col_nav:
        if st.button("◀ PREV", disabled=current_idx == 0):
            session.current_index = max(0, current_idx - 1)
            st.rerun()
    with col_stats:
        progress_bar(reviewed, total, stage="IC")
    with col_nav2:
        if st.button("NEXT ▶", disabled=current_idx >= total - 1):
            session.current_index = min(total - 1, current_idx + 1)
            st.rerun()

    divider()

    if articles and 0 <= current_idx < total:
        article = articles[current_idx]
        render_article_card(article, current_idx)
        render_ai_advisory_panel(article, current_idx)

        divider()

        col_excl, col_incl, col_skip = st.columns([1, 1, 1])
        current_decision = article.ic_stage or ""

        with col_excl:
            excl_clicked = st.button("EXCLUDE", type="secondary", use_container_width=True,
                                   disabled=current_decision == "exclude")
            if excl_clicked:
                session.current_index = current_idx
                session.record_decision("exclude", notes="")
                st.rerun()

        with col_incl:
            incl_clicked = st.button("INCLUDE", type="primary", use_container_width=True,
                                    disabled=current_decision == "include")
            if incl_clicked:
                session.current_index = current_idx
                session.record_decision("include", notes="")
                st.rerun()

        with col_skip:
            skip_clicked = st.button("SKIP", use_container_width=True,
                                    disabled=current_decision == "skip")
            if skip_clicked:
                session.current_index = current_idx
                session.record_decision("skip", notes="")
                st.rerun()

        if current_decision:
            from src.ui.components import status_badge
            status_badge(current_decision.upper())
            if st.button("CLEAR"):
                session.articles[current_idx].ic_stage = ""
                session.articles[current_idx].ic_notes = ""
                session.articles[current_idx].ic_timestamp = ""
                session.ic_completed = max(0, session.ic_completed - 1)
                st.rerun()

    divider()

    if st.button("EXPORT IC RESULTS", type="primary"):
        export_ic_results(session)


def render_article_card(article, index: int):
    """Render a single article card for IC screening in terminal style."""
    from src.core.screening_session import ArticleReview
    if isinstance(article, ArticleReview):
        lit_type = article.get_literature_type()
        article_id = article.article_id
        metadata = article.metadata
    else:
        lit_type = article.get("literature_type", "WL")
        article_id = article.get("global_id", "N/A")
        metadata = article

    st.markdown(f"""
    <div style="border:1px solid {COLORS['border_light']};background:{COLORS['bg_card']};padding:1rem;margin-bottom:1rem;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem;padding-bottom:0.75rem;border-bottom:1px solid {COLORS['border']};">
            <div style="display:flex;align-items:center;gap:1rem;">
                <span style="background:{COLORS['success'] if lit_type == 'WL' else COLORS['warning']};color:#000;padding:2px 8px;font-family:{TYPOGRAPHY['mono']};font-size:0.7rem;font-weight:600;">{lit_type}</span>
                <span style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['text_muted']};">INDEX: {index + 1:04d}</span>
            </div>
            <span style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['text_muted']};">EC: {article.ec_stage if isinstance(article, ArticleReview) else article.get('ec_decision', 'N/A')}</span>
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


def render_ai_advisory_panel(article, current_idx: int):
    """Render AI Advisory Panel for IC screening."""
    from src.core.screening_session import ArticleReview
    divider()
    section_header("AI ADVISORY PANEL", "Optional cognitive assistance - researcher makes final decision")

    cache_key = f"ic_advice_{current_idx}"
    cached_advice = st.session_state.get(cache_key, None)

    with st.expander("REQUEST AI ANALYSIS"):
        st.markdown(f'''
        <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['text_muted']};border-left:2px solid {COLORS['cyan']};padding-left:1rem;margin-bottom:1rem;">
            Human-in-the-Loop Review Mode: AI suggestions are <span style="color:{COLORS['warning']};">ADVISORY ONLY</span>.
            Final decision authority rests with the researcher.
        </div>
        ''', unsafe_allow_html=True)

        col_btn, col_status = st.columns([1, 2])
        with col_btn:
            request_suggestion = st.button(
                "GENERATE ANALYSIS",
                key=f"ic_advice_btn_{current_idx}",
                use_container_width=True
            )
        with col_status:
            if cached_advice:
                st.success("AI analysis available for this article")
            else:
                st.caption("No analysis generated yet for this article")

        if request_suggestion:
            with st.spinner("Generating AI analysis..."):
                suggestion = get_llm_ic_suggestion(article)
                if suggestion:
                    st.session_state[cache_key] = suggestion
                    cached_advice = suggestion
                    st.rerun()
                else:
                    st.warning("LLM unavailable — continue with manual review.")

        if cached_advice:
            divider()
            render_suggestion_details(cached_advice)


def get_llm_ic_suggestion(article) -> Optional[Dict]:
    """Get LLM advisory suggestion for IC screening."""
    from src.core.screening_session import ArticleReview
    try:
        from src.core.llm_assistant import LLMAssistant

        llm = LLMAssistant()
        if not llm.is_available():
            return None

        if isinstance(article, ArticleReview):
            title = article.title
            abstract = article.abstract
            literature_type = article.get_literature_type()
        else:
            title = article.get("title", "")
            abstract = article.get("abstract", "")
            literature_type = article.get("literature_type", "WL")

        protocol_criteria = get_protocol_ic_criteria()

        suggestion = llm.suggest_ic(
            title=title,
            abstract=abstract,
            literature_type=literature_type,
            protocol_criteria=protocol_criteria
        )

        return suggestion.to_dict()
    except Exception:
        return None


def get_protocol_ic_criteria() -> Dict[str, str]:
    """Get IC criteria from current protocol."""
    if "research_protocol" in st.session_state and st.session_state.research_protocol:
        protocol = st.session_state.research_protocol
        return {
            k: v.description
            for k, v in protocol.ic.criteria.items()
            if v.enabled
        }
    return {
        "IC1": "Addresses R&S practices",
        "IC2": "Reports empirical findings",
        "IC3": "Focuses on software industry context"
    }


def render_suggestion_details(suggestion: Dict):
    """Render detailed LLM suggestion in terminal style."""
    decision = suggestion.get("decision", "").upper()
    confidence = suggestion.get("confidence", 0)
    confidence_pct = int(confidence * 100)

    col_dec, col_conf = st.columns(2)
    with col_dec:
        if decision == "EXCLUDE":
            status_badge("EXCLUDED")
        else:
            status_badge("INCLUDED")
    with col_conf:
        metric_tile("CONFIDENCE", f"{confidence_pct}%")

    st.markdown(f"**Justification:** {suggestion.get('justification', 'N/A')}")

    triggered = suggestion.get("triggered_criteria", {})
    if triggered:
        criteria_panel({k: v for k, v in triggered.items() if v}, title="TRIGGERED CRITERIA")

    evidence = suggestion.get("evidence", [])
    if evidence:
        with st.expander("EVIDENCE PHRASES"):
            for phrase in evidence:
                st.markdown(f"  - {phrase}")

    ambiguity = suggestion.get("ambiguity_flags", [])
    if ambiguity:
        with st.expander("AMBIGUITY FLAGS"):
            for flag in ambiguity:
                st.markdown(f"  - {flag}")


def export_ic_results(session):
    """Export IC screening results."""
    import pandas as pd
    from src.core.screening_session import ArticleReview

    articles = session.articles

    results = []
    for i, article in enumerate(articles):
        if isinstance(article, ArticleReview):
            title = article.title
            abstract = article.abstract
            lit_type = article.get_literature_type()
            ec_dec = article.ec_stage or ""
            ic_dec = article.ic_stage or ""
        else:
            title = article.get("title", "")
            abstract = article.get("abstract", "")
            lit_type = article.get("literature_type", "WL")
            ec_dec = article.get("ec_decision", "")
            ic_dec = ""

        results.append({
            "Title": title,
            "Literature_Type": lit_type,
            "EC_Decision": ec_dec.upper(),
            "IC_Decision": ic_dec.upper() if ic_dec else "PENDING",
            "Abstract": abstract
        })

    df = pd.DataFrame(results)
    csv = df.to_csv(index=False)

    st.download_button(
        "Download IC Results (CSV)",
        data=csv,
        file_name="apollo_ic_screening_results.csv",
        mime="text/csv"
    )

    included = sum(1 for r in results if r["IC_Decision"] == "INCLUDE")
    excluded = sum(1 for r in results if r["IC_Decision"] == "EXCLUDE")

    st.success(f"IC Screening Complete: {included} included, {excluded} excluded")