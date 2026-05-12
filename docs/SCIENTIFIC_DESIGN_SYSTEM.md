# APOLLO Scientific Design System

## Overview

The APOLLO Scientific Design System encodes canonical scientific workflow semantics, provenance lineage, reproducibility guarantees, audit chain integrity, and deterministic screening authority into visual tokens.

**This is NOT a cosmetic redesign.** The UI must visually encode:
- Canonical workflow authority
- Provenance lineage
- Reproducibility guarantees
- Audit integrity
- Deterministic execution
- Scientific state transitions

## Design Principles

### DO NOT:
- Redesign into a generic dashboard
- Introduce visual patterns that hide workflow order
- Weaken canonical workflow enforcement
- Add disconnected UI widgets
- Bypass ScreeningSession authority
- Duplicate business logic in UI

### PRESERVE:
- Canonical execution flow
- Deterministic behavior
- Reproducibility semantics
- Audit-chain visibility
- Export authority
- Protocol authority

## Module Structure

```
src/ui/design_system/
├── __init__.py                 # Module exports
├── semantic_colors.py          # Semantic color tokens
├── typography.py               # Typography scale and styles
├── spacing.py                  # Spacing tokens
├── workflow_components.py      # Workflow visualization
├── provenance_components.py    # Provenance visualization
├── audit_components.py         # Audit chain visualization
├── reproducibility_components.py  # Reproducibility visualization
├── article_decision_card.py     # Article decision display
├── protocol_authority_banner.py  # Protocol authority banner
└── session_lineage_panel.py     # Session lineage panel
```

## Semantic Color Tokens

### Decision States

| State | Background | Border | Text | Description |
|-------|------------|--------|------|-------------|
| INCLUDED | rgba(0, 214, 126, 0.15) | #00D67E | #00D67E | Article passed screening |
| EXCLUDED | rgba(255, 71, 87, 0.15) | #FF4757 | #FF4757 | Article failed screening |
| PENDING | rgba(128, 128, 128, 0.15) | #808080 | #808080 | Awaiting review |
| SKIP | rgba(88, 166, 255, 0.15) | #58A6FF | #58A6FF | Temporarily skipped |
| NEEDS_DISCUSSION | rgba(255, 176, 32, 0.15) | #FFB020 | #FFB020 | Requires team discussion |

### Audit & Reproducibility States

| State | Background | Border | Text | Description |
|-------|------------|--------|------|-------------|
| VERIFIED | rgba(0, 214, 126, 0.15) | #00D67E | #00D67E | Audit chain valid |
| AUDIT_MISMATCH | rgba(255, 71, 87, 0.2) | #FF4757 | #FF4757 | Tampering detected |
| REPLAYED | rgba(0, 200, 215, 0.15) | #00c8d7 | #00c8d7 | Session replayed |
| DETERMINISTIC | rgba(0, 200, 215, 0.15) | #00c8d7 | #00c8d7 | Deterministic execution |

### Literature Type States

| State | Background | Border | Text | Description |
|-------|------------|--------|------|-------------|
| WL | rgba(0, 214, 126, 0.15) | #00D67E | #00D67E | White Literature |
| GL | rgba(255, 176, 32, 0.15) | #FFB020 | #FFB020 | Grey Literature |

### Workflow Stage Colors

| Stage | Icon | Background | Border | Text | Description |
|-------|------|------------|--------|------|-------------|
| protocol | ◈ | rgba(88, 166, 255, 0.15) | #58A6FF | #58A6FF | Protocol Configuration |
| ec | ⊘ | rgba(255, 71, 87, 0.15) | #FF4757 | #FF4757 | Exclusion Criteria |
| ic | ⊕ | rgba(255, 176, 32, 0.15) | #FFB020 | #FFB020 | Inclusion Criteria |
| qc | ◎ | rgba(0, 214, 126, 0.15) | #00D67E | #00D67E | Quality Assessment |
| export | ⬇ | rgba(0, 200, 215, 0.15) | #00c8d7 | #00c8d7 | Export & Reporting |
| replay | ⟲ | rgba(0, 200, 215, 0.2) | #00FFFF | #00FFFF | Reproducibility Replay |

## Typography

### Font Families
- **Mono**: JetBrains Mono, Fira Code, Consolas, monospace
- **Sans**: Inter, system-ui, sans-serif

### Typography Scale
| Token | Size | Usage |
|-------|------|-------|
| xs | 0.65rem | Captions, labels |
| sm | 0.7rem | Code, secondary text |
| base | 0.875rem | Body text |
| lg | 1rem | Large body |
| xl | 1.125rem | Subheadings |
| 2xl | 1.25rem | Section headings |
| 3xl | 1.5rem | Page titles |

### Style Guides
- `terminal_header`: Terminal-style headers (monospace, uppercase)
- `section_header`: Section labels (monospace, uppercase, small)
- `body`: Standard body text
- `code`: Code and identifiers (monospace)
- `badge`: Status badges (monospace, small, uppercase)
- `metric_value`: Metric display values (monospace, large)
- `hash_identifier`: Hash display (monospace, small)

## Spacing

### Spacing Scale
| Token | Value | Usage |
|-------|-------|-------|
| xs | 0.25rem | Tight spacing |
| sm | 0.5rem | Small gaps |
| md | 1rem | Default spacing |
| lg | 1.5rem | Section gaps |
| xl | 2rem | Large gaps |

### Layout
- Card padding: 1rem
- Card padding large: 1.5rem
- Section gap: 1.5rem
- Page margin: 1rem

### Touch Targets
- Minimum: 44px
- Recommended: 48px

## Accessibility

### WCAG AA Compliance
- All text colors meet 4.5:1 contrast ratio
- All semantic states are distinguishable
- Font sizes minimum 0.6rem for any text
- Touch targets minimum 44px

### Colorblind Safety
- Semantic meaning preserved through shape and text
- Color is never the only indicator
- All states include text labels

## Usage Examples

### Import Design System
```python
from src.ui.design_system import (
    render_workflow_stepper,
    render_article_decision_card,
    render_provenance_panel,
    render_audit_status_badge,
    render_protocol_authority_banner,
    render_session_lineage_panel,
    get_semantic_color,
)
```

### Render Workflow Stepper
```python
render_workflow_stepper(
    current_stage="ec",
    session_state={"total_count": 100, "current_index": 45},
    protocol_hash="abc123..."
)
```

### Render Article Decision Card
```python
render_article_decision_card(
    article_review=article,
    current_stage="ec",
    show_qc_state=True,
    show_audit_state=True
)
```

### Get Semantic Color
```python
semantic = get_semantic_color("INCLUDED")
# Returns: {'bg': 'rgba(0, 214, 126, 0.15)', 'border': '#00D67E', ...}
```

## Verification Checklist

- [ ] Semantic consistency across all routed views
- [ ] No duplicated inline styling
- [ ] No conflicting visual semantics
- [ ] WCAG AA accessibility compliance
- [ ] Colorblind-safe design
- [ ] Touch target minimums met
- [ ] All states have accessibility labels
