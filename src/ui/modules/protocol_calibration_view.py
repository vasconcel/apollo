"""
APOLLO Protocol Calibration Dashboard

Defensive rendering with:
- Safe COLORS lookups (never KeyError)
- try/except around all calibration rendering blocks
- CalibrationService for rerun-safe runner lifecycle
- Timestamp-based polling (no infinite rerun loops)
- Frozen runtime snapshots (never touch live objects in UI)
"""
import streamlit as st
import time
from typing import Optional, Dict, List
from pathlib import Path

from src.ui.theme import COLORS, TYPOGRAPHY
from src.ui.components import section_header, divider, terminal_header
from src.advisory.calibration_service import calibration_service
from src.advisory.calibration_artifact import (
    load_calibration_artifact,
    index_calibration_reports,
)
from src.advisory.calibration_comparator import compare_calibrations
from src.advisory.advisory_quality import (
    compute_all_diagnostics,
    compute_confidence_histogram,
    compute_uncertainty_distribution,
    compute_decision_distribution,
    compute_escalation_rate,
    compute_calibration_drift,
)
from src.advisory.advisory_cache import get_advisory_cache
from src.advisory.runtime_telemetry import get_runtime_telemetry


def _c(key: str, fallback: str = "#1A1A1D") -> str:
    """Safe COLORS lookup — never raises KeyError."""
    return COLORS.get(key, fallback)


def _safe_render(func):
    """Decorator: wrap rendering in try/except to isolate crashes."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            st.warning(f"Render warning: {e}")
            return None
    return wrapper


@_safe_render
def _render_calibration_progress(runner):
    progress = runner.calibration_progress
    st.markdown(f"""
        <div style="border:1px solid {_c('border')};background:{_c('bg_dark')};padding:1rem;border-radius:8px;margin:1rem 0;">
            <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.7rem;color:{_c('cyan')};margin-bottom:0.75rem;">
                CALIBRATION IN PROGRESS
            </div>
    """, unsafe_allow_html=True)
    current = progress.get("current_stage", "—").upper() if progress.get("current_stage") else "—"
    st.markdown(f"**Current Stage:** `{current}`")
    st.markdown(f"**Sample Size:** `{progress.get('sample_size', 0)}`")
    col1, col2 = st.columns(2)
    with col1:
        ec_done = progress.get("ec_completed", 0)
        ec_total = progress.get("ec_total", 0)
        st.metric("EC Progress", f"{ec_done}/{ec_total}")
        if ec_total > 0:
            st.progress(min(ec_done / max(ec_total, 1), 1.0))
    with col2:
        ic_done = progress.get("ic_completed", 0)
        ic_total = progress.get("ic_total", 0)
        st.metric("IC Progress", f"{ic_done}/{ic_total}")
        if ic_total > 0:
            st.progress(min(ic_done / max(ic_total, 1), 1.0))
    st.markdown("</div>", unsafe_allow_html=True)
    st.caption(f"Status: {progress.get('status', 'idle')}")


@_safe_render
def _render_diagnostics(diagnostics: List[Dict]):
    if not diagnostics:
        st.caption("No diagnostic signals detected.")
        return
    high = [d for d in diagnostics if d.get("severity") == "high"]
    medium = [d for d in diagnostics if d.get("severity") == "medium"]
    low = [d for d in diagnostics if d.get("severity") == "low"]

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("High Severity", len(high), delta_color="inverse")
    with col2:
        st.metric("Medium Severity", len(medium))
    with col3:
        st.metric("Low Severity", len(low))

    for signal_group, label in [
        (high, "High Severity Signals"),
        (medium, "Medium Severity Signals"),
        (low, "Low Severity Signals"),
    ]:
        if not signal_group:
            continue
        with st.expander(f"{label} ({len(signal_group)})", expanded=bool(signal_group == high)):
            for sig in signal_group:
                color = _c("error") if sig.get("severity") == "high" else \
                        _c("warning") if sig.get("severity") == "medium" else \
                        _c("text_muted")
                st.markdown(f"""
                    <div style="border-left:3px solid {color};padding:0.5rem 1rem;margin:0.25rem 0;background:{_c('bg_dark')};border-radius:4px;">
                        <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.6rem;color:{color};text-transform:uppercase;">{sig.get('signal_type', '?')} · {sig.get('criterion_id', '?')}</div>
                        <div style="font-size:0.85rem;margin:0.25rem 0;">{sig.get('description', '')}</div>
                        <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{_c('text_muted')};">→ {sig.get('recommendation', '')}</div>
                    </div>
                """, unsafe_allow_html=True)


@_safe_render
def _render_calibration_report(report: Dict):
    rec = report.get("recommendation", "")
    rec_label = report.get("recommendation_label", "") or report.get("recommendation", "")
    rec_color = _c("success") if rec == "protocol_stable" else \
                _c("warning") if rec in ("protocol_requires_refinement", "criteria_underspecified") else \
                _c("error")

    st.markdown(f"""
        <div style="border:1px solid {rec_color};background:{_c('bg_card')};padding:1rem;border-radius:8px;margin:1rem 0;">
            <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.7rem;color:{rec_color};margin-bottom:0.75rem;">
                CALIBRATION COMPLETE
            </div>
            <div style="font-size:0.9rem;">
                Sample Size: <strong>{report.get('sample_size', 0)}</strong> |
                Processed: <strong>{report.get('total_processed', 0)}</strong> |
                Diagnostics: <strong>{report.get('diagnostics_count', 0)}</strong>
            </div>
            <div style="border-left:3px solid {rec_color};padding:0.5rem 1rem;margin:0.5rem 0;background:{_c('bg_dark')};border-radius:4px;">
                <span style="font-family:{TYPOGRAPHY['mono']};font-size:0.75rem;color:{rec_color};">{rec_label}</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        ec = report.get("ec", {})
        st.markdown(f"""
            <div style="border:1px solid {_c('border')};background:{_c('bg_dark')};padding:0.75rem;border-radius:6px;">
                <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.6rem;color:{_c('text_muted')};margin-bottom:0.5rem;">EC RESULTS</div>
                <div style="font-size:0.9rem;">Accepts: <span style="color:{_c('success')};">{ec.get('accepts', 0)}</span></div>
                <div style="font-size:0.9rem;">Rejects: <span style="color:{_c('error')};">{ec.get('rejects', 0)}</span></div>
                <div style="font-size:0.9rem;">Ambiguous: <span style="color:{_c('warning')};">{ec.get('ambiguous', 0)}</span></div>
                <div style="font-size:0.9rem;">Mean Confidence: <span style="color:{_c('cyan')};">{ec.get('mean_confidence', 0):.2%}</span></div>
                <div style="font-size:0.9rem;">Low Grounding: <span style="color:{_c('warning')};">{ec.get('low_grounding', 0)}</span></div>
                <div style="font-size:0.9rem;">High Ambiguity: <span style="color:{_c('error')};">{ec.get('high_ambiguity', 0)}</span></div>
            </div>
        """, unsafe_allow_html=True)
    with col2:
        ic = report.get("ic", {})
        st.markdown(f"""
            <div style="border:1px solid {_c('border')};background:{_c('bg_dark')};padding:0.75rem;border-radius:6px;">
                <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.6rem;color:{_c('text_muted')};margin-bottom:0.5rem;">IC RESULTS</div>
                <div style="font-size:0.9rem;">Accepts: <span style="color:{_c('success')};">{ic.get('accepts', 0)}</span></div>
                <div style="font-size:0.9rem;">Rejects: <span style="color:{_c('error')};">{ic.get('rejects', 0)}</span></div>
                <div style="font-size:0.9rem;">Ambiguous: <span style="color:{_c('warning')};">{ic.get('ambiguous', 0)}</span></div>
                <div style="font-size:0.9rem;">Mean Confidence: <span style="color:{_c('cyan')};">{ic.get('mean_confidence', 0):.2%}</span></div>
                <div style="font-size:0.9rem;">Low Grounding: <span style="color:{_c('warning')};">{ic.get('low_grounding', 0)}</span></div>
                <div style="font-size:0.9rem;">High Ambiguity: <span style="color:{_c('error')};">{ic.get('high_ambiguity', 0)}</span></div>
            </div>
        """, unsafe_allow_html=True)

    divider()
    overlap = report.get("overlap", {})
    st.markdown(f"""
        <div style="border:1px solid {_c('border')};background:{_c('bg_dark')};padding:0.75rem;border-radius:6px;margin:0.5rem 0;">
            <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.6rem;color:{_c('text_muted')};margin-bottom:0.5rem;">EC/IC OVERLAP</div>
            <div style="font-size:0.9rem;">Overlapping activations: <span style="color:{_c('warning')};">{overlap.get('ec_ic_overlap_count', 0)}</span></div>
            <div style="font-size:0.9rem;">Overlap rate: <span style="color:{_c('warning')};">{overlap.get('ec_ic_overlap_rate', 0):.1%}</span></div>
        </div>
    """, unsafe_allow_html=True)

    diagnostics = report.get("diagnostics", [])
    if diagnostics:
        section_header("PROTOCOL DIAGNOSTICS")
        _render_diagnostics(diagnostics)

    artifact_path = report.get("artifact_path", "")
    if artifact_path:
        st.caption(f"Artifact saved: `{artifact_path}`")


@_safe_render
def _render_historical():
    reports = index_calibration_reports()
    if not reports:
        st.info("No historical calibration reports found. Run a calibration first.")
        return

    section_header("CALIBRATION HISTORY")

    display_df = []
    for r in reports:
        display_df.append({
            "ID": r.get("calibration_id", "?")[:24] + "...",
            "Protocol": r.get("protocol_version", "?"),
            "Sample": r.get("sample_size", 0),
            "Status": r.get("recommendation", ""),
            "Created": r.get("created_at", "")[:19].replace("T", " "),
        })

    st.dataframe(display_df, width="stretch", hide_index=True)

    selected_ids = [r.get("calibration_id", "") for r in reports if r.get("calibration_id")]
    if not selected_ids:
        return
    sel = st.selectbox("Select calibration for details", selected_ids, format_func=lambda x: x[:32])

    selected = next((r for r in reports if r.get("calibration_id") == sel), None)
    if selected and st.button("Load Report", width="stretch"):
        file_path = selected.get("file_path")
        if file_path:
            try:
                st.session_state["selected_calibration"] = load_calibration_artifact(file_path)
            except Exception as e:
                st.error(f"Cannot load selected calibration: {e}")

    artifact = st.session_state.get("selected_calibration")
    if artifact and isinstance(artifact, dict):
        divider()
        section_header("SELECTED CALIBRATION")

        rec = artifact.get("recommendation", {})
        rec_dict = rec if isinstance(rec, dict) else {}
        status = rec_dict.get("status", "") if rec_dict else (rec if isinstance(rec, str) else "")
        label = rec_dict.get("label", "") if rec_dict else ""
        rec_color = _c("success") if status == "protocol_stable" else \
                    _c("warning") if status in ("protocol_requires_refinement", "criteria_underspecified") else \
                    _c("error")

        st.markdown(f"""
            <div style="border:1px solid {rec_color};background:{_c('bg_card')};padding:1rem;border-radius:8px;">
                <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.7rem;color:{rec_color};margin-bottom:0.5rem;">
                    {artifact.get('calibration_id', '—')}
                </div>
                <div style="font-size:0.85rem;">
                    Protocol: {artifact.get('protocol_version', '—')} |
                    Sample: {artifact.get('sample_size', 0)} |
                    Mode: {artifact.get('screening_mode', '—')}
                </div>
                <div style="border-left:3px solid {rec_color};padding:0.25rem 0.75rem;margin:0.5rem 0;background:{_c('bg_dark')};border-radius:4px;">
                    <span style="font-family:{TYPOGRAPHY['mono']};font-size:0.75rem;color:{rec_color};">{label or status}</span>
                </div>
            </div>
        """, unsafe_allow_html=True)

        ec = artifact.get("ec_summary", {}) or {}
        ic = artifact.get("ic_summary", {}) or {}
        col1, col2 = st.columns(2)
        with col1:
            st.metric("EC Mean Confidence", f"{ec.get('mean_confidence', 0):.0%}")
            st.metric("EC Accepts", ec.get("accepts", 0))
        with col2:
            st.metric("IC Mean Confidence", f"{ic.get('mean_confidence', 0):.0%}")
            st.metric("IC Accepts", ic.get("accepts", 0))

        diagnostics = artifact.get("diagnostics", [])
        if diagnostics:
            section_header("DIAGNOSTICS")
            _render_diagnostics(diagnostics)


@_safe_render
def _render_comparison():
    reports = index_calibration_reports()
    if len(reports) < 2:
        st.info("Need at least 2 calibration reports for comparison.")
        return

    section_header("CALIBRATION COMPARISON")

    options = {}
    for r in reports:
        cid = r.get("calibration_id", "")
        fp = r.get("file_path", "")
        if cid and fp:
            options[cid] = fp
    ids = list(options.keys())
    if len(ids) < 2:
        st.info("Need at least 2 valid calibration reports.")
        return

    col1, col2 = st.columns(2)
    with col1:
        baseline_id = st.selectbox("Baseline (earlier)", ids, index=1 if len(ids) > 1 else 0, key="comp_base")
    with col2:
        candidate_id = st.selectbox("Candidate (later)", ids, index=0, key="comp_cand")

    if st.button("Compare", width="stretch"):
        try:
            baseline = load_calibration_artifact(options[baseline_id])
            candidate = load_calibration_artifact(options[candidate_id])
            result = compare_calibrations(baseline, candidate)
            st.session_state["comparison_result"] = result
        except Exception as e:
            st.error(f"Comparison failed: {e}")

    result = st.session_state.get("comparison_result")
    if result:
        summary = result.get("summary", {})
        overall = summary.get("overall_direction", "neutral")
        color = _c("success") if overall == "improved" else \
                _c("error") if overall == "regressed" else \
                _c("text_muted")
        label = "IMPROVED" if overall == "improved" else \
                "REGRESSED" if overall == "regressed" else \
                "NEUTRAL"

        st.markdown(f"""
            <div style="border:1px solid {color};background:{_c('bg_dark')};padding:0.75rem;border-radius:6px;margin:0.75rem 0;">
                <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.6rem;color:{color};">OVERALL DIRECTION</div>
                <div style="font-size:1.1rem;font-weight:bold;color:{color};">{label}</div>
            </div>
        """, unsafe_allow_html=True)

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Improvements", summary.get("improvement_count", 0))
        with col2:
            st.metric("Regressions", summary.get("regression_count", 0))
        with col3:
            st.metric("Unchanged", summary.get("unchanged_count", 0))

        if result.get("improvements"):
            with st.expander(f"Improvements ({len(result['improvements'])})", expanded=True):
                for imp in result["improvements"]:
                    st.markdown(f"""
                        <div style="border-left:3px solid {_c('success')};padding:0.25rem 0.75rem;margin:0.25rem 0;background:{_c('bg_dark')};border-radius:4px;">
                            <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{_c('success')};">{imp.get('metric', '')}</div>
                            <div style="font-size:0.85rem;">{imp.get('baseline_value', '')} → {imp.get('candidate_value', '')} (Δ {imp.get('delta', 0):+.4f})</div>
                        </div>
                    """, unsafe_allow_html=True)

        if result.get("regressions"):
            with st.expander(f"Regressions ({len(result['regressions'])})", expanded=True):
                for reg in result["regressions"]:
                    st.markdown(f"""
                        <div style="border-left:3px solid {_c('error')};padding:0.25rem 0.75rem;margin:0.25rem 0;background:{_c('bg_dark')};border-radius:4px;">
                            <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{_c('error')};">{reg.get('metric', '')}</div>
                            <div style="font-size:0.85rem;">{reg.get('baseline_value', '')} → {reg.get('candidate_value', '')} (Δ {reg.get('delta', 0):+.4f})</div>
                        </div>
                    """, unsafe_allow_html=True)


@_safe_render
def _render_analytics():
    session = st.session_state.get("apollo_session")
    protocol = st.session_state.get("research_protocol")
    if not session or not session.articles:
        st.info("Upload a spreadsheet first.")
        return

    section_header("ADVISORY QUALITY DIAGNOSTICS")

    # Collect advisories from cache for both stages
    cache = get_advisory_cache()
    ec_advisories = []
    ic_advisories = []
    for article in session.articles:
        title = getattr(article, 'title', '') or ''
        abstract = getattr(article, 'abstract', '') or ''
        pv = getattr(protocol, 'protocol_version', '1.0') if protocol else '1.0'
        key = cache.compute_cache_key(title, abstract, pv)
        ec = cache.get(key, pv, stage="ec")
        ic = cache.get(key, pv, stage="ic")
        if ec and ec.is_available():
            ec_advisories.append({
                "decision": ec.decision,
                "confidence": ec.confidence,
                "triggered_criteria": ec.triggered_criteria or [],
                "hallucination_risk_score": ec.hallucination_risk_score,
                "grounding_strength": ec.grounding_strength,
            })
        if ic and ic.is_available():
            ic_advisories.append({
                "decision": ic.decision,
                "confidence": ic.confidence,
                "triggered_criteria": ic.triggered_criteria or [],
                "hallucination_risk_score": ic.hallucination_risk_score,
                "grounding_strength": ic.grounding_strength,
            })

    if not ec_advisories and not ic_advisories:
        st.info("No completed advisories found. Generate advisories first.")
        return

    stage_tabs = st.tabs(["EC Diagnostics", "IC Diagnostics", "Combined"])
    with stage_tabs[0]:
        if ec_advisories:
            _render_stage_diagnostics("EC", ec_advisories)
        else:
            st.caption("No EC advisories available.")
    with stage_tabs[1]:
        if ic_advisories:
            _render_stage_diagnostics("IC", ic_advisories)
        else:
            st.caption("No IC advisories available.")
    with stage_tabs[2]:
        combined = ec_advisories + ic_advisories
        if combined:
            _render_stage_diagnostics("Combined", combined)

    # Telemetry system stats
    section_header("TELEMETRY STATUS")
    try:
        telemetry = get_runtime_telemetry()
        tstats = telemetry.get_stats()
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Telemetry Buckets", tstats.get("bucket_count", 0))
        with col2:
            st.metric("Total Writes", tstats.get("total_writes", 0))
        with col3:
            st.metric("Retention Hours", tstats.get("retention_buckets", 0))
    except Exception as e:
        st.caption(f"Telemetry status unavailable: {e}")


@_safe_render
def _render_stage_diagnostics(label: str, advisories: list):
    diag = compute_all_diagnostics(advisories)
    n = diag.get("total_advisories", 0)

    st.markdown(f"**{label}** — {n} advisories analyzed")

    # Row 1: Decision distribution
    dec_dist = diag.get("decision_distribution", {})
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        inc = dec_dist.get("counts", {}).get("INCLUDE", 0)
        st.metric("Includes", inc)
    with col2:
        exc = dec_dist.get("counts", {}).get("EXCLUDE", 0)
        st.metric("Excludes", exc)
    with col3:
        unc = dec_dist.get("counts", {}).get("UNCERTAIN", 0)
        st.metric("Uncertain", unc)
    with col4:
        esc = diag.get("escalation_rate", {})
        st.metric("Escalation Rate", f"{esc.get('escalation_rate', 0):.0%}")

    # Row 2: Confidence + Uncertainty
    hist = diag.get("confidence_histogram", {})
    unc = diag.get("uncertainty_distribution", {})
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**Confidence Distribution**")
        for bucket, count in sorted(hist.items()):
            pct = count / max(n, 1)
            bar_width = int(pct * 100)
            st.markdown(
                f"<div style='font-family:mono;font-size:0.7rem;display:flex;'>"
                f"<span style='width:80px;'>{bucket}</span>"
                f"<span style='width:{bar_width}px;background:{_c('cyan')};"
                f"height:14px;border-radius:2px;margin:2px 0;'></span>"
                f"<span style='margin-left:4px;'>{count}</span></div>",
                unsafe_allow_html=True,
            )
    with col2:
        st.markdown("**Uncertainty Distribution**")
        st.metric("Mean", f"{unc.get('mean', 0):.2%}")
        st.metric("Median", f"{unc.get('median', 0):.2%}")
        st.metric("High Uncertainty", unc.get("high_uncertainty", 0))
    with col3:
        st.markdown("**Grounding**")
        gnd = diag.get("grounding_distribution", {})
        st.metric("Mean Grounding", f"{gnd.get('mean', 0):.2%}")
        st.metric("Low Grounding", gnd.get("low_grounding", 0))

    # Criteria frequency
    triggered = diag.get("triggered_criteria", [])
    if triggered:
        section_header("TRIGGERED CRITERIA FREQUENCY")
        for tc in triggered[:10]:
            st.markdown(
                f"<div style='border-left:3px solid {_c('cyan')};"
                f"padding:0.15rem 0.75rem;margin:0.15rem 0;"
                f"font-size:0.85rem;'>"
                f"<span style='font-family:mono;'>{tc.get('criterion', '?')}</span>"
                f" — {tc.get('count', 0)}x ({tc.get('rate', 0):.0%})"
                f"</div>",
                unsafe_allow_html=True,
            )


def _compute_session_id() -> str:
    """Compute a stable session identifier from protocol config."""
    session = st.session_state.get("apollo_session")
    protocol = st.session_state.get("research_protocol")
    proto_ver = getattr(protocol, 'protocol_version', '1.0') if protocol else '1.0'
    if session and hasattr(session, 'session_id'):
        return f"{session.session_id}_{proto_ver}"
    return proto_ver


def _get_all_criteria(protocol) -> List[str]:
    """Extract criteria IDs from a protocol object."""
    all_criteria = []
    try:
        for attr in ['ec_criteria', 'ic_criteria', 'criteria']:
            for c in (getattr(protocol, attr, []) or []):
                if isinstance(c, str):
                    all_criteria.append(c)
                elif hasattr(c, 'get'):
                    all_criteria.append(c.get('id', str(c)))
                else:
                    all_criteria.append(str(c))
    except Exception:
        pass
    return all_criteria


@_safe_render
def _render_calibration_tab():
    session = st.session_state.get("apollo_session")
    protocol = st.session_state.get("research_protocol")

    if not session or not session.articles:
        st.info("Upload a spreadsheet first via EC or IC Screening.")
        return
    if not protocol:
        st.info("Configure a research protocol first via Protocol Configuration.")
        return

    total_articles = len(session.articles)
    default_sample = min(10, total_articles)
    session_id = _compute_session_id()

    with st.container():
        st.markdown(f"""
            <div style="border:1px solid {_c('border')};background:{_c('bg_card')};padding:1rem;border-radius:8px;margin:1rem 0;">
                <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.7rem;color:{_c('cyan')};margin-bottom:0.75rem;">
                    CALIBRATION CONFIGURATION
                </div>
        """, unsafe_allow_html=True)
        col1, col2 = st.columns([2, 1])
        with col1:
            sample_size = st.number_input(
                "Calibration Sample Size",
                min_value=1,
                max_value=min(100, total_articles),
                value=default_sample,
                help="Number of studies to include in the calibration run",
            )
        with col2:
            st.markdown(f"""
                <div style="padding-top:1.5rem;">
                    <span style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{_c('text_muted')};">
                        Total available: {total_articles}
                    </span>
                </div>
            """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        if st.button("▶ Start Protocol Calibration", type="primary", width="stretch"):
            runner = calibration_service.get_or_create_runner(
                session_id=session_id,
                articles=session.articles,
                protocol=protocol,
                protocol_version=getattr(protocol, 'protocol_version', '1.0'),
                sample_size=sample_size,
            )
            runner.all_criteria = _get_all_criteria(protocol)
            runner.run_async()

    runner = calibration_service.get_runner(session_id)

    if runner:
        status = runner.status
        if status == "running":
            _render_calibration_progress(runner)
            st.caption("Auto-refreshing...")
            time.sleep(1.0)
            st.rerun()
        elif status == "completed":
            _render_calibration_report(runner.report or {})
            if st.button("Clear Results", width="stretch"):
                calibration_service.remove_runner(session_id)
                st.rerun()
        elif status in ("error", "stopped"):
            err = getattr(runner, '_error', None) or "Unknown error"
            st.error(f"Calibration {status}: {err}")
            if st.button("Retry", width="stretch"):
                calibration_service.remove_runner(session_id)
                st.rerun()


def render_protocol_calibration():
    """Main Protocol Calibration Dashboard."""
    try:
        terminal_header(
            "PROTOCOL CALIBRATION UNIT",
            "Pilot screening: EC → IC on first N studies",
            status="READY",
        )
    except Exception:
        st.title("Protocol Calibration")

    tab_labels = ["Calibration Run", "History", "Compare", "Analytics"]
    try:
        tabs = st.tabs(tab_labels)
    except Exception as e:
        st.error(f"Cannot render tabs: {e}")
        return

    with tabs[0]:
        _render_calibration_tab()

    with tabs[1]:
        _render_historical()

    with tabs[2]:
        _render_comparison()

    with tabs[3]:
        _render_analytics()
