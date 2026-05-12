"""
APOLLO Scientific Design System - Audit Components

Components for visualizing audit chain integrity and tampering detection.

PURPOSE:
- Display session hash and protocol hash
- Show audit chain verification status
- Indicate tampering detection
- Track researcher actions
"""

import streamlit as st
from typing import Dict, List, Optional
from src.ui.design_system.semantic_colors import SEMANTIC_COLORS, get_semantic_color
from src.ui.design_system.typography import TYPOGRAPHY


def render_audit_status_badge(
    status: str,
    show_label: bool = True
) -> None:
    """
    Render audit status badge.

    Args:
        status: 'VERIFIED', 'MISMATCH', 'PENDING'
        show_label: Whether to show full label
    """
    semantic = get_semantic_color(status)

    labels = {
        "VERIFIED": "✓ VERIFIED",
        "MISMATCH": "✗ MISMATCH",
        "PENDING": "○ PENDING"
    }

    label = labels.get(status, status) if show_label else ""

    st.markdown(f"""
    <span style="
        display: inline-flex;
        align-items: center;
        gap: 0.25rem;
        padding: 0.2rem 0.5rem;
        border: 1px solid {semantic['border']};
        background: {semantic['bg']};
        font-family: {TYPOGRAPHY['mono']};
        font-size: 0.65rem;
        font-weight: 600;
        color: {semantic['text']};
        letter-spacing: 0.05em;
    ">
        {label}
    </span>
    """, unsafe_allow_html=True)


def render_hash_verification_panel(
    session_hash: str = "",
    protocol_hash: str = "",
    audit_valid: bool = True,
    audit_errors: List[str] = None
) -> None:
    """
    Render hash verification panel.

    Args:
        session_hash: Session SHA256 hash
        protocol_hash: Protocol hash
        audit_valid: Whether audit chain is valid
        audit_errors: List of audit chain errors
    """
    audit_semantic = get_semantic_color("VERIFIED" if audit_valid else "AUDIT_MISMATCH")

    errors_html = ""
    if audit_errors:
        errors_html = """
        <div style="
            margin-top: 0.75rem;
            padding: 0.5rem;
            border: 1px solid #FF4757;
            background: rgba(255, 71, 87, 0.1);
            font-family: {TYPOGRAPHY['mono']};
            font-size: 0.65rem;
            color: #FF4757;
        ">
            <strong>Audit Chain Errors:</strong><br>
            {errors}
        </div>
        """.format(
            TYPOGRAPHY=TYPOGRAPHY,
            errors="<br>".join([f"• {e}" for e in audit_errors])
        )

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
            ▸ HASH VERIFICATION
        </div>

        <div style="
            display: grid;
            gap: 0.5rem;
        ">
            <div style="
                display: flex;
                justify-content: space-between;
                padding: 0.5rem;
                border: 1px solid #1A1A1A;
                background: #111111;
            ">
                <span style="font-family: {TYPOGRAPHY['mono']}; font-size: 0.6rem; color: #808080;">SESSION HASH</span>
                <span style="font-family: {TYPOGRAPHY['mono']}; font-size: 0.7rem; color: #E5E5E5;">{session_hash[:24] if session_hash else 'N/A'}...</span>
            </div>

            <div style="
                display: flex;
                justify-content: space-between;
                padding: 0.5rem;
                border: 1px solid #1A1A1A;
                background: #111111;
            ">
                <span style="font-family: {TYPOGRAPHY['mono']}; font-size: 0.6rem; color: #808080;">PROTOCOL HASH</span>
                <span style="font-family: {TYPOGRAPHY['mono']}; font-size: 0.7rem; color: #E5E5E5;">{protocol_hash[:24] if protocol_hash else 'N/A'}...</span>
            </div>

            <div style="
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 0.5rem;
                border: 1px solid {audit_semantic['border']};
                background: {audit_semantic['bg']};
            ">
                <span style="font-family: {TYPOGRAPHY['mono']}; font-size: 0.6rem; color: {audit_semantic['text']};">AUDIT CHAIN</span>
                <span style="font-family: {TYPOGRAPHY['mono']}; font-size: 0.7rem; color: {audit_semantic['text']}; font-weight: 600;">
                    {'VALID ✓' if audit_valid else 'INVALID ✗'}
                </span>
            </div>
        </div>

        {errors_html}
    </div>
    """, unsafe_allow_html=True)


def render_audit_event_log(events: List[Dict]) -> None:
    """
    Render audit event log timeline.

    Args:
        events: List of audit chain events
    """
    if not events:
        st.caption("No audit events recorded")
        return

    st.markdown(f"""
    <div style="
        border: 1px solid #252525;
        background: #0D0D0D;
        padding: 1rem;
        margin: 0.5rem 0;
        max-height: 400px;
        overflow-y: auto;
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
            ▸ AUDIT CHAIN ({len(events)} events)
        </div>
    """, unsafe_allow_html=True)

    for i, event in enumerate(events):
        event_num = len(events) - i

        st.markdown(f"""
        <div style="
            font-family: {TYPOGRAPHY['mono']};
            font-size: 0.65rem;
            padding: 0.5rem 0;
            border-left: 2px solid #00c8d7;
            padding-left: 0.75rem;
            margin-left: 0.25rem;
        ">
            <div style="color: #4A4A4A; margin-bottom: 0.25rem;">
                #{event_num:04d} [{event.get('stage', 'N/A').upper()}]
            </div>
            <div style="color: #E5E5E5;">
                <span style="color: #FFB020;">{event.get('reviewer_id', 'UNKNOWN')}</span>
                <span style="color: #808080;">→</span>
                <span style="color: {get_semantic_color(event.get('decision', '').upper())['text']};">{event.get('decision', '').upper()}</span>
            </div>
            <div style="color: #4A4A4A; margin-top: 0.25rem;">
                {event.get('timestamp', '')[:19]}
            </div>
            <div style="color: #4A4A4A; font-size: 0.6rem; margin-top: 0.25rem; word-break: break-all;">
                Hash: {event.get('current_hash', 'N/A')[:16]}...
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


def render_tamper_detection_alert() -> None:
    """Render critical alert for detected tampering."""
    st.error("⚠️ **CRITICAL: Audit chain integrity compromised.** Evidence of tampering detected in the session history. Do not use this session for publication.")


def render_session_integrity_summary(
    session_data: Dict,
    audit_valid: bool
) -> None:
    """
    Render session integrity summary.

    Args:
        session_data: Session state dictionary
        audit_valid: Whether audit chain is valid
    """
    integrity = "INTACT" if audit_valid else "COMPROMISED"
    semantic = get_semantic_color("VERIFIED" if audit_valid else "AUDIT_MISMATCH")

    st.markdown(f"""
    <div style="
        border: 1px solid {semantic['border']};
        background: {semantic['bg']};
        padding: 1rem;
        margin: 0.5rem 0;
    ">
        <div style="
            font-family: {TYPOGRAPHY['mono']};
            font-size: 0.6rem;
            color: {semantic['text']};
            letter-spacing: 0.15em;
            margin-bottom: 0.5rem;
        ">
            ▸ SESSION INTEGRITY: {integrity}
        </div>
        <div style="
            font-family: {TYPOGRAPHY['mono']};
            font-size: 0.7rem;
            color: #808080;
        ">
            Session ID: {session_data.get('session_id', 'N/A')[:16]}... |
            Schema: v{session_data.get('schema_version', 'N/A')} |
            Researcher: {session_data.get('researcher_id', 'N/A')}
        </div>
    </div>
    """, unsafe_allow_html=True)
