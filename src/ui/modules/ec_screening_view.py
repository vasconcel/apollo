"""
APOLLO EC Screening Workspace

Stage-specific workspace for Exclusion Criteria screening.
ONLY EC criteria are visible/applicable in this workspace.

Researcher screens papers manually with optional AI advisory.
No IC or QC execution occurs here.

HUMAN-IN-THE-LOOP PRINCIPLE:
- Researcher makes final screening decisions
- AI suggestions are ADVISORY ONLY
- No automatic LLM processing
- LLM calls only on explicit researcher request
"""
import streamlit as st
from typing import Dict, Optional


def render_ec_screening():
    """Render EC Screening Workspace."""
    from src.core.dynamic_protocol import ProtocolState

    st.markdown("# EC Screening Workspace")
    st.markdown("*Apply Exclusion Criteria to remove irrelevant studies*")
    st.divider()

    if "research_protocol" not in st.session_state or st.session_state.research_protocol is None:
        st.warning("⚠️ No Research Protocol configured. Please go to 'Protocol Configuration' first.")
        return

    protocol = st.session_state.research_protocol

    if protocol.state == ProtocolState.DRAFT.value:
        st.warning("⚠️ Protocol must be locked before screening. Go to 'Protocol Configuration' to lock your protocol.")
        return

    render_protocol_info_banner(protocol)
    st.divider()

    if "ec_session" not in st.session_state:
        st.session_state.ec_session = {
            "articles": [],
            "current_index": 0,
            "decisions": {},
            "loaded": False
        }

    if not st.session_state.ec_session["loaded"]:
        render_upload_section()
    else:
        render_screening_workspace()


def render_protocol_info_banner(protocol):
    """Show protocol info in banner."""
    summary = protocol.get_summary()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Protocol", f"v{summary['version']}")
    with col2:
        st.metric("EC Criteria", summary['ec_count'])
    with col3:
        st.metric("EC Enabled", summary['ec_enabled'])
    with col4:
        st.caption(f"Hash: `{summary['hash']}`")


def render_upload_section():
    """Render upload section for EC screening."""
    st.markdown("### Upload Papers for EC Screening")
    st.info("""
    **Upload your INITIAL SEARCH results** (ATLAS export with WL and GL sheets).

    Papers will be reviewed one at a time. You can:
    - Include or Exclude each paper
    - Request AI advisory for individual papers
    - Navigate with Next/Previous buttons

    Only EC criteria will be applied in this workspace.
    """)

    uploaded_file = st.file_uploader(
        "Upload ATLAS Excel File",
        type=["xlsx"],
        help="Upload your ATLAS export with WL and GL sheets"
    )

    if uploaded_file:
        with st.spinner("Loading papers..."):
            articles = load_atlas_papers(uploaded_file)
            if articles:
                st.session_state.ec_session["articles"] = articles
                st.session_state.ec_session["current_index"] = 0
                st.session_state.ec_session["decisions"] = {}
                st.session_state.ec_session["loaded"] = True
                st.success(f"✅ Loaded {len(articles)} papers. Ready for EC screening.")
                st.rerun()
            else:
                st.error("Failed to load papers from file.")


def load_atlas_papers(uploaded_file) -> list:
    """Load papers from ATLAS Excel file using centralized normalization."""
    import pandas as pd
    from src.core.article_metadata import (
        normalize_wl_metadata, normalize_gl_metadata, article_to_dict
    )

    import tempfile
    temp_path = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False).name

    with open(temp_path, "wb") as f:
        f.write(uploaded_file.getvalue())

    try:
        wl_df = pd.read_excel(temp_path, sheet_name="White Literature")
        gl_df = pd.read_excel(temp_path, sheet_name="Grey Literature")

        articles = []
        for _, row in wl_df.iterrows():
            row_dict = row.to_dict()
            article = normalize_wl_metadata(row_dict)
            article_dict = article_to_dict(article)
            article_dict["ec_decision"] = ""
            article_dict["ec_notes"] = ""
            articles.append(article_dict)

        for _, row in gl_df.iterrows():
            row_dict = row.to_dict()
            article = normalize_gl_metadata(row_dict)
            article_dict = article_to_dict(article)
            article_dict["ec_decision"] = ""
            article_dict["ec_notes"] = ""
            articles.append(article_dict)

        return articles
    except Exception as e:
        st.error(f"Error loading file: {e}")
        return []
    finally:
        import os
        os.unlink(temp_path)


def render_screening_workspace():
    """Render the main EC screening workspace."""
    session = st.session_state.ec_session
    articles = session["articles"]
    current_idx = session["current_index"]
    decisions = session["decisions"]

    total = len(articles)
    reviewed = sum(1 for d in decisions.values() if d.get("decision"))
    pending = total - reviewed

    col_nav, col_stats, col_nav2 = st.columns([1, 2, 1])
    with col_nav:
        if st.button("⬅️ Previous", disabled=current_idx == 0):
            session["current_index"] = max(0, current_idx - 1)
            st.rerun()
    with col_stats:
        st.markdown(f"**Progress:** {reviewed}/{total} reviewed | {pending} pending")
        progress = reviewed / total if total > 0 else 0
        st.progress(progress)
    with col_nav2:
        if st.button("Next ➡️", disabled=current_idx >= total - 1):
            session["current_index"] = min(total - 1, current_idx + 1)
            st.rerun()

    st.divider()

    if articles and 0 <= current_idx < total:
        article = articles[current_idx]
        render_article_card(article, current_idx, decisions)

        render_ai_advisory_panel(article, current_idx, decisions)

        st.divider()

        col_excl, col_incl, col_skip = st.columns([1, 1, 1])
        current_decision = decisions.get(current_idx, {}).get("decision", "")

        with col_excl:
            excl_clicked = st.button("🚫 Exclude", type="secondary", use_container_width=True,
                                   disabled=current_decision == "exclude")
            if excl_clicked:
                decisions[current_idx] = {"decision": "exclude", "notes": ""}
                st.rerun()

        with col_incl:
            incl_clicked = st.button("✅ Include", type="primary", use_container_width=True,
                                    disabled=current_decision == "include")
            if incl_clicked:
                decisions[current_idx] = {"decision": "include", "notes": ""}
                st.rerun()

        with col_skip:
            skip_clicked = st.button("⏭️ Skip", use_container_width=True,
                                    disabled=current_decision == "skip")
            if skip_clicked:
                decisions[current_idx] = {"decision": "skip", "notes": ""}
                st.rerun()

        if current_decision:
            st.success(f"Current decision: **{current_decision.upper()}**")
            if st.button("🔄 Clear Decision"):
                if current_idx in decisions:
                    del decisions[current_idx]
                st.rerun()

    st.divider()

    if st.button("📊 Export EC Results", type="primary"):
        export_ec_results(session)


def render_article_card(article: Dict, index: int, decisions: Dict):
    """Render full paper review card optimized for screening readability."""
    lit_type = article.get("literature_type", "WL")
    has_title = article.get("title") and article.get("title") != "nan"
    has_abstract = article.get("abstract") and article.get("abstract") != "nan"

    st.markdown("---")
    col_badge, col_progress = st.columns([1, 4])
    with col_badge:
        badge = "WL" if lit_type == "WL" else "GL"
        color = "#238636" if lit_type == "WL" else "#f0883e"
        st.markdown(f"<span style='background:{color};color:white;padding:4px 12px;border-radius:6px;font-size:14px;font-weight:bold'>{badge}</span>",
                   unsafe_allow_html=True)
    with col_progress:
        st.caption(f"Paper {index + 1}")

    if not has_title:
        st.warning("⚠️ Title is missing from this record")
    else:
        st.markdown(f"### {article['title']}")

    col_meta1, col_meta2 = st.columns(2)
    with col_meta1:
        authors = article.get("authors", "")
        if authors and authors != "nan":
            st.markdown(f"**Authors:** {authors}")
        else:
            st.markdown("**Authors:** _[NOT AVAILABLE]_")

        year = article.get("year", "")
        if year and year != "nan":
            st.markdown(f"**Year:** {year}")
    with col_meta2:
        source = article.get("source", "")
        if source and source != "nan":
            st.markdown(f"**Source:** {source}")
        else:
            st.markdown("**Source:** _[NOT AVAILABLE]_")

        doi = article.get("doi", "")
        if doi and doi != "nan":
            st.markdown(f"**DOI:** {doi}")
        else:
            url = article.get("url", "")
            if url and url != "nan":
                st.markdown(f"**URL:** [{url[:50]}...]({url})")

    st.divider()

    if not has_abstract:
        st.info("**Abstract:** _[NOT AVAILABLE]_ — Manual review required")
    else:
        with st.expander("📄 Abstract (click to expand)"):
            st.markdown(article.get("abstract", ""))

    keywords = article.get("keywords", "")
    if keywords and keywords != "nan" and len(keywords.strip()) > 0:
        st.markdown(f"**Keywords:** {keywords}")

    completeness = article.get("completeness", "unknown")
    if completeness == "minimal":
        st.warning("⚠️ Limited metadata — review with caution")
    elif completeness == "partial":
        st.info("ℹ️ Partial metadata available")

    with st.expander("🔧 Debug Metadata"):
        st.json(article.get("raw_data", {}))


def render_ai_advisory_panel(article: Dict, current_idx: int, decisions: Dict):
    """Render AI Advisory Panel - OPTIONAL cognitive support for researcher."""
    st.divider()
    st.markdown("### AI Advisory Panel")

    cache_key = f"ec_advice_{current_idx}"
    cached_advice = st.session_state.get(cache_key, None)

    with st.expander("🤖 Request AI Suggestion (Optional)"):
        st.info("""
        **Human-in-the-Loop Review**

        AI suggestions are **ADVISORY ONLY**.
        You are the screener — AI is a cognitive support tool.
        Final decision is always yours.
        """)

        col_btn, col_status = st.columns([1, 2])
        with col_btn:
            request_suggestion = st.button(
                "🔮 Generate AI Suggestion",
                use_container_width=True,
                help="Request AI advisory for this article. Only triggers when you click."
            )
        with col_status:
            if cached_advice:
                st.success("✓ AI suggestion available for this article")
            else:
                st.caption("No suggestion generated yet for this article")

        if request_suggestion:
            with st.spinner("Generating AI suggestion..."):
                suggestion = get_llm_ec_suggestion(article)

                if suggestion:
                    st.session_state[cache_key] = suggestion
                    cached_advice = suggestion
                    st.rerun()
                else:
                    st.warning("LLM unavailable — continue with manual review.")

        if cached_advice:
            st.divider()
            render_suggestion_details(cached_advice)


def get_llm_ec_suggestion(article: Dict) -> Optional[Dict]:
    """Get LLM advisory suggestion for EC screening with metadata robustness."""
    try:
        from src.core.llm_assistant import LLMAssistant

        llm = LLMAssistant()
        if not llm.is_available():
            return None

        title = article.get("title", "")
        abstract = article.get("abstract", "")
        literature_type = article.get("literature_type", "WL")
        year = article.get("year")

        has_title = bool(title and title != "nan" and len(title.strip()) > 0)
        has_abstract = bool(abstract and abstract != "nan" and len(abstract.strip()) > 10)

        if not has_title or not has_abstract:
            return {
                "stage": "ec",
                "decision": "uncertain",
                "confidence": 0.3,
                "justification": "Insufficient metadata: " +
                    ("title " if not has_title else "") +
                    ("abstract " if not has_abstract else "") +
                    "not available for reliable evaluation.",
                "triggered_criteria": {},
                "evidence": [],
                "ambiguity_flags": [
                    "Title missing" if not has_title else "",
                    "Abstract missing" if not has_abstract else "",
                    "Reduce confidence — manual review recommended"
                ]
            }

        protocol_criteria = get_protocol_ec_criteria()

        suggestion = llm.suggest_ec(
            title=title,
            abstract=abstract,
            literature_type=literature_type,
            protocol_criteria=protocol_criteria
        )

        return suggestion.to_dict()
    except Exception:
        return None


def get_protocol_ec_criteria() -> Dict[str, str]:
    """Get EC criteria from current protocol."""
    if "research_protocol" in st.session_state and st.session_state.research_protocol:
        protocol = st.session_state.research_protocol
        return {
            k: v.description
            for k, v in protocol.ec.criteria.items()
            if v.enabled
        }
    return {
        "EC1": "Not empirical SE research",
        "EC2": "Published before 2015",
        "EC3": "Not peer-reviewed (WL only)",
        "EC4": "Duplicate publication"
    }


def render_suggestion_details(suggestion: Dict):
    """Render detailed LLM suggestion with color-coded output."""
    decision = suggestion.get("decision", "").upper()
    confidence = suggestion.get("confidence", 0)
    confidence_pct = int(confidence * 100)

    col_dec, col_conf = st.columns([1, 1])

    if decision == "EXCLUDE":
        with col_dec:
            st.error("🚫 **EXCLUDE**")
    elif decision == "INCLUDE":
        with col_dec:
            st.success("✅ **INCLUDE**")
    elif decision == "UNCERTAIN":
        with col_dec:
            st.warning("⚠️ **UNCERTAIN** — Manual Review Required")
    else:
        with col_dec:
            st.info(f"**{decision}**")

    with col_conf:
        st.metric("Confidence", f"{confidence_pct}%")

    st.markdown(f"**Reasoning:** {suggestion.get('justification', 'N/A')}")

    triggered = suggestion.get("triggered_criteria", {})
    if triggered and any(v for v in triggered.values()):
        st.markdown("**🔍 Triggered Criteria:**")
        for criterion, reason in triggered.items():
            if reason:
                st.markdown(f"  • **{criterion}**: {reason}")

    evidence = suggestion.get("evidence", [])
    if evidence:
        st.markdown("**📝 Evidence Extracted:**")
        for phrase in evidence:
            st.markdown(f"  • \"{phrase}\"")

    ambiguity = suggestion.get("ambiguity_flags", [])
    if ambiguity and any(ambiguity):
        st.markdown("**⚠️ Potential Ambiguities:**")
        for flag in ambiguity:
            if flag:
                st.markdown(f"  • {flag}")


def export_ec_results(session: Dict):
    """Export EC screening results."""
    import pandas as pd

    articles = session["articles"]
    decisions = session["decisions"]

    results = []
    for i, article in enumerate(articles):
        decision = decisions.get(i, {}).get("decision", "pending")
        results.append({
            "Title": article["title"],
            "Literature_Type": article["literature_type"],
            "EC_Decision": decision.upper(),
            "EC_Notes": decisions.get(i, {}).get("notes", ""),
            "Abstract": article.get("abstract", "")
        })

    df = pd.DataFrame(results)
    csv = df.to_csv(index=False)

    st.download_button(
        "📥 Download EC Results (CSV)",
        data=csv,
        file_name="apollo_ec_screening_results.csv",
        mime="text/csv"
    )

    included = sum(1 for r in results if r["EC_Decision"] == "INCLUDE")
    excluded = sum(1 for r in results if r["EC_Decision"] == "EXCLUDE")

    st.success(f"EC Screening Complete: {included} included, {excluded} excluded")
