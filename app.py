"""
APOLLO - Deterministic Screening Engine for Systematic Literature Reviews
Streamlit UI v1.0.0

A STAGE-DRIVEN Human-in-the-Loop screening tool.
Sequential EC → IC → QC with explicit researcher control.

Philosophy:
- Researcher controls each screening stage
- No automatic bulk processing
- LLM suggestions are lazy-loaded, on-demand, advisory-only
- Full audit trail with deterministic reproducibility
"""
import streamlit as st
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from dotenv import load_dotenv
load_dotenv()


st.set_page_config(
    page_title="APOLLO - Scientific Screening Assistant",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="A"
)


from src.ui.styles import get_custom_css as get_professional_styles
st.markdown(get_professional_styles(), unsafe_allow_html=True)


def main():
    """Main entry point for APOLLO Streamlit UI."""

    with st.sidebar:
        st.markdown("**APOLLO**")
        st.caption("Scientific Screening Assistant")
        st.divider()
        st.caption("Version: 1.0.0")
        st.divider()
        st.markdown("""
        **Workflow (Stage-Driven):**
        1. Configure Research Protocol
        2. Lock protocol
        3. EC Screening Workspace
        4. IC Screening Workspace
        5. QC Assessment Workspace
        6. Export & Audit

        **Key Principles:**
        - Researcher controls each stage
        - Sequential staged screening
        - EC → IC → QC funnel traceability
        - Human decisions are final
        - AI is advisory only
        - No bulk automatic processing
        """)
        st.divider()

        view = st.radio(
            "Navigation",
            options=[
                "Protocol Configuration",
                "EC Screening",
                "IC Screening",
                "QC Assessment",
                "Exports & Audit"
            ],
            index=0
        )

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
    else:
        from src.ui.modules.export_view import render_exports
        render_exports()


if __name__ == "__main__":
    main()