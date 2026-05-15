"""
APOLLO Inter-Rater Reliability (IRR) Module
Calibration view for computing Cohen's Kappa between two researchers.

METHODOLOGY:
- Compares decisions from two independent Session JSON files.
- Aligns articles by unique Article ID.
- Computes Confusion Matrix and Cohen's Kappa coefficient.
- Interprets results based on Landis & Koch (1977) scale.
"""
import streamlit as st
import json
import pandas as pd
import numpy as np
from datetime import datetime

from src.ui.theme import COLORS, TYPOGRAPHY
from src.ui.components import section_header, divider, terminal_header
from src.core.calibration_engine import CalibrationEngine

def load_session_json(uploaded_file):
    """Safely loads and parses an APOLLO session file."""
    try:
        data = json.load(uploaded_file)
        # Basic validation
        if "session_id" not in data or "articles" not in data:
            st.error(f"Invalid Session File: {uploaded_file.name}")
            return None
        return data
    except Exception as e:
        st.error(f"Error parsing JSON: {str(e)}")
        return None

def interpret_kappa(kappa):
    """Landis & Koch (1977) scale for Kappa interpretation."""
    if kappa < 0: return "Poor (Disagreement)", COLORS["error"]
    if kappa <= 0.20: return "Slight Agreement", "#FF4757"
    if kappa <= 0.40: return "Fair Agreement", "#FFB020"
    if kappa <= 0.60: return "Moderate Agreement", "#FFD32A"
    if kappa <= 0.80: return "Substantial Agreement", "#05C46B"
    return "Almost Perfect Agreement", COLORS["success"]

def render_calibration_workspace():
    """Main Calibration Dashboard."""
    
    terminal_header(
        "INTER-RATER CALIBRATION UNIT",
        "Calculating reliability between independent reviewers",
        status="READY"
    )

    st.markdown(f"""
    <div style="background:{COLORS['bg_card']}; padding:1rem; border-left:2px solid {COLORS['cyan']}; margin-bottom:2rem;">
        <div style="{TYPOGRAPHY['mono']}; font-size:0.75rem; color:{COLORS['text_secondary']};">
            ▸ LOAD SESSION FILES (.JSON) FROM TWO RESEARCHERS TO COMPUTE COHEN'S KAPPA
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 1. File Selection Area
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"<div style='{TYPOGRAPHY['mono']}; font-size:0.7rem;'>SOURCE_A (PRIMARY)</div>", unsafe_allow_html=True)
        file_a = st.file_uploader("Upload Researcher A Session", type=["json"], label_visibility="collapsed")
        
    with col2:
        st.markdown(f"<div style='{TYPOGRAPHY['mono']}; font-size:0.7rem;'>SOURCE_B (SECONDARY)</div>", unsafe_allow_html=True)
        file_b = st.file_uploader("Upload Researcher B Session", type=["json"], label_visibility="collapsed")

    if file_a and file_b:
        session_a = load_session_json(file_a)
        session_b = load_session_json(file_b)

        if session_a and session_b:
            divider()
            
            # Stage Selection
            selected_stage = st.selectbox(
                "SELECT_STAGE_FOR_ANALYSIS",
                options=["ec", "ic"],
                format_func=lambda x: f"STAGE_{x.upper()}"
            )

            if st.button("RUN CALIBRATION ANALYSIS", type="primary", width="stretch"):
                engine = CalibrationEngine()
                
                # Perform Alignment and Calculation
                # Note: We pass the raw article lists from the session JSON
                results = engine.compute_kappa_between_sessions(
                    session_a["articles"], 
                    session_b["articles"], 
                    stage=selected_stage
                )

                if results["overlap_count"] == 0:
                    st.error("CRITICAL ERROR: No overlapping Article IDs found between sessions.")
                else:
                    # 2. Results Display
                    st.markdown("### 📊 RELIABILITY RESULTS")
                    
                    # Metrics Row
                    m1, m2, m3 = st.columns(3)
                    kappa = results["kappa"]
                    label, color = interpret_kappa(kappa)
                    
                    m1.metric("COHEN'S KAPPA", f"{kappa:.3f}")
                    m2.metric("OVERLAP", f"{results['overlap_count']} papers")
                    m3.markdown(f"""
                        <div style="padding:0.5rem; border:1px solid {color}; border-radius:4px; text-align:center;">
                            <div style="font-size:0.6rem; color:{COLORS['text_muted']};">INTERPRETATION</div>
                            <div style="font-size:0.9rem; color:{color}; font-weight:bold;">{label.upper()}</div>
                        </div>
                    """, unsafe_allow_html=True)

                    divider()

                    # 3. Confusion Matrix
                    st.markdown("#### CONFUSION MATRIX")
                    matrix_df = pd.DataFrame(
                        results["matrix"],
                        index=["A_EXCLUDE", "A_INCLUDE"],
                        columns=["B_EXCLUDE", "B_INCLUDE"]
                    )
                    st.table(matrix_df)

                    # 4. Disagreement Detail
                    if results["disagreements"]:
                        with st.expander("🔍 VIEW DISAGREEMENT LOG", expanded=False):
                            dis_df = pd.DataFrame(results["disagreements"])
                            st.dataframe(dis_df, width="stretch")
                            
                            # Export Disagreements
                            csv = dis_df.to_csv(index=False).encode('utf-8')
                            st.download_button(
                                "📥 DOWNLOAD DISAGREEMENT REPORT (CSV)",
                                data=csv,
                                file_name=f"APOLLO_IRR_Disagreements_{datetime.now().strftime('%Y%m%d')}.csv",
                                mime='text/csv'
                            )

    elif file_a or file_b:
        st.info("Waiting for second session file to perform cross-validation.")
    else:
        # Placeholder / Instructions
        st.markdown(f"""
        <div style="text-align:center; padding:5rem; color:{COLORS['text_muted']}; font-family:{TYPOGRAPHY['mono']}; font-size:0.8rem; border:1px dashed #333;">
            ( [!] IDLE_STATE: UPLOAD TWO SESSION FILES TO START )
        </div>
        """, unsafe_allow_html=True)

def render():
    """Wrapper for routing."""
    render_calibration_workspace()