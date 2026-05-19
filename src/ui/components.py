"""
APOLLO UI Primitives - Reusable Terminal-Style Components

Forensic workstation aesthetic components for evidence analysis interfaces.
"""
import streamlit as st
from typing import Optional, List, Dict, Tuple
from src.ui.theme import (
    COLORS, TYPOGRAPHY, SPACING, get_status_badge, 
    render_status_badge, render_lit_type_badge, render_metric_block,
    render_decision_card, render_telemetry_row, render_timeline_event,
    render_audit_entry, render_stage_indicator
)


def terminal_header(title: str, subtitle: str = "", status: str = None):
    """Render clean section header."""
    status_html = ""
    if status:
        status_html = f'<span style="color:{COLORS["cyan_dim"]};margin-left:0.75rem;font-size:0.8rem;">• {status}</span>'

    st.markdown(f"""
    <div style="padding-bottom:1rem;margin-bottom:1.5rem;border-bottom:1px solid {COLORS['border_light']};">
        <div style="font-family:{TYPOGRAPHY['sans']};font-size:0.7rem;color:{COLORS['text_muted']};margin-bottom:0.5rem;text-transform:uppercase;letter-spacing:0.1em;">
            APOLLO {status_html}
        </div>
        <h2 style="font-family:{TYPOGRAPHY['sans']};font-size:1.25rem;color:{COLORS['text_primary']};margin:0;font-weight:600;">
            {title}
        </h2>
        {f'<div style="font-family:{TYPOGRAPHY["sans"]};font-size:0.875rem;color:{COLORS["text_secondary"]};margin-top:0.5rem;">{subtitle}</div>' if subtitle else ''}
    </div>
    """, unsafe_allow_html=True)


def section_header(title: str, description: str = ""):
    """Render clean section header."""
    desc_html = f'<div style="font-family:{TYPOGRAPHY["sans"]};font-size:0.8rem;color:{COLORS["text_secondary"]};margin-top:0.25rem;">{description}</div>' if description else ""
    st.markdown(f"""
    <div style="margin: 1.5rem 0 1rem 0;">
        <div style="font-family:{TYPOGRAPHY['sans']};font-size:0.75rem;color:{COLORS['cyan']};font-weight:500;letter-spacing:0.05em;padding-bottom:0.5rem;display:inline-block;border-bottom:2px solid {COLORS['cyan']};">
            {title.upper()}
        </div>
        {desc_html}
    </div>
    """, unsafe_allow_html=True)


def status_badge(status: str, key: str = None):
    """Render a status badge (INCLUDED, EXCLUDED, etc.)."""
    label, color = get_status_badge(status)
    st.markdown(
        f'<span style="background:{color};color:#000;padding:2px 8px;font-family:{TYPOGRAPHY["mono"]};font-size:0.7rem;font-weight:600;letter-spacing:0.05em;">{label}</span>',
        unsafe_allow_html=True
    )


def lit_type_badge(lit_type: str):
    """Render literature type badge (WL/GL)."""
    st.markdown(render_lit_type_badge(lit_type), unsafe_allow_html=True)


def metric_tile(label: str, value: str, delta: str = None, color: str = None, style: str = "default"):
    """Render a metric tile in terminal style."""
    if style == "inline":
        delta_html = f' <span style="color:{COLORS["text_muted"]};">({delta})</span>' if delta else ""
        st.markdown(
            f'<div style="font-family:{TYPOGRAPHY["mono"]};font-size:0.8rem;padding:0.5rem;background:{COLORS["bg_card"]};border:1px solid {COLORS["border_light"]};">'
            f'<span style="color:{COLORS["text_muted"]};">{label}:</span> '
            f'<span style="color:{color or COLORS["cyan"]};font-weight:600;">{value}</span>'
            f'{delta_html}'
            f'</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(render_metric_block(label, value, delta, color), unsafe_allow_html=True)


def telemetry_panel(data: Dict[str, Tuple[str, str]], title: str = "TELEMETRY"):
    """Render a telemetry panel with key-value pairs."""
    with st.container():
        st.markdown(f'''
        <div style="border:1px solid {COLORS['border_light']};background:{COLORS['bg_card']};padding:1rem;">
            <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.6rem;color:{COLORS['cyan']};letter-spacing:0.2em;margin-bottom:0.75rem;border-bottom:1px solid {COLORS['border']};padding-bottom:0.5rem;">
                ▸ {title}
            </div>
        ''' + "".join([render_telemetry_row(k, v[0], v[1]) for k, v in data.items()]) + '''
        </div>
        ''', unsafe_allow_html=True)


def decision_card(title: str, decision: str, metadata: Dict[str, str]):
    """Render a structured decision card."""
    st.markdown(render_decision_card(title, decision, metadata), unsafe_allow_html=True)


def timeline_view(events: List[Dict], title: str = "TRACEABILITY"):
    """Render a timeline of events."""
    st.markdown(f'''
    <div style="border:1px solid {COLORS['border_light']};background:{COLORS['bg_card']};padding:1rem;">
        <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.6rem;color:{COLORS['cyan']};letter-spacing:0.2em;margin-bottom:0.75rem;border-bottom:1px solid {COLORS['border']};padding-bottom:0.5rem;">
            ▸ {title}
        </div>
    ''' + "".join([
        render_timeline_event(e.get("timestamp", ""), e.get("event", ""), e.get("details", ""))
        for e in events
    ]) + '</div>', unsafe_allow_html=True)


def audit_log_view(entries: List[Dict], title: str = "AUDIT TRAIL"):
    """Render an audit log view."""
    if not entries:
        st.caption("No audit entries")
        return
    
    st.markdown(f'''
    <div style="border:1px solid {COLORS['border_light']};background:{COLORS['bg_card']};padding:1rem;max-height:400px;overflow-y:auto;">
        <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.6rem;color:{COLORS['cyan']};letter-spacing:0.2em;margin-bottom:0.75rem;border-bottom:1px solid {COLORS['border']};padding-bottom:0.5rem;">
            ▸ {title}
        </div>
    ''' + "".join([
        render_audit_entry(e.get("timestamp", ""), e.get("actor", ""), e.get("action", ""), e.get("target", ""))
        for e in entries
    ]) + '</div>', unsafe_allow_html=True)


def progress_bar(current: int, total: int, stage: str = "", show_pct: bool = True):
    """Render terminal-style progress bar."""
    pct = int((current / total * 100)) if total > 0 else 0
    pct_str = f"[{pct:3d}%]"
    bar_len = 30
    filled = int(bar_len * current / total) if total > 0 else 0
    bar = "█" * filled + "░" * (bar_len - filled)
    
    stage_str = f" {stage}" if stage else ""
    
    st.markdown(
        f'<div style="font-family:{TYPOGRAPHY["mono"]};font-size:0.75rem;color:{COLORS["text_secondary"]};">'
        f'{pct_str} {bar} {current}/{total}{stage_str}'
        f'</div>',
        unsafe_allow_html=True
    )
    
    st.progress(pct / 100)


def stage_indicator(stage: str, status: str):
    """Render a compact stage indicator."""
    st.markdown(render_stage_indicator(stage, status), unsafe_allow_html=True)


def structured_card(content: str, title: str = None, border_color: str = None):
    """Render a structured card with optional title."""
    border = border_color or COLORS["border_light"]
    title_html = f'''
    <div style="font-family:{TYPOGRAPHY['mono']};font-size:0.65rem;color:{COLORS['cyan']};letter-spacing:0.1em;margin-bottom:0.75rem;padding-bottom:0.5rem;border-bottom:1px solid {COLORS['border']};">
        ▸ {title.upper()}
    </div>
    ''' if title else ""
    
    st.markdown(f'''
    <div style="border:1px solid {border};background:{COLORS['bg_card']};padding:1rem;">
        {title_html}
        {content}
    </div>
    ''', unsafe_allow_html=True)


def terminal_stream(lines: List[str], max_lines: int = 50):
    """Render terminal-style activity stream."""
    if len(lines) > max_lines:
        lines = lines[-max_lines:]
    
    st.markdown(
        f'<div style="font-family:{TYPOGRAPHY["mono"]};font-size:0.7rem;background:{COLORS['bg_surface']};border:1px solid {COLORS['border']};padding:1rem;max-height:300px;overflow-y:auto;color:{COLORS['text_secondary']};">' +
        "<br>".join([f'<span style="color:{COLORS["cyan_dim"]};">$</span> {line}' for line in lines]) +
        '</div>',
        unsafe_allow_html=True
    )


def code_block(content: str, language: str = ""):
    """Render code block in terminal style."""
    st.markdown(
        f'<pre style="font-family:{TYPOGRAPHY["mono"]};font-size:0.7rem;background:{COLORS['bg_surface']};border:1px solid {COLORS['border']};padding:1rem;overflow-x:auto;color:{COLORS['text_primary']};">{content}</pre>',
        unsafe_allow_html=True
    )


def data_table(rows: List[Dict], columns: List[str] = None):
    """Render data table in terminal style."""
    if not rows:
        st.caption("No data")
        return
    
    if not columns:
        columns = list(rows[0].keys()) if rows else []
    
    header = " | ".join([f'<th style="text-align:left;padding:0.5rem;border-bottom:1px solid {COLORS["border"]};font-family:{TYPOGRAPHY["mono"]};font-size:0.65rem;color:{COLORS["cyan"]};text-transform:upperpercase;">{c}</th>' for c in columns])
    body = ""
    for row in rows:
        cells = " | ".join([f'<td style="padding:0.5rem;border-bottom:1px solid {COLORS["border"]};font-family:{TYPOGRAPHY["mono"]};font-size:0.7rem;color:{COLORS["text_secondary"]};">{row.get(c, "")}</td>' for c in columns])
        body += f"<tr>{cells}</tr>"
    
    st.markdown(
        f'<table style="width:100%;border-collapse:collapse;">{header}{body}</table>'.replace("<th", "<thead><th").replace("</th>", "</th></thead>").replace("<tr>", "<tbody><tr>").replace("</tr>", "</tr></tbody>"),
        unsafe_allow_html=True
    )


def operational_status(status: str, label: str = None):
    """Render operational status indicator."""
    colors = {
        "online": COLORS["success"],
        "active": COLORS["cyan"],
        "idle": COLORS["text_muted"],
        "error": COLORS["error"],
        "warning": COLORS["warning"],
    }
    color = colors.get(status.lower(), COLORS["text_muted"])
    label_text = label or status.upper()
    
    st.markdown(
        f'<span style="display:inline-flex;align-items:center;gap:0.5rem;font-family:{TYPOGRAPHY["mono"]};font-size:0.65rem;color:{color};">'
        f'<span style="width:6px;height:6px;background:{color};border-radius:50%;"></span>'
        f'{label_text}</span>',
        unsafe_allow_html=True
    )


def provenance_indicator(source: str, count: int = None):
    """Render dataset provenance indicator."""
    count_str = f" [{count}]" if count else ""
    st.markdown(
        f'<span style="font-family:{TYPOGRAPHY["mono"]};font-size:0.65rem;color:{COLORS["text_muted"]};border:1px solid {COLORS["border"]};padding:2px 6px;">'
        f'{source.upper()}{count_str}'
        f'</span>',
        unsafe_allow_html=True
    )


def criteria_panel(criteria: Dict[str, str], title: str = "CRITERIA"):
    """Render criteria list in terminal style."""
    items = "".join([
        f'<div style="display:flex;gap:1rem;padding:0.25rem 0;font-family:{TYPOGRAPHY["mono"]};font-size:0.7rem;">'
        f'<span style="color:{COLORS["cyan_dim"]};min-width:50px;">{k}:</span>'
        f'<span style="color:{COLORS["text_secondary"]};">{v}</span></div>'
        for k, v in criteria.items()
    ])
    
    st.markdown(
        f'<div style="border:1px solid {COLORS["border_light"]};background:{COLORS["bg_card"]};padding:1rem;">'
        f'<div style="font-family:{TYPOGRAPHY["mono"]};font-size:0.6rem;color:{COLORS["cyan"]};letter-spacing:0.15em;margin-bottom:0.75rem;">▸ {title}</div>'
        f'{items}</div>',
        unsafe_allow_html=True
    )


def action_button(label: str, icon: str = "", disabled: bool = False, style: str = "default"):
    """Render action button in terminal style."""
    if style == "primary":
        return st.button(f"{icon} {label}" if icon else label, type="primary", disabled=disabled, use_container_width=True)
    elif style == "secondary":
        return st.button(f"{icon} {label}" if icon else label, type="secondary", disabled=disabled, use_container_width=True)
    else:
        return st.button(f"{icon} {label}" if icon else label, disabled=disabled, use_container_width=True)


def divider():
    """Render terminal-style divider."""
    st.markdown(
        f'<div style="border-top:1px solid {COLORS["border"]};margin:1rem 0;"></div>',
        unsafe_allow_html=True
    )


def empty_state(message: str):
    """Render empty state message."""
    st.markdown(
        f'<div style="font-family:{TYPOGRAPHY["mono"]};font-size:0.8rem;color:{COLORS["text_muted"]};text-align:center;padding:2rem;">{message}</div>',
        unsafe_allow_html=True
    )


def kappa_display(score: float, interpretation: str, n_reviewers: int):
    """Render Cohen's kappa display."""
    color = COLORS["success"] if score >= 0.8 else COLORS["warning"] if score >= 0.6 else COLORS["error"]
    st.markdown(
        f'<div style="border:1px solid {COLORS["border_light"]};background:{COLORS["bg_card"]};padding:1rem;">'
        f'<div style="font-family:{TYPOGRAPHY["mono"]};font-size:0.6rem;color:{COLORS["cyan"]};letter-spacing:0.2em;margin-bottom:0.5rem;">▸ INTER-RATER RELIABILITY</div>'
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'<div style="font-family:{TYPOGRAPHY["mono"]};font-size:2rem;font-weight:bold;color:{color};">κ = {score:.3f}</div>'
        f'<div style="font-family:{TYPOGRAPHY["mono"]};font-size:0.7rem;color:{COLORS["text_secondary"]};text-align:right;">'
        f'{interpretation}<br>n = {n_reviewers} reviewers'
        f'</div></div></div>',
        unsafe_allow_html=True
    )


def conflict_resolution_card(article_title: str, reviewer1: str, decision1: str, reviewer2: str, decision2: str):
    """Render conflict resolution card."""
    badge1 = render_status_badge(decision1)
    badge2 = render_status_badge(decision2)
    
    st.markdown(
        f'''<div style="border:1px solid {COLORS["status_conflict"]};background:{COLORS["bg_card"]};padding:1rem;">
            <div style="font-family:{TYPOGRAPHY["mono"]};font-size:0.7rem;color:{COLORS["text_secondary"]};margin-bottom:0.5rem;">{article_title[:80]}...</div>
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <div><span style="color:{COLORS["warning"]};font-family:{TYPOGRAPHY["mono"]};font-size:0.65rem;">{reviewer1}:</span> {badge1}</div>
                <div style="color:{COLORS["text_muted"]};">vs</div>
                <div><span style="color:{COLORS["warning"]};font-family:{TYPOGRAPHY["mono"]};font-size:0.65rem;">{reviewer2}:</span> {badge2}</div>
            </div>
        </div>''',
        unsafe_allow_html=True
    )