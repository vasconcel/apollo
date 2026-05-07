"""
APOLLO - Deterministic Screening Engine for Systematic Literature Reviews
Streamlit UI v1.0.0

A simple, local, deterministic EC/IC/QC screening tool.
No database, no authentication, no multi-user workflows.
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


# Import and apply professional dark styles
from src.ui.styles import get_custom_css as get_professional_styles
st.markdown(get_professional_styles(), unsafe_allow_html=True)


# Navigation for different views
def main():
    """Main entry point for APOLLO Streamlit UI."""
    
    with st.sidebar:
        st.markdown("**APOLLO**")
        st.caption("Scientific Screening Assistant")
        st.divider()
        st.caption("Version: 1.0.0")
        st.caption("Protocol: 1.0")
        st.divider()
        st.markdown("""
        **Workflow:**
        1. Human-in-the-loop screening
        2. EC → IC → QC stages
        3. Export with audit trail
        
        **Principles:**
        - Human decisions are final
        - AI is advisory only
        - Full audit trail preserved
        """)
        st.divider()
        
        # View selector
        view = st.radio(
            "Navigation",
            options=["Review Interface", "Upload & Process"]
        )
    
    # Route to appropriate view
    if view == "Review Interface":
        from src.ui.modules.review_view import render_review_interface
        render_review_interface()
    else:
        from src.ui.modules.atlas_processor_view import render_atlas_processor
        render_atlas_processor()


if __name__ == "__main__":
    main()