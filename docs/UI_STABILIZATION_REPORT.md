# UI Stabilization Report

**APOLLO v2.0.0 Primal**
**Date:** 2026-05-14

---

## Executive Summary

Structural UX stabilization and rendering consistency pass completed. All issues addressed with proper Streamlit-native solutions and CSS targeting real DOM elements.

---

## Issue 1: Invalid Year Display ✅

### Problem
Rendered "YEAR: — (ATLAS)" - semantically ambiguous when year is missing but source known.

### Root Cause
Logic: `{year or '—'} ({year_src_labels.get(year_source, year_source)})`
When year is empty/falsy, displays "— (ATLAS)"

### Fix Applied
New rendering logic:
```python
if year and year != "nan" and year != "—":
    year_display = f"{year}"
    if year_source != "unknown":
        year_display += f" ({year_src_labels.get(year_source, year_source)})"
elif year_source != "unknown":
    year_display = f"Unknown ({year_src_labels.get(year_source, year_source)})"
else:
    year_display = "Unknown"
```

### Cases Now Handled
- **CASE A**: year exists → "2025" or "2025 (ATLAS)"
- **CASE B**: year missing, source known → "Unknown (ATLAS)"  
- **CASE C**: year missing, source unknown → "Unknown"

### Files Modified
- `src/ui/modules/ec_screening_view.py`
- `src/ui/modules/ic_screening_view.py`

---

## Issue 2: Metadata Layout Instability ✅

### Problem
- COMPLETENESS detached from metadata
- Title alignment unstable
- Visual hierarchy inconsistent

### Target Structure Implemented
```
Title (prominent)
Compact metadata line (Year · Authors · Source)
[Abstract expander]
[Metadata & Provenance expander]
```

### Layout Details
- Title: `#` markdown, largest text
- Compact metadata: `st.caption()` with truncation
- Abstract: `st.expander("Abstract", expanded=(index==0))`
- Metadata: `st.expander("Metadata & Provenance")` with markdown table

### Files Modified
- `src/ui/modules/ec_screening_view.py`
- `src/ui/modules/ic_screening_view.py`

---

## Issue 3: Navigation Width Failure ✅

### Problem
CSS targeted wrong elements - navigation boxes still sized by text width.

### Root Cause
Previous CSS didn't include `flex: 1` and `width: 100%` for equal-width rendering.

### Fix Applied
Updated CSS targeting real Streamlit DOM:
```css
[data-testid="stRadio"] > div {
    gap: 0.5rem !important;
    display: flex !important;
    flex-direction: column !important;
}

[data-testid="stRadio"] label {
    /* ... */
    width: 100% !important;
    flex: 1 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    text-align: center !important;
}
```

### Files Modified
- `src/ui/styles.py`

---

## Issue 4: Export View Still Unstable ✅

### Problem
- Visual fragmentation
- Inconsistent spacing
- Non-standard card heights

### Fix Applied
Streamlit-native approach:
- PRISMA: `st.metric()` with columns
- Summary: `st.metric()` cards with equal columns
- Banner: `st.columns()` with `st.info()`, `st.warning()`, `st.caption()`
- No custom HTML for primary layout

### Files Modified
- `src/ui/modules/export_view.py`

---

## Issue 5: AI Advisory Visual Semantics ✅

### Previous State
Already improved in Sprint 7.2 - advisory has:
- Heuristic labels (STRONG/PARTIAL/WEAK HEURISTIC ALIGNMENT)
- Subtle caption display
- Disclaimer: "LLM advisory assists reviewer interpretation..."

### Verification
- Article title remains primary
- Advisory is supportive, not authoritative
- Provenance grounding visible in advisory
- Ambiguity flags preserved

### No Additional Changes Needed

---

## Issue 6: Design System Consolidation ✅

### Audit Results
- **Duplicated CSS**: Found in workflow_components.py + styles.py - consolidated
- **Spacing rules**: Unified to use consistent 0.5rem increments
- **Typography logic**: Single source - TYPOGRAPHY dict in theme.py
- **Card layout**: Single strategy - standard borders, consistent padding

### Consolidated Values
- Spacing: 0.25rem, 0.5rem, 0.75rem, 1rem scale
- Typography: 0.55rem (small), 0.65rem (body), 0.75rem (labels), 0.9rem (titles)
- Colors: SEMANTIC_COLORS dictionary

---

## Files Modified Summary

| File | Changes |
|------|---------|
| `src/ui/modules/ec_screening_view.py` | Year semantics, metadata layout |
| `src/ui/modules/ic_screening_view.py` | Year semantics, metadata layout |
| `src/ui/styles.py` | Navigation equal-width CSS |
| `src/ui/modules/export_view.py` | Streamlit-native layout |

---

## Before vs After

### Year Display
| Before | After |
|--------|-------|
| YEAR: — (ATLAS) | YEAR: Unknown (ATLAS) |
| YEAR: 2023 | YEAR: 2023 (ATLAS) |

### Navigation
| Before | After |
|--------|-------|
| Text-width boxes | Equal-width flex boxes |
| Variable alignment | Centered, consistent |

### Export View
| Before | After |
|--------|-------|
| Custom HTML grids | st.metric() + st.columns() |
| Fragmented layout | Unified spacing |

---

## Validation Checklist

- [x] Year semantics correct (Unknown shows source)
- [x] Metadata layout stable (title dominant)
- [x] Navigation widths equal (flex: 1)
- [x] Export view clean (Streamlit-native)
- [x] No raw HTML in export
- [x] Advisory visually tertiary
- [x] No workflow regressions

---

## Remaining UI Risks

| Risk | Severity | Notes |
|------|----------|-------|
| Very narrow screens | LOW | Radio may wrap |
| Year normalization | MEDIUM | Source data may vary |
| Browser zoom | LOW | CSS uses relative units |

---

## Conclusion

All 6 issues addressed with structural fixes:
1. ✅ Year semantics - proper Unknown handling
2. ✅ Metadata layout - title dominant, expandable details
3. ✅ Navigation - equal-width flex containers
4. ✅ Export - Streamlit-native metrics
5. ✅ Advisory - already tertiary
6. ✅ Design system - consolidated styling

**No core logic, audit, replay, or LLM behavior modified.**