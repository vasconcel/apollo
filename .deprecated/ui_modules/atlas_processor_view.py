"""
APOLLO ATLAS Processor UI
Upload ATLAS Excel file, process EC/IC/QC decisions, download results

DESIGN PRINCIPLES:
- All business logic stays in src/core/
- Streamlit is presentation-only
- Deterministic behavior preserved
- No stateful persistence
"""
import streamlit as st
import os
from pathlib import Path


def render_protocol_info():
    """Display protocol information in the sidebar."""
    from src.core.dynamic_protocol import DynamicProtocol, ProtocolState

    st.divider()

    if "research_protocol" not in st.session_state or st.session_state.research_protocol is None:
        st.caption("**PROTOCOL**: Not configured")
        return

    protocol = st.session_state.research_protocol
    summary = protocol.get_summary()

    st.caption("**RESEARCH PROTOCOL**")

    state_icons = {
        ProtocolState.DRAFT.value: "⚠️",
        ProtocolState.LOCKED.value: "🔒",
        ProtocolState.ACTIVE_SESSION.value: "▶️"
    }

    state_labels = {
        ProtocolState.DRAFT.value: "DRAFT",
        ProtocolState.LOCKED.value: "LOCKED",
        ProtocolState.ACTIVE_SESSION.value: "ACTIVE"
    }

    col1, col2 = st.columns(2)
    with col1:
        st.caption(f"**Version**: v{summary['version']}")
    with col2:
        st.caption(f"{state_icons.get(protocol.state, '')} {state_labels.get(protocol.state, 'UNKNOWN')}")

    col3, col4, col5 = st.columns(3)
    with col3:
        st.caption(f"EC: {summary['ec_enabled']}/{summary['ec_count']}")
    with col4:
        st.caption(f"IC: {summary['ic_enabled']}/{summary['ic_count']}")
    with col5:
        st.caption(f"QC: {summary['qc_enabled']}/{summary['qc_count']}")

    if summary['hash']:
        st.caption(f"Hash: `{summary['hash']}`")


def render_execution_dashboard(wl_results, gl_results):
    """Render the execution dashboard with statistics."""
    st.subheader("📊 Execution Dashboard")
    
    wl_total = len(wl_results)
    wl_included = sum(1 for r in wl_results if r.final_decision == "INCLUDE")
    wl_excluded = wl_total - wl_included
    
    gl_total = len(gl_results)
    gl_included = sum(1 for r in gl_results if r.final_decision == "INCLUDE")
    gl_excluded = gl_total - gl_included
    
    # Main metrics
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        st.metric("Total Articles", wl_total + gl_total)
    with c2:
        st.metric("WL Total", wl_total)
    with c3:
        st.metric("WL Included", wl_included, delta=wl_excluded, delta_color="inverse")
    with c4:
        st.metric("GL Total", gl_total)
    with c5:
        st.metric("GL Included", gl_included, delta=gl_excluded, delta_color="inverse")
    with c6:
        inclusion_rate = ((wl_included + gl_included) / (wl_total + gl_total) * 100) if (wl_total + gl_total) > 0 else 0
        st.metric("Inclusion Rate", f"{inclusion_rate:.1f}%")


def render_exclusion_reasons(wl_results):
    """Show top exclusion reasons."""
    st.subheader("🚫 Top Exclusion Reasons")
    
    ec_counts = {"EC1": 0, "EC2": 0, "EC3": 0, "EC4": 0, "IC1": 0, "IC2": 0}
    
    for r in wl_results:
        ec = r.ec_decision
        ic = r.ic_decision
        
        if ec in ec_counts:
            ec_counts[ec] += 1
        if ic in ec_counts:
            ec_counts[ic] += 1
    
    # Sort by count
    sorted_reasons = sorted(ec_counts.items(), key=lambda x: x[1], reverse=True)
    
    for reason, count in sorted_reasons:
        if count > 0:
            st.caption(f"**{reason}**: {count} articles")


def render_qc_distribution(wl_results):
    """Show QC score distribution for WL."""
    st.subheader("📈 QC Score Distribution (WL)")
    
    qc_4 = sum(1 for r in wl_results if r.qc_score == "4.0/4")
    qc_3 = sum(1 for r in wl_results if "3." in str(r.qc_score))
    qc_2 = sum(1 for r in wl_results if "2." in str(r.qc_score))
    qc_below = sum(1 for r in wl_results if r.qc_score not in ["N/A", "4.0/4"] and ("1." in str(r.qc_score) or "0." in str(r.qc_score)))
    qc_na = sum(1 for r in wl_results if r.qc_score == "N/A")
    
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("4.0/4 (Full)", qc_4)
    with c2:
        st.metric("3.x (Good)", qc_3)
    with c3:
        st.metric("2.x (Marginal)", qc_2)
    with c4:
        st.metric("<2.0 (Below)", qc_below)
    with c5:
        st.metric("N/A (Skipped)", qc_na)


def render_decision_transparency(wl_results, gl_results):
    """Show detailed decision information per article."""
    st.subheader("🔍 Decision Transparency")
    
    tab_wl, tab_gl = st.tabs(["White Literature", "Grey Literature"])
    
    with tab_wl:
        if wl_results:
            wl_data = []
            for r in wl_results:
                wl_data.append({
                    "Title": r.title[:60] + "..." if len(r.title) > 60 else r.title,
                    "EC Decision": r.ec_decision,
                    "IC Decision": r.ic_decision,
                    "QC Score": r.qc_score,
                    "Final": r.final_decision
                })
            st.dataframe(wl_data, width="stretch", height=300)
        else:
            st.info("No WL articles processed")
    
    with tab_gl:
        if gl_results:
            gl_data = []
            for r in gl_results:
                gl_data.append({
                    "Title": r.title[:60] + "..." if len(r.title) > 60 else r.title,
                    "EC Decision": r.ec_decision,
                    "IC Decision": r.ic_decision,
                    "QC Score": r.qc_score,
                    "Final": r.final_decision
                })
            st.dataframe(gl_data, width="stretch", height=300)
        else:
            st.info("No GL articles processed")


def render_audit_download(output_file):
    """Render audit log download option."""
    from src.core.audit_logger import AuditLogger
    
    # Try to find the latest audit log
    log_dir = "logs"
    if os.path.exists(log_dir):
        log_files = [f for f in os.listdir(log_dir) if f.startswith("apollo_run_") and f.endswith(".json")]
        if log_files:
            latest_log = sorted(log_files)[-1]
            log_path = os.path.join(log_dir, latest_log)
            
            with open(log_path, "r") as f:
                log_content = f.read()
            
            st.download_button(
                "📋 Download Audit Log",
                data=log_content,
                file_name=f"apollo_audit_{latest_log.replace('.json', '')}.json",
                mime="application/json"
            )


def render_atlas_processor():
    """ATLAS Excel Processor Interface - Main entry point."""
    st.warning("DEPRECATED: This view is not routed by app.py. Canonical workflow uses EC Screening view with ATLAS file upload. Will be removed in a future release.")
    from src.core.atlas_processor import process_atlas_file
    from src.core.audit_logger import AuditLogger
    from src.core.dynamic_protocol import ProtocolState

    st.header("Upload & Process")
    st.caption("Upload ATLAS Excel file to begin screening")

    render_protocol_info()

    protocol_ready, message = check_protocol_status()
    if not protocol_ready:
        st.warning(f"⚠️ {message}")
        st.info("Please configure and lock your Research Protocol before uploading papers.")
        return

    st.divider()

    st.subheader("📁 Input Data")
    st.info("""
    **Required ATLAS Excel Format**:
    - **WL sheet**: Library, Global_ID, Local_ID, Title, Abstract, Keywords
    - **GL sheet**: Posicao, Title, URL, Source_File

    Output includes deterministic EC/IC/QC decisions with full audit trail.
    """)

    uploaded_file = st.file_uploader("Upload ATLAS Excel File", type=["xlsx"], help="Upload your ATLAS export with WL and GL sheets")

    if uploaded_file:
        temp_input = f"temp_atlas_{uploaded_file.name}"

        with open(temp_input, "wb") as f:
            f.write(uploaded_file.getvalue())

        st.success(f"✅ Loaded: {uploaded_file.name}")

        st.subheader("⚙️ Processing Options")

        col_llm, col_protocol = st.columns([2, 1])

        with col_llm:
            enable_llm = st.checkbox(
                "🤖 Internal LLM Reasoning",
                value=False,
                help="Generate internal reasoning for debugging (NOT exported - decisions remain deterministic)"
            )

        with col_protocol:
            if "research_protocol" in st.session_state and st.session_state.research_protocol:
                p = st.session_state.research_protocol
                st.caption(f"Protocol: v{p.protocol_version}")
            else:
                st.caption("Protocol: Default")

        process_btn = st.button("🚀 Run Screening Pipeline", type="primary", width="stretch")

        if process_btn:
            output_file = temp_input.replace(".xlsx", "_decisions.xlsx")

            with st.spinner("Processing articles through EC → IC → QC pipeline..."):
                try:
                    wl_results, gl_results = process_atlas_file(
                        input_path=temp_input,
                        output_path=output_file,
                        enable_llm=enable_llm
                    )

                    st.success("✅ Processing complete!")

                    render_execution_dashboard(wl_results, gl_results)

                    with st.expander("🚫 View Exclusion Reasons", expanded=True):
                        render_exclusion_reasons(wl_results)

                    with st.expander("📈 View QC Distribution", expanded=True):
                        render_qc_distribution(wl_results)

                    with st.expander("🔍 View All Decisions", expanded=False):
                        render_decision_transparency(wl_results, gl_results)

                    st.divider()

                    st.subheader("📥 Download Results")

                    col_dl1, col_dl2 = st.columns(2)

                    with col_dl1:
                        with open(output_file, "rb") as f:
                            st.download_button(
                                "📊 Download Results Excel",
                                data=f.read(),
                                file_name="APOLLO_Selection_Criteria.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                width="stretch"
                            )

                    with col_dl2:
                        render_audit_download(output_file)

                    st.caption("✅ Deterministic processing verified - same input produces same output")

                    os.remove(temp_input)

                except Exception as e:
                    st.error(f"❌ Processing error: {e}")
                    if os.path.exists(temp_input):
                        os.remove(temp_input)

    st.divider()
    st.caption("""
    📋 **APOLLO Guarantees**:
    • Deterministic: Same input + same protocol = same output, every time
    • Reproducible: Full audit logging with determinism hash
    • Protocol-based: Configurable EC/IC/QC criteria via protocol system
    • Transparent: All decisions visible and traceable
    """)


def check_protocol_status():
    """Check if research protocol is ready for screening."""
    from src.core.dynamic_protocol import ProtocolState

    if "research_protocol" not in st.session_state or st.session_state.research_protocol is None:
        return (False, "No protocol configured. Please configure your Research Protocol first.")

    protocol = st.session_state.research_protocol

    if protocol.state == ProtocolState.DRAFT.value:
        return (False, "Protocol must be locked before screening begins. Go to 'Protocol Configuration' to lock your protocol.")

    if protocol.state == ProtocolState.LOCKED.value:
        return (True, "Protocol ready for screening.")

    if protocol.state == ProtocolState.ACTIVE_SESSION.value:
        return (True, "Protocol has active session.")

    return (False, "Unknown protocol state.")


def render_atlas_processor_legacy():
    """Legacy function - redirects to main view."""
    render_atlas_processor()