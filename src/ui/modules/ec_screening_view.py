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
import time
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
from src.advisory import (
    get_ec_advisory,
    get_ec_advisory_status,
    AdvisoryStatus,
    get_advisory_cache,
    get_advisory_queue,
)
from src.advisory.advisory_models import (
    safe_decision,
    safe_enum_value,
    safe_status,
    AdvisoryDecision,
    assess_autonomy,
    compute_evidence_strength,
    compute_uncertainty_score,
)
from src.advisory.advisory_scheduler import set_active_stage
from src.advisory.queue_manager import compute_queue_summary, get_cached_queue_summary, filter_articles_by_queue, ReviewMode, clear_queue_cache


def validate_session_index(articles_count: int, current_index: int) -> int:
    """
    Validate and fix session index to prevent out-of-bounds navigation.
    Returns safe index within valid range.
    """
    if articles_count == 0:
        return 0
    if current_index < 0:
        return 0
    if current_index >= articles_count:
        return max(0, articles_count - 1)
    return current_index


def add_runtime_event(event_type: str, message: str) -> None:
    """
    Add a runtime event to session state for observability.
    Thread-safe, append-only, bounded memory.
    """
    from datetime import datetime
    if "runtime_events" not in st.session_state:
        st.session_state.runtime_events = []
    
    timestamp = datetime.now().strftime("%H:%M:%S")
    event = f"[{timestamp}] {event_type}: {message}"
    
    events = st.session_state.runtime_events
    events.append(event)
    
    if len(events) > 50:
        events[:] = events[-50:]
    
    st.session_state.runtime_events = events


def reset_session_for_new_articles(session, articles_count: int):
    """
    Reset session state when article set changes to prevent stale indexes.
    """
    session.current_index = validate_session_index(articles_count, session.current_index)
    if hasattr(session, 'ec_completed'):
        session.ec_completed = min(session.ec_completed, articles_count)


def _get_cache_counts(protocol_version: str, stage: str) -> Dict[str, int]:
    """Get batch prefilter/quarantine/LLM counts from cache (single pass)."""
    from src.advisory.advisory_cache import get_advisory_cache
    cache = get_advisory_cache()
    return {
        "prefiltered": cache.count_prefiltered(protocol_version, stage),
        "quarantined": cache.count_quarantined(protocol_version, stage),
        "llm": cache.count_llm_generated(protocol_version, stage),
    }


def _auto_refresh_if_worker_active(stage: str = "ic"):
    """Auto-rerun when advisory worker is actively generating for the given stage.
    
    Bounded to minimum REFRESH_INTERVAL seconds between reruns to prevent
    render storms. Uses session state to track last refresh timestamp.
    
    Must NOT wrap st.rerun() in try/except Exception — RerunException is how
    Streamlit triggers reruns and catching it silently freezes the dashboard.
    """
    from src.advisory.runtime_mode import UI_POLL_INTERVAL_SECONDS
    REFRESH_INTERVAL = UI_POLL_INTERVAL_SECONDS

    now = time.time()
    last_refresh = st.session_state.get(f"_last_refresh_{stage}", 0.0)
    if now - last_refresh < REFRESH_INTERVAL:
        return

    from src.advisory import is_advisory_generation_active
    from src.advisory.advisory_queue import get_advisory_queue

    should_refresh = False
    try:
        queue = get_advisory_queue(stage=stage)
        has_pending = queue is not None and len(queue.get_pending()) > 0
        is_active = is_advisory_generation_active(stage=stage)
        should_refresh = is_active or has_pending
    except Exception:
        return

    if should_refresh:
        st.session_state[f"_last_refresh_{stage}"] = now
        st.caption("🔄 Updating...")
        time.sleep(0.3)
        st.rerun()


def render_advisory_status_banner(stage: str = "ic"):
    """Render advisory generation progress banner for the given stage."""
    try:
        from src.advisory import get_advisory_pipeline_status, is_advisory_generation_active
        
        status = get_advisory_pipeline_status(stage=stage)
        
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
    from src.core.screening_session import ScreeningSession
    from src.core.protocol_service import ensure_protocol_locked, validate_protocol_for_screening

    set_active_stage("ec")

    if "research_protocol" not in st.session_state or st.session_state.research_protocol is None:
        st.warning("⚠ No Research Protocol configured.")
        return

    protocol = st.session_state.research_protocol

    if not getattr(st.session_state, "_protocol_lock_attempted_ec", False):
        ensure_protocol_locked(protocol)
        st.session_state._protocol_lock_attempted_ec = True

    is_valid, error_msg = validate_protocol_for_screening(protocol)
    if not is_valid:
        st.warning(f"⚠ {error_msg}")
        return

    if "apollo_session" not in st.session_state:
        st.session_state.apollo_session = ScreeningSession(
            session_id=str(uuid.uuid4())[:8],
            created_at=datetime.now().isoformat(),
            protocol_version=protocol.protocol_version,
            researcher_id="researcher_1"
        )

    session = st.session_state.apollo_session
    session.stage = "ec"

    if "keyboard_shortcuts_enabled" not in st.session_state:
        st.session_state.keyboard_shortcuts_enabled = True

    if st.session_state.keyboard_shortcuts_enabled:
        st.markdown("""
        <style>
        div.stKeyListener {
            display: none;
        }
        </style>
        """, unsafe_allow_html=True)

    if "advisory_pipeline_initialized_ec" not in st.session_state and session.articles:
        from src.advisory import initialize_advisory_pipeline
        from src.advisory.advisory_queue import reset_queue_for_stage
        from src.advisory.advisory_orchestrator import reset_orchestrator_for_stage

        reset_queue_for_stage("ec")
        reset_orchestrator_for_stage("ec")

        pv = get_protocol_value(protocol, "protocol_version", "1.0")

        result = initialize_advisory_pipeline(
            articles=session.articles,
            protocol_version=pv,
            stage="ec",
            auto_start=True,
            protocol=protocol
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

    protocol_version = get_protocol_value(st.session_state.get("research_protocol", {}), "protocol_version", "1.0")
    queue_summary = get_cached_queue_summary(articles, protocol_version, "ec")

    with st.expander("📊 REVIEW QUEUE", expanded=True):
        col_crit, col_high, col_med, col_low_samp, col_low_auto, col_no_adv = st.columns(6)
        with col_crit:
            st.metric("Critical", queue_summary.get("CRITICAL_REVIEW", 0))
        with col_high:
            st.metric("High Risk", queue_summary.get("HIGH_RISK", 0))
        with col_med:
            st.metric("Medium", queue_summary.get("MEDIUM_RISK", 0))
        with col_low_samp:
            st.metric("Sampled", queue_summary.get("LOW_RISK_SAMPLED", 0))
        with col_low_auto:
            auto_low = queue_summary.get("AUTO_LOW_RISK", 0)
            if auto_low > 0:
                st.markdown(f"⚪ **{auto_low}** auto-screened")
            else:
                st.metric("Auto-Screen", auto_low)
        with col_no_adv:
            st.metric("Pending", queue_summary.get("NO_ADVISORY", 0))

        from src.advisory.advisory_reliability import get_operational_metrics
        ops = get_operational_metrics().get_stats()
        st.markdown(f"---")
        st.markdown("**Reliability Metrics**")
        col_prec, col_esc, col_thr, col_lat = st.columns(4)
        with col_prec:
            st.metric("Est. Precision", f"{ops.get('estimated_precision', 0):.0%}")
        with col_esc:
            st.metric("Escalation Rate", f"{ops.get('escalation_rate', 0):.0%}")
        with col_thr:
            st.metric("Throughput", f"{ops.get('throughput_items_per_sec', 0):.1f}/s")
        with col_lat:
            st.metric("Latency", f"{ops.get('latency_avg_ms', 0):.0f}ms")

        with st.expander("⚡ OPERATIONAL METRICS", expanded=False):
            from src.advisory.advisory_orchestrator import get_advisory_pipeline_status
            from src.advisory.advisory_reliability import get_operational_metrics
            try:
                pipeline_status = get_advisory_pipeline_status("ec")
            except Exception:
                pipeline_status = {}

            queue_pending = pipeline_status.get("pending_count", 0) if pipeline_status else 0
            queue_generated = pipeline_status.get("generated_count", 0) if pipeline_status else 0
            workers_active = pipeline_status.get("workers_active", 0) if pipeline_status else 0

            ops = get_operational_metrics().get_stats()

            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.metric("Throughput", f"{ops.get('throughput_items_per_sec', 0):.1f}/s")
            with m2:
                st.metric("Queue Depth", queue_pending)
            with m3:
                st.metric("Avg Latency", f"{ops.get('latency_avg_ms', 0):.0f}ms")
            with m4:
                st.metric("Escalation Rate", f"{ops.get('escalation_rate', 0):.0%}")

            m5, m6, m7, m8 = st.columns(4)
            with m5:
                st.metric("Est. Precision", f"{ops.get('estimated_precision', 0):.0%}")
            with m6:
                st.metric("Agreement Rate", f"{ops.get('human_agreement_rate', 0):.0%}")
            with m7:
                st.metric("Total Processed", ops.get('total_processed', 0))
            with m8:
                st.metric("Active Workers", workers_active)

            from src.advisory.advisory_cache import get_advisory_cache
            cache = get_advisory_cache()
            cache_size = len(cache)
            st.caption(f"Cache entries: {cache_size}")

    col_mode, col_queue = st.columns([1, 2])
    with col_mode:
        review_mode = st.selectbox(
            "Review Mode",
            options=["FOCUSED_RISK_REVIEW", "SEQUENTIAL_REVIEW"],
            index=0,
            format_func=lambda x: {
                "FOCUSED_RISK_REVIEW": "🎯 Focused Risk",
                "SEQUENTIAL_REVIEW": "📋 Sequential",
            }.get(x, x),
            key="ec_review_mode"
        )
    with col_queue:
            if "ec_selected_queue" not in st.session_state:
                st.session_state.ec_selected_queue = "ALL"
            queue_filter = st.selectbox(
                "Review Queue",
                options=["ALL", "CRITICAL_REVIEW", "HIGH_RISK", "MEDIUM_RISK", "LOW_RISK_SAMPLED", "AUTO_LOW_RISK", "UNCERTAIN", "AUTONOMOUS", "HUMAN_REVIEW"],
                index=0,
                format_func=lambda x: {
                    "ALL": "📄 All Papers",
                    "CRITICAL_REVIEW": "🔴 Critical (needs review)",
                    "HIGH_RISK": "🟠 High Risk",
                    "MEDIUM_RISK": "🟡 Medium Risk",
                    "LOW_RISK_SAMPLED": "🔵 Sampled for Validation",
                    "AUTO_LOW_RISK": "⚪ Auto-Screened",
                    "UNCERTAIN": "❓ Uncertain",
                    "AUTONOMOUS": "🤖 Autonomous",
                    "HUMAN_REVIEW": "👤 Human Review"
                }.get(x, x),
                key="ec_selected_queue"
            )

    filtered_articles = articles

    if queue_filter != "ALL":
        filtered_articles = filter_articles_by_queue(articles, protocol_version, "ec", queue_filter)

    if queue_filter == "AUTO_LOW_RISK" and len(filtered_articles) > 20:
        with st.expander(f"📋 Review {len(filtered_articles)} Auto-Screened Papers (Batch Validation)", expanded=False):
            st.markdown("**Quick Validation Mode** - Review a sample to verify auto-screening quality")
            
            batch_size = min(10, len(filtered_articles))
            sample_indices = list(range(0, min(batch_size * 10, len(filtered_articles)), 10))[:batch_size]
            
            for i, sample_idx in enumerate(sample_indices):
                if sample_idx < len(filtered_articles):
                    article = filtered_articles[sample_idx]
                    with st.container():
                        col_b1, col_b2, col_b3 = st.columns([3, 1, 1])
                        with col_b1:
                            st.markdown(f"**{article.get('title', 'Untitled')[:80]}...**")
                        with col_b2:
                            st.caption(f"Confidence: {article.get('advisory_confidence', 'N/A')}")
                        with col_b3:
                            if st.button("✓ Quick Accept", key=f"quick_accept_{sample_idx}"):
                                pass
                        st.divider()

    total = len(filtered_articles)
    if total == 0:
        st.warning(f"No articles in queue: {queue_filter}")
        return

    current_idx = session.current_index
    if current_idx >= total:
        session.current_index = max(0, total - 1)
        current_idx = session.current_index
    if current_idx < 0:
        session.current_index = 0
        current_idx = 0

    col_nav, col_stats, col_nav2 = st.columns([1, 3, 1])
    with col_nav:
        if st.button("◀", disabled=current_idx == 0, key="prev_filtered"):
            session.current_index = current_idx - 1
            st.rerun()
    with col_stats:
        progress_bar(min(current_idx + 1, total), total, stage=f"EC ({queue_filter})")
    with col_nav2:
        if st.button("▶", disabled=current_idx >= total - 1, key="next_filtered"):
            session.current_index = current_idx + 1
            st.rerun()

    render_advisory_status_banner(stage="ec")

    _auto_refresh_if_worker_active(stage="ec")

    st.markdown(f"**Queue:** {queue_filter} | **Paper:** {current_idx + 1} / {total}")

    if filtered_articles and 0 <= current_idx < total:
        article = filtered_articles[current_idx]
        render_literature_status_header(article, current_idx)
        
        col_article, col_advice = st.columns([3, 1])
        with col_article:
            render_article_card(article, current_idx)
        with col_advice:
            render_ai_advisory_panel(article, current_idx, total, session)

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

            advisory = get_ec_advisory(article.title, article.abstract, protocol_version) if article.title else None
            ai_decision_str = ""
            if advisory and hasattr(advisory, 'decision') and advisory.decision:
                ai_decision_str = safe_decision(advisory.decision)

            override_severity = "MEDIUM"
            if ai_decision_str and ai_decision_str not in ("UNKNOWN", "UNAVAILABLE", "INSUFFICIENT_METADATA"):
                st.caption(f"AI suggests: {ai_decision_str}")
                override_severity = st.selectbox(
                    "Override Severity (if disagreeing)",
                    options=["LOW", "MEDIUM", "HIGH", "CRITICAL"],
                    index=1,
                    key=f"severity_{current_idx}"
                )

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


def render_ai_advisory_panel(article, current_idx: int, total: int, session):
    """
    Render AI Advisory Panel using centralized cache.

    STRICT ISOLATION: This function ONLY renders - never generates advisories.
    UI MUST NEVER call LLM directly or generate advisories.
    """
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

    advisory = get_ec_advisory(title, abstract, protocol_version)
    status = get_ec_advisory_status(title, abstract, protocol_version)
    
    with st.container(border=True):
        with st.expander("🤖 AI ADVISORY", expanded=False):

            if advisory and advisory.is_available():
                decision_val = advisory.decision
                is_uncertain = decision_val in (
                    AdvisoryDecision.UNCERTAIN,
                    AdvisoryDecision.INSUFFICIENT_EVIDENCE,
                    AdvisoryDecision.CANNOT_DETERMINE,
                )

                prefilter_applied = getattr(advisory, 'prefilter_applied', False)
                prefilter_reason = getattr(advisory, 'prefilter_reason', "") or ""
                stage_validation = getattr(advisory, 'stage_validation', "") or ""
                is_quarantined = "QUARANTINED" in stage_validation
                model_used = getattr(advisory, 'model_used', "") or ""

                if prefilter_applied:
                    st.info(f"⚡ PREFILTERED: {prefilter_reason}")
                if is_quarantined:
                    st.warning(f"⚠️ QUARANTINED: {stage_validation}")

                evidence_strength = compute_evidence_strength(advisory)
                uncertainty_score = compute_uncertainty_score(advisory)
                autonomy = assess_autonomy(
                    decision=advisory.decision,
                    confidence=advisory.confidence,
                    grounding_strength=advisory.grounding_strength,
                    evidence_strength=evidence_strength,
                    uncertainty_score=uncertainty_score,
                    triggered_criteria=advisory.triggered_criteria,
                )

                risk_class = safe_enum_value(advisory.risk_classification, "UNKNOWN") if advisory.risk_classification else "UNKNOWN"
                validation_queue = safe_enum_value(advisory.validation_queue, "UNKNOWN") if advisory.validation_queue else "UNKNOWN"
                requires_val = "YES" if advisory.requires_validation else "NO"

                risk_color = {
                    "LOW_RISK": COLORS["success"],
                    "MEDIUM_RISK": COLORS["warning"],
                    "HIGH_RISK": COLORS["error"],
                    "CRITICAL_REVIEW": "#FF0000",
                    "UNKNOWN": COLORS["text_muted"]
                }.get(risk_class, COLORS["text_muted"])

                if autonomy.autonomous_eligible:
                    autonomy_badge = f'<span style="background:{COLORS["success"]};color:#000;padding:2px 8px;font-size:0.65rem;font-weight:600;border-radius:2px;">AUTONOMOUS</span>'
                elif is_uncertain:
                    autonomy_badge = f'<span style="background:{COLORS["warning"]};color:#000;padding:2px 8px;font-size:0.65rem;font-weight:600;border-radius:2px;">UNCERTAIN</span>'
                elif prefilter_applied:
                    autonomy_badge = f'<span style="background:{COLORS["info"]};color:#000;padding:2px 8px;font-size:0.65rem;font-weight:600;border-radius:2px;">PREFILTERED</span>'
                elif is_quarantined:
                    autonomy_badge = f'<span style="background:#FF0000;color:#fff;padding:2px 8px;font-size:0.65rem;font-weight:600;border-radius:2px;">QUARANTINED</span>'
                else:
                    autonomy_badge = f'<span style="background:{COLORS["info"]};color:#000;padding:2px 8px;font-size:0.65rem;font-weight:600;border-radius:2px;">HUMAN VALIDATION REQUIRED</span>'

                st.markdown(f"""
                <div style="border:1px solid {COLORS['border_light']};background:{COLORS['bg_card']};padding:8px;border-radius:4px;margin-bottom:8px;">
                    <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                        <span style="font-size:0.7rem;color:{COLORS['text_muted']};">RISK</span>
                        <span style="font-size:0.75rem;font-weight:600;color:{risk_color};">{risk_class}</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                        <span style="font-size:0.7rem;color:{COLORS['text_muted']};">CONFIDENCE</span>
                        <span style="font-size:0.75rem;color:{COLORS['text_secondary']};">{advisory.confidence:.2f}</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                        <span style="font-size:0.7rem;color:{COLORS['text_muted']};">VALIDATION</span>
                        <span style="font-size:0.75rem;color:{COLORS['text_secondary']};">{requires_val}</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                        <span style="font-size:0.7rem;color:{COLORS['text_muted']};">QUEUE</span>
                        <span style="font-size:0.65rem;color:{COLORS['text_secondary']};">{validation_queue}</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;margin-top:4px;">
                        <span style="font-size:0.7rem;color:{COLORS['text_muted']};">STATUS</span>
                        <span>{autonomy_badge}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                status_str = safe_status(status)
                if prefilter_applied:
                    status_str = f"PREFILTERED ({prefilter_reason})"
                st.caption(f"Decision: {safe_decision(advisory.decision)} | {status_str}")

                grounding_strength = getattr(advisory, 'grounding_strength', 0.0)
                hallucination_risk = getattr(advisory, 'hallucination_risk_score', 0.0)

                col_g1, col_g2, col_g3 = st.columns(3)
                with col_g1:
                    alignment_label = "Strong" if grounding_strength >= 0.7 else "Moderate" if grounding_strength >= 0.4 else "Weak"
                    st.metric("Evidence Alignment", alignment_label, delta=f"{grounding_strength:.0%}" if grounding_strength else None)
                with col_g2:
                    reliability_label = "High" if hallucination_risk < 0.3 else "Medium" if hallucination_risk < 0.7 else "Low"
                    st.metric("Evidence Reliability", reliability_label, delta=f"{hallucination_risk:.0%}" if hallucination_risk else None)
                with col_g3:
                    unsupported = getattr(advisory, 'unsupported_claims_detected', False)
                    st.metric("Weak Signals", "⚠️ Detected" if unsupported else "✓ Clear")

                col_r1, col_r2, col_r3 = st.columns(3)
                from src.advisory.advisory_reliability import compute_advisory_reliability, check_escalation, get_threshold_calibrator
                override_rate = get_threshold_calibrator().get_override_rate("ec")
                reliability_score = compute_advisory_reliability(advisory, override_rate=override_rate)
                escalation = check_escalation(advisory, reliability_score)
                with col_r1:
                    score_pct = f"{reliability_score:.0%}"
                    if reliability_score >= 0.7:
                        st.metric("Reliability", score_pct, delta="✓ Reliable")
                    elif reliability_score >= 0.5:
                        st.metric("Reliability", score_pct, delta="⚠ Borderline")
                    else:
                        st.metric("Reliability", score_pct, delta="✗ Low")
                with col_r2:
                    st.metric("Escalate", "⚠️ Yes" if escalation["escalate"] else "✓ No")
                with col_r3:
                    st.metric("Precision Est.", f"{cal_data.get('agreement_rate', 'N/A')}")

                if escalation["reasons"]:
                    with st.expander("🔔 Escalation Reasons", expanded=True):
                        for reason in escalation["reasons"]:
                            st.caption(f"- {reason}")

                if is_uncertain:
                    st.warning("⚠ AI could not determine relevance with sufficient confidence. Manual review required.")
                    st.markdown(f"**Uncertainty Score:** {uncertainty_score:.2f} | **Evidence Strength:** {evidence_strength:.2f}")

                if hasattr(advisory, 'justification') and advisory.justification:
                    with st.expander("🔍 Why did APOLLO decide this?"):
                        st.markdown("**Rationale:**")
                        st.text(advisory.justification[:500] + "..." if len(advisory.justification) > 500 else advisory.justification)

                        if hasattr(advisory, 'criterion_grounding') and advisory.criterion_grounding:
                            st.markdown("**Criterion Grounding:**")
                            for crit_id, evidence in advisory.criterion_grounding.items():
                                st.markdown(f"- **{crit_id}:** {evidence[:200]}...")

                if hasattr(advisory, 'screening_evidence') and advisory.screening_evidence:
                    se = advisory.screening_evidence
                    with st.expander("⚙️ Deterministic Screening Evidence", expanded=False):
                        st.markdown(f"**Decision:** {se.get('decision', 'N/A')} | **Confidence:** {se.get('confidence', 0.0):.2f}")
                        st.markdown(f"**Escalation Required:** {'Yes' if se.get('escalation_required') else 'No'}")
                        if se.get('study_type'):
                            st.markdown(f"**Study Type:** {se['study_type']}")
                        if se.get('hard_negative'):
                            st.markdown("**🔴 Hard Negative Exclusion**")
                        triggered = se.get('triggered_rules', [])
                        if triggered:
                            st.markdown(f"**Triggered Rules ({len(triggered)}):**")
                            for rid in triggered:
                                st.markdown(f"- `{rid}`")
                        evidence_list = se.get('evidence', [])
                        if evidence_list:
                            st.markdown(f"**Evidence ({len(evidence_list)}):**")
                            for e in evidence_list:
                                st.markdown(f"- [{e.get('evidence_type', '?')}] {e.get('rule_name', '?')} → *{e.get('match', '')[:80]}*")
                        signals = se.get('semantic_signals', {})
                        if signals:
                            st.markdown(f"**Semantic Signals:**")
                            for k, v in signals.items():
                                st.markdown(f"- {k}: {v:.3f}")
                        ct = se.get('consensus_trace', {})
                        if ct:
                            st.markdown(f"**Consensus Trace:**")
                            src = ct.get('source_contributions', {})
                            for k, v in src.items():
                                val = v.get('contribution', 0)
                                st.markdown(f"- {k}: {val:.4f}")
                        if se.get('rationale'):
                            with st.expander("Rationale"):
                                st.text(se['rationale'][:500])

                if not is_uncertain and not prefilter_applied and not is_quarantined:
                    col_w1, col_w2, col_w3 = st.columns(3)

                    approved_key = f"approve_{current_idx}"
                    override_key = f"override_{current_idx}"
                    escalate_key = f"escalate_{current_idx}"

                    with col_w1:
                        if st.button("✓ Confirm", key=approved_key, help="Confirm AI decision and log agreement"):
                            if current_idx < total - 1:
                                session.current_index = current_idx + 1
                            st.rerun()
                    with col_w2:
                        override_clicked = st.button("⚠️ Override", key=override_key, help="Override AI decision")
                        if override_clicked:
                            pass
                    with col_w3:
                        escalate_clicked = st.button("🔺 Escalate", key=escalate_key, help="Mark for manual review")
                        if escalate_clicked:
                            pass

                    if override_clicked or escalate_clicked:
                        with st.form(f"review_action_form_{current_idx}"):
                            human_decision = st.radio(
                                "Your decision:",
                                options=["INCLUDE", "EXCLUDE"],
                                horizontal=True,
                                key=f"human_decision_{current_idx}"
                            )
                            override_severity = st.selectbox(
                                "Severity:",
                                options=["LOW", "MEDIUM", "HIGH", "CRITICAL"],
                                key=f"override_severity_{current_idx}"
                            )
                            override_reason = st.text_area(
                                "Reason for override:",
                                key=f"override_reason_{current_idx}",
                                height=80
                            )
                            submit_action = st.form_submit_button("Submit Review")
                            if submit_action:
                                ai_decision = safe_decision(advisory.decision) if hasattr(advisory, 'decision') else "UNKNOWN"
                                is_disagreement = human_decision != ai_decision
                                
                                from src.advisory.advisory_reliability import get_threshold_calibrator, get_operational_metrics
                                get_threshold_calibrator().record_override("ec", was_overridden=is_disagreement)
                                get_operational_metrics().record_escalation(escalated=is_disagreement)
                                if not is_disagreement:
                                    get_operational_metrics().record_agreement(agreed=True)
                                
                                st.success(f"✓ Review logged: {human_decision} (was {ai_decision})")
                                if current_idx < total - 1:
                                    session.current_index = current_idx + 1
                                st.rerun()

                    st.caption("⌨️ Keyboard: A=Confirm | O=Override | E=Escalate | N=Next | P=Previous")

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
                    "justification": advisory.justification,
                    "prefilter_applied": prefilter_applied,
                    "prefilter_reason": prefilter_reason,
                }
                render_suggestion_details(advisory_dict)
            else:
                if status == AdvisoryStatus.PENDING:
                    st.caption("⏳ Advisory pending — manual screening operational")
                elif status == AdvisoryStatus.GENERATING:
                    st.caption("🔄 Generating advisory...")
                elif status == AdvisoryStatus.PROCESSING:
                    st.caption("🔄 Advisory generating — please wait...")
                elif status == AdvisoryStatus.FAILED:
                    error_msg = advisory.error if advisory and hasattr(advisory, 'error') and advisory.error else "Unknown error"
                    st.caption(f"⚠️ Advisory failed: {error_msg}")
                elif status == AdvisoryStatus.UNAVAILABLE:
                    st.caption("○ Advisory unavailable — manual screening fully operational")
                else:
                    status_val = safe_status(status, "UNKNOWN")
                    st.caption(f"○ Advisory state: {status_val} — manual screening operational")





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
    """Get EC criteria from current protocol - routes through protocol_query_service."""
    from src.core.protocol_query_service import get_ec_criteria
    if "research_protocol" in st.session_state and st.session_state.research_protocol:
        return get_ec_criteria(st.session_state.research_protocol)
    return get_ec_criteria(None)


def get_ec_codes() -> Dict[str, str]:
    """Get EC codes as button labels for coded selection."""
    return get_protocol_ec_criteria()


def render_suggestion_details(suggestion: Dict):
    """
    Render LLM advisory as clean recommendation - researcher-focused.
    
    DEFENSIVE VALIDATION: Added type checking to handle malformed advisory structures.
    """
    if not isinstance(suggestion, dict) or not suggestion:
        st.warning("Advisory data unavailable - manual review required")
        return
    
    decision = suggestion.get("decision", "").upper()

    is_uncertain = decision in ("UNCERTAIN", "INSUFFICIENT_EVIDENCE", "CANNOT_DETERMINE")
    is_fallback = suggestion.get("is_fallback", False)

    if is_uncertain:
        confidence_label = "Insufficient evidence for reliable determination"
        label_color = COLORS["warning"]
        decision_color = COLORS["warning"]
        icon = "⚠️"
    elif decision == "INCLUDE":
        confidence_label = "Strong heuristic alignment"
        label_color = COLORS["success"]
        decision_color = COLORS["success"]
        icon = "✅"
    elif decision == "EXCLUDE":
        confidence_label = "Weak heuristic alignment"
        label_color = COLORS["error"]
        decision_color = COLORS["error"]
        icon = "❌"
    else:
        confidence_label = "Moderate LLM signal"
        label_color = COLORS["warning"]
        decision_color = COLORS["warning"]
        icon = "⚠️"

    if is_fallback:
        st.warning("LLM service unavailable - manual review required")
        return

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