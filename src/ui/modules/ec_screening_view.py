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
import os
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
    """Render EC Screening Workspace - Focus Mode."""
    from src.core.dynamic_protocol import ProtocolState
    from src.core.screening_session import ScreeningSession

    if "research_protocol" not in st.session_state or st.session_state.research_protocol is None:
        st.warning("⚠ No Research Protocol configured.")
        return

    protocol = st.session_state.research_protocol

    if protocol.state == ProtocolState.DRAFT.value:
        print("!!! DEBUG UI !!! Auto-locking DRAFT protocol for screening")
        protocol.state = ProtocolState.LOCKED.value
        protocol.lock()

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
    """Render upload section for EC screening with scientific terminology."""
    section_header("📥 LITERATURE IMPORT", "Load ATLAS export to begin systematic review")

    st.markdown(f'''
    <div style="border:1px solid {COLORS['border_light']};background:{COLORS['bg_card']};padding:1rem;margin:1rem 0;">
        <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['text_secondary']};margin-bottom:0.5rem;">
            ▸ SOURCE REQUIREMENT
        </div>
        <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.7rem;color:{COLORS['text_muted']};line-height:1.6;">
            ATLAS export containing <span style="color:{COLORS['cyan']};">White Literature</span> (peer-reviewed) and 
            <span style="color:{COLORS['warning']};">Grey Literature</span> (non-peer-reviewed) sheets.
            Sequential screening with per-article eligibility decisions.
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
    """Render the main EC screening workspace - Focus Mode."""
    from src.core.screening_session import ArticleReview

    wl_progress = session.get_wl_progress()
    gl_progress = session.get_gl_progress()
    
    articles = session.articles
    current_idx = session.current_index
    total = len(articles)
    reviewed = session.ec_completed

    col_nav, col_stats, col_nav2 = st.columns([1, 3, 1])
    with col_nav:
        if st.button("◀", disabled=current_idx == 0, width="stretch"):
            session.current_index = max(0, current_idx - 1)
            st.rerun()
    with col_stats:
        progress_bar(reviewed, total, stage="EC")
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
        with col_advice:
            render_ai_advisory_panel(article, current_idx)

        divider()

        current_decision = article.ec_stage or ""
        current_ec_code = article.ces1 or ""
        ec_codes = get_ec_codes()
        
        if not current_decision:
            col_excl, col_incl, col_skip = st.columns([1, 1, 1])
            with col_excl:
                excl_clicked = st.button("EXCLUDE", type="secondary", width="stretch")
            with col_incl:
                incl_clicked = st.button("INCLUDE", type="primary", width="stretch")
            with col_skip:
                skip_clicked = st.button("SKIP", width="stretch")
            
            if excl_clicked:
                st.session_state[f"ec_show_codes_{current_idx}"] = "exclude"
                st.rerun()
            
            if incl_clicked:
                session.record_decision("include", notes="")
                article.cis1 = "PENDING"
                article.ces1 = "NO"
                article.revisor1 = session.researcher_id
                st.toast(f"✓ Article {current_idx + 1} INCLUDED", icon="✅")
                if current_idx < total - 1:
                    session.current_index = current_idx + 1
                st.rerun()
            
            if skip_clicked:
                session.record_decision("skip", notes="")
                st.toast(f"→ Article {current_idx + 1} SKIPPED", icon="⏭️")
                if current_idx < total - 1:
                    session.current_index = current_idx + 1
                st.rerun()
        
        elif current_decision == "exclude" and not current_ec_code:
            st.markdown(f'<div style="font-family:{TYPOGRAPHY["mono"]};font-size:0.7rem;color:{COLORS["error"]};margin-bottom:0.5rem;">▸ SELECT EXCLUSION CODE</div>', unsafe_allow_html=True)
            
            code_cols = st.columns(len(ec_codes))
            for i, (code, desc) in enumerate(ec_codes.items()):
                with code_cols[i]:
                    if st.button(f"[{code}]", key=f"ec_code_{current_idx}_{code}", width="stretch"):
                        article.ces1 = code
                        article.cis1 = "NO"
                        article.revisor1 = session.researcher_id
                        session.ec_completed += 1
                        st.toast(f"✗ Article {current_idx + 1} EXCLUDED ({code})", icon="❌")
                        if current_idx < total - 1:
                            session.current_index = current_idx + 1
                        st.rerun()
        
        else:
            col_status, col_clear = st.columns([3, 1])
            with col_status:
                status_badge("EXCLUDED" if current_decision == "exclude" else current_decision.upper())
            with col_clear:
                if st.button("CLEAR", width="stretch"):
                    session.articles[current_idx].ec_stage = ""
                    session.articles[current_idx].ces1 = ""
                    session.articles[current_idx].cis1 = ""
                    session.articles[current_idx].revisor1 = ""
                    session.ec_completed = max(0, session.ec_completed - 1)
                    st.toast(f"↺ Article {current_idx + 1} cleared", icon="🔄")
                    st.rerun()

    with st.sidebar:
        st.markdown("**PROTOCOL**")
        protocol = st.session_state.get("research_protocol")
        if protocol:
            summary = protocol.get_summary()
            st.markdown(f"v{summary['version']} | EC:{summary['ec_enabled']}")
        
        st.markdown("---")
        st.markdown(f"**WL:** {wl_progress['completed']}/{wl_progress['total']}")
        st.markdown(f"**GL:** {gl_progress['completed']}/{gl_progress['total']}")
        st.markdown("---")
        if st.button("EXPORT EC RESULTS", width="stretch"):
            export_ec_results(session)


def render_literature_type_filter(session):
    """Render literature type filter controls."""
    wl_progress = session.get_wl_progress()
    gl_progress = session.get_gl_progress()
    
    st.markdown(f'''
    <div style="border:1px solid {COLORS['border_light']};background:{COLORS['bg_card']};padding:0.75rem;margin-bottom:0.5rem;">
        <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.6rem;color:{COLORS['text_muted']};letter-spacing:0.1em;margin-bottom:0.5rem;">LITERATURE TYPE FILTER</div>
        <div style="display:flex;gap:1rem;align-items:center;">
            <span style="font-family:{TYPOGRAPHY['mono']};font-size:0.7rem;color:{COLORS['cyan']};">WL: {wl_progress['total']} articles</span>
            <span style="font-family:{TYPOGRAPHY['mono']};font-size:0.7rem;color:{COLORS['warning']};">GL: {gl_progress['total']} articles</span>
            <span style="font-family:{TYPOGRAPHY['mono']};font-size:0.7rem;color:{COLORS['text_secondary']};">| TOTAL: {len(session.articles)}</span>
        </div>
    </div>
    ''', unsafe_allow_html=True)


def render_literature_status_header(article, index: int):
    """Render compact literature type status header - Focus Mode. Duck typing safe."""
    try:
        if hasattr(article, 'get_literature_type'):
            lit_type = article.get_literature_type()
        elif hasattr(article, 'metadata') and isinstance(article.metadata, dict):
            lit_type = article.metadata.get("literature_type", "WL")
        else:
            lit_type = "WL"
    except:
        lit_type = "WL"
    
    header_bg = COLORS['cyan'] if lit_type == "WL" else COLORS['warning']
    header_text = "WL" if lit_type == "WL" else "GL"
    
    st.markdown(f'''
    <div style="display:flex;justify-content:space-between;align-items:center;background:{COLORS['bg_card']};border:1px solid {COLORS['border_light']};padding:0.5rem 1rem;margin-bottom:0.75rem;border-left:3px solid {header_bg};">
        <span style="background:{header_bg};color:#000;padding:2px 8px;font-family:{TYPOGRAPHY['mono']};font-size:0.7rem;font-weight:700;border-radius:2px;">{header_text}</span>
        <span style="font-family:{TYPOGRAPHY['mono']};font-size:0.7rem;color:{COLORS['text_muted']};">INDEX: {index + 1:04d}</span>
    </div>
    ''', unsafe_allow_html=True)


def render_article_card(article, index: int):
    """Render paper review card - Title dominant, metadata secondary."""
    try:
        if hasattr(article, 'get_literature_type'):
            lit_type = article.get_literature_type()
            title = getattr(article, 'title', '')
            abstract = getattr(article, 'abstract', '')
            metadata = getattr(article, 'metadata', {})
            if isinstance(metadata, dict):
                pass
            else:
                metadata = {}
        else:
            lit_type = "WL"
            title = ""
            abstract = ""
            metadata = {}
    except:
        lit_type = "WL"
        title = ""
        abstract = ""
        metadata = {}
    
    has_title = bool(title and str(title) != "nan" and len(str(title).strip()) > 0)
    has_abstract = bool(abstract and str(abstract) != "nan" and len(str(abstract).strip()) > 10)

    if not has_title:
        st.warning("Title is missing from this record")
    else:
        st.markdown(f"### {title}")
    
    try:
        year = metadata.get("year", "") if isinstance(metadata, dict) else ""
        authors = metadata.get("authors", "") if isinstance(metadata, dict) else ""
        source = metadata.get("source", "") if isinstance(metadata, dict) else ""
        doi = metadata.get("doi", "") if isinstance(metadata, dict) else ""
        
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
    cache_key = f"ec_advice_{article_id}"
    failed_key = f"ec_advice_failed_{article_id}"
    
    if st.session_state.get(failed_key, False):
        with st.container(border=True):
            from src.core.llm_assistant import get_llm_assistant
            llm = get_llm_assistant()
            error_msg = st.session_state.get(f"ec_advice_error_{article_id}", "")
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
            suggestion = get_llm_ec_suggestion(article)
            if suggestion:
                if "_error" in suggestion:
                    st.session_state[f"ec_advice_error_{article_id}"] = suggestion["_error"]
                    st.session_state[failed_key] = True
                else:
                    st.session_state[cache_key] = suggestion
            else:
                st.session_state[failed_key] = True
        st.rerun()


def get_llm_ec_suggestion(article) -> Optional[Dict]:
    """
    Get LLM advisory suggestion for EC screening with metadata robustness.
    """
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
            year = _extract_year_robust(article) if hasattr(article, 'metadata') else ""
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
            year = _extract_year_robust(metadata) if hasattr(metadata, 'get') else ""

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
            year=year,
            protocol_criteria=protocol_criteria,
            metadata=metadata
        )

        return suggestion.to_dict()
    except Exception as e:
        error_msg = str(e)
        print(f"!!! LLM CRASH !!! EC Suggestion failed: {error_msg}")
        return {"_error": error_msg}


def _extract_year_robust(source) -> Optional[int]:
    """
    Robust year extraction with multiple fallback sources.
    
    SPRINT 7.12 FIX: The ATLAS export stores the original Year
    in article.metadata['raw_data']['Year'], NOT in article.metadata['Year'].
    """
    raw_year = None
    
    if hasattr(source, 'metadata') and isinstance(source.metadata, dict):
        m = source.metadata
        raw = m.get("raw_data", {})
        
        raw_year = raw.get("Year") or raw.get("year") or raw.get("Publication_Year")
        if raw_year is None:
            raw_year = m.get("Year") or m.get("year") or m.get("publication_year")
    
    if hasattr(source, 'year') and raw_year is None:
        raw_year = getattr(source, 'year', None)
    
    if isinstance(source, dict) and raw_year is None:
        raw_year = source.get("Year") or source.get("year") or source.get("raw_data", {}).get("Year")
    
    if raw_year is None:
        return None
    
    if isinstance(raw_year, int) and 1900 <= raw_year <= 2030:
        return raw_year
    
    if isinstance(raw_year, float) and 1900 <= raw_year <= 2030:
        return int(raw_year)
    
    if isinstance(raw_year, str):
        cleaned = raw_year.strip()
        if cleaned and cleaned.lower() not in ['', 'none', 'nan', 'n/a', '#na']:
            try:
                result = int(float(cleaned))
                if 1900 <= result <= 2030:
                    return result
            except (ValueError, TypeError):
                pass
    
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
        "EC3": "Not peer-reviewed - WL sources must be peer-reviewed academic publications",
        "EC4": "Duplicate publication"
    }


def get_ec_codes() -> Dict[str, str]:
    """Get EC codes as button labels for coded selection."""
    return get_protocol_ec_criteria()


def render_suggestion_details(suggestion: Dict):
    """Render LLM advisory as clean recommendation - no percentages."""
    decision = suggestion.get("decision", "").upper()
    
    if decision == "INCLUDE":
        confidence_label = "Strong heuristic alignment"
        label_color = COLORS["success"]
    elif decision == "EXCLUDE":
        confidence_label = "Weak heuristic alignment"  
        label_color = COLORS["error"]
    else:
        confidence_label = "Moderate LLM signal"
        label_color = COLORS["warning"]
    
    is_fallback = suggestion.get("is_fallback", False)

    if is_fallback:
        st.warning("LLM service unavailable - manual review required")
        return

    grounding = suggestion.get("metadata_grounding", {})
    grounding_issues = []
    if grounding:
        if not grounding.get("title_used"):
            grounding_issues.append("Title partial")
        if not grounding.get("year_used"):
            grounding_issues.append("Year incomplete")
        if not grounding.get("abstract_used"):
            grounding_issues.append("Abstract partial")

    with st.container():
        st.markdown("**Recommendation**")
        decision_color = COLORS["success"] if decision == "INCLUDE" else (COLORS["error"] if decision == "EXCLUDE" else COLORS["warning"])
        st.markdown(f":{['x', 'check', 'warning'][0 if decision == 'EXCLUDE' else 1 if decision == 'INCLUDE' else 2]}**: {decision}")
        
        st.caption(f"Assessment: {confidence_label}")
        st.caption("_Human reviewer makes final eligibility decision_")

    reasoning = suggestion.get("reasoning_summary") or suggestion.get("justification", "")
    if reasoning:
        with st.expander("Assessment"):
            st.write(reasoning)

    criterion_evals = suggestion.get("criterion_evaluations", {})
    if criterion_evals:
        triggered = {k: v for k, v in criterion_evals.items() if v.get("triggered")}
        if triggered:
            with st.expander("Triggered criteria"):
                for cid, eval_data in triggered.items():
                    st.write(f"- {cid}: {eval_data.get('justification', '')[:80]}")

    ambiguity = suggestion.get("ambiguity_flags", [])
    if ambiguity and any(flag for flag in ambiguity if flag):
        st.warning(f"Note: {ambiguity[0] if ambiguity[0] else ambiguity[-1]}")

    # End of clean advisory

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
        ec_criteria = get_protocol_ec_criteria()
        
        with st.expander("CRITERION EVALUATIONS"):
            for cid, eval_data in criterion_evals.items():
                triggered = eval_data.get("triggered", False)
                eval_justification = eval_data.get("justification", "")
                ambiguity = eval_data.get("ambiguity_detected", False)
                
                official_def = ec_criteria.get(cid, "No definition available")
                is_methodological_na = eval_justification and "N/A:" in eval_justification
                
                if is_methodological_na:
                    eval_confidence = "◉"
                    eval_color = COLORS["cyan"]
                    st.markdown(f'''
                    <div style="border-left:2px solid {COLORS['cyan']};padding-left:0.75rem;margin:0.5rem 0;">
                        <span style="color:{eval_color};font-family:{TYPOGRAPHY["mono"]};font-size:0.75rem;">◉ {cid}</span>
                        <div style="font-family:{TYPOGRAPHY["mono"]};font-size:0.65rem;color:{COLORS['text_secondary']};margin-top:0.25rem;">▸ {official_def}</div>
                        <div style="font-family:{TYPOGRAPHY["mono"]};font-size:0.65rem;color:{COLORS['text_muted']};margin-top:0.25rem;font-style:italic;">└ {eval_justification}</div>
                    </div>
                    ''', unsafe_allow_html=True)
                else:
                    eval_confidence = "✓" if triggered else "✗"
                    eval_color = COLORS["error"] if triggered else COLORS["text_muted"]
                    border_color = COLORS["error"] if triggered else COLORS["border_light"]
                    
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

    def export_ec_results(session):
        """Export EC screening results using ExportEngine Excel format."""
        import tempfile
        import os
        from src.core.export_engine import ExportEngine

        try:
            engine = ExportEngine(protocol_version=session.protocol_version)
            
            ec_criteria = get_protocol_ec_criteria()
            
            protocol = st.session_state.get("research_protocol")
            ic_criteria = {}
            if protocol:
                ic_criteria = {
                    k: v.description
                    for k, v in protocol.ic.criteria.items()
                    if v.enabled
                }
            
            with tempfile.TemporaryDirectory() as tmpdir:
                excel_path = engine.export_decisions_excel(
                    session,
                    os.path.join(tmpdir, "ec_decisions.xlsx"),
                    ec_criteria_descriptions=ic_criteria,
                    ic_criteria_descriptions=ec_criteria
                )
                
                with open(excel_path, "rb") as f:
                    excel_data = f.read()
                
                st.download_button(
                    "Download EC Results (Excel)",
                    data=excel_data,
                    file_name="apollo_ec_screening_results.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
                wl_count = len(session.get_wl_articles())
                gl_count = len(session.get_gl_articles())
                st.success(f"EC Export Ready: {wl_count} WL + {gl_count} GL articles")
        except Exception as e:
            st.error(f"Export failed: {e}")