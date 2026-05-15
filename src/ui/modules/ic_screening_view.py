"""
APOLLO IC Screening Workspace - Forensic Terminal Aesthetic

Stage-specific workspace for Inclusion Criteria screening.
ONLY IC criteria are visible/applicable in this workspace.

Researcher screens papers that passed EC filtering.
"""
import streamlit as st
import uuid
import os
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
    """Render IC Screening Workspace - Focus Mode."""
    from src.core.dynamic_protocol import ProtocolState
    from src.core.screening_session import ScreeningSession

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
    """Render the main IC screening workspace - Focus Mode."""
    from src.core.screening_session import ArticleReview

    wl_progress = session.get_wl_progress()
    gl_progress = session.get_gl_progress()
    
    articles = [a for a in session.articles if a.is_ec_included]
    current_idx = session.current_index
    total = len(articles)
    reviewed = session.ic_completed
    
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
            session.current_index = max(0, current_idx - 1)
            st.rerun()
    with col_stats:
        progress_bar(reviewed, total, stage="IC")
    with col_nav2:
        if st.button("▶", disabled=current_idx >= total - 1, width="stretch"):
            session.current_index = min(total - 1, current_idx + 1)
            st.rerun()

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
        current_ic_code = article.cis1 or ""
        ic_codes = get_ic_codes()
        
        if not current_decision:
            col_excl, col_incl, col_skip = st.columns([1, 1, 1])
            with col_excl:
                excl_clicked = st.button("EXCLUDE", type="secondary", width="stretch")
            with col_incl:
                incl_clicked = st.button("INCLUDE", type="primary", width="stretch")
            with col_skip:
                skip_clicked = st.button("SKIP", width="stretch")
            
            if excl_clicked:
                st.session_state[f"ic_show_codes_{current_idx}"] = "exclude"
                st.rerun()
            
            if incl_clicked:
                st.session_state[f"ic_show_codes_{current_idx}"] = "include"
                st.toast(f"✓ Article {current_idx + 1} marked for INCLUSION", icon="✅")
                st.rerun()
            
            if skip_clicked:
                session.record_decision("skip", notes="")
                st.toast(f"→ Article {current_idx + 1} SKIPPED", icon="⏭️")
                if current_idx < total - 1:
                    session.current_index = current_idx + 1
                st.rerun()
        
        elif current_decision == "exclude" and not current_ic_code:
            st.markdown(f'<div style="font-family:{TYPOGRAPHY["mono"]};font-size:0.7rem;color:{COLORS["error"]};margin-bottom:0.5rem;">▸ SELECT EXCLUSION CODE</div>', unsafe_allow_html=True)
            
            code_cols = st.columns(len(ic_codes))
            for i, (code, desc) in enumerate(ic_codes.items()):
                with code_cols[i]:
                    if st.button(f"[{code}]", key=f"ic_code_{current_idx}_{code}", width="stretch"):
                        article.cis1 = "NO"
                        article.ces1 = code
                        article.revisor1 = session.researcher_id
                        session.ic_completed += 1
                        st.toast(f"✗ Article {current_idx + 1} EXCLUDED ({code})", icon="❌")
                        if current_idx < total - 1:
                            session.current_index = current_idx + 1
                        st.rerun()
        
        elif current_decision == "include" and not current_ic_code:
            st.markdown(f'<div style="font-family:{TYPOGRAPHY["mono"]};font-size:0.7rem;color:{COLORS["success"]};margin-bottom:0.5rem;">▸ SELECT INCLUSION CODE</div>', unsafe_allow_html=True)
            
            code_cols = st.columns(len(ic_codes))
            for i, (code, desc) in enumerate(ic_codes.items()):
                with code_cols[i]:
                    if st.button(f"[{code}]", key=f"ic_code_{current_idx}_{code}", width="stretch"):
                        article.cis1 = code
                        article.ces1 = "NO"
                        article.revisor1 = session.researcher_id
                        session.ic_completed += 1
                        st.toast(f"✓ Article {current_idx + 1} INCLUDED ({code})", icon="✅")
                        if current_idx < total - 1:
                            session.current_index = current_idx + 1
                        st.rerun()
        
        else:
            col_status, col_clear = st.columns([3, 1])
            with col_status:
                from src.ui.components import status_badge
                status_badge("INCLUDED" if current_decision == "include" else current_decision.upper())
            with col_clear:
                if st.button("CLEAR", width="stretch"):
                    session.articles[current_idx].ic_stage = ""
                    session.articles[current_idx].cis1 = ""
                    session.articles[current_idx].ces1 = ""
                    session.articles[current_idx].revisor1 = ""
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
        wl_ic_count = sum(1 for a in session.get_wl_articles() if a.is_ec_included)
        gl_ic_count = sum(1 for a in session.get_gl_articles() if a.is_ec_included)
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
    """Auto-trigger AI Advisory Panel - Zero manual interaction."""
    article_id = getattr(article, 'article_id', f"idx_{current_idx}")
    cache_key = f"ic_advice_{article_id}"
    failed_key = f"ic_advice_failed_{article_id}"
    
    if st.session_state.get(failed_key, False):
        with st.container(border=True):
            from src.core.llm_assistant import get_llm_assistant
            llm = get_llm_assistant()
            error_msg = st.session_state.get(f"ic_advice_error_{article_id}", "")
            if error_msg:
                st.error(f"LLM Error: {error_msg}")
            elif not llm.is_available():
                st.warning("⚠️ AI Advisory Offline: Check .env file or library installation.")
            else:
                st.warning("🤖 AI Advisory Unavailable - LLM service unreachable")
        return
    
    cached_advice = st.session_state.get(cache_key, None)
    
    if cached_advice:
        with st.container(border=True):
            with st.expander("🤖 AI ADVISORY", expanded=True):
                render_suggestion_details(cached_advice)
    else:
        with st.spinner("🤖 AI Consultant is analyzing paper..."):
            suggestion = get_llm_ic_suggestion(article)
            if suggestion:
                if "_error" in suggestion:
                    st.session_state[f"ic_advice_error_{article_id}"] = suggestion["_error"]
                    st.session_state[failed_key] = True
                else:
                    st.session_state[cache_key] = suggestion
            else:
                st.session_state[failed_key] = True
        st.rerun()


def get_llm_ic_suggestion(article) -> Optional[Dict]:
    """Get LLM advisory suggestion for IC screening."""
    try:
        from src.core.llm_assistant import LLMAssistant

        llm = LLMAssistant()
        if not llm.is_available():
            return None

        if hasattr(article, 'get_literature_type'):
            title = getattr(article, 'title', '')
            abstract = getattr(article, 'abstract', '')
            literature_type = article.get_literature_type()
            metadata = getattr(article, 'metadata', {})
        else:
            try:
                title = article.get("title", "") if hasattr(article, 'get') else ""
            except:
                title = ""
            try:
                abstract = article.get("abstract", "") if hasattr(article, 'get') else ""
            except:
                abstract = ""
            try:
                literature_type = article.get("literature_type", "WL") if hasattr(article, 'get') else "WL"
            except:
                literature_type = "WL"
            metadata = article if hasattr(article, 'get') else {}

        protocol_criteria = get_protocol_ic_criteria()

        suggestion = llm.suggest_ic(
            title=title,
            abstract=abstract,
            literature_type=literature_type,
            protocol_criteria=protocol_criteria,
            metadata=metadata
        )

        return suggestion.to_dict()
    except Exception as e:
        error_msg = str(e)
        print(f"!!! LLM CRASH !!! IC Suggestion failed: {error_msg}")
        return {"_error": error_msg}


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


def get_ic_codes() -> Dict[str, str]:
    """Get IC codes as button labels for coded selection."""
    return get_protocol_ic_criteria()


def render_suggestion_details(suggestion: Dict):
    """Render detailed LLM suggestion in terminal style with criterion-by-criterion view."""
    decision = suggestion.get("decision", "").upper()
    confidence = suggestion.get("confidence", 0)
    is_fallback = suggestion.get("is_fallback", False)

    if confidence >= 0.7:
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
    triggered_list = suggestion.get("triggered_criteria", [])

    if isinstance(triggered_list, dict):
        triggered_dict = {k: v for k, v in triggered_list.items() if v}
    else:
        triggered_dict = {}
        for cid in triggered_list:
            eval_data = criterion_evals.get(cid, {})
            if eval_data.get("triggered"):
                triggered_dict[cid] = eval_data.get("justification", "")

    if triggered_dict:
        criteria_panel(triggered_dict, title="TRIGGERED CRITERIA")

    if criterion_evals:
        ic_criteria = get_protocol_ic_criteria()
        
        with st.expander("CRITERION EVALUATIONS"):
            for cid, eval_data in criterion_evals.items():
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
                
                if ambiguity:
                    st.markdown(f'<div style="font-family:{TYPOGRAPHY["mono"]};font-size:0.65rem;color:{COLORS["warning"]};margin-left:1.5rem;">⚠ ambiguity detected</div>', unsafe_allow_html=True)

    ambiguity = suggestion.get("ambiguity_flags", [])
    if ambiguity and any(flag for flag in ambiguity if flag):
        with st.expander("AMBIGUITY FLAGS"):
            for flag in ambiguity:
                if flag:
                    st.markdown(f"  - {flag}")

    advisory_hash = suggestion.get("advisory_hash", "")
    if advisory_hash:
        st.caption(f"advisory: {advisory_hash}")


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