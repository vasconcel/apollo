# Provenance Visibility Report

**APOLLO v2.0.0 Primal - Sprint 7**
**Date:** 2026-05-14

---

## Objective

Expand metadata visibility in article review cards so provenance is easy to inspect rapidly, without abstract dominating the screen.

---

## Before/After UX Rationale

### Before (v1.0.0)
```
┌─────────────────────────────────────────┐
│ [WL] | ID: a1b2...        [INCLUDE]   │
├─────────────────────────────────────────┤
│ Title                                    │
│ Authors • Year                          │
├─────────────────────────────────────────┤
│ Source: PubMed | DOI: 10.xxx           │
├─────────────────────────────────────────┤
│ Abstract: (DOMINATED SCREEN)            │
│ ...large text block...                  │
│ ...continues...                         │
│ ...more...                              │
├─────────────────────────────────────────┤
│ [Expand for metadata in expander]       │
└─────────────────────────────────────────┘
```

**Issues:**
- Abstract dominated the screen
- Provenance was hidden in expander
- Required extra click to see DOI, year source, completeness
- Scanner unfriendly - couldn't quickly verify article identity

### After (v2.0.0)
```
┌─────────────────────────────────────────┐
│ [WL] | ID: a1b2...        [INCLUDE]   │
├─────────────────────────────────────────┤
│ ▸ PROVENANCE (prominent, above title)   │
│ Year: 2023 • Authors: Smith et al.     │
│ Source: PubMed | ID: abc123             │
│ [COMPLETE] Year: ATLAS                  │
├─────────────────────────────────────────┤
│ Title (compact)                         │
│ Authors • Year                          │
├─────────────────────────────────────────┤
│ EC | IC                                 │
│ INCLUDE | —                             │
├─────────────────────────────────────────┤
│ [Expand for full abstract]              │
└─────────────────────────────────────────┘
```

**Improvements:**
- Provenance visible without clicking
- DOI and year source immediately inspectable
- Metadata completeness color-coded at a glance
- Scanner-friendly: can verify article in 2 seconds

---

## Required Metadata Fields - Implementation Status

| Field | Status | Location |
|-------|--------|----------|
| Year | ✓ | Provenance line |
| Authors | ✓ | Provenance line |
| Venue / Source | ✓ | Secondary provenance line |
| DOI | ✓ | Secondary provenance line |
| Literature Type | ✓ | Header badge |
| Global ID | ✓ | Provenance line |
| Metadata Completeness | ✓ | Color-coded badge |
| Year Source | ✓ | "Year: ATLAS/DOI/Manual" |
| Protocol Version | ✓ | Export summary cards |

**Optional fields implemented:**
- Keywords: In expanders
- Language: Not available in current data model

---

## Scientific Framing Improvements

| Before | After | Rationale |
|--------|-------|-----------|
| "Source" | "▸ PROVENANCE" | Scientific terminology |
| "Metadata" | "Metadata Provenance" | Clearer purpose |
| Generic badges | Color-coded semantic badges | Faster visual scanning |

---

## Visual Accessibility

### Color Coding
- **Complete metadata**: Green (#00D67E)
- **Partial metadata**: Yellow (#FFB020)
- **Minimal metadata**: Red (#FF4757)
- **Year source**: Cyan (#00c8d7)

### Compact Layout
- Reduced padding throughout (0.5rem standard)
- Font hierarchy: 0.9rem title, 0.65rem provenance, 0.55rem labels
- Single-line provenance display where possible

---

## Verification

Run the EC screening workflow:
```bash
streamlit run app.py
```

Navigate to EC Screening and verify:
1. Article cards show provenance above title
2. DOI and year source visible
3. Completeness badge color-coded
4. Abstract in expandable section

---

## Files Modified

- `src/ui/design_system/article_decision_card.py`
  - Added `render_provenance_compact_html()`
  - Modified main card layout
  - Compacted spacing throughout

---

## Remaining Provenance Risks

| Risk | Severity | Notes |
|------|----------|-------|
| URL truncation for long URLs | LOW | Shows first 60 chars |
| Missing fields show placeholder | LOW | "Year/Authors unavailable" |
| No language field | MEDIUM | Would require schema change |

---

## Conclusion

Provenance is now visually prominent and easy to inspect rapidly. The layout rebalancing ensures metadata is easier to check than before, without abstract dominating the review experience.