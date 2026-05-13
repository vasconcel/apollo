"""
APOLLO Research Protocol Configuration View - Forensic Terminal Aesthetic

This module provides the dedicated Research Protocol configuration interface
that must be completed BEFORE screening begins.

Workflow:
1. Researcher configures EC/IC criteria
"""
from typing import Dict, Optional
import streamlit as st
from src.core.dynamic_protocol import (
    DynamicProtocol, Criterion, ECProtocol, ICProtocol,
    ProtocolState, ProtocolTemplate
)

SE_RS_BOOTSTRAP_TEMPLATE = ProtocolTemplate.SE_RS_BOOTSTRAP


def render_protocol_dashboard():
    """Render the Research Protocol configuration dashboard."""
    terminal_header(
        "PROTOCOL CONFIGURATION",
        "Configure screening criteria before uploading papers",
        status="DRAFT" if st.session_state.get("research_protocol") and st.session_state.research_protocol.state == ProtocolState.DRAFT.value else "LOCKED"
    )
    divider()

    st.session_state.setdefault("research_protocol", None)
    st.session_state.setdefault("protocol_locked", False)

    if st.session_state.research_protocol is None:
        st.session_state.research_protocol = DynamicProtocol(template=SE_RS_BOOTSTRAP_TEMPLATE)

    protocol = st.session_state.research_protocol
    st.session_state.protocol_locked = protocol.state == ProtocolState.LOCKED.value

    if protocol.state != ProtocolState.DRAFT.value:
        render_locked_protocol_view(protocol)
    else:
        render_draft_protocol_view(protocol)


def render_draft_protocol_view(protocol: DynamicProtocol):
    """Render editable protocol configuration in terminal style."""
    with st.container():
        section_header("PROTOCOL STATUS", "Current configuration state")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            ec_count = len(protocol.ec.criteria)
            metric_tile("EC CRITERIA", str(ec_count))
        with col2:
            ic_count = len(protocol.ic.criteria)
            metric_tile("IC CRITERIA", str(ic_count))
        with col3:
            st.markdown(f'''
            <div style="border:1px solid {COLORS['warning']};background:{COLORS['bg_card']};padding:0.75rem;text-align:center;">
                <span style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['warning']};">STATUS</span><br>
                <span style="font-family:{TYPOGRAPHY['mono']};font-size:0.9rem;color:{COLORS['warning']};">DRAFT</span>
            </div>
            ''', unsafe_allow_html=True)

    template_info = protocol.get_template_info()
    if template_info.get("bootstrapped"):
        st.success(f"Default Bootstrap Template Loaded: {template_info.get('template_name', 'Unknown')}")

    divider()

    section_header("TEMPLATE SELECTION", "Load predefined protocol templates")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("RESET TO SE R&S DEFAULT", width="stretch"):
            protocol._apply_template(SE_RS_BOOTSTRAP_TEMPLATE)
            st.success("Loaded: SE Recruitment & Selection")
            st.rerun()
    with col2:
        if st.button("KITCHENHAM SLR TEMPLATE", width="stretch"):
            protocol._apply_template(ProtocolTemplate.KITCHENHAM_SLR)
            st.success("Loaded: Kitchenham SLR Template")
            st.rerun()
    with col3:
        if st.button("GENERIC MLR TEMPLATE", width="stretch"):
            protocol._apply_template(ProtocolTemplate.GENERIC_MLR)
            st.success("Loaded: Generic MLR Template")
            st.rerun()

    divider()

    with st.container():
        section_header("EXCLUSION CRITERIA (EC)", "First-stage filtering to remove irrelevant studies")
        
        with st.expander("INFO: EXCLUSION CRITERIA"):
            st.markdown(f'''
            <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.7rem;color:{COLORS['text_secondary']};line-height:1.6;">
                <strong>Exclusion Criteria (EC)</strong> are applied first in the screening funnel to remove
                clearly irrelevant studies.
                <ul style="color:{COLORS['text_muted']};">
                    <li>Papers failing ANY enabled EC criterion are excluded</li>
                    <li>EC filtering preserves PRISMA-style funnel traceability</li>
                    <li>Examples: non-English, not empirical, wrong domain, too old</li>
                </ul>
            </div>
            ''', unsafe_allow_html=True)
        render_criteria_editor(protocol, "ec", "EC")

    divider()

    with st.container():
        section_header("INCLUSION CRITERIA (IC)", "Second-stage assessment of methodological relevance")
        
        with st.expander("INFO: INCLUSION CRITERIA"):
            st.markdown(f'''
            <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.7rem;color:{COLORS['text_secondary']};line-height:1.6;">
                <strong>Inclusion Criteria (IC)</strong> are evaluated only among papers that passed EC filtering.
                <ul style="color:{COLORS['text_muted']};">
                    <li>Papers failing ANY enabled IC criterion are excluded</li>
                    <li>IC assessment examines methodological relevance</li>
                    <li>Examples: addresses research questions, uses appropriate methods</li>
                </ul>
            </div>
            ''', unsafe_allow_html=True)
        render_criteria_editor(protocol, "ic", "IC")

    divider()

    divider()

    is_complete, errors = protocol.is_complete()
    if not is_complete:
        st.warning("Protocol cannot be locked until complete:")
        for error in errors:
            st.markdown(f"  - {error}")
    else:
        st.success("Protocol is complete and ready to lock")

    col_lock, col_clear = st.columns([2, 1])
    with col_lock:
        st.button(
            "LOCK PROTOCOL",
            type="primary",
            width="stretch",
            disabled=not is_complete,
            on_click=lock_protocol
        )
    with col_clear:
        if st.button("RESET PROTOCOL", width="stretch"):
            st.session_state.research_protocol = DynamicProtocol(template=SE_RS_BOOTSTRAP_TEMPLATE)
            st.rerun()


def load_template(protocol: DynamicProtocol, template_data: Dict):
    """Load a template into the protocol using _apply_template."""
    protocol._apply_template(template_data)


def lock_protocol():
    """Callback to lock the protocol."""
    protocol = st.session_state.research_protocol
    try:
        protocol.lock()
        st.session_state.protocol_locked = True
        st.success("Protocol locked successfully!")
    except ValueError as e:
        st.error(f"Cannot lock protocol: {e}")


def render_criteria_editor(protocol: DynamicProtocol, stage: str, prefix: str):
    """Render editable criteria for a stage (EC or IC) in terminal style."""
    stage_protocol = protocol.get_stage_protocol(stage)
    enabled_count = len([c for c in stage_protocol.criteria.values() if c.enabled])
    total_count = len(stage_protocol.criteria)
    
    st.markdown(f'<span style="font-family:{TYPOGRAPHY["mono"]};font-size:0.65rem;color:{COLORS["text_muted"]};">ENABLED: {enabled_count}/{total_count}</span>', unsafe_allow_html=True)

    if total_count == 0:
        render_empty_state(stage)
    else:
        for criterion_id, criterion in stage_protocol.criteria.items():
            render_criterion_card(criterion, stage, criterion_id)

    divider()

    col_id, col_desc, col_btn = st.columns([1, 3, 1])
    with col_id:
        new_id = st.text_input(f"ID", placeholder=f"{prefix}5", key=f"new_{stage}_id", label_visibility="collapsed")
    with col_desc:
        new_desc = st.text_input(f"Description", placeholder="Criterion description", key=f"new_{stage}_desc", label_visibility="collapsed")
    with col_btn:
        st.markdown("&nbsp;")
        if st.button("+ ADD", key=f"add_{stage}"):
            if new_id and new_desc:
                if new_id in stage_protocol.criteria:
                    st.error(f"{new_id} already exists")
                else:
                    stage_protocol.criteria[new_id] = Criterion(
                        id=new_id,
                        description=new_desc,
                        enabled=True
                    )
                    st.rerun()


def render_empty_state(stage: str):
    """Render empty state placeholder."""
    stage_labels = {"ec": "Exclusion Criterion", "ic": "Inclusion Criterion"}
    label = stage_labels.get(stage, "Criterion")
    st.info(f"No {label.lower()}s defined yet. Create your first {stage.upper()} criterion above to begin.")


def render_criterion_card(criterion: Criterion, stage: str, criterion_id: str):
    """Render a single criterion as a card in terminal style."""
    with st.container():
        col1, col2, col3 = st.columns([4, 1, 1])
        with col1:
            new_desc = st.text_input(
                f"Description",
                value=criterion.description,
                key=f"{stage}_{criterion_id}_desc",
                label_visibility="collapsed"
            )
            criterion.description = new_desc
        with col2:
            enabled = st.checkbox(
                "Enabled",
                value=criterion.enabled,
                key=f"{stage}_{criterion_id}_enabled"
            )
            criterion.enabled = enabled
        with col3:
            if st.button("X", key=f"del_{stage}_{criterion_id}"):
                stage_protocol = st.session_state.research_protocol.get_stage_protocol(stage)
                del stage_protocol.criteria[criterion_id]
                st.rerun()
        divider()


def render_locked_protocol_view(protocol: DynamicProtocol):
    """Render read-only view of locked protocol in terminal style."""
    summary = protocol.get_summary()

    st.markdown(f'''
    <div style="border:1px solid {COLORS['success']};background:{COLORS['bg_card']};padding:1rem;margin-bottom:1rem;">
        <span style="font-family:{TYPOGRAPHY['mono']};font-size:0.7rem;color:{COLORS['success']};">PROTOCOL LOCKED</span>
    </div>
    ''', unsafe_allow_html=True)
    
    with st.container():
        section_header("PROTOCOL SUMMARY", "Current locked configuration")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            metric_tile("EC CRITERIA", str(summary['ec_count']))
        with col2:
            metric_tile("IC CRITERIA", str(summary['ic_count']))
        with col3:
            metric_tile("VERSION", f"v{summary['version']}")

        col4, col5 = st.columns(2)
        with col4:
            metric_tile("HASH", summary['hash'][:12] + "..." if summary['hash'] else "N/A")

        if protocol.locked_at:
            st.markdown(f'<span style="font-family:{TYPOGRAPHY["mono"]};font-size:0.65rem;color:{COLORS["text_muted"]};">LOCKED AT: {protocol.locked_at}</span>', unsafe_allow_html=True)

        if summary.get('template_name'):
            st.markdown(f'<span style="font-family:{TYPOGRAPHY["mono"]};font-size:0.65rem;color:{COLORS["text_muted"]};">TEMPLATE: {summary["template_name"]} (v{summary.get("template_version", "N/A")})</span>', unsafe_allow_html=True)

    divider()

    with st.container():
        section_header("EXCLUSION CRITERIA (EC)", "Locked criteria list")
        for criterion_id, criterion in protocol.ec.criteria.items():
            status = "✓" if criterion.enabled else "✗"
            color = COLORS['success'] if criterion.enabled else COLORS['error']
            st.markdown(f'<span style="font-family:{TYPOGRAPHY["mono"]};font-size:0.75rem;"><span style="color:{color};">{status}</span> <strong>{criterion_id}</strong>: {criterion.description}</span>', unsafe_allow_html=True)

    with st.container():
        section_header("INCLUSION CRITERIA (IC)", "Locked criteria list")
        for criterion_id, criterion in protocol.ic.criteria.items():
            status = "✓" if criterion.enabled else "✗"
            color = COLORS['success'] if criterion.enabled else COLORS['error']
            st.markdown(f'<span style="font-family:{TYPOGRAPHY["mono"]};font-size:0.75rem;"><span style="color:{color};">{status}</span> <strong>{criterion_id}</strong>: {criterion.description}</span>', unsafe_allow_html=True)

    divider()

    col1, col2 = st.columns(2)
    with col1:
        if st.button("UNLOCK FOR NEW VERSION", type="secondary", width="stretch"):
            new_protocol = protocol.unlock()
            st.session_state.research_protocol = new_protocol
            st.session_state.protocol_locked = False
            st.success("New version created. You may now modify the protocol.")
            st.rerun()
    with col2:
        if st.button("USE THIS PROTOCOL", type="primary", width="stretch"):
            st.session_state.protocol_locked = True
            st.success("Ready to upload papers!")


def check_protocol_ready_for_screening() -> tuple:
    """Check if protocol is ready for screening."""
    if st.session_state.research_protocol is None:
        return (False, "No protocol configured.")

    protocol = st.session_state.research_protocol

    if protocol.state == ProtocolState.DRAFT.value:
        return (False, "Protocol must be locked before screening begins.")

    if protocol.state == ProtocolState.LOCKED.value:
        return (True, "Protocol ready for screening.")

    return (True, "Protocol has active session.")


def get_session_protocol() -> DynamicProtocol:
    """Get the current research protocol for session creation."""
    if st.session_state.research_protocol is None:
        return DynamicProtocol(template=SE_RS_BOOTSTRAP_TEMPLATE)
    return st.session_state.research_protocol


def get_locked_protocol_dict() -> Optional[Dict]:
    """Get locked protocol as dict for session storage."""
    protocol = st.session_state.research_protocol
    if protocol and protocol.state == ProtocolState.LOCKED.value:
        protocol.create_session()
        return protocol.to_dict()
    return None


def reset_protocol_for_new_session():
    """Reset protocol to fresh state for new session."""
    st.session_state.research_protocol = DynamicProtocol(template=SE_RS_BOOTSTRAP_TEMPLATE)
    st.session_state.protocol_locked = False
    st.rerun()