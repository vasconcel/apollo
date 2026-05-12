"""
APOLLO Scientific Design System - Reproducibility Components

Components for visualizing reproducibility state and deterministic execution.

PURPOSE:
- Display replay parity status
- Show checksum verification
- Indicate deterministic execution confirmation
- Track reproducibility bundle state
"""

import streamlit as st
from typing import Dict, Optional
from src.ui.design_system.semantic_colors import SEMANTIC_COLORS, get_semantic_color
from src.ui.design_system.typography import TYPOGRAPHY


def render_replay_verification_panel(
    original_hash: str = "",
    replay_hash: str = "",
    parity: bool = None,
    bundle_id: str = ""
) -> None:
    """
    Render replay verification panel.

    Args:
        original_hash: Original session hash
        replay_hash: Replayed session hash
        parity: Whether hashes match (True=match, False=mismatch, None=pending)
        bundle_id: Reproducibility bundle identifier
    """
    if parity is True:
        status_semantic = get_semantic_color("REPLAYED")
        status_text = "PARITY CONFIRMED ✓"
    elif parity is False:
        status_semantic = get_semantic_color("AUDIT_MISMATCH")
        status_text = "PARITY FAILED ✗"
    else:
        status_semantic = get_semantic_color("PENDING")
        status_text = "VERIFICATION PENDING ○"

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
            ▸ REPLAY VERIFICATION
        </div>

        <div style="display: grid; gap: 0.5rem;">
            {f'''
            <div style="
                display: flex;
                justify-content: space-between;
                padding: 0.5rem;
                border: 1px solid #1A1A1A;
                background: #111111;
            ">
                <span style="font-family: {TYPOGRAPHY['mono']}; font-size: 0.6rem; color: #808080;">ORIGINAL HASH</span>
                <span style="font-family: {TYPOGRAPHY['mono']}; font-size: 0.65rem; color: #E5E5E5;">{original_hash[:24] if original_hash else 'N/A'}...</span>
            </div>
            ''' if original_hash else ''}

            {f'''
            <div style="
                display: flex;
                justify-content: space-between;
                padding: 0.5rem;
                border: 1px solid #1A1A1A;
                background: #111111;
            ">
                <span style="font-family: {TYPOGRAPHY['mono']}; font-size: 0.6rem; color: #808080;">REPLAY HASH</span>
                <span style="font-family: {TYPOGRAPHY['mono']}; font-size: 0.65rem; color: #E5E5E5;">{replay_hash[:24] if replay_hash else 'N/A'}...</span>
            </div>
            ''' if replay_hash else ''}

            <div style="
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 0.5rem;
                border: 1px solid {status_semantic['border']};
                background: {status_semantic['bg']};
            ">
                <span style="font-family: {TYPOGRAPHY['mono']}; font-size: 0.6rem; color: {status_semantic['text']};">PARITY STATUS</span>
                <span style="font-family: {TYPOGRAPHY['mono']}; font-size: 0.7rem; color: {status_semantic['text']}; font-weight: 600;">
                    {status_text}
                </span>
            </div>

            {f'''
            <div style="
                display: flex;
                justify-content: space-between;
                padding: 0.5rem;
                border: 1px solid #1A1A1A;
                background: #111111;
            ">
                <span style="font-family: {TYPOGRAPHY['mono']}; font-size: 0.6rem; color: #808080;">BUNDLE ID</span>
                <span style="font-family: {TYPOGRAPHY['mono']}; font-size: 0.65rem; color: #00c8d7;">{bundle_id}</span>
            </div>
            ''' if bundle_id else ''}
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_determinism_status_indicator(
    is_deterministic: bool,
    explanation: str = ""
) -> None:
    """
    Render deterministic execution status indicator.

    Args:
        is_deterministic: Whether execution is deterministic
        explanation: Optional explanation text
    """
    semantic = get_semantic_color("DETERMINISTIC" if is_deterministic else "AUDIT_MISMATCH")

    status_icon = "◎" if is_deterministic else "⚠"
    status_text = "DETERMINISTIC" if is_deterministic else "NON-DETERMINISTIC"

    default_explanation = (
        "Session execution is deterministic: same input + same protocol = same output."
        if is_deterministic
        else "Non-deterministic behavior detected. Results may vary between runs."
    )

    st.markdown(f"""
    <div style="
        display: inline-flex;
        align-items: center;
        gap: 0.75rem;
        padding: 0.5rem 1rem;
        border: 1px solid {semantic['border']};
        background: {semantic['bg']};
    ">
        <span style="
            font-size: 1rem;
            color: {semantic['text']};
        ">
            {status_icon}
        </span>
        <div>
            <div style="
                font-family: {TYPOGRAPHY['mono']};
                font-size: 0.7rem;
                font-weight: 600;
                color: {semantic['text']};
                letter-spacing: 0.05em;
            ">
                {status_text}
            </div>
            <div style="
                font-family: {TYPOGRAPHY['mono']};
                font-size: 0.6rem;
                color: #808080;
                margin-top: 0.25rem;
            ">
                {explanation or default_explanation}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_checksum_verification_panel(
    checksums: Dict[str, str] = None,
    bundle_path: str = ""
) -> None:
    """
    Render checksum verification panel.

    Args:
        checksums: Dictionary of file paths to SHA256 checksums
        bundle_path: Path to reproducibility bundle
    """
    if not checksums:
        st.caption("No checksums available")
        return

    st.markdown(f"""
    <div style="
        border: 1px solid #252525;
        background: #0D0D0D;
        padding: 1rem;
        margin: 0.5rem 0;
        max-height: 300px;
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
            ▸ CHECKSUM VERIFICATION ({len(checksums)} files)
        </div>
    """, unsafe_allow_html=True)

    for filename, checksum in checksums.items():
        st.markdown(f"""
        <div style="
            display: flex;
            justify-content: space-between;
            padding: 0.25rem 0;
            border-bottom: 1px solid #1A1A1A;
            font-family: {TYPOGRAPHY['mono']};
            font-size: 0.65rem;
        ">
            <span style="color: #808080; max-width: 150px; overflow: hidden; text-overflow: ellipsis;">
                {filename}
            </span>
            <span style="color: #00c8d7; word-break: break-all;">
                {checksum[:32]}...
            </span>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


def render_reproducibility_bundle_summary(bundle_data: Dict) -> None:
    """
    Render reproducibility bundle summary.

    Args:
        bundle_data: ReproducibilityBundle data dictionary
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
            ▸ REPRODUCIBILITY BUNDLE
        </div>

        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.5rem;">
            <div style="
                padding: 0.5rem;
                border: 1px solid #1A1A1A;
                background: #111111;
            ">
                <div style="font-family: {TYPOGRAPHY['mono']}; font-size: 0.55rem; color: #4A4A4A; text-transform: uppercase;">Bundle ID</div>
                <div style="font-family: {TYPOGRAPHY['mono']}; font-size: 0.65rem; color: #E5E5E5;">{bundle_data.get('bundle_id', 'N/A')}</div>
            </div>

            <div style="
                padding: 0.5rem;
                border: 1px solid #1A1A1A;
                background: #111111;
            ">
                <div style="font-family: {TYPOGRAPHY['mono']}; font-size: 0.55rem; color: #4A4A4A; text-transform: uppercase;">Created</div>
                <div style="font-family: {TYPOGRAPHY['mono']}; font-size: 0.65rem; color: #E5E5E5;">{bundle_data.get('created_at', 'N/A')[:19]}</div>
            </div>

            <div style="
                padding: 0.5rem;
                border: 1px solid #1A1A1A;
                background: #111111;
            ">
                <div style="font-family: {TYPOGRAPHY['mono']}; font-size: 0.55rem; color: #4A4A4A; text-transform: uppercase;">Article Count</div>
                <div style="font-family: {TYPOGRAPHY['mono']}; font-size: 0.65rem; color: #E5E5E5;">{bundle_data.get('article_count', 0)}</div>
            </div>

            <div style="
                padding: 0.5rem;
                border: 1px solid #1A1A1A;
                background: #111111;
            ">
                <div style="font-family: {TYPOGRAPHY['mono']}; font-size: 0.55rem; color: #4A4A4A; text-transform: uppercase;">Path</div>
                <div style="font-family: {TYPOGRAPHY['mono']}; font-size: 0.6rem; color: #00c8d7; word-break: break-all;">{bundle_data.get('bundle_path', 'N/A')}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_bundle_file_manifest(files: List[str]) -> None:
    """
    Render bundle file manifest.

    Args:
        files: List of file paths in the bundle
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
            ▸ BUNDLE CONTENTS ({len(files)} files)
        </div>
    """, unsafe_allow_html=True)

    for filepath in files:
        import os
        filename = os.path.basename(filepath)

        file_colors = {
            "protocol.json": "#58A6FF",
            "session.json": "#00c8d7",
            "audit_log.json": "#FFB020",
            "manifest.json": "#00D67E",
            "checksums.sha256": "#808080",
            "environment.json": "#4A4A4A",
        }
        color = file_colors.get(filename, "#E5E5E5")

        st.markdown(f"""
        <div style="
            font-family: {TYPOGRAPHY['mono']};
            font-size: 0.65rem;
            padding: 0.25rem 0;
            border-bottom: 1px solid #1A1A1A;
        ">
            <span style="color: {color};">•</span>
            <span style="color: #E5E5E5; margin-left: 0.5rem;">{filename}</span>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)
