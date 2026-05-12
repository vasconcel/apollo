"""
APOLLO EC Screening Workspace - Forensic Terminal Aesthetic

Stage-specific workspace for Exclusion Criteria screening.
ONLY EC criteria are visible/applicable in this workspace.

HUMAN-IN-THE-LOOP PRINCIPLE:
- Researcher makes final screening decisions
- AI suggestions are ADVISORY ONLY
- No automatic LLM processing
- LLM calls only on explicit researcher request
"""
import streamlit as st
import uuid
from datetime import datetime
from typing import Dict, Optional
from src.ui.components import (
    terminal_header, section_header, status_badge, lit_type_badge,
    metric_tile, telemetry_panel, decision_card, progress_bar,
    stage_indicator, structured_card, terminal_stream, code_block,
    criteria_panel, divider, operational_status, provenance_indicator,
    kappa_display, conflict_resolution_card
)
from src.ui.theme import COLORS, TYPOGRAPHY


def render_ec_screening():
    """Render EC Screening Workspace."""
    from src.core.dynamic_protocol import ProtocolState
    from src.core.screening_session import ScreeningSession

    terminal_header(
        "EC SCREENING WORKSPACE",
        "Apply Exclusion Criteria to remove irrelevant studies",
        status="ACTIVE"
    )
    divider()

    if "research_protocol" not in st.session_state or st.session_state.research_protocol is None:
        st.warning("⚠ No Research Protocol configured. Please go to 'Protocol Configuration' first.")
        return

    protocol = st.session_state.research_protocol

    if protocol.state == ProtocolState.DRAFT.value:
        st.warning("⚠ Protocol must be locked before screening. Go to 'Protocol Configuration' to lock your protocol.")
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
        st.session_state.apollo_session.stage = "ec"

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
            <div><span style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['text_muted']};">EC CRITERIA</span><br><span style="font-family:{TYPOGRAPHY['mono']};font-size:0.9rem;color:{COLORS['cyan']};">{summary['ec_enabled']}/{summary['ec_count']}</span></div>
            <div><span style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['text_muted']};">STATUS</span><br><span style="font-family:{TYPOGRAPHY['mono']};font-size:0.9rem;color:{COLORS['success']};">ACTIVE</span></div>
            <div><span style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['text_muted']};">HASH</span><br><span style="font-family:{TYPOGRAPHY['mono']};font-size:0.7rem;color:{COLORS['text_secondary']};">{summary['hash'][:16]}...</span></div>
        </div>
    </div>
    ''', unsafe_allow_html=True)


def render_upload_section(session):
    """Render upload section for EC screening."""
    section_header("DATA INGESTION", "Upload ATLAS export files to begin EC screening")

    st.markdown(f'''
    <div style="border:1px solid {COLORS['border_light']};background:{COLORS['bg_card']};padding:1rem;margin:1rem 0;">
        <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['text_secondary']};margin-bottom:0.5rem;">
            INPUT FORMAT REQUIREMENT
        </div>
        <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.7rem;color:{COLORS['text_muted']};line-height:1.6;">
            Upload ATLAS export with <span style="color:{COLORS['cyan']};">White Literature</span> and <span style="color:{COLORS['cyan']};">Grey Literature</span> sheets.
            Papers reviewed sequentially. Decisions recorded per-item.
        </div>
    </div>
    ''', unsafe_allow_html=True)

    uploaded_file = st.file_uploader(
        "Upload ATLAS Excel File",
        type=["xlsx"],
        help="Upload your ATLAS export with WL and GL sheets",
        label_visibility="collapsed"
    )

    if uploaded_file:
        with st.spinner("Loading papers..."):
            articles = session.ingest_from_upload(uploaded_file, stage="ec")
            if articles:
                session.current_index = 0
                st.success(f"Loaded {len(articles)} papers. Ready for EC screening.")
                st.rerun()
            else:
                st.error("Failed to load papers from file.")


def render_screening_workspace(session):
    """Render the main EC screening workspace."""
    from src.core.screening_session import ArticleReview

    articles = session.articles
    current_idx = session.current_index
    total = len(articles)
    reviewed = session.ec_completed
    pending = total - reviewed

    col_nav, col_stats, col_nav2 = st.columns([1, 2, 1])
    with col_nav:
        if st.button("◀ PREV", disabled=current_idx == 0):
            session.current_index = max(0, current_idx - 1)
            st.rerun()
    with col_stats:
        progress_bar(reviewed, total, stage="EC")
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
        current_decision = article.ec_stage or ""

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
                session.articles[current_idx].ec_stage = ""
                session.articles[current_idx].ec_notes = ""
                session.articles[current_idx].ec_timestamp = ""
                session.ec_completed = max(0, session.ec_completed - 1)
                st.rerun()

    divider()

    if st.button("EXPORT EC RESULTS", type="primary"):
        export_ec_results(session)


def render_article_card(article, index: int):
    """Render full paper review card in terminal style."""
    from src.core.screening_session import ArticleReview
    if isinstance(article, ArticleReview):
        lit_type = article.get_literature_type()
        has_title = bool(article.title and article.title != "nan" and len(article.title.strip()) > 0)
        has_abstract = bool(article.abstract and article.abstract != "nan" and len(article.abstract.strip()) > 10)
        metadata = article.metadata
        article_id = article.article_id
    else:
        lit_type = article.get("literature_type", "WL")
        has_title = article.get("title") and article.get("title") != "nan"
        has_abstract = article.get("abstract") and article.get("abstract") != "nan"
        metadata = article
        article_id = metadata.get("global_id", "N/A")

    st.markdown(f"""
    <div style="border:1px solid {COLORS['border_light']};background:{COLORS['bg_card']};padding:1rem;margin-bottom:1rem;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem;padding-bottom:0.75rem;border-bottom:1px solid {COLORS['border']};">
            <div style="display:flex;align-items:center;gap:1rem;">
                <span style="background:{COLORS['success'] if lit_type == 'WL' else COLORS['warning']};color:#000;padding:2px 8px;font-family:{TYPOGRAPHY['mono']};font-size:0.7rem;font-weight:600;">{lit_type}</span>
                <span style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['text_muted']};">INDEX: {index + 1:04d}</span>
            </div>
            <span style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['text_muted']};">ARTICLE ID: {article_id[:16] if article_id else 'N/A'}...</span>
        </div>
    """, unsafe_allow_html=True)

    if not has_title:
        st.warning("Title is missing from this record")
    else:
        st.markdown(f"### {article.title}")

    col_meta1, col_meta2 = st.columns(2)
    with col_meta1:
        authors = metadata.get("authors", "")
        if authors and authors != "nan":
            st.markdown(f"**Authors:** {authors}")
        else:
            st.markdown("**Authors:** _[NOT AVAILABLE]_")

        year = metadata.get("year", "")
        if year and year != "nan":
            st.markdown(f"**Year:** {year}")
    with col_meta2:
        source = metadata.get("source", "")
        if source and source != "nan":
            st.markdown(f"**Source:** {source}")
        else:
            st.markdown("**Source:** _[NOT AVAILABLE]_")

        doi = metadata.get("doi", "")
        if doi and doi != "nan":
            st.markdown(f"**DOI:** {doi}")
        else:
            url = metadata.get("url", "")
            if url and url != "nan":
                st.markdown(f"**URL:** [{url[:50]}...]({url})")

    st.markdown("</div>", unsafe_allow_html=True)

    if not has_abstract:
        st.info("Abstract: _[NOT AVAILABLE]_ — Manual review required")
    else:
        with st.expander("ABSTRACT", expanded=True):
            st.markdown(article.abstract if isinstance(article, ArticleReview) else article.get("abstract", ""))

    keywords = metadata.get("keywords", "")
    if keywords and keywords != "nan" and len(keywords.strip()) > 0:
        st.markdown(f"**Keywords:** {keywords}")

    completeness = metadata.get("metadata_completeness", "unknown")
    if completeness == "minimal":
        st.warning("Limited metadata — review with caution")
    elif completeness == "partial":
        st.info("Partial metadata available")

    with st.expander("DEBUG METADATA"):
        st.json(metadata.get("raw_data", {}))


def render_ai_advisory_panel(article, current_idx: int):
    """Render AI Advisory Panel - OPTIONAL cognitive support for researcher."""
    divider()
    section_header("AI ADVISORY PANEL", "Optional cognitive assistance - researcher makes final decision")

    cache_key = f"ec_advice_{current_idx}"
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
                use_container_width=True,
                help="Request AI advisory for this article"
            )
        with col_status:
            if cached_advice:
                st.success("AI analysis available for this article")
            else:
                st.caption("No analysis generated yet for this article")

        if request_suggestion:
            with st.spinner("Generating AI analysis..."):
                suggestion = get_llm_ec_suggestion(article)

                if suggestion:
                    st.session_state[cache_key] = suggestion
                    cached_advice = suggestion
                    st.rerun()
                else:
                    st.warning("LLM unavailable — continue with manual review.")

        if cached_advice:
            divider()
            render_suggestion_details(cached_advice)


def get_llm_ec_suggestion(article) -> Optional[Dict]:
    """Get LLM advisory suggestion for EC screening with metadata robustness."""
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
            year = article.metadata.get("year", "")
            metadata = article.metadata
        else:
            title = article.get("title", "")
            abstract = article.get("abstract", "")
            literature_type = article.get("literature_type", "WL")
            year = article.get("year")
            metadata = article

        has_title = bool(title and title != "nan" and len(title.strip()) > 0)
        has_abstract = bool(abstract and abstract != "nan" and len(abstract.strip()) > 10)

        if not has_title or not has_abstract:
            return {
                "stage": "ec",
                "decision": "uncertain",
                "confidence": 0.3,
                "justification": "Insufficient metadata: " +
                    ("title " if not has_title else "") +
                    ("abstract " if not has_abstract else "") +
                    "not available for reliable evaluation.",
                "triggered_criteria": {},
                "evidence": [],
                "ambiguity_flags": [
                    "Title missing" if not has_title else "",
                    "Abstract missing" if not has_abstract else "",
                    "Reduce confidence — manual review recommended"
                ]
            }

        protocol_criteria = get_protocol_ec_criteria()

        suggestion = llm.suggest_ec(
            title=title,
            abstract=abstract,
            literature_type=literature_type,
            protocol_criteria=protocol_criteria
        )

        return suggestion.to_dict()
    except Exception:
        return None


def get_protocol_ec_criteria() -> Dict[str, str]:
    """Get EC criteria from current protocol."""
    if "research_protocol" in st.session_state and st.session_state.research_protocol:
        protocol = st.session_state.research_protocol
        return {
            k: v.description
            for k, v in protocol.ec.criteria.items()
            if v.enabled
        }
    return {
        "EC1": "Not empirical SE research",
        "EC2": "Published before 2015",
        "EC3": "Not peer-reviewed (WL only)",
        "EC4": "Duplicate publication"
    }


def render_suggestion_details(suggestion: Dict):
    """Render detailed LLM suggestion in terminal style."""
    decision = suggestion.get("decision", "").upper()
    confidence = suggestion.get("confidence", 0)
    confidence_pct = int(confidence * 100)

    col_dec, col_conf = st.columns([1, 1])

    if decision == "EXCLUDE":
        with col_dec:
            status_badge("EXCLUDED")
    elif decision == "INCLUDE":
        with col_dec:
            status_badge("INCLUDED")
    elif decision == "UNCERTAIN":
        with col_dec:
            status_badge("PENDING")
    else:
        with col_dec:
            st.markdown(f"**{decision}**")

    with col_conf:
        metric_tile("CONFIDENCE", f"{confidence_pct}%")

    st.markdown(f"**Reasoning:** {suggestion.get('justification', 'N/A')}")

    triggered = suggestion.get("triggered_criteria", {})
    if triggered and any(v for v in triggered.values()):
        criteria_panel({k: v for k, v in triggered.items() if v}, title="TRIGGERED CRITERIA")

    evidence = suggestion.get("evidence", [])
    if evidence:
        with st.expander("EVIDENCE EXTRACTED"):
            for phrase in evidence:
                st.markdown(f"  - \"{phrase}\"")

    ambiguity = suggestion.get("ambiguity_flags", [])
    if ambiguity and any(ambiguity):
        with st.expander("AMBIGUITY FLAGS"):
            for flag in ambiguity:
                if flag:
                    st.markdown(f"  - {flag}")


def export_ec_results(session):
    """Export EC screening results."""
    import pandas as pd
    from src.core.screening_session import ArticleReview

    articles = session.articles

    results = []
    for i, article in enumerate(articles):
        if isinstance(article, ArticleReview):
            title = article.title
            abstract = article.abstract
            lit_type = article.get_literature_type()
            metadata = article.metadata
        else:
            title = article.get("title", "")
            abstract = article.get("abstract", "")
            lit_type = article.get("literature_type", "WL")
            metadata = article

        decision = article.ec_stage if isinstance(article, ArticleReview) else metadata.get("ec_decision", "")
        results.append({
            "Title": title,
            "Literature_Type": lit_type,
            "EC_Decision": decision.upper() if decision else "PENDING",
            "EC_Notes": article.ec_notes if isinstance(article, ArticleReview) else metadata.get("ec_notes", ""),
            "Abstract": abstract
        })

    df = pd.DataFrame(results)
    csv = df.to_csv(index=False)

    st.download_button(
        "Download EC Results (CSV)",
        data=csv,
        file_name="apollo_ec_screening_results.csv",
        mime="text/csv"
    )

    included = sum(1 for r in results if r["EC_Decision"] == "INCLUDE")
    excluded = sum(1 for r in results if r["EC_Decision"] == "EXCLUDE")

    st.success(f"EC Screening Complete: {included} included, {excluded} excluded")