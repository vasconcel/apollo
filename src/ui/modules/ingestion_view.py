"""
APOLLO Data Ingestion - ATLAS Excel Input Only
Strictly accepts: ATLAS Excel file with WL sheet and GL sheet
"""
import streamlit as st
import pandas as pd
from pathlib import Path


def get_database():
    return Database(review_id=st.session_state.get("review_id", 1))


def render_ingestion():
    """ATLAS Excel Ingestion Hub - WL and GL sheets only."""
    from src.core.database import Database
    
    db = get_database()
    
    st.header("ATLAS Data Import")
    st.caption("Input: ATLAS Excel export with WL and GL sheets")
    
    st.info("""
    **Input Format**: ATLAS Excel file (.xlsx)
    - **WL sheet**: White Literature (academic publications)
    - **GL sheet**: Grey Literature (reports, white papers, etc.)
    
    No other formats are accepted.
    """)
    
    uploaded_file = st.file_uploader(
        "Upload ATLAS Excel File",
        type=["xlsx"],
        help="ATLAS export must contain 'WL' and 'GL' sheets"
    )
    
    if uploaded_file:
        try:
            wl_df = pd.read_excel(uploaded_file, sheet_name="WL")
            gl_df = pd.read_excel(uploaded_file, sheet_name="GL")
            
            st.success(f"Found sheets: WL ({len(wl_df)} records), GL ({len(gl_df)} records)")
            
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("White Literature Preview")
                st.dataframe(wl_df.head(5), use_container_width=True)
            with col2:
                st.subheader("Grey Literature Preview")
                st.dataframe(gl_df.head(5), use_container_width=True)
            
            st.divider()
            
            col_btn1, col_btn2 = st.columns(2)
            
            with col_btn1:
                wl_import = st.button(f"Import WL ({len(wl_df)} records)", type="primary")
            
            with col_btn2:
                gl_import = st.button(f"Import GL ({len(gl_df)} records)")
            
            imported_count = 0
            
            if wl_import:
                with st.spinner("Importing White Literature..."):
                    for _, row in wl_df.iterrows():
                        try:
                            db.add_article({
                                "title": str(row.get("title", "Untitled")),
                                "authors": str(row.get("authors", "")),
                                "year": row.get("year"),
                                "abstract": str(row.get("abstract", "")),
                                "doi": str(row.get("doi", "")),
                                "url": str(row.get("url", "")),
                                "source": str(row.get("source", "ATLAS-WL")),
                                "literature_type": "WL"
                            })
                            imported_count += 1
                        except Exception:
                            pass
                    st.success(f"Imported {imported_count} WL records")
                    st.rerun()
            
            if gl_import:
                with st.spinner("Importing Grey Literature..."):
                    for _, row in gl_df.iterrows():
                        try:
                            db.add_article({
                                "title": str(row.get("title", "Untitled")),
                                "authors": str(row.get("authors", "")),
                                "year": row.get("year"),
                                "abstract": str(row.get("abstract", "")),
                                "doi": str(row.get("doi", "")),
                                "url": str(row.get("url", "")),
                                "source": str(row.get("source", "ATLAS-GL")),
                                "literature_type": "GL"
                            })
                            imported_count += 1
                        except Exception:
                            pass
                    st.success(f"Imported {imported_count} GL records")
                    st.rerun()
                    
        except Exception as e:
            st.error(f"Error reading ATLAS Excel: {e}")
            st.warning("Ensure file contains 'WL' and 'GL' sheets")
    
    st.divider()
    st.subheader("Current Database Status")
    
    stats = db.get_stats()
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Articles", stats["total_articles"])
    with c2:
        wl_count = len([a for a in db.get_articles() if a.get("literature_type") == "WL"])
        st.metric("White Literature", wl_count)
    with c3:
        gl_count = len([a for a in db.get_articles() if a.get("literature_type") == "GL"])
        st.metric("Grey Literature", gl_count)
    with c4:
        st.metric("EC Passed", stats["ec_passed"])
    
    st.caption("Next: Proceed to Eligibility Evaluation (EC → IC)")