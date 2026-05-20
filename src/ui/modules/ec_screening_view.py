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
from src.core.protocol_utils import get_protocol_value
from src.advisory.advisory_scheduler import set_active_stage


def render_advisory_status_banner():
    """Render advisory generation progress banner."""
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


def render_ec_screening():
    """Render EC Screening Workspace - Focus Mode."""
    from src.core.dynamic_protocol import ProtocolState
    from src.core.screening_session import ScreeningSession

    set_active_stage("ec")

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

    session = st.session_state.apollo_session
    session.stage = "ec"

    if "advisory_pipeline_initialized_ec" not in st.session_state and session.articles:
        from src.advisory import initialize_advisory_pipeline
        from src.advisory.advisory_queue import reset_queue_for_stage
        from src.advisory.advisory_orchestrator import reset_orchestrator_for_stage

        print(f"[EC SCREEN] Resetting EC pipeline state")
        reset_queue_for_stage("ec")
        reset_orchestrator_for_stage("ec")

        pv = get_protocol_value(protocol, "protocol_version", "1.0")

        print(f"[EC SCREEN] Initializing advisory pipeline for EC stage")

        result = initialize_advisory_pipeline(
            articles=session.articles,
            protocol_version=pv,
            stage="ec",
            auto_start=True
        )

        st.session_state["advisory_pipeline_initialized_ec"] = True
        st.session_state["advisory_init_result_ec"] = result

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
    
    render_advisory_status_banner()

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
        current_ic_code = article.cis1 or ""
        ec_codes = get_ec_codes()

        st.markdown(f'''
        <div style="font-family:{TYPOGRAPHY["mono"]};font-size:0.65rem;color:{COLORS["cyan"]};letter-spacing:0.1em;margin-bottom:0.5rem;">
            ▸ MANUAL CRITERIA SELECTION (HUMAN AUTHORITY)
        </div>
        ''', unsafe_allow_html=True)

        selected_ec_manual = []
        cols_per_row = 5
        code_items = list(ec_codes.items())
        for i in range(0, len(code_items), cols_per_row):
            row_codes = code_items[i:i+cols_per_row]
            row_cols = st.columns(cols_per_row)
            for j, (code, desc) in enumerate(row_codes):
                with row_cols[j]:
                    key = f"ec_manual_{current_idx}_{code}"
                    default_selected = code in (article.ces1 or "").split(";") if article.ces1 else False
                    if st.checkbox(f"{code}", key=key, value=default_selected):
                        selected_ec_manual.append(code)

        manual_codes_str = ";".join(selected_ec_manual) if selected_ec_manual else ""
        article.ces1 = manual_codes_str
        article.cis1 = "NO" if manual_codes_str else ""

        divider()

        if not current_decision:
            if selected_ec_manual:
                st.markdown(f'<div style="font-size:0.75rem;color:{COLORS["error"]};margin-bottom:0.5rem;">Selected: {manual_codes_str}</div>', unsafe_allow_html=True)

            col_excl, col_incl, col_skip = st.columns([1, 1, 1])
            with col_excl:
                excl_clicked = st.button("EXCLUDE", type="secondary", width="stretch")
            with col_incl:
                incl_clicked = st.button("INCLUDE", type="primary", width="stretch")
            with col_skip:
                skip_clicked = st.button("SKIP", width="stretch")

            if excl_clicked:
                article.ec_stage = "exclude"
                article.ces1 = manual_codes_str if manual_codes_str else ""
                article.cis1 = "NO"
                article.revisor1 = session.researcher_id
                session.ec_completed += 1
                st.toast(f"✗ Article {current_idx + 1} EXCLUDED ({manual_codes_str or 'Manual'})", icon="❌")
                if current_idx < total - 1:
                    session.current_index = current_idx + 1
                st.rerun()

            if incl_clicked:
                article.ec_stage = "include"
                article.cis1 = "YES"
                article.ces1 = "NO"
                article.revisor1 = session.researcher_id
                session.ec_completed += 1
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
        
        else:
            selected_display = article.ces1 if article.ec_stage == "exclude" else "N/A"
            st.markdown(f'<div style="font-size:0.75rem;color:{COLORS["text_muted"]};margin-bottom:0.5rem;">Selected criteria: {selected_display}</div>', unsafe_allow_html=True)

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


def _format_authors_short(authors: str) -> str:
    """Format authors for compact display - max 2-3 with et al."""
    if not authors:
        return ""
    author_list = [a.strip() for a in authors.split(";") if a.strip()]
    if not author_list:
        return ""
    if len(author_list) <= 2:
        return "; ".join(author_list[:2])
    return f"{author_list[0]} et al."


def render_article_card(article, index: int):
    """Render paper review card - Abstract dominant, clean metadata."""
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
        return

    st.markdown(f"### {title}")

    try:
        year = metadata.get("year", "") if isinstance(metadata, dict) else ""
        authors = metadata.get("authors", "") if isinstance(metadata, dict) else ""
        source = metadata.get("source", "") if isinstance(metadata, dict) else ""
        doi = metadata.get("doi", "") if isinstance(metadata, dict) else ""

        authors_formatted = _format_authors_short(authors)

        meta_parts = []
        if year:
            meta_parts.append(str(year))
        if authors_formatted:
            meta_parts.append(authors_formatted)
        if source:
            meta_parts.append(source)

        if meta_parts:
            st.caption(" • ".join(meta_parts))
    except:
        pass

    if has_abstract:
        st.markdown(f"**Abstract**")
        st.markdown(f"<div style='line-height:1.7; font-size:0.9rem; color:{COLORS['text_secondary']};'>{abstract}</div>", unsafe_allow_html=True)
    else:
        st.info("No abstract available - review metadata for assessment")

    with st.expander("Provenance", expanded=False):
        try:
            global_id = metadata.get("global_id", "—")[:16] if isinstance(metadata, dict) else "—"
            completeness = metadata.get("completeness", "unknown") if isinstance(metadata, dict) else "unknown"

            st.markdown(f"**Full Authors:** {authors or '—'}")
            st.markdown(f"**DOI:** {doi or '—'}")
            st.markdown(f"**Source ID:** {global_id}")
            st.markdown(f"**Metadata Quality:** {completeness}")
        except:
            st.caption("Metadata unavailable")


def render_ai_advisory_panel(article, current_idx: int):
    """
    Render AI Advisory Panel using centralized cache.

    STRICT ISOLATION: This function ONLY renders - never generates advisories.
    UI MUST NEVER call LLM directly or generate advisories.
    """
    from src.advisory import get_ec_advisory, get_ec_advisory_status, AdvisoryStatus
    from src.advisory.advisory_cache import get_advisory_cache

    protocol_version = get_protocol_value(
        st.session_state.get("research_protocol"),
        "protocol_version",
        "1.0"
    )

    if hasattr(article, 'title'):
        title = getattr(article, 'title', '')
        abstract = getattr(article, 'abstract', '')
    else:
        title = article.get("title", "") if hasattr(article, 'get') else ""
        abstract = article.get("abstract", "") if hasattr(article, 'get') else ""

    print(f"[UI ADVISORY LOOKUP] Stage: ec | Title: {title[:50]} | Abstract: {abstract[:50] if abstract else 'empty'}...")
    print(f"[UI ADVISORY LOOKUP] Article ID: {getattr(article, 'article_id', 'N/A')}")

    cache = get_advisory_cache()
    ui_cache_key = cache.compute_cache_key(title, abstract, protocol_version)
    print(f"[UI ADVISORY LOOKUP] UICacheKey: {ui_cache_key} | Protocol: {protocol_version}")

    # Check what's in the queue for this article
    from src.advisory.advisory_queue import get_advisory_queue
    queue = get_advisory_queue(stage='ec')
    matching_items = [item for item in queue.state.items if item.article_id == getattr(article, 'article_id', None)]
    if matching_items:
        queue_key = matching_items[0].cache_key
        print(f"[UI ADVISORY LOOKUP] QueueCacheKey: {queue_key} | Match: {ui_cache_key == queue_key}")
    else:
        print(f"[UI ADVISORY LOOKUP] No matching queue item for article")

    advisory = get_ec_advisory(title, abstract, protocol_version)
    status = get_ec_advisory_status(title, abstract, protocol_version)

    print(f"[UI ADVISORY LOAD] Status: {status} | Advisory: {advisory}")
    
    with st.container(border=True):
        with st.expander("🤖 AI ADVISORY", expanded=False):
            print(f"[UI ADVISORY CHECK] Status: {status} == COMPLETED: {status == AdvisoryStatus.COMPLETED} | is_available: {advisory.is_available()}")

            if status == AdvisoryStatus.COMPLETED and advisory.is_available():
                from src.advisory.advisory_models import safe_enum_value, safe_decision, safe_status
                st.caption(f"Status: {safe_status(status)} | Decision: {safe_decision(advisory.decision)}")
                advisory_dict = {
                    "decision": safe_decision(advisory.decision),
                    "confidence": advisory.confidence,
                    "triggered_criteria": advisory.triggered_criteria,
                    "criterion_evaluations": {
                        ce.criterion_id: {
                            "criterion_name": ce.criterion_name,
                            "satisfied": ce.satisfied,
                            "evidence": ce.evidence,
                            "confidence": ce.confidence
                        }
                        for ce in advisory.criterion_evaluations
                    },
                    "justification": advisory.justification
                }
                render_suggestion_details(advisory_dict)
            else:
                print(f"[UI ADVISORY FALLBACK] Status: {status} | Decision: {advisory.decision if hasattr(advisory, 'decision') else 'N/A'}")
                if status == AdvisoryStatus.PENDING:
                    st.caption("⏳ Advisory pending — manual screening operational")
                    print(f"[EC ADVISORY STATE] PENDING | Status: {status}")
                elif status == AdvisoryStatus.PROCESSING:
                    st.caption("🔄 Advisory generating — please wait...")
                    print(f"[EC ADVISORY STATE] PROCESSING | Status: {status}")
                elif status == AdvisoryStatus.FAILED:
                    error_msg = advisory.error if advisory and hasattr(advisory, 'error') and advisory.error else "Unknown error"
                    st.caption(f"⚠️ Advisory failed: {error_msg}")
                    print(f"[EC ADVISORY STATE] FAILED | Error: {error_msg}")
                elif status == AdvisoryStatus.UNAVAILABLE:
                    st.caption("○ Advisory unavailable — manual screening fully operational")
                    print(f"[EC ADVISORY STATE] UNAVAILABLE | Status: {status}")
                else:
                    st.caption("○ No advisory generated — manual screening operational")
                    print(f"[EC ADVISORY STATE] UNKNOWN | Status: {status}")





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
    """
    Render LLM advisory as clean recommendation - researcher-focused.
    
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

    decision_color = COLORS["success"] if decision == "INCLUDE" else (COLORS["error"] if decision == "EXCLUDE" else COLORS["warning"])
    icon = "✅" if decision == "INCLUDE" else ("❌" if decision == "EXCLUDE" else "⚠️")

    st.markdown(f'''
    <div style="background:{COLORS['bg_card']};border:1px solid {COLORS['border_light']};padding:0.75rem;border-radius:4px;margin-bottom:0.75rem;">
        <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.25rem;">
            <span style="font-size:1.2rem;">{icon}</span>
            <span style="font-weight:600;font-size:1rem;color:{decision_color};">{decision}</span>
        </div>
        <div style="font-size:0.75rem;color:{COLORS['text_secondary']};">{confidence_label}</div>
    </div>
    ''', unsafe_allow_html=True)

    reasoning = suggestion.get("reasoning_summary") or suggestion.get("justification", "")
    if reasoning:
        with st.expander("Rationale", expanded=False):
            st.markdown(f"<div style='line-height:1.6;font-size:0.85rem;'>{reasoning}</div>", unsafe_allow_html=True)

    criterion_evals = suggestion.get("criterion_evaluations", {})
    if criterion_evals:
        if not isinstance(criterion_evals, dict):
            print(f"[ADVISORY RENDER ERROR] Invalid criterion_evaluations type in EC: {type(criterion_evals).__name__}")
            st.caption("Criterion evaluation data unavailable")
        else:
            ec_criteria = get_protocol_ec_criteria()
            triggered = {k: v for k, v in criterion_evals.items() if isinstance(v, dict) and v.get("triggered")}

            if triggered:
                st.markdown("**Triggered Criteria**")
                for cid, eval_data in triggered.items():
                    eval_justification = eval_data.get("justification", "")
                    official_def = ec_criteria.get(cid, "")
                    display_text = eval_justification[:100] if eval_justification else official_def
                    st.markdown(f"• **{cid}** — {display_text}")

            with st.expander("All Criteria Analysis", expanded=False):
                for cid, eval_data in criterion_evals.items():
                    if not isinstance(eval_data, dict):
                        continue
                    triggered = eval_data.get("triggered", False)
                    eval_justification = eval_data.get("justification", "")
                    official_def = ec_criteria.get(cid, "No definition")

                    status_icon = "✗" if triggered else "✓"
                    status_color = COLORS["error"] if triggered else COLORS["text_muted"]

                    st.markdown(f"**{status_icon} {cid}** — {official_def}")
                    if eval_justification:
                        st.caption(f"_{eval_justification}_")

    st.caption("*Human reviewer makes final eligibility decision*")

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