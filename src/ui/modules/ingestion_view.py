import streamlit as st
import pandas as pd
from pathlib import Path
import tempfile

from src.core.database import Database
from src.core.converter import convert_bibtex_to_df, convert_ris_to_df, convert_wos_txt_to_df


def get_database():
    """Returns a cached Database instance with current review_id."""
    review_id = st.session_state.get("review_id", 1)
    return Database(review_id=review_id)


def render_ingestion():
    """Data ingestion hub with WL and GL uploaders."""
    db = get_database()
    
    st.markdown("""
    **Getting Started:**
    1. Prepare your literature in CSV, BibTeX, RIS, or Excel format
    2. Upload files below to import
    """)
    
    with st.expander("Data Ingestion Hub", expanded=True):
        st.subheader("Upload Literature Files")
        
        col_src, col_file = st.columns([1, 2])
        with col_src:
            lit_type = st.radio("Literature Source Type", ["White Literature (WL)", "Grey Literature (GL)"], horizontal=True)
        with col_file:
            uploaded_files = st.file_uploader(
                "Upload files (any format: .bib, .ris, .csv, .xlsx, .txt, or no extension)",
                accept_multiple_files=True
            )
        
        if uploaded_files:
            st.caption(f"{len(uploaded_files)} file(s) selected")
            
            all_dfs = []
            for uploaded in uploaded_files:
                st.info(f"Processing: {uploaded.name}")
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded.name).suffix) as tmp:
                    tmp.write(uploaded.getvalue())
                    tmp_path = tmp.name
                
                suffix = Path(uploaded.name).suffix.lower()
                
                if not suffix or suffix not in [".bib", ".ris", ".xlsx", ".csv", ".txt"]:
                    suffix = ".bib"
                
                try:
                    if suffix == ".bib":
                        try:
                            df = convert_bibtex_to_df(tmp_path)
                        except Exception as bib_error:
                            st.warning(f"Not BibTeX format, skipping: {bib_error}")
                            df = pd.DataFrame()
                    elif suffix == ".ris":
                        df = convert_ris_to_df(tmp_path)
                    elif suffix == ".xlsx":
                        df = pd.read_excel(tmp_path)
                    elif suffix == ".csv":
                        df = pd.read_csv(tmp_path)
                    elif suffix == ".txt":
                        df = convert_wos_txt_to_df(tmp_path)
                    else:
                        df = pd.DataFrame()
                    
                    if not df.empty:
                        df["literature_type"] = "WL" if "WL" in lit_type else "GL"
                        all_dfs.append(df)
                        st.success(f"Converted: {len(df)} records")
                except Exception as conv_error:
                    st.error(f"Conversion failed: {conv_error}")
            
            if all_dfs:
                combined = pd.concat(all_dfs, ignore_index=True)
                
                if st.button(f"Import {len(combined)} Records", type="primary"):
                    imported = 0
                    review_id = st.session_state.get("review_id", 1)
                    for _, row in combined.iterrows():
                        try:
                            art_id = db.add_article(
                                {
                                    "title": row.get("title", "Untitled"),
                                    "abstract": row.get("abstract"),
                                    "doi": row.get("doi"),
                                    "url": row.get("url"),
                                    "source": row.get("source"),
                                    "literature_type": row.get("literature_type", "WL"),
                                    "authors": row.get("authors", ""),
                                    "year": row.get("year")
                                },
                                review_id
                            )
                            if art_id:
                                imported += 1
                        except:
                            pass
                    st.success(f"{imported} records added!")
                    st.rerun()
    
    st.subheader("Grey Literature Saturation")
    
    with st.expander("GL Saturation Check", expanded=False):
        gl_file = st.file_uploader("Upload GL file for saturation check", type=["tsv", "csv"])
        
        if gl_file and st.button("Run Saturation Check"):
            with st.spinner("Checking saturation..."):
                try:
                    if gl_file.name.endswith('.tsv'):
                        gl_df = pd.read_csv(gl_file, sep='\t')
                    else:
                        gl_df = pd.read_csv(gl_file)
                    
                    from src.core.saturation import check_gl_saturation
                    results = check_gl_saturation(gl_df, db)
                    
                    st.json(results)
                except Exception as e:
                    st.error(f"Error: {e}")