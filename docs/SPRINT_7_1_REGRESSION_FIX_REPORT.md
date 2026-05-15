# Sprint 7.1: Regression Fix Report

**APOLLO v2.0.0 Primal**
**Date:** 2026-05-14

---

## Executive Summary

Fixed four critical UI regression issues that impacted researcher experience. All fixes target presentation layer only - no core logic changes.

---

## Issue 1: Metadata Provenance Panel Empty

### Root Cause

**Location:** `src/ui/modules/ec_screening_view.py` and `src/ui/modules/ic_screening_view.py`

The `render_article_card()` function was rendering metadata in an EXPANDER with `expanded=False` by default. Users had to manually expand to see provenance, and many key fields were missing:

- **Missing fields:** Year Source, Global ID, Metadata Completeness
- **Fields shown:** Source, DOI, Keywords only

The design system component `render_article_decision_card` had proper provenance but was **never called** in the actual screening workflow.

### Fix Applied

1. **Replaced expander with prominent provenance grid** - Now displays all required fields immediately
2. **Added missing fields:** Year Source, Global ID, Metadata Completeness
3. **Changed layout:** Provenance now appears BEFORE title, not hidden in expander

### Files Modified

- `src/ui/modules/ec_screening_view.py` (render_article_card)
- `src/ui/modules/ic_screening_view.py` (render_article_card)

### Before/After

**Before:**
```
┌────────────────────────────┐
│ Title                      │
│ Year                       │
├────────────────────────────┤
│ [ABSTRACT - prominent]     │
│ ...large text...           │
├────────────────────────────┤
│ [Metadata - hidden]        │
└────────────────────────────┘
```

**After:**
```
┌────────────────────────────┐
│ ▸ PROVENANCE               │
│ YEAR: 2023 (ATLAS)         │
│ AUTHORS: Smith             │
│ SOURCE: PubMed | DOI: ...  │
│ ID: abc123 | COMPLETENESS  │
├────────────────────────────┤
│ Title                      │
├────────────────────────────┤
│ [Abstract - collapsed]     │
└────────────────────────────┘
```

---

## Issue 2: Navigation Button Width Inconsistent

### Root Cause

The workflow stepper in `src/ui/design_system/workflow_components.py` was already correctly using `flex: 1` for equal-width blocks. However, the `min-width: 100px` could cause issues on narrow screens.

### Verification

The workflow stepper already has:
- `flex: 1` on each step → equal width
- Equal padding on all blocks
- Visual consistency maintained

**Status:** No fix needed - already correct from Sprint 7.

---

## Issue 3: Abstract Dominates Screen

### Root Cause

**Location:** `src/ui/modules/ec_screening_view.py` and `src/ui/modules/ic_screening_view.py`

The `render_article_card()` was rendering abstract:
- In a prominent 1rem padding box
- With full line-height 1.6
- BEFORE metadata provenance
- Expanded by default

This consumed excessive vertical space and pushed provenance visibility below the fold.

### Fix Applied

1. **Abstract now in collapsible expander** - `expanded=False` by default
2. **Provenance displayed first** - Above title, immediate visibility
3. **Reduced padding** - 0.5rem instead of 1rem
4. **Smaller abstract text** - More compact when collapsed

### Layout Change

**Before:**
1. Title + Year
2. Abstract (prominent, expanded)
3. Metadata (hidden in expander)

**After:**
1. Provenance grid (prominent, always visible)
2. Title
3. Abstract (collapsed, expandable)

---

## Issue 4: Advisory Visual Hierarchy

### Root Cause

**Location:** `src/ui/modules/ec_screening_view.py`

The advisory panel displayed:
- Decision (left column, 50% width)
- Confidence (right column, 50% width) - same importance as decision

This made confidence feel **authoritative** rather than **advisory**.

### Fix Applied

1. **Changed column ratio** - Decision: 3 parts, Confidence: 1 part
2. **Reduced confidence visual weight** - Lower opacity (0.85), smaller padding
3. **Made confidence feel secondary** - Less prominent styling
4. **Kept grounding/provenance first** - Already prioritized in previous Sprint 7 fix

### Visual Change

**Before:**
```
┌─────────────┬─────────────┐
│  DECISION  │  95% HIGH   │
│  (equal)   │  (equal)    │
└─────────────┴─────────────┘
```

**After:**
```
┌────────────────────┬────────┐
│     DECISION      │ 95%    │
│  (prominent)      │ (small)│
└────────────────────┴────────┘
```

---

## Files Modified

1. **src/ui/modules/ec_screening_view.py**
   - `render_article_card()`: Provenance-first layout, collapsed abstract
   - `render_suggestion_details()`: Adjusted column widths, reduced confidence visual weight

2. **src/ui/modules/ic_screening_view.py**
   - `render_article_card()`: Same provenance-first layout changes

---

## Validation Checklist

- [x] Metadata panel populated (Year, Authors, Source, DOI, ID, Completeness, Year Source)
- [x] Equal-width workflow navigation (already correct)
- [x] Improved scan ergonomics (provenance before abstract)
- [x] Provenance visually prioritized (grid display, always visible)
- [x] Abstract collapsed by default
- [x] Confidence visually secondary (smaller, less prominent)
- [x] NO core logic changes
- [x] NO advisory semantic changes

---

## Remaining UX Risks

| Risk | Severity | Notes |
|------|----------|-------|
| Very small screens may still have layout issues | LOW | overflow-x: auto handles this |
| Long abstracts still take space when expanded | LOW | User-controlled expansion |
| Metadata unavailable shows fallback text | LOW | Graceful degradation |

---

## Conclusion

All four regression issues fixed:

1. ✅ **Metadata provenance** - Now visible without clicking, all required fields shown
2. ✅ **Navigation width** - Already correct, verified equal-width
3. ✅ **Abstract dominance** - Collapsed by default, provenance first
4. ✅ **Advisory hierarchy** - Confidence now visually secondary to decision

**No core logic, advisory logic, or determinism changes - presentation only.**