"""
APOLLO ATLAS Processor UI
Upload ATLAS Excel file, process EC/IC/QC decisions, download results
"""
import streamlit as st
import os
from pathlib import Path


def get_database():
    from src.core.database import Database
    return Database(review_id=st.session_state.get("review_id", 1))


def render_atlas_processor():
    """ATLAS Excel Processor Interface."""
    from src.core.atlas_processor import process_atlas_file
    
    st.header("ATLAS Decision Processor")
    st.caption("Process WL/GL Excel exports through EC/IC/QC pipeline")
    
    st.info("""
    **Input Format**: ATLAS Excel file with:
    - **WL sheet**: Library, Global_ID, Local_ID, Title, Abstract, Keywords
    - **GL sheet**: Posicao, Title, URL, Source_File
    
    **Output**: Excel with decisions (CIs1, CEs1, Decision columns)
    """)
    
    uploaded_file = st.file_uploader("Upload ATLAS Excel File", type=["xlsx"])
    
    if uploaded_file:
        temp_input = f"temp_atlas_{uploaded_file.name}"
        
        # Save uploaded file temporarily
        with open(temp_input, "wb") as f:
            f.write(uploaded_file.getvalue())
        
        st.success(f"Loaded: {uploaded_file.name}")
        
        col_llm, col_process = st.columns([2, 1])
        
        with col_llm:
            enable_llm = st.checkbox(
                "🤖 Enable LLM Reasoning",
                value=bool(os.environ.get("GROQ_API_KEY") or os.environ.get("OPENAI_API_KEY")),
                help="Internal reasoning for decision correctness (not exported)"
            )
        
        with col_process:
            st.write("")
            st.write("")
            process_btn = st.button("🚀 Process Decisions", type="primary")
        
        if process_btn:
            output_file = temp_input.replace(".xlsx", "_decisions.xlsx")
            
            with st.spinner("Processing WL and GL through EC/IC/QC pipeline..."):
                try:
                    wl_results, gl_results = process_atlas_file(
                        input_path=temp_input,
                        output_path=output_file,
                        enable_llm=enable_llm
                    )
                    
                    # Stats
                    wl_included = sum(1 for r in wl_results if r.final_decision == "INCLUDE")
                    gl_included = sum(1 for r in gl_results if r.final_decision == "INCLUDE")
                    
                    st.success("Processing complete!")
                    
                    # Display summary
                    st.subheader("Results Summary")
                    
                    c1, c2, c3, c4 = st.columns(4)
                    with c1:
                        st.metric("WL Processed", len(wl_results))
                    with c2:
                        st.metric("WL Included", wl_included)
                    with c3:
                        st.metric("GL Processed", len(gl_results))
                    with c4:
                        st.metric("GL Included", gl_included)
                    
                    # Show sample results
                    st.subheader("Sample WL Results")
                    wl_sample = []
                    for r in wl_results[:5]:
                        wl_sample.append({
                            "Title": r.title[:50] + "..." if len(r.title) > 50 else r.title,
                            "EC": r.ec_decision,
                            "IC": r.ic_decision,
                            "QC": r.qc_score,
                            "Decision": r.final_decision
                        })
                    st.dataframe(wl_sample, use_container_width=True)
                    
                    st.subheader("Sample GL Results")
                    gl_sample = []
                    for r in gl_results[:5]:
                        gl_sample.append({
                            "Title": r.title[:50] + "..." if len(r.title) > 50 else r.title,
                            "EC": r.ec_decision,
                            "IC": r.ic_decision,
                            "QC": r.qc_score,
                            "Decision": r.final_decision
                        })
                    st.dataframe(gl_sample, use_container_width=True)
                    
                    # Download button
                    with open(output_file, "rb") as f:
                        st.download_button(
                            "📥 Download Results Excel",
                            data=f.read(),
                            file_name="apollo_decisions.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    
                    # Clean up temp file
                    os.remove(temp_input)
                    
                except Exception as e:
                    st.error(f"Processing error: {e}")
                    if os.path.exists(temp_input):
                        os.remove(temp_input)
    
    st.divider()
    st.subheader("Column Structure")
    
    st.markdown("""
    **WL Output Columns**:
    | Original | Decision |
    |----------|----------|
    | Library | CIs1 (IC) |
    | Global_ID | CEs1 (EC) |
    | Local_ID | Decision |
    | Title | |
    | Abstract | |
    | Keywords | |
    
    **GL Output Columns**:
    | Original | Decision |
    |----------|----------|
    | Posicao | Revisor 1 EC |
    | Title | Revisor 1 IC |
    | URL | Decision |
    | Source_File | |
    """)
    
    st.caption("""
    Note: LLM reasoning is generated internally for debugging but NOT exported.
    Only deterministic EC/IC/QC decisions appear in output.
    """)