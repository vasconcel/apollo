"""
APOLLO - Deterministic Screening Engine for Systematic Literature Reviews
Streamlit UI v2.0.0 - Primal (EC/IC only)

A STAGE-DRIVEN Human-in-the-Loop screening tool.
Sequential EC → IC with explicit researcher control.

Philosophy:
- Researcher controls each screening stage
- No automatic bulk processing
- LLM suggestions are lazy-loaded, on-demand, advisory-only
- Full audit trail with deterministic reproducibility
- Forensic-grade research operations console aesthetic
"""
import streamlit as st
import logging
import os
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
    """Render APOLLO clean research platform header - compact."""
    st.markdown(f"""
    <div style="padding:0.5rem 0 1rem 0;margin-bottom:1rem;border-bottom:1px solid {COLORS['border_light']};">
        <div style="font-family:{TYPOGRAPHY['sans']};font-size:0.65rem;color:{COLORS['cyan_dim']};letter-spacing:0.15em;margin-bottom:0.25rem;">
            Systematic Literature Review Platform
        </div>
        <h1 style="font-family:{TYPOGRAPHY['sans']};font-size:1.25rem;color:{COLORS['text_primary']};margin:0;font-weight:600;letter-spacing:0.05em;">
            APOLLO
        </h1>
        <div style="font-family:{TYPOGRAPHY['sans']};font-size:0.7rem;color:{COLORS['text_muted']};margin-top:0.25rem;">
            Version 2.0.0
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_sidebar():
    """Render clean sidebar navigation."""
    from src.ui.theme import COLORS, TYPOGRAPHY

    with st.sidebar:
        st.markdown(f"""
        <div style="font-family:{TYPOGRAPHY['sans']};font-size:0.7rem;color:{COLORS['text_muted']};padding:0.5rem 0;border-bottom:1px solid {COLORS['border']};margin-bottom:0.75rem;letter-spacing:0.1em;text-transform:uppercase;">
            NAVIGATION
        </div>
        """, unsafe_allow_html=True)
        
        view = st.radio(
            "MODULE",
            options=[
                "Protocol Configuration",
                "EC Screening",
                "IC Screening",
                "Inter-Rater Calibration",
                "Exports & Audit"
            ],
            index=0,
            label_visibility="collapsed"
        )
        
        session = st.session_state.get("apollo_session")
        protocol = st.session_state.get("research_protocol")
        
        st.markdown(f"""
        <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.55rem;color:{COLORS['text_muted']};letter-spacing:0.1em;padding:0.75rem 0 0.5rem 0;border-bottom:1px solid {COLORS['border_light']};margin-top:0.75rem;">
            ACTIVE PROTOCOL
        </div>
        """, unsafe_allow_html=True)

        if protocol:
            summary = protocol.get_summary()
            protocol_hash = summary.get('hash', 'N/A')[:12] if summary.get('hash') else 'N/A'
            active_stage = "EC" if view in ["EC Screening", "Protocol Configuration"] else "IC" if view == "IC Screening" else "—"

            total_articles = len(session.articles) if session and session.articles else 0
            screened = session.ec_completed if session else 0

            st.markdown(f'''
            <div style="border:1px solid {COLORS['border_light']};background:{COLORS['bg_card']};padding:0.5rem;border-radius:6px;margin-bottom:0.5rem;">
                <div style="display:flex;justify-content:space-between;margin-bottom:0.35rem;">
                    <span style="font-family:{TYPOGRAPHY['mono']};font-size:0.55rem;color:{COLORS['text_muted']};">HASH</span>
                    <span style="font-family:{TYPOGRAPHY['mono']};font-size:0.6rem;color:{COLORS['cyan']};">{protocol_hash}</span>
                </div>
                <div style="display:flex;justify-content:space-between;margin-bottom:0.35rem;">
                    <span style="font-family:{TYPOGRAPHY['mono']};font-size:0.55rem;color:{COLORS['text_muted']};">STAGE</span>
                    <span style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['warning']};font-weight:600;">{active_stage}</span>
                </div>
                <div style="display:flex;justify-content:space-between;">
                    <span style="font-family:{TYPOGRAPHY['mono']};font-size:0.55rem;color:{COLORS['text_muted']};">PROGRESS</span>
                    <span style="font-family:{TYPOGRAPHY['mono']};font-size:0.6rem;color:{COLORS['text_secondary']};">{screened}/{total_articles}</span>
                </div>
            </div>
            ''', unsafe_allow_html=True)
        else:
            st.markdown(f'''
            <div style="border:1px solid {COLORS['border_light']};background:{COLORS['bg_card']};padding:0.5rem;border-radius:6px;text-align:center;">
                <span style="font-family:{TYPOGRAPHY['mono']};font-size:0.55rem;color:{COLORS['text_muted']};">No protocol loaded</span>
            </div>
            ''', unsafe_allow_html=True)
        
        if session and session.articles:
            wl_count = len(session.get_wl_articles())
            gl_count = len(session.get_gl_articles())

            st.markdown(f'''
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:0.5rem;">
                <div style="border:1px solid {COLORS['border_light']};background:{COLORS['bg_card']};padding:0.35rem;border-radius:6px;text-align:center;">
                    <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.5rem;color:{COLORS['text_muted']};">WL</div>
                    <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.75rem;color:{COLORS['success']};">{wl_count}</div>
                </div>
                <div style="border:1px solid {COLORS['border_light']};background:{COLORS['bg_card']};padding:0.35rem;border-radius:6px;text-align:center;">
                    <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.5rem;color:{COLORS['text_muted']};">GL</div>
                    <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.75rem;color:{COLORS['warning']};">{gl_count}</div>
                </div>
            </div>
            ''', unsafe_allow_html=True)

        st.markdown(f"""
        <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.55rem;color:{COLORS['text_muted']};letter-spacing:0.1em;padding:0.75rem 0 0.5rem 0;border-bottom:1px solid {COLORS['border_light']};margin-top:0.75rem;">
            WORKFLOW
        </div>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f'<span style="font-family:{TYPOGRAPHY["mono"]};font-size:0.6rem;color:#FF4757;">[EC]</span>', unsafe_allow_html=True)
        with col2:
            st.markdown(f'<span style="font-family:{TYPOGRAPHY["mono"]};font-size:0.6rem;color:#FFB020;">[IC]</span>', unsafe_allow_html=True)

        st.markdown(f'''
        <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.55rem;color:{COLORS['text_muted']};margin-top:0.75rem;">
            <span style="color:{COLORS['success']};">●</span> System Online
        </div>
        ''', unsafe_allow_html=True)
    
    return view


def export_session_excel(session):
    """Export session to Excel from sidebar (Researcher 1 Package)."""
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
                os.path.join(tmpdir, "session_export.xlsx"),
                ec_criteria_descriptions=ic_criteria,
                ic_criteria_descriptions=ec_criteria
            )
            
            with open(excel_path, "rb") as f:
                excel_data = f.read()
            
            st.sidebar.download_button(
                "Download R1 Package (XLSX)",
                data=excel_data,
                file_name="apollo_researcher1_package.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_excel_from_sidebar"
            )
            st.sidebar.success("Export ready")
    except Exception as e:
        st.sidebar.error(f"Export failed: {e}")


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
    elif view == "Inter-Rater Calibration":
        from src.ui.modules.calibration_view import render_calibration_workspace
        render_calibration_workspace()
    else:
        from src.ui.modules.export_view import render_exports
        render_exports()


if __name__ == "__main__":
    main()