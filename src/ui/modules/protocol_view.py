"""
APOLLO Research Protocol Configuration View - Forensic Terminal Aesthetic

This module provides the dedicated Research Protocol configuration interface
that must be completed BEFORE screening begins.

Workflow:
1. Researcher configures EC/IC/QC criteria
2. Researcher explicitly locks the protocol
3. Protocol snapshot/hash is created
4. ONLY THEN screening may begin
"""
import streamlit as st
from typing import Dict, List, Optional
from src.ui.components import (
    terminal_header, section_header, status_badge, lit_type_badge,
    metric_tile, telemetry_panel, decision_card, progress_bar,
    stage_indicator, structured_card, criteria_panel, divider,
    operational_status, provenance_indicator
)
from src.ui.theme import COLORS, TYPOGRAPHY
from src.core.dynamic_protocol import (
    DynamicProtocol, Criterion, ECProtocol, ICProtocol, QCProtocol,
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
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            ec_count = len(protocol.ec.criteria)
            metric_tile("EC CRITERIA", str(ec_count))
        with col2:
            ic_count = len(protocol.ic.criteria)
            metric_tile("IC CRITERIA", str(ic_count))
        with col3:
            wl_qc = len(protocol.qc.wl_criteria)
            gl_qc = len(protocol.qc.gl_criteria)
            metric_tile("QC CRITERIA", f"{wl_qc}WL / {gl_qc}GL")
        with col4:
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
        if st.button("RESET TO SE R&S DEFAULT", use_container_width=True):
            protocol._apply_template(SE_RS_BOOTSTRAP_TEMPLATE)
            st.success("Loaded: SE Recruitment & Selection")
            st.rerun()
    with col2:
        if st.button("KITCHENHAM SLR TEMPLATE", use_container_width=True):
            protocol._apply_template(ProtocolTemplate.KITCHENHAM_SLR)
            st.success("Loaded: Kitchenham SLR Template")
            st.rerun()
    with col3:
        if st.button("GENERIC MLR TEMPLATE", use_container_width=True):
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

    with st.container():
        section_header("QUALITY CRITERIA (QC)", "Methodological rigor assessment")
        
        with st.expander("INFO: QUALITY CRITERIA"):
            st.markdown(f'''
            <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.7rem;color:{COLORS['text_secondary']};line-height:1.6;">
                <strong>Quality Criteria (QC)</strong> assess methodological rigor of included papers.
                <ul style="color:{COLORS['text_muted']};">
                    <li>Each enabled criterion contributes to quality score</li>
                    <li>Papers scoring below threshold are excluded</li>
                    <li>QC is evaluated sequentially after EC and IC stages</li>
                </ul>
            </div>
            ''', unsafe_allow_html=True)
        render_qc_editor(protocol)

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
            use_container_width=True,
            disabled=not is_complete,
            on_click=lock_protocol
        )
    with col_clear:
        if st.button("RESET PROTOCOL", use_container_width=True):
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


def render_qc_editor(protocol: DynamicProtocol):
    """Render QC-specific editor with WL/GL framework separation in terminal style."""
    qc = protocol.qc

    st.markdown(f'''
    <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.7rem;color:{COLORS['success']};margin-bottom:0.5rem;">
        WHITE LITERATURE (WL) QUALITY CRITERIA
    </div>
    ''', unsafe_allow_html=True)
    st.caption("Scientific rigor assessment for peer-reviewed publications")

    wl_enabled = len([c for c in qc.wl_criteria.values() if c.enabled])
    wl_total = len(qc.wl_criteria)
    st.markdown(f'<span style="font-family:{TYPOGRAPHY["mono"]};font-size:0.65rem;color:{COLORS["text_muted"]};">WL Enabled: {wl_enabled}/{wl_total} | Threshold: {qc.wl_threshold}</span>', unsafe_allow_html=True)

    wl_threshold = st.slider(
        "WL Quality Threshold",
        min_value=0.0,
        max_value=4.0,
        value=float(qc.wl_threshold),
        step=0.5,
        key="wl_threshold"
    )
    qc.wl_threshold = wl_threshold

    if wl_total == 0:
        st.info("No WL quality criteria defined yet.")
    else:
        for criterion_id, criterion in qc.wl_criteria.items():
            with st.container():
                col1, col2, col3, col4 = st.columns([4, 1, 1, 1])
                with col1:
                    new_desc = st.text_input(
                        f"{criterion_id}",
                        value=criterion.description,
                        key=f"wl_qc_{criterion_id}_desc",
                        label_visibility="collapsed"
                    )
                    criterion.description = new_desc
                with col2:
                    new_weight = st.number_input(
                        "Weight",
                        min_value=0.0,
                        max_value=2.0,
                        value=float(criterion.weight),
                        step=0.5,
                        key=f"wl_qc_{criterion_id}_weight"
                    )
                    criterion.weight = new_weight
                with col3:
                    enabled = st.checkbox(
                        "On",
                        value=criterion.enabled,
                        key=f"wl_qc_{criterion_id}_enabled"
                    )
                    criterion.enabled = enabled
                with col4:
                    if st.button("X", key=f"del_wl_qc_{criterion_id}"):
                        del qc.wl_criteria[criterion_id]
                        st.rerun()
                divider()

    wl_col_id, wl_col_desc, wl_col_btn = st.columns([1, 3, 1])
    with wl_col_id:
        new_wl_id = st.text_input(f"WL ID", placeholder=f"WL-Q{wl_total + 1}", key="new_wl_qc_id", label_visibility="collapsed")
    with wl_col_desc:
        new_wl_desc = st.text_input(f"WL Description", placeholder="WL quality criterion", key="new_wl_qc_desc", label_visibility="collapsed")
    with wl_col_btn:
        st.markdown("&nbsp;")
        if st.button("+ ADD WL", key="add_wl_qc"):
            if new_wl_id and new_wl_desc:
                if new_wl_id in qc.wl_criteria:
                    st.error(f"{new_wl_id} already exists")
                else:
                    qc.wl_criteria[new_wl_id] = Criterion(
                        id=new_wl_id,
                        description=new_wl_desc,
                        enabled=True,
                        weight=1.0
                    )
                    st.rerun()

    divider()

    st.markdown(f'''
    <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.7rem;color:{COLORS['warning']};margin-bottom:0.5rem;">
        GREY LITERATURE (GL) QUALITY CRITERIA
    </div>
    ''', unsafe_allow_html=True)
    st.caption("Trustworthiness assessment for non-peer-reviewed sources")

    gl_enabled = len([c for c in qc.gl_criteria.values() if c.enabled])
    gl_total = len(qc.gl_criteria)
    st.markdown(f'<span style="font-family:{TYPOGRAPHY["mono"]};font-size:0.65rem;color:{COLORS["text_muted"]};">GL Enabled: {gl_enabled}/{gl_total} | Threshold: {qc.gl_threshold}</span>', unsafe_allow_html=True)

    gl_threshold = st.slider(
        "GL Quality Threshold",
        min_value=0.0,
        max_value=4.0,
        value=float(qc.gl_threshold),
        step=0.5,
        key="gl_threshold"
    )
    qc.gl_threshold = gl_threshold

    if gl_total == 0:
        st.info("No GL quality criteria defined yet.")
    else:
        for criterion_id, criterion in qc.gl_criteria.items():
            with st.container():
                col1, col2, col3, col4 = st.columns([4, 1, 1, 1])
                with col1:
                    new_desc = st.text_input(
                        f"{criterion_id}",
                        value=criterion.description,
                        key=f"gl_qc_{criterion_id}_desc",
                        label_visibility="collapsed"
                    )
                    criterion.description = new_desc
                with col2:
                    new_weight = st.number_input(
                        "Weight",
                        min_value=0.0,
                        max_value=2.0,
                        value=float(criterion.weight),
                        step=0.5,
                        key=f"gl_qc_{criterion_id}_weight"
                    )
                    criterion.weight = new_weight
                with col3:
                    enabled = st.checkbox(
                        "On",
                        value=criterion.enabled,
                        key=f"gl_qc_{criterion_id}_enabled"
                    )
                    criterion.enabled = enabled
                with col4:
                    if st.button("X", key=f"del_gl_qc_{criterion_id}"):
                        del qc.gl_criteria[criterion_id]
                        st.rerun()
                divider()

    gl_col_id, gl_col_desc, gl_col_btn = st.columns([1, 3, 1])
    with gl_col_id:
        new_gl_id = st.text_input(f"GL ID", placeholder=f"GL-Q{gl_total + 1}", key="new_gl_qc_id", label_visibility="collapsed")
    with gl_col_desc:
        new_gl_desc = st.text_input(f"GL Description", placeholder="GL quality criterion", key="new_gl_qc_desc", label_visibility="collapsed")
    with gl_col_btn:
        st.markdown("&nbsp;")
        if st.button("+ ADD GL", key="add_gl_qc"):
            if new_gl_id and new_gl_desc:
                if new_gl_id in qc.gl_criteria:
                    st.error(f"{new_gl_id} already exists")
                else:
                    qc.gl_criteria[new_gl_id] = Criterion(
                        id=new_gl_id,
                        description=new_gl_desc,
                        enabled=True,
                        weight=1.0
                    )
                    st.rerun()


def render_empty_state(stage: str):
    """Render empty state placeholder."""
    stage_labels = {"ec": "Exclusion Criterion", "ic": "Inclusion Criterion", "qc": "Quality Criterion"}
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
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            metric_tile("EC CRITERIA", str(summary['ec_count']))
        with col2:
            metric_tile("IC CRITERIA", str(summary['ic_count']))
        with col3:
            metric_tile("WL QC", str(summary['wl_qc_count']))
        with col4:
            metric_tile("GL QC", str(summary['gl_qc_count']))

        col5, col6, col7, col8 = st.columns(4)
        with col5:
            metric_tile("VERSION", f"v{summary['version']}")
        with col6:
            metric_tile("HASH", summary['hash'][:12] + "..." if summary['hash'] else "N/A")
        with col7:
            metric_tile("WL THRESH", str(summary['wl_threshold']))
        with col8:
            metric_tile("GL THRESH", str(summary['gl_threshold']))

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

    with st.container():
        section_header("WHITE LITERATURE QC (WL)", "Locked criteria list")
        wl_enabled = len([c for c in protocol.qc.wl_criteria.values() if c.enabled])
        st.markdown(f'<span style="font-family:{TYPOGRAPHY["mono"]};font-size:0.65rem;color:{COLORS["text_muted"]};">Threshold: {protocol.qc.wl_threshold} | Enabled: {wl_enabled}/{len(protocol.qc.wl_criteria)}</span>', unsafe_allow_html=True)
        for criterion_id, criterion in protocol.qc.wl_criteria.items():
            status = "✓" if criterion.enabled else "✗"
            color = COLORS['success'] if criterion.enabled else COLORS['error']
            st.markdown(f'<span style="font-family:{TYPOGRAPHY["mono"]};font-size:0.75rem;"><span style="color:{color};">{status}</span> <strong>{criterion_id}</strong> (w:{criterion.weight}): {criterion.description}</span>', unsafe_allow_html=True)

    with st.container():
        section_header("GREY LITERATURE QC (GL)", "Locked criteria list")
        gl_enabled = len([c for c in protocol.qc.gl_criteria.values() if c.enabled])
        st.markdown(f'<span style="font-family:{TYPOGRAPHY["mono"]};font-size:0.65rem;color:{COLORS["text_muted"]};">Threshold: {protocol.qc.gl_threshold} | Enabled: {gl_enabled}/{len(protocol.qc.gl_criteria)}</span>', unsafe_allow_html=True)
        for criterion_id, criterion in protocol.qc.gl_criteria.items():
            status = "✓" if criterion.enabled else "✗"
            color = COLORS['success'] if criterion.enabled else COLORS['error']
            st.markdown(f'<span style="font-family:{TYPOGRAPHY["mono"]};font-size:0.75rem;"><span style="color:{color};">{status}</span> <strong>{criterion_id}</strong> (w:{criterion.weight}): {criterion.description}</span>', unsafe_allow_html=True)

    divider()

    col1, col2 = st.columns(2)
    with col1:
        if st.button("UNLOCK FOR NEW VERSION", type="secondary", use_container_width=True):
            new_protocol = protocol.unlock()
            st.session_state.research_protocol = new_protocol
            st.session_state.protocol_locked = False
            st.success("New version created. You may now modify the protocol.")
            st.rerun()
    with col2:
        if st.button("USE THIS PROTOCOL", type="primary", use_container_width=True):
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