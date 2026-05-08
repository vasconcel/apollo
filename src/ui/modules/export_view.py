"""
APOLLO Exports & Audit Workspace

Centralized export and audit functionality for PRISMA-compatible reporting.
"""
import streamlit as st
import pandas as pd
from datetime import datetime


def render_exports():
    """Render Exports & Audit Workspace."""
    st.markdown("# Exports & Audit")
    st.markdown("*Generate PRISMA-compatible reports and audit trails*")
    st.divider()

    if "research_protocol" not in st.session_state or st.session_state.research_protocol is None:
        st.warning("⚠️ No Research Protocol configured.")
        return

    protocol = st.session_state.research_protocol
    summary = protocol.get_summary()

    st.markdown("### Protocol Summary")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Version", f"v{summary['version']}")
    with col2:
        st.metric("Hash", summary['hash'] if summary['hash'] else "N/A")
    with col3:
        st.metric("EC/IC/QC", f"{summary['ec_count']}/{summary['ic_count']}/{summary['wl_qc_count'] + summary['gl_qc_count']}")
    with col4:
        st.metric("Status", summary['state'].upper())

    st.divider()

    st.markdown("### Export Protocol Definition")

    protocol_dict = protocol.to_dict()
    protocol_json = str(protocol_dict)

    st.download_button(
        "📄 Download Protocol JSON",
        data=protocol_json,
        file_name=f"apollo_protocol_v{summary['version']}.json",
        mime="application/json"
    )

    st.divider()

    st.markdown("### PRISMA-Compatible Counts")

    ec_session = st.session_state.get("ec_session", {})
    ic_session = st.session_state.get("ic_session", {})
    qc_session = st.session_state.get("qc_session", {})

    render_prisma_counts(ec_session, ic_session, qc_session)

    st.divider()

    st.markdown("### Session Audit Trail")

    render_audit_info(protocol, ec_session, ic_session, qc_session)


def render_prisma_counts(ec_session: dict, ic_session: dict, qc_session: dict):
    """Render PRISMA-style funnel counts."""
    st.markdown("""
    **PRISMA Flow Diagram Counts**

    Use these counts to populate your PRISMA flow diagram.
    """)

    ec_total = len(ec_session.get("articles", []))
    ec_excluded = sum(1 for d in ec_session.get("decisions", {}).values() if d.get("decision") == "exclude")
    ec_included = ec_total - ec_excluded

    ic_total = len(ic_session.get("articles", []))
    ic_excluded = sum(1 for d in ic_session.get("decisions", {}).values() if d.get("decision") == "exclude")
    ic_included = ic_total - ic_excluded

    qc_total = len(qc_session.get("articles", []))
    qc_excluded = sum(1 for a in qc_session.get("assessments", {}).values() if a.get("qc_decision") == "exclude")
    qc_passed = qc_total - qc_excluded

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("#### Identification")
        st.metric("Papers Identified", ec_total)
        st.caption("(from initial search)")

    with col2:
        st.markdown("#### Screening")
        if ec_total > 0:
            st.metric("EC Excluded", ec_excluded)
            st.metric("After EC", ec_included)
        else:
            st.caption("No EC screening data")

    with col3:
        st.markdown("#### Included")
        if qc_total > 0:
            st.metric("Final Included", qc_passed)
            st.caption(f"({qc_passed/qc_total*100:.1f}% inclusion rate)")
        else:
            st.caption("No QC data")

    st.markdown("""
    ```
    ┌─────────────────────────────────────────────────┐
    │  Identification                                 │
    │  Papers identified: {total}                     │
    └─────────────────┬───────────────────────────────┘
                      │
    ┌─────────────────▼───────────────────────────────┐
    │  Screening                                      │
    │  Excluded by EC: {ec_excluded}                  │
    │  After EC: {ec_included}                        │
    │  Excluded by IC: {ic_excluded}                  │
    │  After IC: {ic_included}                        │
    └─────────────────┬───────────────────────────────┘
                      │
    ┌─────────────────▼───────────────────────────────┐
    │  Included                                      │
    │  Passed QC: {qc_passed}                         │
    │  Failed QC: {qc_excluded}                      │
    └─────────────────────────────────────────────────┘
    ```
    """.format(
        total=ec_total,
        ec_excluded=ec_excluded,
        ec_included=ec_included,
        ic_excluded=ic_excluded,
        ic_included=ic_included,
        qc_passed=qc_passed,
        qc_excluded=qc_excluded
    ))


def render_audit_info(protocol, ec_session: dict, ic_session: dict, qc_session: dict):
    """Render audit information."""
    st.markdown("### Audit Information")

    audit_data = {
        "protocol_version": protocol.protocol_version,
        "protocol_hash": protocol.protocol_hash,
        "protocol_locked_at": protocol.locked_at,
        "created_at": protocol.created_at,
        "ec_criteria": len(protocol.ec.criteria),
        "ic_criteria": len(protocol.ic.criteria),
        "wl_qc_criteria": len(protocol.qc.wl_criteria),
        "gl_qc_criteria": len(protocol.qc.gl_criteria),
        "ec_threshold": protocol.qc.wl_threshold,
        "gl_threshold": protocol.qc.gl_threshold,
        "session_timestamp": datetime.now().isoformat()
    }

    st.json(audit_data)

    st.download_button(
        "📋 Download Audit Log (JSON)",
        data=str(audit_data),
        file_name=f"apollo_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json"
    )
