"""
APOLLO Scientific Design System - Protocol Authority Banner

Visual component for displaying protocol authority and session lineage.

PURPOSE:
- Display protocol hash for authority verification
- Show session lineage information
- Encode protocol state (draft, locked, active)
- Display researcher identity
"""

import streamlit as st
from typing import Dict, Optional
from datetime import datetime
from src.ui.design_system.semantic_colors import (
    SEMANTIC_COLORS, get_semantic_color, WORKFLOW_STAGE_COLORS
)
from src.ui.design_system.typography import TYPOGRAPHY


def render_protocol_authority_banner(
    protocol_summary: Dict,
    session_info: Dict = None,
    compact: bool = False
) -> None:
    """
    Render protocol authority banner.

    Args:
        protocol_summary: Protocol summary dictionary from DynamicProtocol.get_summary()
        session_info: Optional session info dictionary
        compact: Whether to render in compact mode
    """
    state = protocol_summary.get("state", "draft")
    protocol_hash = protocol_summary.get("hash", "")

    if state == "locked":
        state_semantic = get_semantic_color("PROTOCOL_LOCKED")
        state_label = "LOCKED"
    elif state == "active_session":
        state_semantic = get_semantic_color("ACTIVE")
        state_label = "ACTIVE SESSION"
    else:
        state_semantic = get_semantic_color("PROTOCOL_DRAFT")
        state_label = "DRAFT"

    if compact:
        render_compact_protocol_banner(protocol_summary, state_semantic, state_label)
    else:
        render_full_protocol_banner(protocol_summary, state_semantic, state_label, session_info)


def render_full_protocol_banner(
    protocol_summary: Dict,
    state_semantic: Dict,
    state_label: str,
    session_info: Dict = None
) -> None:
    """Render full protocol authority banner."""
    st.markdown(f"""
    <div style="
        border: 1px solid #252525;
        background: #0D0D0D;
        padding: 1rem;
        margin: 0.5rem 0;
    ">
        <!-- Header Row -->
        <div style="
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
            padding-bottom: 0.75rem;
            border-bottom: 1px solid #1A1A1A;
        ">
            <div style="display: flex; align-items: center; gap: 1rem;">
                <span style="
                    font-size: 1.5rem;
                    color: #00c8d7;
                ">◈</span>
                <div>
                    <div style="
                        font-family: {TYPOGRAPHY['mono']};
                        font-size: 0.7rem;
                        color: #E5E5E5;
                        font-weight: 600;
                    ">
                        {protocol_summary.get('template_name', 'Custom Protocol') or 'Custom Protocol'}
                    </div>
                    <div style="
                        font-family: {TYPOGRAPHY['mono']};
                        font-size: 0.6rem;
                        color: #808080;
                    ">
                        v{protocol_summary.get('version', '1.0')}
                    </div>
                </div>
            </div>

            <div style="display: flex; align-items: center; gap: 1rem;">
                <span style="
                    padding: 0.25rem 0.75rem;
                    border: 1px solid {state_semantic['border']};
                    background: {state_semantic['bg']};
                    font-family: {TYPOGRAPHY['mono']};
                    font-size: 0.65rem;
                    font-weight: 600;
                    color: {state_semantic['text']};
                    letter-spacing: 0.05em;
                ">
                    {state_label}
                </span>
            </div>
        </div>

        <!-- Protocol Metrics -->
        <div style="
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 0.75rem;
            margin-bottom: 1rem;
        ">
            <div style="
                padding: 0.75rem;
                background: #111111;
                border: 1px solid #1A1A1A;
                text-align: center;
            ">
                <div style="
                    font-family: {TYPOGRAPHY['mono']};
                    font-size: 0.55rem;
                    color: #4A4A4A;
                    text-transform: uppercase;
                    letter-spacing: 0.1em;
                    margin-bottom: 0.25rem;
                ">EC Criteria</div>
                <div style="
                    font-family: {TYPOGRAPHY['mono']};
                    font-size: 1.25rem;
                    color: #FF4757;
                    font-weight: 600;
                ">
                    {protocol_summary.get('ec_count', 0)}
                </div>
            </div>

            <div style="
                padding: 0.75rem;
                background: #111111;
                border: 1px solid #1A1A1A;
                text-align: center;
            ">
                <div style="
                    font-family: {TYPOGRAPHY['mono']};
                    font-size: 0.55rem;
                    color: #4A4A4A;
                    text-transform: uppercase;
                    letter-spacing: 0.1em;
                    margin-bottom: 0.25rem;
                ">IC Criteria</div>
                <div style="
                    font-family: {TYPOGRAPHY['mono']};
                    font-size: 1.25rem;
                    color: #FFB020;
                    font-weight: 600;
                ">
                    {protocol_summary.get('ic_count', 0)}
                </div>
            </div>

            <div style="
                padding: 0.75rem;
                background: #111111;
                border: 1px solid #1A1A1A;
                text-align: center;
            ">
                <div style="
                    font-family: {TYPOGRAPHY['mono']};
                    font-size: 0.55rem;
                    color: #4A4A4A;
                    text-transform: uppercase;
                    letter-spacing: 0.1em;
                    margin-bottom: 0.25rem;
                ">Threshold</div>
                <div style="
                    font-family: {TYPOGRAPHY['mono']};
                    font-size: 1.25rem;
                    color: #00c8d7;
                    font-weight: 600;
                ">
                    {protocol_summary.get('wl_threshold', 0):.1f}
                </div>
            </div>
        </div>

        <!-- Protocol Hash -->
        <div style="
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.75rem;
            background: #0A0A0A;
            border: 1px solid #1A1A1A;
        ">
            <span style="
                font-family: {TYPOGRAPHY['mono']};
                font-size: 0.6rem;
                color: #808080;
            ">
                PROTOCOL HASH
            </span>
            <span style="
                font-family: {TYPOGRAPHY['mono']};
                font-size: 0.7rem;
                color: #00c8d7;
                word-break: break-all;
            ">
                {protocol_summary.get('hash', 'N/A') or 'N/A'}
            </span>
        </div>

        {render_locked_timestamp(protocol_summary) if protocol_summary.get('locked_at') else ''}
    </div>
    """, unsafe_allow_html=True)


def render_compact_protocol_banner(
    protocol_summary: Dict,
    state_semantic: Dict,
    state_label: str
) -> None:
    """Render compact protocol banner."""
    st.markdown(f"""
    <div style="
        display: flex;
        align-items: center;
        gap: 1rem;
        padding: 0.75rem 1rem;
        background: #0D0D0D;
        border: 1px solid #252525;
        margin: 0.5rem 0;
    ">
        <span style="font-size: 1rem; color: #00c8d7;">◈</span>
        <div style="flex: 1;">
            <span style="
                font-family: {TYPOGRAPHY['mono']};
                font-size: 0.7rem;
                color: #E5E5E5;
            ">
                v{protocol_summary.get('version', '1.0')} | {protocol_summary.get('ec_count', 0)}EC/{protocol_summary.get('ic_count', 0)}IC
            </span>
        </div>
        <span style="
            padding: 0.15rem 0.5rem;
            border: 1px solid {state_semantic['border']};
            background: {state_semantic['bg']};
            font-family: {TYPOGRAPHY['mono']};
            font-size: 0.6rem;
            font-weight: 600;
            color: {state_semantic['text']};
        ">
            {state_label}
        </span>
    </div>
    """, unsafe_allow_html=True)


def render_locked_timestamp(protocol_summary: Dict) -> str:
    """Render locked timestamp."""
    locked_at = protocol_summary.get('locked_at', '')
    if locked_at:
        try:
            dt = datetime.fromisoformat(locked_at.replace('Z', '+00:00'))
            formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        except:
            formatted_time = locked_at[:19]

        return f'''
        <div style="
            margin-top: 0.75rem;
            padding: 0.5rem;
            background: rgba(88, 166, 255, 0.05);
            border: 1px solid rgba(88, 166, 255, 0.2);
            font-family: {TYPOGRAPHY['mono']};
            font-size: 0.6rem;
            color: #808080;
        ">
            Protocol locked at: <span style="color: #58A6FF;">{formatted_time}</span>
        </div>
        '''
    return ''
