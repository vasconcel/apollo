"""
APOLLO IC Screening Workspace - Forensic Terminal Aesthetic

Stage-specific workspace for Inclusion Criteria screening.
ONLY IC criteria are visible/applicable in this workspace.

Researcher screens papers that passed EC filtering.
"""
import streamlit as st
import uuid
import os
import json
import hashlib
import time
from datetime import datetime
from typing import Dict, Optional, Any
from src.ui.components import (
    terminal_header, section_header, status_badge, lit_type_badge,
    metric_tile, telemetry_panel, decision_card, progress_bar,
    stage_indicator, structured_card, terminal_stream, code_block,
    criteria_panel, divider, operational_status, provenance_indicator
)
from src.ui.theme import COLORS, TYPOGRAPHY

from src.advisory import (
    get_advisory,
    get_advisory_status,
    get_cache_stats,
    AdvisoryStatus,
    AdvisoryDecision,
)
from src.advisory.advisory_models import (
    safe_decision,
    safe_status,
    safe_enum_value,
    compute_evidence_strength,
    compute_uncertainty_score,
    assess_autonomy,
)
from src.advisory.calibration_tracker import log_calibration_event
from src.advisory.advisory_scheduler import set_active_stage

_st_cache_key_calls = 0
from src.core.protocol_utils import get_protocol_value








def _get_protocol_ic_criteria_cached() -> Dict[str, str]:
    """Get IC criteria from protocol - routes through protocol_query_service."""
    from src.core.protocol_query_service import get_ic_criteria
    if "research_protocol" in st.session_state and st.session_state.research_protocol:
        return get_ic_criteria(st.session_state.research_protocol)
    return get_ic_criteria(None)


def _record_ic_decision(session, article, current_idx: int, decision: str):
    """
    Record IC decision.
    CRITICAL: Codes are assigned MANUALLY by researcher, NOT from AI.
    Human always has final authority over AI suggestions.
    """
    original_idx = session.articles.index(article)
    session.articles[original_idx].ic_stage = decision
    session.articles[original_idx].revisor1 = session.researcher_id
    session.record_decision(decision, notes=f"Auto-inferred from AI advisory")


def render_ic_screening():
    """Render IC Screening Workspace - Focus Mode."""
    from src.core.dynamic_protocol import ProtocolState
    from src.core.screening_session import ScreeningSession

    set_active_stage("ic")

    if "research_protocol" not in st.session_state or st.session_state.research_protocol is None:
        st.warning("⚠ No Research Protocol configured.")
        return

    protocol = st.session_state.research_protocol

    if protocol.state == ProtocolState.DRAFT.value:
        print("!!! DEBUG UI !!! Auto-locking DRAFT protocol for IC screening")
        protocol.state = ProtocolState.LOCKED.value
        protocol.lock()

    if "apollo_session" not in st.session_state:
        st.session_state.apollo_session = ScreeningSession(
            session_id=str(uuid.uuid4())[:8],
            created_at=datetime.now().isoformat(),
            protocol_version=protocol.protocol_version,
            researcher_id="researcher_1"
        )

    session = st.session_state.apollo_session
    session.stage = "ic"

    if "advisory_pipeline_initialized_ic" not in st.session_state and session.articles:
        from src.advisory import initialize_advisory_pipeline
        from src.advisory.advisory_queue import reset_queue_for_stage
        from src.advisory.advisory_orchestrator import reset_orchestrator_for_stage

        print(f"[IC SCREEN] Resetting IC pipeline state")
        reset_queue_for_stage("ic")
        reset_orchestrator_for_stage("ic")

        pv = get_protocol_value(protocol, "protocol_version", "1.0")

        print(f"[IC SCREEN] Initializing advisory pipeline for IC stage")

        result = initialize_advisory_pipeline(
            articles=session.articles,
            protocol_version=pv,
            stage="ic",
            auto_start=True,
            protocol=protocol
        )

        st.session_state["advisory_pipeline_initialized_ic"] = True
        st.session_state["advisory_init_result_ic"] = result
    
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
    """Render the main IC screening workspace - Focus Mode."""
    from src.core.screening_session import ArticleReview

    wl_progress = session.get_wl_progress()
    gl_progress = session.get_gl_progress()

    ec_included_articles = session.get_ec_included_articles()
    total_ec_included = len(ec_included_articles)

    if "ic_current_index" not in st.session_state:
        st.session_state.ic_current_index = 0

    current_idx = min(st.session_state.ic_current_index, total_ec_included - 1) if total_ec_included > 0 else 0
    total = total_ec_included
    reviewed = session.ic_completed

    articles = ec_included_articles
    
    st.markdown(f'''
    <div style="border:1px solid {COLORS['cyan']};background:{COLORS['bg_card']};padding:0.75rem;margin-bottom:1rem;">
        <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['cyan']};letter-spacing:0.1em;margin-bottom:0.5rem;">
            ▸ IC FUNNEL STATUS
        </div>
        <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.8rem;color:{COLORS['text_primary']};">
            <span style="color:{COLORS['success']};">Articles arriving from EC: {total}</span>
            <span style="color:{COLORS['text_muted']};margin-left:1rem;">|</span>
            <span style="color:{COLORS['text_muted']};margin-left:1rem;">Total session: {len(session.articles)}</span>
        </div>
    </div>
    ''', unsafe_allow_html=True)
    
    if total == 0:
        st.warning("No articles have passed EC stage. Complete EC screening first.")
        return

    col_nav, col_stats, col_nav2 = st.columns([1, 3, 1])
    with col_nav:
        if st.button("◀", disabled=current_idx == 0, width="stretch"):
            st.session_state.ic_current_index = max(0, current_idx - 1)
            st.rerun()
    with col_stats:
        progress_bar(reviewed, total, stage="IC")
    with col_nav2:
        if st.button("▶", disabled=current_idx >= total - 1, width="stretch"):
            st.session_state.ic_current_index = min(total - 1, current_idx + 1)
            st.rerun()
    
    _render_ic_advisory_status_banner()
    
    if articles and 0 <= current_idx < total:
        article = articles[current_idx]
        render_literature_status_header(article, current_idx)
        
        col_article, col_advice = st.columns([3, 1])
        with col_article:
            render_article_card(article, current_idx)
            
            try:
                if hasattr(article, 'get_literature_type'):
                    lit_type = article.get_literature_type()
                else:
                    lit_type = article.get("literature_type", "WL") if hasattr(article, 'get') else "WL"
            except:
                lit_type = "WL"
            if lit_type == "GL":
                render_gl_ic_requirements(article)
        with col_advice:
            render_ai_advisory_panel(article, current_idx)

        divider()

        current_decision = article.ic_stage or ""
        current_ic_code = getattr(article, 'cis1', "") or ""
        ic_codes = get_ic_codes()

        st.markdown(f'''
        <div style="font-family:{TYPOGRAPHY["mono"]};font-size:0.65rem;color:{COLORS["cyan"]};letter-spacing:0.1em;margin-bottom:0.5rem;">
            ▸ MANUAL CRITERIA SELECTION (HUMAN AUTHORITY)
        </div>
        ''', unsafe_allow_html=True)

        selected_ic_manual = []
        cols_per_row = 5
        code_items = list(ic_codes.items())
        for i in range(0, len(code_items), cols_per_row):
            row_codes = code_items[i:i+cols_per_row]
            row_cols = st.columns(cols_per_row)
            for j, (code, desc) in enumerate(row_codes):
                with row_cols[j]:
                    key = f"ic_manual_{current_idx}_{code}"
                    default_selected = code in (article.cis1 or "").split(";") if article.cis1 else False
                    if st.checkbox(f"{code}", key=key, value=default_selected):
                        selected_ic_manual.append(code)

        manual_codes_str = ";".join(selected_ic_manual) if selected_ic_manual else ""

        divider()

        if not current_decision:
            if selected_ic_manual:
                st.markdown(f'<div style="font-size:0.75rem;color:{COLORS["success"]};margin-bottom:0.5rem;">Selected: {manual_codes_str}</div>', unsafe_allow_html=True)

            col_excl, col_incl, col_skip = st.columns([1, 1, 1])
            with col_excl:
                excl_clicked = st.button("EXCLUDE", type="secondary", width="stretch")
            with col_incl:
                incl_clicked = st.button("INCLUDE", type="primary", width="stretch")
            with col_skip:
                skip_clicked = st.button("SKIP", width="stretch")

            if excl_clicked:
                original_idx = session.articles.index(article)
                session.articles[original_idx].ic_stage = "exclude"
                session.articles[original_idx].cis1 = manual_codes_str if manual_codes_str else "N/A"
                session.articles[original_idx].revisor1 = session.researcher_id
                session.ic_completed += 1

                advisory = get_advisory(article.title, article.abstract, protocol_version, stage="ic") if article.title else None
                if advisory:
                    metadata = article.metadata if hasattr(article, 'metadata') else {}
                    log_calibration_event(
                        article_id=article.article_id,
                        protocol_version=protocol_version,
                        stage="ic",
                        advisory=advisory,
                        human_decision="EXCLUDE",
                        metadata=metadata
                    )

                st.toast(f"✗ Article {current_idx + 1} EXCLUDED ({manual_codes_str or 'Manual'})", icon="❌")
                if current_idx < total - 1:
                    st.session_state.ic_current_index = current_idx + 1
                st.rerun()

            if incl_clicked:
                original_idx = session.articles.index(article)
                session.articles[original_idx].ic_stage = "include"
                session.articles[original_idx].cis1 = manual_codes_str if manual_codes_str else "YES"
                session.articles[original_idx].revisor1 = session.researcher_id
                session.ic_completed += 1

                advisory = get_advisory(article.title, article.abstract, protocol_version, stage="ic") if article.title else None
                if advisory:
                    metadata = article.metadata if hasattr(article, 'metadata') else {}
                    log_calibration_event(
                        article_id=article.article_id,
                        protocol_version=protocol_version,
                        stage="ic",
                        advisory=advisory,
                        human_decision="INCLUDE",
                        metadata=metadata
                    )

                st.toast(f"✓ Article {current_idx + 1} INCLUDED ({manual_codes_str or 'YES'})", icon="✅")
                if current_idx < total - 1:
                    st.session_state.ic_current_index = current_idx + 1
                st.rerun()

            if skip_clicked:
                session.record_decision("skip", notes="")
                st.toast(f"→ Article {current_idx + 1} SKIPPED", icon="⏭️")
                if current_idx < total - 1:
                    st.session_state.ic_current_index = current_idx + 1
                st.rerun()

        else:
            selected_display = article.cis1 if article.ic_stage else "N/A"
            st.markdown(f'<div style="font-size:0.75rem;color:{COLORS["text_muted"]};margin-bottom:0.5rem;">Selected criteria: {selected_display}</div>', unsafe_allow_html=True)

            original_idx = session.articles.index(article)
            col_status, col_clear = st.columns([3, 1])
            with col_status:
                from src.ui.components import status_badge
                status_badge("INCLUDED" if current_decision == "include" else current_decision.upper())
            with col_clear:
                if st.button("CLEAR", width="stretch"):
                    session.articles[original_idx].ic_stage = ""
                    session.articles[original_idx].cis1 = ""
                    session.articles[original_idx].revisor1 = ""
                    session.ic_completed = max(0, session.ic_completed - 1)
                    st.toast(f"↺ Article {current_idx + 1} cleared", icon="🔄")
                    st.rerun()

    with st.sidebar:
        st.markdown("**PROTOCOL**")
        protocol = st.session_state.get("research_protocol")
        if protocol:
            summary = protocol.get_summary()
            st.markdown(f"v{summary['version']} | IC:{summary['ic_enabled']}")
        
        st.markdown("---")
        wl_articles = session.get_wl_articles()
        gl_articles = session.get_gl_articles()
        wl_ic_count = sum(1 for a in wl_articles if a.is_ec_included)
        gl_ic_count = sum(1 for a in gl_articles if a.is_ec_included)
        st.markdown(f"**WL:** {reviewed}/{wl_ic_count}")
        st.markdown(f"**GL:** {reviewed}/{gl_ic_count}")
        st.markdown("---")
        if st.button("EXPORT IC RESULTS", width="stretch"):
            export_ic_results(session)


def render_literature_type_filter(session):
    """Render literature type filter controls."""
    wl_progress = session.get_wl_progress()
    gl_progress = session.get_gl_progress()
    
    wl_ec_passed = sum(1 for a in session.get_wl_articles() if a.is_ec_included)
    gl_ec_passed = sum(1 for a in session.get_gl_articles() if a.is_ec_included)
    
    st.markdown(f'''
    <div style="border:1px solid {COLORS['border_light']};background:{COLORS['bg_card']};padding:0.75rem;margin-bottom:0.5rem;">
        <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.6rem;color:{COLORS['text_muted']};letter-spacing:0.1em;margin-bottom:0.5rem;">LITERATURE TYPE FILTER - IC STAGE</div>
        <div style="display:flex;gap:1rem;align-items:center;">
            <span style="font-family:{TYPOGRAPHY['mono']};font-size:0.7rem;color:{COLORS['cyan']};">WL: {wl_ec_passed} EC-passed</span>
            <span style="font-family:{TYPOGRAPHY['mono']};font-size:0.7rem;color:{COLORS['warning']};">GL: {gl_ec_passed} EC-passed</span>
            <span style="font-family:{TYPOGRAPHY['mono']};font-size:0.7rem;color:{COLORS['text_secondary']};">| TOTAL IC: {wl_ec_passed + gl_ec_passed}</span>
        </div>
    </div>
    ''', unsafe_allow_html=True)


def render_literature_status_header(article, index: int):
    """Render compact literature type status header - Focus Mode. Duck typing safe."""
    try:
        if hasattr(article, 'get_literature_type'):
            lit_type = article.get_literature_type()
            ec_stage = getattr(article, 'ec_stage', '')
        elif hasattr(article, 'metadata') and isinstance(article.metadata, dict):
            lit_type = article.metadata.get("literature_type", "WL")
            ec_stage = article.metadata.get("ec_stage", "")
        else:
            lit_type = "WL"
            ec_stage = ""
    except:
        lit_type = "WL"
        ec_stage = ""
    
    header_bg = COLORS['cyan'] if lit_type == "WL" else COLORS['warning']
    header_text = "WL" if lit_type == "WL" else "GL"
    
    st.markdown(f'''
    <div style="display:flex;justify-content:space-between;align-items:center;background:{COLORS['bg_card']};border:1px solid {COLORS['border_light']};padding:0.5rem 1rem;margin-bottom:0.75rem;border-left:3px solid {header_bg};">
        <span style="background:{header_bg};color:#000;padding:2px 8px;font-family:{TYPOGRAPHY['mono']};font-size:0.7rem;font-weight:700;border-radius:2px;">{header_text}</span>
        <span style="font-family:{TYPOGRAPHY['mono']};font-size:0.7rem;color:{COLORS['text_muted']};">INDEX: {index + 1:04d} | EC: {ec_stage}</span>
    </div>
    ''', unsafe_allow_html=True)


def render_gl_ic_requirements(article):
    """
    Render GL IC stage requirements panel.
    GL articles passing EC must be reviewed via URL since no abstract exists.
    """
    try:
        if hasattr(article, 'get_literature_type'):
            metadata = getattr(article, 'metadata', {})
            url = metadata.get("url", "") if isinstance(metadata, dict) else ""
            title = getattr(article, 'title', "")
        else:
            url = article.get("url", "") if hasattr(article, 'get') else ""
            title = article.get("title", "") if hasattr(article, 'get') else ""
    except:
        url = ""
        title = ""
    
    st.markdown(f'''
    <div style="border:2px solid {COLORS['warning']};background:{COLORS['bg_card']};padding:1rem;margin-bottom:1rem;">
        <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['warning']};letter-spacing:0.1em;margin-bottom:0.75rem;">
            ⚠ GL IC STAGE REQUIREMENTS
        </div>
        <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.7rem;color:{COLORS['text_secondary']};line-height:1.6;">
            <p>Grey Literature does NOT contain abstracts in ATLAS. If this article passed EC (Title-only evaluation), you must <strong>manually review the source document</strong> to assess IC relevance.</p>
            <p style="color:{COLORS['warning']};font-weight:600;">This article's IC decision must NOT be auto-excluded or skipped.</p>
        </div>
    </div>
    ''', unsafe_allow_html=True)
    
    if url and url != "nan" and len(str(url).strip()) > 0:
        st.markdown(f'''
        <div style="text-align:center;margin:1.5rem 0;">
            <a href="{url}" target="_blank">
                <button style="background:linear-gradient(135deg, #FFB020 0%, #FF9500 100%);color:#000;padding:1rem 3rem;font-family:{TYPOGRAPHY['mono']};font-size:1rem;font-weight:700;border:none;border-radius:4px;cursor:pointer;box-shadow:0 4px 12px rgba(255,176,32,0.3);">
                    🔗 OPEN SOURCE URL
                </button>
            </a>
        </div>
        ''', unsafe_allow_html=True)
    else:
        st.warning("⚠ No URL available for this GL article. Manual review may not be possible.")


def render_article_card(article, index: int):
    """Render paper review card - Title dominant, metadata secondary."""
    try:
        if hasattr(article, 'get_literature_type'):
            title = getattr(article, 'title', '')
            abstract = getattr(article, 'abstract', '')
            metadata = getattr(article, 'metadata', {})
            if not isinstance(metadata, dict):
                metadata = {}
        else:
            title = ""
            abstract = ""
            metadata = {}
    except:
        title = ""
        abstract = ""
        metadata = {}
    
    has_abstract = bool(abstract and str(abstract) != "nan" and len(str(abstract)) > 10)

    st.markdown(f"### {title}")
    
    try:
        year = metadata.get("year", "") if isinstance(metadata, dict) else ""
        authors = metadata.get("authors", "") if isinstance(metadata, dict) else ""
        source = metadata.get("source", "") if isinstance(metadata, dict) else ""
        
        authors_short = authors[:35] + "..." if len(authors) > 35 else authors if authors else "—"
        
        if year:
            meta_line = f"**{year}**"
            if authors_short != "—":
                meta_line += f" · {authors_short}"
            if source:
                meta_line += f" · {source[:25]}"
            st.caption(meta_line)
        elif authors_short != "—":
            st.caption(f"**{authors_short}**" + (f" · {source[:25]}" if source else ""))
    except:
        pass

    with st.expander("Metadata & Provenance", expanded=False):
        try:
            doi = metadata.get("doi", "") if isinstance(metadata, dict) else ""
            global_id = metadata.get("global_id", "—")[:16] if isinstance(metadata, dict) else "—"
            year_source = metadata.get("year_source", "unknown") if isinstance(metadata, dict) else "unknown"
            completeness = metadata.get("metadata_completeness", "unknown") if isinstance(metadata, dict) else "unknown"
            
            year_src_labels = {"atlas": "ATLAS", "doi": "DOI", "manual": "Manual", "csv": "CSV", "unknown": "Unknown"}
            
            if year and year != "nan" and year != "—":
                year_display = f"{year}"
                if year_source != "unknown":
                    year_display += f" ({year_src_labels.get(year_source, year_source)})"
            elif year_source != "unknown":
                year_display = f"Unknown ({year_src_labels.get(year_source, year_source)})"
            else:
                year_display = "Unknown"
            
            st.markdown(f"""
            | Field | Value |
            |-------|--------|
            | Year | {year_display} |
            | Authors | {authors or '—'} |
            | Source | {source or '—'} |
            """)
            
            with st.expander("Provenance Details", expanded=False):
                st.markdown(f"""
                | Field | Value |
                |-------|--------|
                | DOI | {doi or '—'} |
                | ID | {global_id} |
                | Completeness | {completeness} |
                """, unsafe_allow_html=True)
        except:
            st.caption("Metadata unavailable")

    if has_abstract:
        with st.expander("Abstract", expanded=(index == 0)):
            st.markdown(f"<div style='line-height:1.7; font-size:0.9rem;'>{abstract}</div>", unsafe_allow_html=True)


def render_ai_advisory_panel(article, current_idx: int):
    """
    Render AI Advisory Panel using centralized cache.
    
    STRICT ISOLATION: This function ONLY renders - never generates advisories.
    
    UI MUST NEVER:
    - Call LLM directly
    - Generate advisories
    - Retry or backoff
    
    UI MAY:
    - Read from advisory cache
    - Show status (READY/PROCESSING/FAILED/UNAVAILABLE)
    - Render persisted advisories
    """
    protocol_version = get_protocol_value(
        st.session_state.get("research_protocol"),
        "protocol_version",
        "1.0"
    )
    
    stage = "ic"
    
    if hasattr(article, 'title'):
        title = getattr(article, 'title', '')
        abstract = getattr(article, 'abstract', '')
    else:
        title = article.get("title", "") if hasattr(article, 'get') else ""
        abstract = article.get("abstract", "") if hasattr(article, 'get') else ""
    
    advisory = get_advisory(title, abstract, protocol_version, stage=stage)
    
    status = get_advisory_status(title, abstract, protocol_version, stage=stage)

    with st.container(border=True):
        with st.expander("🤖 AI ADVISORY", expanded=False):
            print(f"[IC ADVISORY RENDER] Title: {title[:30]}... | Status: {status} | Decision: {safe_decision(advisory.decision) if advisory else 'N/A'} | Available: {advisory.is_available() if advisory and hasattr(advisory, 'is_available') else False}")

            is_completed = status == AdvisoryStatus.COMPLETED
            if is_completed:
                decision_val = advisory.decision if advisory else None
                is_uncertain = decision_val in (
                    AdvisoryDecision.UNCERTAIN,
                    AdvisoryDecision.INSUFFICIENT_EVIDENCE,
                    AdvisoryDecision.CANNOT_DETERMINE,
                ) if decision_val else False

                if (advisory and advisory.is_available()) or is_uncertain:
                    st.caption(f"Status: {safe_status(status)} | Decision: {safe_decision(advisory.decision) if advisory else 'N/A'}")

                    if is_uncertain and advisory:
                        evidence_strength = compute_evidence_strength(advisory)
                        uncertainty_score = compute_uncertainty_score(advisory)
                        st.warning("⚠ AI could not determine relevance with sufficient confidence. Manual review required.")
                        st.markdown(f"**Uncertainty Score:** {uncertainty_score:.2f} | **Evidence Strength:** {evidence_strength:.2f}")

                    advisory_dict = {
                        "decision": safe_decision(advisory.decision) if advisory else "N/A",
                        "confidence": advisory.confidence if advisory else 0.0,
                        "triggered_criteria": advisory.triggered_criteria if advisory else [],
                        "criterion_evaluations": {
                            ce.criterion_id: {
                                "criterion_name": ce.criterion_name,
                                "satisfied": ce.satisfied,
                                "evidence": ce.evidence,
                                "confidence": ce.confidence
                            }
                            for ce in (advisory.criterion_evaluations if advisory else [])
                        },
                        "justification": advisory.justification if advisory else ""
                    }
                    render_suggestion_details(advisory_dict)
                else:
                    if status == AdvisoryStatus.PENDING:
                        st.caption("⏳ Advisory pending — manual screening operational")
                        print(f"[IC ADVISORY STATE] PENDING | Article: {title[:30]}...")
                    elif status == AdvisoryStatus.PROCESSING:
                        st.caption("🔄 Advisory generating — please wait...")
                        print(f"[IC ADVISORY STATE] PROCESSING | Article: {title[:30]}...")
                    elif status == AdvisoryStatus.FAILED:
                        error_msg = advisory.error if advisory and hasattr(advisory, 'error') and advisory.error else "Unknown error"
                        st.caption(f"⚠️ Advisory failed: {error_msg}")
                        print(f"[IC ADVISORY STATE] FAILED | Article: {title[:30]}... | Error: {error_msg}")
                    elif status == AdvisoryStatus.UNAVAILABLE:
                        st.caption("○ Advisory unavailable — manual screening fully operational")
                        print(f"[IC ADVISORY STATE] UNAVAILABLE | Article: {title[:30]}...")
                    else:
                        st.caption("○ No advisory generated — manual screening operational")
                        print(f"[IC ADVISORY STATE] UNKNOWN | Article: {title[:30]}... | Status: {status}")





def get_protocol_ic_criteria() -> Dict[str, str]:
    """Get IC criteria from current protocol - routes through protocol_query_service."""
    from src.core.protocol_query_service import get_ic_criteria
    if "research_protocol" in st.session_state and st.session_state.research_protocol:
        return get_ic_criteria(st.session_state.research_protocol)
    return get_ic_criteria(None)


def get_ic_codes() -> Dict[str, str]:
    """Get IC codes as button labels for coded selection."""
    return get_protocol_ic_criteria()


def render_suggestion_details(suggestion: Dict):
    """
    Render detailed LLM suggestion in terminal style with criterion-by-criterion view.
    
    DEFENSIVE VALIDATION: Added type checking to handle malformed advisory structures.
    """
    if not isinstance(suggestion, dict):
        print(f"[ADVISORY RENDER ERROR] Invalid suggestion type: {type(suggestion).__name__}")
        st.warning("Advisory data unavailable - manual review required")
        return
    
    if not suggestion:
        print(f"[ADVISORY RENDER ERROR] Empty suggestion dict")
        st.warning("Advisory empty - manual review required")
        return
    
    decision = suggestion.get("decision", "").upper()
    confidence = suggestion.get("confidence", 0)
    is_fallback = suggestion.get("is_fallback", False)
    is_uncertain = decision in ("UNCERTAIN", "INSUFFICIENT_EVIDENCE", "CANNOT_DETERMINE")

    if is_uncertain:
        signal_label = "Insufficient evidence for reliable determination"
    elif confidence >= 0.7:
        signal_label = "Strong heuristic alignment"
    elif confidence >= 0.4:
        signal_label = "Moderate LLM signal"
    else:
        signal_label = "Weak heuristic alignment"

    if is_fallback:
        st.warning("⚠ STRUCTURED ADVISORY UNAVAILABLE — LLM service unavailable. Manual review required.")
    else:
        metadata_grounding = suggestion.get("metadata_grounding", {})
        if metadata_grounding:
            st.markdown(f'''
            <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.55rem;color:{COLORS['text_muted']};border-left:2px solid {COLORS['success']};padding:0.5rem;margin-bottom:0.75rem;">
                METADATA GROUNDING: title={metadata_grounding.get("title_used", False)} | abstract={metadata_grounding.get("abstract_used", False)} | lit_type={metadata_grounding.get("literature_type_used", False)}
            </div>
            ''', unsafe_allow_html=True)

    col_dec, col_conf = st.columns([1, 1])
    with col_dec:
        if decision == "EXCLUDE":
            status_badge("EXCLUDED")
        elif decision == "INCLUDE":
            status_badge("INCLUDED")
        elif is_uncertain:
            status_badge("UNCERTAIN")
        elif decision == "UNAVAILABLE":
            status_badge("FALLBACK")
        else:
            status_badge(decision)
    with col_conf:
        metric_tile("SIGNAL", signal_label)

    reasoning_summary = suggestion.get("reasoning_summary", "")
    if reasoning_summary:
        st.markdown(f"**Reasoning:** {reasoning_summary}")
    else:
        st.markdown(f"**Justification:** {suggestion.get('justification', 'N/A')}")

    criterion_evals = suggestion.get("criterion_evaluations", {})
    
    if not isinstance(criterion_evals, dict):
        print(f"[ADVISORY RENDER ERROR] Invalid criterion_evaluations type: {type(criterion_evals).__name__}")
        criterion_evals = {}
    
    triggered_list = suggestion.get("triggered_criteria", [])

    if isinstance(triggered_list, dict):
        triggered_dict = {k: v for k, v in triggered_list.items() if v}
    else:
        triggered_dict = {}
        if isinstance(triggered_list, list):
            for cid in triggered_list:
                eval_data = criterion_evals.get(cid, {})
                if isinstance(eval_data, dict) and eval_data.get("triggered"):
                    triggered_dict[cid] = eval_data.get("justification", "")

    if triggered_dict:
        criteria_panel(triggered_dict, title="TRIGGERED CRITERIA")

    if criterion_evals:
        ic_criteria = get_protocol_ic_criteria()
        
        with st.expander("CRITERION EVALUATIONS"):
            if not isinstance(criterion_evals, dict):
                st.caption("Criterion evaluation data unavailable")
            else:
                for cid, eval_data in criterion_evals.items():
                    if not isinstance(eval_data, dict):
                        continue
                    triggered = eval_data.get("triggered", False)
                    eval_justification = eval_data.get("justification", "")
                    ambiguity = eval_data.get("ambiguity_detected", False)
                
                official_def = ic_criteria.get(cid, "No definition available")
                eval_confidence = "✓" if triggered else "✗"
                eval_color = COLORS["warning"] if triggered else COLORS["text_muted"]
                border_color = COLORS["warning"] if triggered else COLORS["border_light"]
                
                st.markdown(f'''
                <div style="border-left:2px solid {border_color};padding-left:0.75rem;margin:0.5rem 0;">
                    <span style="color:{eval_color};font-family:{TYPOGRAPHY["mono"]};font-size:0.8rem;font-weight:600;">{eval_confidence} {cid}</span>
                    <div style="font-family:{TYPOGRAPHY["mono"]};font-size:0.65rem;color:{COLORS['text_secondary']};margin-top:0.25rem;">▸ {official_def}</div>
                </div>
                ''', unsafe_allow_html=True)
                
                if eval_justification:
                    st.markdown(f'<div style="font-family:{TYPOGRAPHY["mono"]};font-size:0.65rem;color:{COLORS["text_muted"]};margin-left:1.5rem;margin-top:0.25rem;">└ {eval_justification}</div>', unsafe_allow_html=True)
    
    ambiguity = suggestion.get("ambiguity_flags", [])
    if ambiguity and any(flag for flag in ambiguity if flag):
        with st.expander("AMBIGUITY FLAGS"):
            for flag in ambiguity_flags:
                if flag:
                    st.markdown(f"  - {flag}")


def _render_ic_advisory_status_banner():
    """Render advisory generation progress banner for IC screening."""
    try:
        from src.advisory import get_advisory_pipeline_status, is_advisory_generation_active
        
        status = get_advisory_pipeline_status()
        
        generated = status.get("generated_count", 0)
        pending = status.get("pending_count", 0)
        failed = status.get("failed_count", 0)
        total = generated + pending + failed
        
        is_active = is_advisory_generation_active()
        
        if total > 0:
            with st.container(border=True):
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    if is_active:
                        st.info(f"🔄 Generating: {generated}/{total}")
                    else:
                        st.success(f"✓ Generated: {generated}/{total}")
                
                with col2:
                    st.info(f"⏳ Pending: {pending}")
                
                with col3:
                    if failed > 0:
                        st.warning(f"⚠ Failed: {failed}")
                    else:
                        st.caption("✓ No failures")
                
                with col4:
                    if is_active:
                        st.caption("Worker: Active")
                    else:
                        st.caption("Worker: Idle")
                        
    except Exception as e:
        pass


def render_advisory_status_panel():
    """
    Render read-only advisory status panel.
    
    Shows:
    - Cache statistics
    - Generated/pending counts
    - Status breakdown
    
    STRICT ISOLATION: This function ONLY reads, never generates.
    """
    st.markdown("### 📊 ADVISORY STATUS")
    
    try:
        stats = get_cache_stats()
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            metric_tile("CACHED", f"{stats.get('disk_cache_count', 0)}")
        
        with col2:
            total = stats.get('total_cached', 0)
            if total > 0:
                st.success(f"✓ {total} ready")
            else:
                st.info("○ None generated")
        
        with col3:
            cache_dir = stats.get('cache_dir', 'data/cache/advisories')
            st.caption(f"📁 {cache_dir}")
        
        st.markdown("---")
        
        st.caption("**Usage:** Run `python -m src.advisory.precompute_advisories` to generate advisories offline.")
        st.caption("**Note:** UI never invokes LLM. Advisories must be precomputed.")
        
    except Exception as e:
        st.warning(f"Advisory status unavailable: {e}")


def export_ic_results(session):
    """Export IC screening results using ExportEngine Excel format."""
    import tempfile
    from src.core.export_engine import ExportEngine

    try:
        engine = ExportEngine(protocol_version=session.protocol_version)
        
        ic_criteria = get_protocol_ic_criteria()
        
        protocol = st.session_state.get("research_protocol")
        ec_criteria = {}
        if protocol:
            ec_criteria = {
                k: v.description
                for k, v in protocol.ec.criteria.items()
                if v.enabled
            }
        
        with tempfile.TemporaryDirectory() as tmpdir:
            excel_path = engine.export_decisions_excel(
                session,
                os.path.join(tmpdir, "ic_decisions.xlsx"),
                ec_criteria_descriptions=ic_criteria,
                ic_criteria_descriptions=ec_criteria
            )
            
            with open(excel_path, "rb") as f:
                excel_data = f.read()
            
            st.download_button(
                "Download IC Results (Excel)",
                data=excel_data,
                file_name="apollo_ic_screening_results.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
            wl_included = sum(1 for a in session.get_wl_articles() if a.ic_stage == "include")
            gl_included = sum(1 for a in session.get_gl_articles() if a.ic_stage == "include")
            st.success(f"IC Export Ready: {wl_included} WL + {gl_included} GL included")
    except Exception as e:
        st.error(f"Export failed: {e}")