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
    """Render Exports & Audit Workspace - Researcher 1 Package."""
    terminal_header(
        "EXPORT & AUDIT WORKSPACE",
        "Researcher 1 Independent Review Package - Decision column open for Consensus",
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
    render_researcher1_banner()
    divider()
    render_download_section()
    divider()
    render_session_health_check()
    divider()
    render_live_preview_section()
    divider()
    render_export_protocol_section(protocol)
    divider()
    render_prisma_counts_section()
    divider()
    render_audit_section(protocol)


def get_pending_count():
    """Calculate pending articles count using live ces1/cis1 values - no caching."""
    session = st.session_state.get("apollo_session") or st.session_state.get("session")
    
    pending_count = 0
    if session and hasattr(session, 'articles') and session.articles:
        for article in session.articles:
            ces1 = getattr(article, 'ces1', '') or ''
            cis1 = getattr(article, 'cis1', '') or ''
            
            ec_pending = not ces1 or ces1 == ""
            ic_pending = ces1 == "NO" and (not cis1 or cis1 == "")
            if ec_pending or ic_pending:
                pending_count += 1
    
    return pending_count


def render_researcher1_banner():
    """Render Researcher 1 package indicator - Streamlit-native rendering."""
    pending_count = get_pending_count()
    
    with st.container():
        st.markdown("### Independent Reviewer Package")
        if pending_count > 0:
            st.caption(f"({pending_count} articles pending review)")
        
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            if pending_count > 0:
                st.info("Reviewer 1: In Progress")
            else:
                st.success("Reviewer 1: Complete")
        
        with col2:
            st.warning("Reviewer 2: Pending")
        
        with col3:
            st.caption("Consensus: Pending")


def render_download_section():
    """Render prominent download section."""
    section_header("📥 DOWNLOAD RESEARCHER 1 PACKAGE", "Export final Excel package for peer review")
    
    session = st.session_state.get("apollo_session") or st.session_state.get("session")
    
    if not session or not session.articles:
        st.info("No session data available. Complete screening to enable export.")
        return
    
    st.markdown(f'''
    <div style="border:2px solid {COLORS['success']};background:linear-gradient(135deg, {COLORS['bg_card']} 0%, #1a2e1a 100%);padding:1.5rem;margin:1rem 0;text-align:center;">
        <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.7rem;color:{COLORS['success']};letter-spacing:0.1em;margin-bottom:1rem;">
            ▸ FINAL EXPORT
        </div>
        <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.9rem;color:{COLORS['text_primary']};margin-bottom:1rem;">
            {len(session.articles)} articles | WL/GL separated | Coded decisions | Tab-colored sheets
        </div>
    </div>
    ''', unsafe_allow_html=True)
    
    if st.button("📥 DOWNLOAD RESEARCHER 1 PACKAGE (.xlsx)", type="primary", width="stretch"):
        export_full_session(session)


def render_session_health_check():
    """Render session health diagnostics - check for PENDING articles."""
    session = st.session_state.get("apollo_session") or st.session_state.get("session")
    
    if not session or not hasattr(session, 'articles') or not session.articles:
        return
    
    pending_articles = []
    for i, article in enumerate(session.articles):
        ces1 = getattr(article, 'ces1', '') or ''
        cis1 = getattr(article, 'cis1', '') or ''
        
        ec_pending = not ces1 or ces1 == ""
        ic_pending = ces1 == "NO" and (not cis1 or cis1 == "")
        
        if ec_pending or ic_pending:
            ec_status = ces1 if ces1 else "PENDING"
            ic_status = cis1 if ces1 == "NO" else "N/A"
            pending_articles.append({
                "index": i + 1,
                "title": article.title[:60] + "..." if len(article.title) > 60 else article.title,
                "ec_status": ec_status,
                "ic_status": ic_status
            })
    
    if pending_articles:
        st.markdown(f'''
        <div style="border:1px solid {COLORS['warning']};background:{COLORS['bg_card']};padding:1rem;margin:1rem 0;">
            <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['warning']};letter-spacing:0.1em;margin-bottom:0.75rem;">
                ▸ SESSION HEALTH WARNING: {len(pending_articles)} PENDING ARTICLES
            </div>
            <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.7rem;color:{COLORS['text_muted']};">
                The following articles have incomplete decisions. Export will include PENDING values.
            </div>
        </div>
        ''', unsafe_allow_html=True)
        
        with st.expander(f"View {len(pending_articles)} Pending Articles", expanded=False):
            for pa in pending_articles[:10]:
                st.markdown(f"""
                <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;padding:0.5rem;border-bottom:1px solid {COLORS['border']};">
                    <span style="color:{COLORS['cyan']};">{pa['index']:04d}</span> | 
                    {pa['title']} | 
                    <span style="color:{COLORS['error']};">EC: {pa['ec_status']}</span> | 
                    <span style="color:{COLORS['warning']};">IC: {pa['ic_status']}</span>
                </div>
                """, unsafe_allow_html=True)
            
            if len(pending_articles) > 10:
                st.caption(f"... and {len(pending_articles) - 10} more")
    else:
        st.markdown(f'''
        <div style="border:1px solid {COLORS['success']};background:{COLORS['bg_card']};padding:0.75rem;margin:0.5rem 0;">
            <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.6rem;color:{COLORS['success']};">
                ✓ SESSION HEALTH: All {len(session.articles)} articles have complete decisions
            </div>
        </div>
        ''', unsafe_allow_html=True)


def render_live_preview_section():
    """Render live spreadsheet preview of export."""
    section_header("LIVE PREVIEW", "Preview of Researcher 1 package with styling")
    
    session = st.session_state.get("apollo_session") or st.session_state.get("session")
    
    if not session or not session.articles:
        st.info("No session data available. Complete screening to see preview.")
        return
    
    import pandas as pd
    
    wl_articles = session.get_wl_articles()
    gl_articles = session.get_gl_articles()
    
    if wl_articles:
        wl_data = []
        for article in wl_articles:
            meta = article.metadata
            final_dec = article.final_decision if article.final_decision else ""
            
            cis1_val = article.cis1 if article.cis1 else (article.ic_stage if article.ic_stage else "PENDING")
            ces1_val = article.ces1 if article.ces1 else (article.ec_stage if article.ec_stage else "PENDING")
            
            wl_data.append({
                "Library": meta.get("library", ""),
                "Global_ID": meta.get("global_id", ""),
                "Local_ID": meta.get("local_id", ""),
                "Title": article.title[:50] + "..." if len(article.title) > 50 else article.title,
                "Abstract": (article.abstract[:30] + "...") if article.abstract and len(article.abstract) > 30 else article.abstract if article.abstract else "",
                "Keywords": meta.get("keywords", ""),
                "CIs1": cis1_val,
                "CEs1": ces1_val,
                "Revisor 1": article.revisor1 if article.revisor1 else session.researcher_id,
                "CIs2": "",
                "CEs2": "",
                "Revisor 2": "",
                "Decision": final_dec
            })
        
        df_wl = pd.DataFrame(wl_data)
        
        st.markdown(f"**WL Sheet Preview ({len(wl_articles)} articles)**")
        
        def highlight_cis1(val):
            if val and val not in ["", "PENDING", "NO"]:
                return 'background-color: #C6EFCE; color: #006100'
            return None
        
        def highlight_ces1(val):
            if val and val not in ["", "PENDING", "NO"]:
                return 'background-color: #FFC7CE; color: #9C0006'
            return None
        
        st.dataframe(
            df_wl.style.map(highlight_cis1, subset=['CIs1'])
                       .map(highlight_ces1, subset=['CEs1']),
            width="stretch",
            height=300
        )
    
    if gl_articles:
        gl_data = []
        for article in gl_articles:
            meta = article.metadata
            final_dec = article.final_decision if article.final_decision else ""
            
            ces1_val = article.ces1 if article.ces1 else (article.ec_stage if article.ec_stage else "PENDING")
            cis1_val = article.cis1 if article.cis1 else (article.ic_stage if article.ic_stage else "PENDING")
            
            gl_data.append({
                "Posicao": meta.get("posicao", meta.get("#", "")),
                "Title": article.title[:50] + "..." if len(article.title) > 50 else article.title,
                "URL": meta.get("url", "")[:40] + "..." if meta.get("url") and len(meta.get("url", "")) > 40 else meta.get("url", ""),
                "Source_File": meta.get("source_file", ""),
                "Revisor 1 EC": ces1_val,
                "Revisor 1 IC": cis1_val,
                "Decision": final_dec
            })
        
        df_gl = pd.DataFrame(gl_data)
        
        st.markdown(f"**GL Sheet Preview ({len(gl_articles)} articles)**")
        
        def highlight_ec(val):
            if val and val not in ["", "PENDING", "NO"]:
                return 'background-color: #C6EFCE; color: #006100'
            return None
        
        st.dataframe(
            df_gl.style.map(highlight_ec, subset=['Revisor 1 EC', 'Revisor 1 IC']),
            width="stretch",
            height=200
        )


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
            <div><span style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['text_muted']};">CRITERIA</span><br><span style="font-family:{TYPOGRAPHY['mono']};font-size:0.9rem;color:{COLORS['cyan']};">EC:{summary['ec_count']} | IC:{summary['ic_count']}</span></div>
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
    """Render PRISMA-style flow diagram with proper visual cards."""
    section_header("PRISMA FLOW DIAGRAM", "Visual screening workflow for publication")

    session = st.session_state.get("apollo_session") or st.session_state.get("session")

    if session and hasattr(session, 'articles') and session.articles:
        articles = session.articles
        ec_total = len(articles)
        ec_excluded = sum(1 for a in articles if (getattr(a, 'ces1', '') or '').strip() not in ['', 'NO'])
        ec_included = ec_total - ec_excluded

        ic_excluded = sum(1 for a in articles if (getattr(a, 'ces1', '') or '') == "NO" and (getattr(a, 'cis1', '') or '').strip() not in ['', 'NO'])
        ic_included = ec_included - ic_excluded
        
        pending_count = get_pending_count()

        st.markdown("### PRISMA Flow Diagram")
        
        c1, c2, c3, c4, c5 = st.columns([2, 0.3, 2, 0.3, 2])
        
        with c1:
            st.metric("Identification", ec_total, "articles from search")
        
        with c2:
            st.caption("→")
        
        with c3:
            st.metric("After EC", ec_included, f"-{ec_excluded} excluded")
        
        with c4:
            st.caption("→")
        
        with c5:
            rate = f"{(ic_included/ec_total*100):.1f}%" if ec_total > 0 else "0%"
            st.metric("Final Included", ic_included, rate)
        
        if pending_count > 0:
            st.warning(f"{pending_count} articles pending review")
        
        render_export_summary_cards(session, ec_total, ec_excluded, ec_included, ic_excluded, ic_included)
    else:
        st.info("No screening session data found. Complete EC → IC screening to enable full export.")


def render_export_summary_cards(session, ec_total, ec_excluded, ec_included, ic_excluded, ic_included):
    """Render export summary cards with key metrics."""
    protocol = st.session_state.get("research_protocol")
    protocol_version = protocol.protocol_version if protocol else "N/A"
    session_checksum = session.compute_checksum() if hasattr(session, 'compute_checksum') else "N/A"
    
    wl_count = len(session.get_wl_articles()) if hasattr(session, 'get_wl_articles') else 0
    gl_count = len(session.get_gl_articles()) if hasattr(session, 'get_gl_articles') else 0
    
    st.markdown("### Export Summary")
    
    s1, s2, s3, s4 = st.columns(4)
    with s1:
        st.metric("Total", ec_total, f"WL: {wl_count}, GL: {gl_count}")
    with s2:
        st.metric("Excluded", ec_excluded + ic_excluded, f"EC: {ec_excluded}, IC: {ic_excluded}")
    with s3:
        st.metric("Included", ic_included, "final selection")
    with s4:
        st.metric("Protocol", f"v{protocol_version}", session_checksum[:8] + "...")


def render_audit_section(protocol):
    """Render audit information section - Reviewer 1 only."""
    section_header("SESSION AUDIT TRAIL", "Complete audit log with timestamp and provenance")

    audit_data = {
        "protocol_version": protocol.protocol_version,
        "protocol_hash": protocol.protocol_hash,
        "protocol_locked_at": protocol.locked_at,
        "created_at": protocol.created_at,
        "ec_criteria_count": len(protocol.ec.criteria),
        "ic_criteria_count": len(protocol.ic.criteria),
        "reviewer": "Reviewer 1 (Researcher 1 Package)",
        "stage_boundary": "EC + IC Complete",
        "consensus_phase": "Pending (Reviewer 2 + Consensus)",
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
    """Export full session using canonical ExportEngine (Researcher 1 Package)."""
    import tempfile
    from src.core.export_engine import ExportEngine

    try:
        engine = ExportEngine(protocol_version=session.protocol_version)
        
        protocol = st.session_state.get("research_protocol")
        ec_criteria = {}
        ic_criteria = {}
        
        if protocol:
            ec_criteria = {
                k: v.description
                for k, v in protocol.ec.criteria.items()
                if v.enabled
            }
            ic_criteria = {
                k: v.description
                for k, v in protocol.ic.criteria.items()
                if v.enabled
            }

        with tempfile.TemporaryDirectory() as tmpdir:
            excel_path = engine.export_decisions_excel(
                session,
                os.path.join(tmpdir, "decisions.xlsx"),
                ec_criteria_descriptions=ic_criteria,
                ic_criteria_descriptions=ec_criteria
            )

            with open(excel_path, "rb") as f:
                excel_data = f.read()

            st.download_button(
                "Download Researcher 1 Package (XLSX)",
                data=excel_data,
                file_name="apollo_researcher1_package.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            st.success("Researcher 1 Package export complete.")
    except Exception as e:
        st.error(f"Export failed: {e}")