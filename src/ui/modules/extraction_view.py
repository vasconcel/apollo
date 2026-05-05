import streamlit as st
import sqlite3
import pandas as pd
import tempfile

from src.core.database import Database, DatabaseError
from src.core.workflow import ReviewStage


def get_database():
    review_id = st.session_state.get("review_id", 1)
    return Database(review_id=review_id)


def require_stage(required_stage: ReviewStage) -> bool:
    db = get_database()
    current = ReviewStage(db.get_current_stage())
    if current != required_stage:
        st.error(f"[LOCKED] This section requires '{required_stage.value}' stage")
        st.info(f"Workflow: {db.get_stage_prompt()}")
        return False
    return True


def render_extraction():
    st.header(" Evidence Extraction")
    st.caption("Extract fragments from quality-assessed articles")
    
    db = get_database()
    
    if not require_stage(ReviewStage.EXTRACTION):
        return
    
    ready_articles = db.get_included_articles_for_extraction()
    
    if not ready_articles:
        st.warning("No articles ready for extraction. Complete screening and quality assessment first.")
        return
    
    st.markdown("### 📄 Ready for Extraction")
    
    st.markdown('<div class="ais-card">', unsafe_allow_html=True)
    articles_data = []
    for art in ready_articles:
        articles_data.append({
            "ID": art[0],
            "Title": art[1][:70] + ("..." if len(art[1]) > 70 else ""),
            "Type": art[3]
        })
    
    df_articles = pd.DataFrame(articles_data)
    st.dataframe(df_articles, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.divider()
    
    st.markdown("### 📥 Extract Evidence")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        selected_article_id = st.selectbox(
            "Select Article",
            [a[0] for a in ready_articles],
            format_func=lambda x: next((a[1] for a in ready_articles if a[0] == x), str(x))
        )
    
    existing_fragments = db.get_fragments_by_article(selected_article_id)
    
    with col2:
        st.metric("Extracted", f"{len(existing_fragments)} fragments")
    
    if selected_article_id:
        article_title = next((a[1] for a in ready_articles if a[0] == selected_article_id), "")
        
        st.markdown('<div class="ais-card">', unsafe_allow_html=True)
        st.markdown(f"**Selected:** {article_title}")
        
        conn = sqlite3.connect(db.db_path)
        article_abstract = pd.read_sql_query(f"SELECT abstract FROM articles WHERE id = {selected_article_id}", conn).iloc[0]['abstract']
        conn.close()
        
        if article_abstract:
            with st.expander("📝 Abstract", expanded=False):
                st.write(article_abstract[:500] + "..." if len(str(article_abstract)) > 500 else article_abstract)
        
        with st.form("extraction_form"):
            rq_code = st.selectbox("Research Question", ["RQ1", "RQ2", "RQ3", "RQ4", "RQ5"])
            theme_category = st.selectbox("Theme Category", ["challenge", "practice", "context", "finding", "gap", "other"])
            fragment_text = st.text_area("Evidence Fragment", height=100, placeholder="Paste or type the extracted evidence...")
            page_or_section = st.text_input("Page/Section Reference", placeholder="e.g., 4.2, Introduction")
            
            if st.form_submit_button("➕ Add Fragment", type="primary"):
                if not fragment_text.strip():
                    st.error("Fragment text cannot be empty")
                else:
                    try:
                        frag_id = db.insert_fragment(
                            article_id=selected_article_id,
                            rq_code=rq_code,
                            fragment_text=fragment_text,
                            reviewer_id=st.session_state.get("reviewer_id", "Reviewer_1"),
                            theme_category=theme_category,
                            page_or_section=page_or_section
                        )
                        st.success(f"Fragment added (ID: {frag_id})")
                        st.rerun()
                    except DatabaseError as e:
                        st.error(str(e))
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.divider()
        
        st.markdown("### Extracted Fragments")
        
        if existing_fragments:
            for frag in existing_fragments:
                with st.expander(f"RQ{frag[2]} - {frag[4] or 'No category'}"):
                    st.write(frag[3])
                    st.caption(f"Page: {frag[6] or 'N/A'} | Reviewer: {frag[5]}")
        else:
            st.info("No fragments extracted yet")
        
        st.divider()
        with st.expander("🤖 AI Document Analysis", expanded=False):
            st.caption("Upload a PDF to auto-extract evidence using AI")
            
            uploaded_pdf = st.file_uploader("Upload Article PDF", type=["pdf"], key="extraction_pdf")
            
            if uploaded_pdf:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(uploaded_pdf.getvalue())
                    pdf_path = tmp.name
                
                try:
                    from src.core.pdf_processor import extract_text_from_pdf
                    
                    with st.spinner("Extracting text from PDF..."):
                        pdf_result = extract_text_from_pdf(pdf_path, max_pages=30)
                    
                    if pdf_result.get("error"):
                        st.error(f"PDF Error: {pdf_result['error']}")
                    else:
                        pdf_text = pdf_result["text"]
                        st.success(f"Extracted {len(pdf_text)} characters from {pdf_result['page_count']} pages")
                        
                        if st.button("🤖 AI Auto-Extract Evidence", width=True, key="ai_extract_btn"):
                            with st.spinner("AI analyzing document..."):
                                try:
                                    from groq import Groq
                                    import os
                                    import json
                                    
                                    api_key = os.environ.get("GROQ_API_KEY")
                                    if not api_key:
                                        st.warning("Configure GROQ_API_KEY in environment for AI extraction")
                                    else:
                                        client = Groq(api_key=api_key)
                                        
                                        settings = db.get_settings()
                                        extraction_fields = settings.get("extraction_fields", [])
                                        fields_text = "\n".join([f"- {f}" for f in extraction_fields]) if extraction_fields else "RQ Code, Theme Category, Evidence Fragment, Page/Section"
                                        
                                        prompt = f"""Extract evidence from this research paper. Return JSON with these fields:
{fields_text}

If a field cannot be found, use empty string.

Paper text (first 4000 chars):
{pdf_text[:4000]}"""
                                        
                                        response = client.chat.completions.create(
                                            model="llama3-70b-8192",
                                            messages=[{"role": "user", "content": prompt}],
                                            temperature=0.1,
                                            max_tokens=2000
                                        )
                                        
                                        ai_response = response.choices[0].message.content
                                        
                                        try:
                                            extracted = json.loads(ai_response)
                                            st.json(extracted)
                                            st.success("AI extraction complete! Review and edit.")
                                        except json.JSONDecodeError:
                                            st.warning("Could not parse AI response as JSON")
                                            st.text(ai_response[:500])
                                except Exception as e:
                                    st.error(f"AI extraction error: {e}")
                finally:
                    import os
                    if os.path.exists(pdf_path):
                        os.remove(pdf_path)