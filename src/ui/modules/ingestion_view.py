"""
APOLLO Data Ingestion - ATLAS Excel Input
Strictly accepts: ATLAS Excel file with WL and GL sheets.

V1.0.0 UPDATES:
- Migration from SQLite to Session-based architecture.
- Full integration with ATLASLoader for schema validation.
- Automatic session initialization after successful upload.
"""
import streamlit as st
import pandas as pd
import os
from datetime import datetime
from src.ui.theme import COLORS, TYPOGRAPHY
from src.ui.components import section_header, divider, terminal_header
from src.core.atlas_processor import ATLASLoader, create_screening_session

def render_ingestion():
    """ATLAS Excel Ingestion Hub - Forensic Console."""

    st.warning("DEPRECATED: This view is not routed by app.py. Canonical ingestion uses EC Screening view with ATLAS file upload. Will be removed in a future release.")

    terminal_header(
        "DATA INGESTION UNIT", 
        "Waiting for ATLAS v2.0 compatible source...",
        status="STANDBY"
    )

    st.markdown(f"""
    <div style="background:{COLORS['bg_card']}; padding:1.5rem; border:1px solid {COLORS['border_light']}; border-radius:4px; margin-bottom:2rem;">
        <div style="{TYPOGRAPHY['mono']}; font-size:0.7rem; color:{COLORS['cyan']}; margin-bottom:1rem;">▸ SYSTEM_REQUIREMENTS</div>
        <ul style="color:{COLORS['text_muted']}; font-family:{TYPOGRAPHY['mono']}; font-size:0.75rem; line-height:1.6;">
            <li>SOURCE_TYPE: Microsoft Excel (.xlsx)</li>
            <li>SHEET_ALPHA: "WL" or "White Literature" (Required)</li>
            <li>SHEET_BETA: "GL" or "Grey Literature" (Required)</li>
            <li>DEDUPLICATION: Pre-processed by ATLAS v2.0</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

    uploaded_file = st.file_uploader(
        "DROP_ATLAS_FILE_HERE",
        type=["xlsx"],
        label_visibility="collapsed"
    )

    if uploaded_file:
        # Salva temporariamente para validação
        temp_filename = "latest_ingestion.xlsx"
        with open(temp_filename, "wb") as f:
            f.write(uploaded_file.getbuffer())

        try:
            # Validação via Core Engine
            wl_df, gl_df = ATLASLoader.load_atlas_file(temp_filename)
            
            st.success(f"✓ SOURCE VERIFIED: {len(wl_df)} WL papers | {len(gl_df)} GL records identified.")
            
            # Painel de Preview
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"<div style='{TYPOGRAPHY['mono']}; font-size:0.6rem; color:{COLORS['text_muted']}'>PREVIEW_WL</div>", unsafe_allow_html=True)
                st.dataframe(wl_df[['Title', 'Authors']].head(3), use_container_width=True)
            with col2:
                st.markdown(f"<div style='{TYPOGRAPHY['mono']}; font-size:0.6rem; color:{COLORS['text_muted']}'>PREVIEW_GL</div>", unsafe_allow_html=True)
                st.dataframe(gl_df[['Title', 'URL']].head(3), use_container_width=True)

            divider()

            # Configurações de Início de Sessão
            st.markdown(f"### ⚙️ INITIALIZE SCREENING SESSION")
            
            c1, c2 = st.columns(2)
            with c1:
                researcher_name = st.text_input("RESEARCHER_ID", value="researcher_1")
                protocol_ver = st.selectbox("PROTOCOL_VERSION", ["1.0 (Default)", "1.1 (Draft)"])
            
            with c2:
                start_stage = st.selectbox(
                    "INITIAL_STAGE", 
                    options=["ec", "ic", "qc"],
                    format_func=lambda x: f"STAGE_{x.upper()}"
                )

            if st.button("🚀 INITIALIZE APOLLO PIPELINE", type="primary", use_container_width=True):
                with st.spinner("Initializing deterministic engine..."):
                    # Aqui chamamos o factory do core que unifica tudo
                    session, rev_state, _, _ = create_screening_session(
                        input_path=temp_filename,
                        researcher_id=researcher_name,
                    )
                    
                    # Sobrescreve o estágio se o usuário escolheu um diferente do default
                    session.stage = start_stage
                    rev_state.stage = start_stage
                    
                    # Salva no st.session_state (Memória) e persiste JSON (Audit)
                    st.session_state.session = session
                    st.session_state.reviewer_state = rev_state
                    session.save("sessions")
                    
                    st.toast("Pipeline Initialized Successfully!", icon="🚀")
                    st.rerun()

        except Exception as e:
            st.error(f"FATAL_ERROR: {str(e)}")
            st.warning("Ensure the Excel file follows the ATLAS v2.0 export schema.")

    # Se já houver uma sessão ativa, mostra o status atual
    if "session" in st.session_state and st.session_state.session:
        divider()
        st.markdown(f"<div style='{TYPOGRAPHY['mono']}; font-size: 0.65rem; color:{COLORS['success']}'>● ACTIVE_SESSION_DETECTED</div>", unsafe_allow_html=True)
        session = st.session_state.session
        st.info(f"Sessão ID: {session.session_id[:16]}... | Stage atual: {session.stage.upper()}")
        if st.button("CONTINUE TO REVIEW"):
            # O roteamento no app.py lidará com a mudança de view, 
            # mas aqui podemos forçar um estado se necessário.
            st.switch_page("app.py") # Ou apenas rerun dependendo da lógica do app.py

def render():
    """Wrapper for routing."""
    render_ingestion()