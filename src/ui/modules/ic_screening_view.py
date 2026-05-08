"""
APOLLO IC Screening Workspace

Stage-specific workspace for Inclusion Criteria screening.
ONLY IC criteria are visible/applicable in this workspace.

Researcher screens papers that passed EC filtering.
No EC or QC execution occurs here.
"""
import streamlit as st
from typing import Dict


def render_ic_screening():
    """Render IC Screening Workspace."""
    from src.core.dynamic_protocol import ProtocolState

    st.markdown("# IC Screening Workspace")
    st.markdown("*Apply Inclusion Criteria to assess methodological relevance*")
    st.divider()

    if "research_protocol" not in st.session_state or st.session_state.research_protocol is None:
        st.warning("⚠️ No Research Protocol configured. Please go to 'Protocol Configuration' first.")
        return

    protocol = st.session_state.research_protocol

    if protocol.state == ProtocolState.DRAFT.value:
        st.warning("⚠️ Protocol must be locked before screening.")
        return

    render_protocol_info_banner(protocol)
    st.divider()

    if "ic_session" not in st.session_state:
        st.session_state.ic_session = {
            "articles": [],
            "current_index": 0,
            "decisions": {},
            "loaded": False
        }

    if not st.session_state.ic_session["loaded"]:
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
        st.metric("IC Criteria", summary['ic_count'])
    with col3:
        st.metric("IC Enabled", summary['ic_enabled'])
    with col4:
        st.caption(f"Hash: `{summary['hash']}`")


def render_upload_section():
    """Render upload section for IC screening."""
    st.markdown("### Upload EC-Filtered Papers")
    st.info("""
    **Upload the results from EC Screening** (papers that were included/excluded).

    The IC stage is applied to papers that passed EC filtering.
    Only IC criteria will be applied in this workspace.
    """)

    uploaded_file = st.file_uploader(
        "Upload EC Results or ATLAS File",
        type=["xlsx", "csv"],
        help="Upload papers for IC screening"
    )

    if uploaded_file:
        with st.spinner("Loading papers..."):
            articles = load_papers(uploaded_file)
            if articles:
                st.session_state.ic_session["articles"] = articles
                st.session_state.ic_session["current_index"] = 0
                st.session_state.ic_session["decisions"] = {}
                st.session_state.ic_session["loaded"] = True
                st.success(f"✅ Loaded {len(articles)} papers. Ready for IC screening.")
                st.rerun()
            else:
                st.error("Failed to load papers.")


def load_papers(uploaded_file) -> list:
    """Load papers from file."""
    import pandas as pd

    import tempfile
    temp_path = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False).name

    with open(temp_path, "wb") as f:
        f.write(uploaded_file.getvalue())

    try:
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(temp_path)
        else:
            try:
                df = pd.read_excel(temp_path, sheet_name="White Literature")
            except:
                df = pd.read_excel(temp_path, sheet_name=0)

        articles = []
        for _, row in df.iterrows():
            articles.append({
                "title": str(row.get("Title", row.get("title", ""))),
                "abstract": str(row.get("Abstract", row.get("abstract", ""))),
                "literature_type": str(row.get("Literature_Type", "WL")),
                "ec_decision": str(row.get("EC_Decision", "INCLUDE")),
                "ic_decision": "",
                "ic_notes": ""
            })

        return articles
    except Exception as e:
        st.error(f"Error loading file: {e}")
        return []
    finally:
        import os
        os.unlink(temp_path)


def render_screening_workspace():
    """Render the main IC screening workspace."""
    session = st.session_state.ic_session
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

    if st.button("📊 Export IC Results", type="primary"):
        export_ic_results(session)


def render_ai_advisory_panel(article: Dict, current_idx: int, decisions: Dict):
    """Render AI Advisory Panel for IC screening."""
    st.divider()
    st.markdown("### AI Advisory Panel")

    cache_key = f"ic_advice_{current_idx}"
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
                key=f"ic_advice_btn_{current_idx}",
                use_container_width=True
            )
        with col_status:
            if cached_advice:
                st.success("✓ AI suggestion available for this article")
            else:
                st.caption("No suggestion generated yet for this article")

        if request_suggestion:
            with st.spinner("Generating AI suggestion..."):
                suggestion = get_llm_ic_suggestion(article)
                if suggestion:
                    st.session_state[cache_key] = suggestion
                    cached_advice = suggestion
                    st.rerun()
                else:
                    st.warning("LLM unavailable — continue with manual review.")

        if cached_advice:
            st.divider()
            render_suggestion_details(cached_advice)


def get_llm_ic_suggestion(article: Dict) -> Optional[Dict]:
    """Get LLM advisory suggestion for IC screening."""
    try:
        from src.core.llm_assistant import LLMAssistant

        llm = LLMAssistant()
        if not llm.is_available():
            return None

        protocol_criteria = get_protocol_ic_criteria()

        suggestion = llm.suggest_ic(
            title=article.get("title", ""),
            abstract=article.get("abstract", ""),
            literature_type=article.get("literature_type", "WL"),
            protocol_criteria=protocol_criteria
        )

        return suggestion.to_dict()
    except Exception:
        return None


def get_protocol_ic_criteria() -> Dict[str, str]:
    """Get IC criteria from current protocol."""
    if "research_protocol" in st.session_state and st.session_state.research_protocol:
        protocol = st.session_state.research_protocol
        return {
            k: v.description
            for k, v in protocol.ic.criteria.items()
            if v.enabled
        }
    return {
        "IC1": "Addresses R&S practices",
        "IC2": "Reports empirical findings",
        "IC3": "Focuses on software industry context"
    }


def render_suggestion_details(suggestion: Dict):
    """Render detailed LLM suggestion."""
    decision = suggestion.get("decision", "").upper()
    confidence = suggestion.get("confidence", 0)
    confidence_pct = int(confidence * 100)

    col_dec, col_conf = st.columns(2)
    with col_dec:
        if decision == "EXCLUDE":
            st.error(f"**AI Suggestion: {decision}**")
        else:
            st.success(f"**AI Suggestion: {decision}**")
    with col_conf:
        st.metric("Confidence", f"{confidence_pct}%")

    st.markdown(f"**Justification:** {suggestion.get('justification', 'N/A')}")

    triggered = suggestion.get("triggered_criteria", {})
    if triggered:
        with st.expander("🔍 Triggered Criteria"):
            for criterion, reason in triggered.items():
                if reason:
                    st.markdown(f"  **{criterion}**: {reason}")

    evidence = suggestion.get("evidence", [])
    if evidence:
        with st.expander("📝 Evidence Phrases"):
            for phrase in evidence:
                st.markdown(f"  - {phrase}")

    ambiguity = suggestion.get("ambiguity_flags", [])
    if ambiguity:
        with st.expander("⚠️ Ambiguity Flags"):
            for flag in ambiguity:
                st.markdown(f"  - {flag}")


def render_article_card(article: Dict, index: int, decisions: Dict):
    """Render a single article card for IC screening."""
    lit_type = article.get("literature_type", "WL")

    col_type, col_id = st.columns([1, 3])
    with col_type:
        badge = "WL" if lit_type == "WL" else "GL"
        color = "#238636" if lit_type == "WL" else "#f0883e"
        st.markdown(f"<span style='background:{color};color:white;padding:2px 8px;border-radius:4px'>{badge}</span>",
                   unsafe_allow_html=True)
    with col_id:
        st.caption(f"EC Decision: {article.get('ec_decision', 'N/A')}")

    st.markdown(f"### {article['title']}")

    abstract = article.get("abstract", "")
    if abstract and abstract != "nan":
        with st.expander("📄 Abstract"):
            st.markdown(abstract)


def export_ic_results(session: Dict):
    """Export IC screening results."""
    import pandas as pd

    articles = session["articles"]
    decisions = session["decisions"]

    results = []
    for i, article in enumerate(articles):
        decision = decisions.get(i, {}).get("decision", "pending")
        results.append({
            "Title": article["title"],
            "Literature_Type": article["literature_type"],
            "EC_Decision": article.get("ec_decision", ""),
            "IC_Decision": decision.upper(),
            "IC_Notes": decisions.get(i, {}).get("notes", ""),
            "Abstract": article.get("abstract", "")
        })

    df = pd.DataFrame(results)
    csv = df.to_csv(index=False)

    st.download_button(
        "📥 Download IC Results (CSV)",
        data=csv,
        file_name="apollo_ic_screening_results.csv",
        mime="text/csv"
    )

    included = sum(1 for r in results if r["IC_Decision"] == "INCLUDE")
    excluded = sum(1 for r in results if r["IC_Decision"] == "EXCLUDE")

    st.success(f"IC Screening Complete: {included} included, {excluded} excluded")
