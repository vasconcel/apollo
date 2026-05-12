"""
APOLLO Exports & Audit Workspace - Forensic Terminal Aesthetic

Centralized export and audit functionality for PRISMA-compatible reporting.
Evidence traceability and audit-grade operations.
"""
import streamlit as st
import pandas as pd
from datetime import datetime
import json
import os
from src.ui.components import (
    terminal_header, section_header, status_badge, lit_type_badge,
    metric_tile, telemetry_panel, decision_card, progress_bar,
    stage_indicator, structured_card, terminal_stream, code_block,
    criteria_panel, divider, operational_status, provenance_indicator,
    audit_log_view, timeline_view, kappa_display, conflict_resolution_card
)
from src.ui.theme import COLORS, TYPOGRAPHY


def render_exports():
    """Render Exports & Audit Workspace."""
    terminal_header(
        "EXPORT & AUDIT WORKSPACE",
        "Generate PRISMA-compatible reports and audit trails",
        status="SYSTEM READY"
    )
    divider()

    if "research_protocol" not in st.session_state or st.session_state.research_protocol is None:
        st.warning("⚠ No Research Protocol configured.")
        return

    protocol = st.session_state.research_protocol
    summary = protocol.get_summary()

    render_protocol_summary(summary)
    divider()
    render_export_protocol_section(protocol)
    divider()
    render_prisma_counts_section()
    divider()
    render_audit_section(protocol)


def render_protocol_summary(summary: dict):
    """Render protocol summary in terminal style."""
    st.markdown(f'''
    <div style="border:1px solid {COLORS['border_light']};background:{COLORS['bg_card']};padding:1rem;">
        <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.6rem;color:{COLORS['cyan']};letter-spacing:0.15em;margin-bottom:0.75rem;">
            ▸ PROTOCOL TELEMETRY
        </div>
        <div style="display:grid;grid-template-columns:repeat(4, 1fr);gap:1rem;">
            <div><span style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['text_muted']};">VERSION</span><br><span style="font-family:{TYPOGRAPHY['mono']};font-size:0.9rem;color:{COLORS['text_primary']};">v{summary['version']}</span></div>
            <div><span style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['text_muted']};">HASH</span><br><span style="font-family:{TYPOGRAPHY['mono']};font-size:0.7rem;color:{COLORS['text_secondary']};">{summary['hash'][:16] if summary['hash'] else 'N/A'}...</span></div>
            <div><span style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['text_muted']};">CRITERIA</span><br><span style="font-family:{TYPOGRAPHY['mono']};font-size:0.9rem;color:{COLORS['cyan']};">{summary['ec_count']}/{summary['ic_count']}/{summary['wl_qc_count'] + summary['gl_qc_count']}</span></div>
            <div><span style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['text_muted']};">STATUS</span><br><span style="font-family:{TYPOGRAPHY['mono']};font-size:0.9rem;color:{COLORS['success']};">{summary['state'].upper()}</span></div>
        </div>
    </div>
    ''', unsafe_allow_html=True)


def render_export_protocol_section(protocol):
    """Render protocol export section."""
    section_header("PROTOCOL DEFINITION EXPORT", "Export locked protocol for reproducibility")
    
    protocol_dict = protocol.to_dict()
    protocol_json = json.dumps(protocol_dict, sort_keys=True, ensure_ascii=False)

    st.markdown(f'''
    <div style="border:1px solid {COLORS['border_light']};background:{COLORS['bg_card']};padding:1rem;margin:1rem 0;">
        <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['text_secondary']};margin-bottom:0.5rem;">
            REPRODUCIBILITY REQUIREMENT
        </div>
        <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.7rem;color:{COLORS['text_muted']};line-height:1.6;">
            Export protocol JSON to enable deterministic reproduction. Same protocol + same input = same output.
        </div>
    </div>
    ''', unsafe_allow_html=True)

    st.download_button(
        "Download Protocol JSON",
        data=protocol_json,
        file_name=f"apollo_protocol_v{protocol.protocol_version}.json",
        mime="application/json"
    )


def render_prisma_counts_section():
    """Render PRISMA-style funnel counts."""
    section_header("PRISMA FLOW DIAGRAM COUNTS", "Use for PRISMA flow diagram population")

    session = st.session_state.get("apollo_session")

    if session and session.articles:
        articles = session.articles
        ec_total = len(articles)
        ec_excluded = sum(1 for a in articles if a.ec_stage == "exclude")
        ec_included = ec_total - ec_excluded

        ic_excluded = sum(1 for a in articles if a.ic_stage == "exclude")
        ic_included = ec_included - ic_excluded

        qc_excluded = sum(1 for a in articles if a.qc_stage == "exclude")
        qc_passed = ic_included - qc_excluded

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown(f'''
            <div style="border:1px solid {COLORS['border_light']};background:{COLORS['bg_card']};padding:1rem;">
                <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.6rem;color:{COLORS['cyan']};letter-spacing:0.15em;margin-bottom:0.5rem;">IDENTIFICATION</div>
                <div style="font-family:{TYPOGRAPHY['mono']};font-size:1.5rem;color:{COLORS['text_primary']};">{ec_total}</div>
                <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['text_muted']};">Papers identified (from initial search)</div>
            </div>
            ''', unsafe_allow_html=True)
        with col2:
            st.markdown(f'''
            <div style="border:1px solid {COLORS['border_light']};background:{COLORS['bg_card']};padding:1rem;">
                <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.6rem;color:{COLORS['cyan']};letter-spacing:0.15em;margin-bottom:0.5rem;">SCREENING</div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem;">
                    <div><span style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['error']};">EXCLUDED</span><br><span style="font-family:{TYPOGRAPHY['mono']};font-size:1.1rem;color:{COLORS['text_primary']};">{ec_excluded}</span></div>
                    <div><span style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['success']};">AFTER EC</span><br><span style="font-family:{TYPOGRAPHY['mono']};font-size:1.1rem;color:{COLORS['text_primary']};">{ec_included}</span></div>
                </div>
                <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['text_muted']};margin-top:0.5rem;">After IC: {ic_included}</div>
            </div>
            ''', unsafe_allow_html=True)
        with col3:
            st.markdown(f'''
            <div style="border:1px solid {COLORS['border_light']};background:{COLORS['bg_card']};padding:1rem;">
                <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.6rem;color:{COLORS['cyan']};letter-spacing:0.15em;margin-bottom:0.5rem;">INCLUDED</div>
                <div style="font-family:{TYPOGRAPHY['mono']};font-size:1.5rem;color:{COLORS['success']};">{qc_passed}</div>
                <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['text_muted']};">{f"{(qc_passed/ic_included*100):.1f}%" if ic_included > 0 else "0%"} inclusion rate</div>
            </div>
            ''', unsafe_allow_html=True)

        st.markdown(f'''
        <pre style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;background:{COLORS['bg_surface']};border:1px solid {COLORS['border']};padding:1rem;margin-top:1rem;color:{COLORS['text_secondary']};">
┌─────────────────────────────────────────────────┐
│  IDENTIFICATION                                 │
│  Papers identified: {ec_total:>4}                     │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│  SCREENING                                      │
│  Excluded by EC:   {ec_excluded:>4}                     │
│  After EC:         {ec_included:>4}                     │
│  Excluded by IC:   {ic_excluded:>4}                     │
│  After IC:         {ic_included:>4}                     │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│  INCLUDED                                      │
│  Passed QC:        {qc_passed:>4}                     │
│  Failed QC:        {qc_excluded:>4}                     │
└─────────────────────────────────────────────────┘
        ''', unsafe_allow_html=True)

        if st.button("EXPORT FULL SESSION (Excel)", type="primary"):
            export_full_session(session)
    else:
        st.info("No screening session data found. Complete EC → IC → QC screening to enable full export.")


def render_audit_section(protocol):
    """Render audit information section."""
    section_header("SESSION AUDIT TRAIL", "Complete audit log with timestamp and provenance")

    audit_data = {
        "protocol_version": protocol.protocol_version,
        "protocol_hash": protocol.protocol_hash,
        "protocol_locked_at": protocol.locked_at,
        "created_at": protocol.created_at,
        "ec_criteria_count": len(protocol.ec.criteria),
        "ic_criteria_count": len(protocol.ic.criteria),
        "wl_qc_criteria_count": len(protocol.qc.wl_criteria),
        "gl_qc_criteria_count": len(protocol.qc.gl_criteria),
        "wl_threshold": protocol.qc.wl_threshold,
        "gl_threshold": protocol.qc.gl_threshold,
        "session_timestamp": datetime.now().isoformat()
    }

    st.markdown(f'''
    <div style="border:1px solid {COLORS['border_light']};background:{COLORS['bg_card']};padding:1rem;margin:1rem 0;">
        <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.6rem;color:{COLORS['cyan']};letter-spacing:0.15em;margin-bottom:0.75rem;">
            ▸ AUDIT METADATA
        </div>
    ''' + "".join([
        f'<div style="display:flex;justify-content:space-between;padding:0.25rem 0;border-bottom:1px solid {COLORS["border"]};font-family:{TYPOGRAPHY["mono"]};font-size:0.7rem;"><span style="color:{COLORS["text_muted"]};">{k}:</span><span style="color:{COLORS["text_secondary"]};">{v}</span></div>'
        for k, v in audit_data.items()
    ]) + '</div>', unsafe_allow_html=True)

    st.download_button(
        "Download Audit Log (JSON)",
        data=json.dumps(audit_data, sort_keys=True, ensure_ascii=False),
        file_name=f"apollo_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json"
    )


def export_full_session(session):
    """Export full session using canonical ExportEngine."""
    import tempfile
    from src.core.export_engine import ExportEngine

    try:
        engine = ExportEngine(protocol_version=session.protocol_version)

        with tempfile.TemporaryDirectory() as tmpdir:
            excel_path = engine.export_decisions_excel(session, os.path.join(tmpdir, "decisions.xlsx"))

            import pandas as pd
            df = pd.read_excel(excel_path, sheet_name="WL")
            csv_data = df.to_csv(index=False)

            st.download_button(
                "Download Full Session (CSV)",
                data=csv_data,
                file_name="apollo_full_session.csv",
                mime="text/csv"
            )

            st.success("Session export complete.")
    except Exception as e:
        st.error(f"Export failed: {e}")