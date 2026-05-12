"""
APOLLO Scientific Design System - Session Lineage Panel

Visual component for displaying session lineage and ancestor tracking.

PURPOSE:
- Show session lineage (parent sessions, forks)
- Display session creation metadata
- Track session evolution through replay operations
- Encode researcher identity and timestamps
"""

import streamlit as st
from typing import Dict, List, Optional
from datetime import datetime
from src.ui.design_system.semantic_colors import SEMANTIC_COLORS, get_semantic_color
from src.ui.design_system.typography import TYPOGRAPHY


def render_session_lineage_panel(
    session_data: Dict,
    lineage_info: Dict = None
) -> None:
    """
    Render session lineage panel.

    Args:
        session_data: Session state dictionary
        lineage_info: Optional lineage metadata (parent_session_id, created_from_replay, etc.)
    """
    st.markdown(f"""
    <div style="
        border: 1px solid #252525;
        background: #0D0D0D;
        padding: 1rem;
        margin: 0.5rem 0;
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
            ▸ SESSION LINEAGE
        </div>

        <!-- Session Identity -->
        <div style="
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 0.5rem;
            margin-bottom: 0.75rem;
        ">
            <div style="
                padding: 0.5rem;
                background: #111111;
                border: 1px solid #1A1A1A;
            ">
                <div style="
                    font-family: {TYPOGRAPHY['mono']};
                    font-size: 0.55rem;
                    color: #4A4A4A;
                    text-transform: uppercase;
                    letter-spacing: 0.1em;
                    margin-bottom: 0.25rem;
                ">Session ID</div>
                <div style="
                    font-family: {TYPOGRAPHY['mono']};
                    font-size: 0.65rem;
                    color: #E5E5E5;
                    word-break: break-all;
                ">
                    {session_data.get('session_id', 'N/A')}
                </div>
            </div>

            <div style="
                padding: 0.5rem;
                background: #111111;
                border: 1px solid #1A1A1A;
            ">
                <div style="
                    font-family: {TYPOGRAPHY['mono']};
                    font-size: 0.55rem;
                    color: #4A4A4A;
                    text-transform: uppercase;
                    letter-spacing: 0.1em;
                    margin-bottom: 0.25rem;
                ">Researcher</div>
                <div style="
                    font-family: {TYPOGRAPHY['mono']};
                    font-size: 0.65rem;
                    color: #FFB020;
                ">
                    {session_data.get('researcher_id', 'UNKNOWN')}
                </div>
            </div>

            <div style="
                padding: 0.5rem;
                background: #111111;
                border: 1px solid #1A1A1A;
            ">
                <div style="
                    font-family: {TYPOGRAPHY['mono']};
                    font-size: 0.55rem;
                    color: #4A4A4A;
                    text-transform: uppercase;
                    letter-spacing: 0.1em;
                    margin-bottom: 0.25rem;
                ">Created</div>
                <div style="
                    font-family: {TYPOGRAPHY['mono']};
                    font-size: 0.65rem;
                    color: #E5E5E5;
                ">
                    {format_timestamp(session_data.get('created_at', ''))}
                </div>
            </div>

            <div style="
                padding: 0.5rem;
                background: #111111;
                border: 1px solid #1A1A1A;
            ">
                <div style="
                    font-family: {TYPOGRAPHY['mono']};
                    font-size: 0.55rem;
                    color: #4A4A4A;
                    text-transform: uppercase;
                    letter-spacing: 0.1em;
                    margin-bottom: 0.25rem;
                ">Last Saved</div>
                <div style="
                    font-family: {TYPOGRAPHY['mono']};
                    font-size: 0.65rem;
                    color: #E5E5E5;
                ">
                    {format_timestamp(session_data.get('last_saved', ''))}
                </div>
            </div>
        </div>

        <!-- Lineage Tree -->
        {render_lineage_tree(lineage_info, session_data)}

        <!-- Schema Version -->
        <div style="
            margin-top: 0.75rem;
            padding: 0.5rem;
            background: #0A0A0A;
            border: 1px solid #1A1A1A;
            font-family: {TYPOGRAPHY['mono']};
            font-size: 0.6rem;
            color: #808080;
        ">
            Schema v{session_data.get('schema_version', 'N/A')} |
            Protocol v{session_data.get('protocol_version', 'N/A')}
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_lineage_tree(lineage_info: Optional[Dict], session_data: Dict) -> str:
    """Render lineage tree visualization."""
    if not lineage_info:
        return render_no_lineage(session_data)

    parent_id = lineage_info.get("parent_session_id", "")
    replayed_from = lineage_info.get("replayed_from_bundle", "")
    fork_reason = lineage_info.get("fork_reason", "")

    tree_elements = []

    if parent_id:
        tree_elements.append(render_lineage_node("PARENT", parent_id, "#58A6FF"))
    if replayed_from:
        tree_elements.append(render_lineage_node("REPLAY SOURCE", replayed_from, "#00c8d7"))
    if fork_reason:
        tree_elements.append(render_fork_reason(fork_reason))

    if not tree_elements:
        return render_no_lineage(session_data)

    return f'''
    <div style="
        margin-top: 0.75rem;
        padding: 0.75rem;
        background: #0A0A0A;
        border: 1px solid #1A1A1A;
    ">
        <div style="
            font-family: {TYPOGRAPHY['mono']};
            font-size: 0.55rem;
            color: #4A4A4A;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            margin-bottom: 0.5rem;
        ">Ancestry</div>
        {''.join(tree_elements)}
    </div>
    '''


def render_lineage_node(label: str, value: str, color: str) -> str:
    """Render a lineage node."""
    return f'''
    <div style="
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-bottom: 0.5rem;
        font-family: {TYPOGRAPHY['mono']};
        font-size: 0.65rem;
    ">
        <span style="
            padding: 0.1rem 0.3rem;
            background: {color}20;
            border: 1px solid {color}50;
            color: {color};
            font-size: 0.55rem;
        ">
            {label}
        </span>
        <span style="color: #808080;">→</span>
        <span style="color: #E5E5E5; word-break: break-all;">{value[:24]}...</span>
    </div>
    '''


def render_fork_reason(reason: str) -> str:
    """Render fork reason."""
    return f'''
    <div style="
        margin-top: 0.5rem;
        padding: 0.5rem;
        background: rgba(255, 176, 32, 0.05);
        border-left: 2px solid #FFB020;
        font-family: {TYPOGRAPHY['mono']};
        font-size: 0.6rem;
        color: #808080;
    ">
        <span style="color: #FFB020;">FORK:</span> {reason}
    </div>
    '''


def render_no_lineage(session_data: Dict) -> str:
    """Render no lineage available message."""
    session_id = session_data.get('session_id', 'N/A')
    return f'''
    <div style="
        margin-top: 0.75rem;
        padding: 0.75rem;
        background: #0A0A0A;
        border: 1px solid #1A1A1A;
        font-family: {TYPOGRAPHY['mono']};
        font-size: 0.65rem;
        color: #4A4A4A;
        text-align: center;
    ">
        ◈ Genesis session: {session_id[:16]}...<br>
        <span style="color: #808080; font-size: 0.6rem;">
            No parent session or replay lineage
        </span>
    </div>
    '''


def format_timestamp(timestamp: str) -> str:
    """Format ISO timestamp for display."""
    if not timestamp:
        return "N/A"

    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return timestamp[:19] if len(timestamp) > 19 else timestamp


def render_session_stats(session_data: Dict) -> None:
    """
    Render session statistics summary.

    Args:
        session_data: Session state dictionary
    """
    st.markdown(f"""
    <div style="
        border: 1px solid #252525;
        background: #0D0D0D;
        padding: 1rem;
        margin: 0.5rem 0;
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
            ▸ SESSION STATISTICS
        </div>

        <div style="
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 0.5rem;
        ">
            <div style="text-align: center;">
                <div style="
                    font-family: {TYPOGRAPHY['mono']};
                    font-size: 1.5rem;
                    font-weight: 600;
                    color: #E5E5E5;
                ">
                    {session_data.get('total_count', 0)}
                </div>
                <div style="
                    font-family: {TYPOGRAPHY['mono']};
                    font-size: 0.55rem;
                    color: #4A4A4A;
                    text-transform: uppercase;
                ">Total</div>
            </div>

            <div style="text-align: center;">
                <div style="
                    font-family: {TYPOGRAPHY['mono']};
                    font-size: 1.5rem;
                    font-weight: 600;
                    color: #00D67E;
                ">
                    {session_data.get('included_count', 0)}
                </div>
                <div style="
                    font-family: {TYPOGRAPHY['mono']};
                    font-size: 0.55rem;
                    color: #4A4A4A;
                    text-transform: uppercase;
                ">Included</div>
            </div>

            <div style="text-align: center;">
                <div style="
                    font-family: {TYPOGRAPHY['mono']};
                    font-size: 1.5rem;
                    font-weight: 600;
                    color: #FF4757;
                ">
                    {session_data.get('excluded_count', 0)}
                </div>
                <div style="
                    font-family: {TYPOGRAPHY['mono']};
                    font-size: 0.55rem;
                    color: #4A4A4A;
                    text-transform: uppercase;
                ">Excluded</div>
            </div>
        </div>

        <div style="
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 0.5rem;
            margin-top: 0.75rem;
        ">
            <div style="
                padding: 0.5rem;
                background: #111111;
                border: 1px solid #1A1A1A;
                text-align: center;
            ">
                <div style="font-family: {TYPOGRAPHY['mono']}; font-size: 0.6rem; color: #808080;">
                    Skipped: <span style="color: #58A6FF;">{session_data.get('skip_count', 0)}</span>
                </div>
            </div>
            <div style="
                padding: 0.5rem;
                background: #111111;
                border: 1px solid #1A1A1A;
                text-align: center;
            ">
                <div style="font-family: {TYPOGRAPHY['mono']}; font-size: 0.6rem; color: #808080;">
                    Discussion: <span style="color: #FFB020;">{session_data.get('discussion_count', 0)}</span>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
