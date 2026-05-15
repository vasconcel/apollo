"""
APOLLO Scientific Design System - Workflow Components

Components for visualizing canonical screening workflow:
Protocol → EC → IC → Export → Replay

PURPOSE:
- Enforce workflow order visually
- Lock future stages
- Display protocol hash and session lineage
- Show replay state
"""

import streamlit as st
from typing import Dict, List, Optional
from src.ui.design_system.semantic_colors import (
    SEMANTIC_COLORS, WORKFLOW_STAGE_COLORS, get_semantic_color, get_workflow_stage_color
)
from src.ui.design_system.typography import TYPOGRAPHY, STYLE_GUIDES


WORKFLOW_STAGES = [
    {"id": "protocol", "label": "PROTOCOL", "icon": "◈"},
    {"id": "ec", "label": "EC", "icon": "⊘"},
    {"id": "ic", "label": "IC", "icon": "⊕"},
    {"id": "export", "label": "EXPORT", "icon": "⬇"},
    {"id": "replay", "label": "REPLAY", "icon": "⟲"},
]


def render_workflow_stepper(
    current_stage: str,
    session_state: Dict = None,
    locked: bool = False,
    protocol_hash: str = ""
) -> None:
    """
    Render canonical workflow stepper with equal-width blocks.
    SCIENTIFIC UX: Strong workflow hierarchy - Protocol → EC → IC → Export → Replay
    """
    stage_order = [s["id"] for s in WORKFLOW_STAGES]
    current_idx = stage_order.index(current_stage) if current_stage in stage_order else 0

    st.markdown("""
    <style>
    .workflow-stepper {
        display: flex;
        align-items: stretch;
        gap: 0;
        padding: 0.5rem 0;
        overflow-x: auto;
        width: 100%;
    }
    .workflow-step {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 0.25rem;
        padding: 0.6rem 0.4rem;
        border: 1px solid #252525;
        background: #0D0D0D;
        position: relative;
        flex: 1 1 0;
        min-width: 80px;
        width: 100%;
        text-align: center;
    }
    .workflow-step.completed {
        border-color: #00D67E;
        background: rgba(0, 214, 126, 0.08);
    }
    .workflow-step.active {
        border-color: #00c8d7;
        background: rgba(0, 200, 215, 0.1);
    }
    .workflow-step.locked {
        border-color: #58A6FF;
        background: rgba(88, 166, 255, 0.08);
    }
    .workflow-step.future {
        border-color: #252525;
        opacity: 0.5;
    }
    .workflow-connector {
        width: 16px;
        height: 2px;
        background: #252525;
        align-self: center;
    }
    .workflow-connector.completed {
        background: #00D67E;
    }
    .workflow-icon {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.1rem;
    }
    .workflow-label {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.6rem;
        letter-spacing: 0.1em;
        text-transform: uppercase;
    }
    </style>
    """, unsafe_allow_html=True)

    steps_html = '<div class="workflow-stepper">'

    for i, stage in enumerate(WORKFLOW_STAGES):
        stage_id = stage["id"]
        stage_color = get_workflow_stage_color(stage_id)

        if i < current_idx:
            state_class = "completed"
        elif i == current_idx:
            state_class = "active" if not locked else "locked"
        else:
            state_class = "future"

        steps_html += f'''
        <div class="workflow-step {state_class}" style="border-color: {stage_color['border']}; background: {stage_color['bg']};">
            <span class="workflow-icon" style="color: {stage_color['text']};">{stage["icon"]}</span>
            <span class="workflow-label" style="color: {stage_color['text']};">{stage["label"]}</span>
        </div>
        '''

        if i < len(WORKFLOW_STAGES) - 1:
            connector_class = "completed" if i < current_idx else ""
            connector_color = "#00D67E" if i < current_idx else stage_color["border"]
            steps_html += f'<div class="workflow-connector {connector_class}" style="background: {connector_color};"></div>'

    steps_html += '</div>'
    st.markdown(steps_html, unsafe_allow_html=True)

    if protocol_hash:
        st.caption(f"🔐 Protocol Hash: `{protocol_hash[:16]}...`")


def render_stage_progress(
    stage: str,
    completed: int,
    total: int,
    included: int = None,
    excluded: int = None
) -> None:
    """
    Render progress indicator for a specific stage.

    Args:
        stage: Stage identifier
        completed: Number of articles reviewed
        total: Total number of articles
        included: Number of included articles (optional)
        excluded: Number of excluded articles (optional)
    """
    stage_color = get_workflow_stage_color(stage)
    progress = completed / total if total > 0 else 0
    pct = int(progress * 100)

    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        progress_bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        st.markdown(f"""
        <div style="font-family: {TYPOGRAPHY['mono']}; font-size: 0.75rem; color: #808080;">
            [{pct:3d}%] {progress_bar} {completed}/{total}
        </div>
        """, unsafe_allow_html=True)
        st.progress(progress)

    with col2:
        if included is not None:
            st.metric("Included", included, delta_color="off")

    with col3:
        if excluded is not None:
            st.metric("Excluded", excluded, delta_color="off")


def render_stage_lock_banner(stage: str, message: str = "") -> None:
    """
    Render banner indicating a locked stage.

    Args:
        stage: Stage identifier
        message: Optional custom message
    """
    stage_color = get_workflow_stage_color(stage)
    default_msg = f"⚠ Stage '{stage.upper()}' is locked. Complete current stage to proceed."

    st.markdown(f"""
    <div style="
        border: 1px solid {stage_color['border']};
        background: {stage_color['bg']};
        padding: 1rem;
        margin: 0.5rem 0;
    ">
        <div style="
            font-family: {TYPOGRAPHY['mono']};
            font-size: 0.7rem;
            color: {stage_color['text']};
            letter-spacing: 0.1em;
        ">
            🔒 {message or default_msg}
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_canonical_workflow_summary(
    session_state: Dict,
    current_stage: str
) -> None:
    """
    Render summary of canonical workflow state.

    Args:
        session_state: Session state dictionary
        current_stage: Current stage identifier
    """
    stage_color = get_workflow_stage_color(current_stage)

    st.markdown(f"""
    <div style="
        border: 1px solid #252525;
        background: #0D0D0D;
        padding: 1rem;
        margin: 1rem 0;
    ">
        <div style="
            font-family: {TYPOGRAPHY['mono']};
            font-size: 0.6rem;
            color: #00c8d7;
            letter-spacing: 0.15em;
            margin-bottom: 0.75rem;
            border-bottom: 1px solid #1A1A1A;
            padding-bottom: 0.5rem;
        ">
            ▸ CANONICAL WORKFLOW STATE
        </div>
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem;">
            <div>
                <div style="font-family: {TYPOGRAPHY['mono']}; font-size: 0.6rem; color: #4A4A4A; text-transform: uppercase; letter-spacing: 0.1em;">
                    Current Stage
                </div>
                <div style="font-family: {TYPOGRAPHY['mono']}; font-size: 1rem; color: {stage_color['text']}; margin-top: 0.25rem;">
                    {current_stage.upper()}
                </div>
            </div>
            <div>
                <div style="font-family: {TYPOGRAPHY['mono']}; font-size: 0.6rem; color: #4A4A4A; text-transform: uppercase; letter-spacing: 0.1em;">
                    Total Articles
                </div>
                <div style="font-family: {TYPOGRAPHY['mono']}; font-size: 1rem; color: #E5E5E5; margin-top: 0.25rem;">
                    {session_state.get('total_count', 0)}
                </div>
            </div>
            <div>
                <div style="font-family: {TYPOGRAPHY['mono']}; font-size: 0.6rem; color: #4A4A4A; text-transform: uppercase; letter-spacing: 0.1em;">
                    Completed
                </div>
                <div style="font-family: {TYPOGRAPHY['mono']}; font-size: 1rem; color: #E5E5E5; margin-top: 0.25rem;">
                    {session_state.get('current_index', 0)} / {session_state.get('total_count', 0)}
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
