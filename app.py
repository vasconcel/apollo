"""
APOLLO - Deterministic Screening Engine for Systematic Literature Reviews
Streamlit UI v2.0.0 - Forensic Terminal Aesthetic

A STAGE-DRIVEN Human-in-the-Loop screening tool.
Sequential EC → IC → QC with explicit researcher control.

Philosophy:
- Researcher controls each screening stage
- No automatic bulk processing
- LLM suggestions are lazy-loaded, on-demand, advisory-only
- Full audit trail with deterministic reproducibility
- Forensic-grade research operations console aesthetic
"""
import streamlit as st
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from dotenv import load_dotenv
load_dotenv()


st.set_page_config(
    page_title="APOLLO - Audit Pipeline for Literature Operations",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="A"
)


from src.ui.styles import get_custom_css
from src.ui.theme import COLORS, TYPOGRAPHY
st.markdown(get_custom_css(), unsafe_allow_html=True)


def render_apollo_header():
    """Render APOLLO terminal-style header."""
    cursor_html = '<span style="animation:blink 1s infinite;color:#00c8d7;">▋</span>'
    
    st.markdown(f"""
    <div style="border-bottom:1px solid #00c8d7;padding:1rem 0;margin-bottom:1.5rem;">
        <div style="{TYPOGRAPHY['mono']};font-size:0.6rem;color:#009BA0;letter-spacing:0.25em;margin-bottom:0.5rem;">
            ▸ AUDIT PIPELINE FOR LITERATURE OPERATIONS & LAYERED OBSERVATION
        </div>
        <h1 style="{TYPOGRAPHY['mono']};font-size:1.75rem;color:#E5E5E5;margin:0;letter-spacing:0.15em;">
            APOLLO {cursor_html}
        </h1>
        <div style="{TYPOGRAPHY['mono']};font-size:0.7rem;color:#4A4A4A;margin-top:0.5rem;">
            Deterministic Screening Engine v2.0.0 // {datetime.now().strftime('%Y-%m-%d')}
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_sidebar():
    """Render terminal-style sidebar."""
    with st.sidebar:
        st.markdown(f"""
        <div style="{TYPOGRAPHY['mono']};font-size:0.65rem;color:#00c8d7;letter-spacing:0.15em;padding:0.5rem 0;border-bottom:1px solid #252525;margin-bottom:1rem;">
            ▸ NAVIGATION
        </div>
        """, unsafe_allow_html=True)
        
        view = st.radio(
            "MODULE",
            options=[
                "Protocol Configuration",
                "EC Screening",
                "IC Screening",
                "QC Assessment",
                "Inter-Rater Calibration",  # NEW ROUTE ADDED HERE
                "Exports & Audit"
            ],
            index=0,
            label_visibility="collapsed"
        )
        
        st.markdown(f"""
        <div style="{TYPOGRAPHY['mono']};font-size:0.6rem;color:#4A4A4A;letter-spacing:0.1em;padding:1rem 0;border-top:1px solid #1A1A1A;margin-top:1rem;">
            WORKFLOW STAGES
        </div>
        <div style="{TYPOGRAPHY['mono']};font-size:0.7rem;color:#808080;line-height:1.8;">
            <div style="color:#FF4757;">[EC] Exclusion Criteria</div>
            <div style="color:#FFB020;">[IC] Inclusion Criteria</div>
            <div style="color:#00D67E;">[QC] Quality Assessment</div>
            <div style="color:#9B59B6;">[IRR] Inter-Rater Reliability</div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
        <div style="{TYPOGRAPHY['mono']};font-size:0.6rem;color:#4A4A4A;letter-spacing:0.1em;padding:1rem 0;border-top:1px solid #1A1A1A;margin-top:1rem;">
            PRINCIPLES
        </div>
        <div style="{TYPOGRAPHY['mono']};font-size:0.65rem;color:#4A4A4A;line-height:1.8;">
            • Human decisions final<br>
            • Sequential staged funnel<br>
            • EC → IC → QC traceability<br>
            • Cross-validation mapping<br>
            • AI advisory only<br>
            • No bulk automation
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
        <div style="{TYPOGRAPHY['mono']};font-size:0.6rem;color:#4A4A4A;letter-spacing:0.1em;padding:1rem 0;border-top:1px solid #1A1A1A;margin-top:1rem;text-align:center;">
            <span style="color:#009BA0;">●</span> SYSTEM ONLINE
        </div>
        """, unsafe_allow_html=True)
    
    return view


def main():
    """Main entry point for APOLLO Streamlit UI."""
    
    render_apollo_header()
    view = render_sidebar()
    
    if view == "Protocol Configuration":
        from src.ui.modules.protocol_view import render_protocol_dashboard
        render_protocol_dashboard()
    elif view == "EC Screening":
        from src.ui.modules.ec_screening_view import render_ec_screening
        render_ec_screening()
    elif view == "IC Screening":
        from src.ui.modules.ic_screening_view import render_ic_screening
        render_ic_screening()
    elif view == "QC Assessment":
        from src.ui.modules.qc_assessment_view import render_qc_assessment
        render_qc_assessment()
    elif view == "Inter-Rater Calibration":
        # METHODOLOGICAL FIX: New Route for Cohen's Kappa integration
        from src.ui.modules.calibration_view import render_calibration_view
        render_calibration_view()
    else:
        from src.ui.modules.export_view import render_exports
        render_exports()


if __name__ == "__main__":
    main()