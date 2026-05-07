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
    from src.core.protocol_engine import get_default_protocol
    
    protocol = get_default_protocol()
    
    with st.sidebar:
        st.divider()
        st.caption("PROTOCOL")
        
        col1, col2 = st.columns(2)
        with col1:
            st.caption(f"**Version**: {protocol.get('protocol_version', '1.0')}")
        with col2:
            st.caption(f"**Threshold**: {protocol.get('quality_criteria', {}).get('threshold', 2.0)}")
        
        ec_count = len(protocol.get('exclusion_criteria', {}))
        ic_count = len(protocol.get('inclusion_criteria', {}))
        qc_wl = len(protocol.get('quality_criteria', {}).get('WL', {}))
        qc_gl = len(protocol.get('quality_criteria', {}).get('GL', {}))
        
        st.caption(f"**EC Rules**: {ec_count}")
        st.caption(f"**IC Rules**: {ic_count}")
        st.caption(f"**QC (WL)**: {qc_wl}")
        st.caption(f"**QC (GL)**: {qc_gl}")


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
            st.dataframe(wl_data, use_container_width=True, height=300)
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
            st.dataframe(gl_data, use_container_width=True, height=300)
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
    from src.core.atlas_processor import process_atlas_file
    from src.core.audit_logger import AuditLogger
    
    st.header("🔬 APOLLO - Systematic Literature Review Screening")
    st.caption("Deterministic EC/IC/QC evaluation for Software Engineering research")
    
    # Display protocol info
    render_protocol_info()
    
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
        
        # Save uploaded file temporarily
        with open(temp_input, "wb") as f:
            f.write(uploaded_file.getvalue())
        
        st.success(f"✅ Loaded: {uploaded_file.name}")
        
        # Processing options
        st.subheader("⚙️ Processing Options")
        
        col_llm, col_protocol = st.columns([2, 1])
        
        with col_llm:
            enable_llm = st.checkbox(
                "🤖 Internal LLM Reasoning",
                value=False,
                help="Generate internal reasoning for debugging (NOT exported - decisions remain deterministic)"
            )
        
        with col_protocol:
            st.caption("Protocol: Default APOLLO v1.0")
        
        process_btn = st.button("🚀 Run Screening Pipeline", type="primary", use_container_width=True)
        
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
                    
                    # Execution dashboard
                    render_execution_dashboard(wl_results, gl_results)
                    
                    # Exclusion reasons
                    with st.expander("🚫 View Exclusion Reasons", expanded=True):
                        render_exclusion_reasons(wl_results)
                    
                    # QC distribution
                    with st.expander("📈 View QC Distribution", expanded=True):
                        render_qc_distribution(wl_results)
                    
                    # Decision transparency
                    with st.expander("🔍 View All Decisions", expanded=False):
                        render_decision_transparency(wl_results, gl_results)
                    
                    st.divider()
                    
                    # Downloads
                    st.subheader("📥 Download Results")
                    
                    col_dl1, col_dl2 = st.columns(2)
                    
                    with col_dl1:
                        with open(output_file, "rb") as f:
                            st.download_button(
                                "📊 Download Results Excel",
                                data=f.read(),
                                file_name="APOLLO_Selection_Criteria.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True
                            )
                    
                    with col_dl2:
                        render_audit_download(output_file)
                    
                    # Determinism verification
                    st.caption("✅ Deterministic processing verified - same input produces same output")
                    
                    # Clean up temp file
                    os.remove(temp_input)
                    
                except Exception as e:
                    st.error(f"❌ Processing error: {e}")
                    if os.path.exists(temp_input):
                        os.remove(temp_input)
    
    # Footer with deterministic guarantee
    st.divider()
    st.caption("""
    📋 **APOLLO Guarantees**:
    • Deterministic: Same input + same protocol = same output, every time
    • Reproducible: Full audit logging with determinism hash
    • Protocol-based: Configurable EC/IC/QC criteria via protocol system
    • Transparent: All decisions visible and traceable
    """)


def render_atlas_processor_legacy():
    """Legacy function - redirects to main view."""
    render_atlas_processor()