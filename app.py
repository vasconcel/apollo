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
    """Render terminal-style sidebar - Telemetria Forense hierarchy."""
    from src.ui.theme import COLORS, TYPOGRAPHY
    
    st.markdown("""
    <style>
    div[data-testid="stRadio"] > div {
        gap: 0.25rem;
    }
    div[data-testid="stRadio"] > div > label {
        background: #0D0D0D;
        border: 1px solid #252525;
        padding: 0.75rem 1rem;
        margin: 0;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.75rem;
        color: #808080;
        transition: all 0.2s;
    }
    div[data-testid="stRadio"] > div > label:hover {
        background: #111111;
        border-color: #00c8d7;
        color: #E5E5E5;
    }
    div[data-testid="stRadio"] > div > label[data-checked="true"] {
        background: #00c8d7;
        border-color: #00c8d7;
        color: #000;
        font-weight: 600;
    }
    </style>
    """, unsafe_allow_html=True)
    
    with st.sidebar:
        st.markdown(f"""
        <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['cyan']};letter-spacing:0.15em;padding:0.5rem 0;border-bottom:1px solid {COLORS['border_light']};margin-bottom:0.75rem;">
            ▸ NAVIGATION
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
        <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.6rem;color:{COLORS['text_muted']};letter-spacing:0.1em;padding:1rem 0 0.5rem 0;border-bottom:1px solid {COLORS['border_light']};margin-top:1rem;">
            ▸ ACTIVE PROTOCOL
        </div>
        """, unsafe_allow_html=True)
        
        if protocol:
            summary = protocol.get_summary()
            protocol_hash = summary.get('hash', 'N/A')[:12] if summary.get('hash') else 'N/A'
            active_stage = "EC" if view in ["EC Screening", "Protocol Configuration"] else "IC" if view == "IC Screening" else "—"
            
            total_articles = len(session.articles) if session and session.articles else 0
            screened = session.ec_completed if session else 0
            
            st.markdown(f'''
            <div style="border:1px solid {COLORS['border_light']};background:{COLORS['bg_card']};padding:0.75rem;margin-bottom:0.5rem;">
                <div style="display:flex;justify-content:space-between;margin-bottom:0.5rem;">
                    <span style="font-family:{TYPOGRAPHY['mono']};font-size:0.6rem;color:{COLORS['text_muted']};">HASH</span>
                    <span style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['cyan']};">{protocol_hash}</span>
                </div>
                <div style="display:flex;justify-content:space-between;margin-bottom:0.5rem;">
                    <span style="font-family:{TYPOGRAPHY['mono']};font-size:0.6rem;color:{COLORS['text_muted']};">STAGE</span>
                    <span style="font-family:{TYPOGRAPHY['mono']};font-size:0.7rem;color:{COLORS['warning']};font-weight:600;">{active_stage}</span>
                </div>
                <div style="display:flex;justify-content:space-between;">
                    <span style="font-family:{TYPOGRAPHY['mono']};font-size:0.6rem;color:{COLORS['text_muted']};">PROGRESS</span>
                    <span style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['text_secondary']};">{screened}/{total_articles}</span>
                </div>
            </div>
            ''', unsafe_allow_html=True)
        else:
            st.markdown(f'''
            <div style="border:1px solid {COLORS['border_light']};background:{COLORS['bg_card']};padding:0.75rem;text-align:center;">
                <span style="font-family:{TYPOGRAPHY['mono']};font-size:0.6rem;color:{COLORS['text_muted']};">No protocol loaded</span>
            </div>
            ''', unsafe_allow_html=True)
        
        if session and session.articles:
            wl_count = len(session.get_wl_articles())
            gl_count = len(session.get_gl_articles())
            
            st.markdown(f'''
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem;margin-top:0.5rem;">
                <div style="border:1px solid {COLORS['border_light']};background:{COLORS['bg_card']};padding:0.5rem;text-align:center;">
                    <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.55rem;color:{COLORS['text_muted']};">WL</div>
                    <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.8rem;color:{COLORS['success']};">{wl_count}</div>
                </div>
                <div style="border:1px solid {COLORS['border_light']};background:{COLORS['bg_card']};padding:0.5rem;text-align:center;">
                    <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.55rem;color:{COLORS['text_muted']};">GL</div>
                    <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.8rem;color:{COLORS['warning']};">{gl_count}</div>
                </div>
            </div>
            ''', unsafe_allow_html=True)
        
        st.markdown(f"""
        <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.6rem;color:{COLORS['text_muted']};letter-spacing:0.1em;padding:1rem 0 0.5rem 0;border-bottom:1px solid {COLORS['border_light']};margin-top:1rem;">
            ▸ WORKFLOW
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f'<span style="font-family:{TYPOGRAPHY["mono"]};font-size:0.65rem;color:#FF4757;">[EC]</span>', unsafe_allow_html=True)
        with col2:
            st.markdown(f'<span style="font-family:{TYPOGRAPHY["mono"]};font-size:0.65rem;color:#FFB020;">[IC]</span>', unsafe_allow_html=True)
        
        st.markdown(f'''
        <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.6rem;color:{COLORS['text_muted']};margin-top:1rem;">
            <span style="color:{COLORS['success']};">●</span> SYSTEM ONLINE
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