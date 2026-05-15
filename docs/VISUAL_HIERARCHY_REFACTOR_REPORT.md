# Visual Hierarchy Refactor Report

**Date:** 2026-05-15
**Status:** COMPLETED

## Executive Summary

Refactored EC Screening View to follow researcher-focused UI principles. Abstract now dominates screen, advisory is compact, metadata is clean, and provenance is collapsed by default.

## Changes Implemented

### 1. Article Card Restructuring

**Before:**
- Title → Metadata line → Expander (Metadata & Provenance) → Expander (Abstract)
- Too many expanders, metadata before abstract

**After:**
- Title → Metadata line → Abstract (prominent, always visible) → Collapsed Provenance expander
- Abstract now visually dominant

### 2. Metadata Line Cleanup

**Before:**
```
2025 · M"{u}ller; Ivana; Dill; Katja; ...
```

**After:**
```
2025 • Müller et al. • PACM HCI
```

- Proper author decoding via pylatexenc
- Max 2-3 authors inline with "et al." for remaining
- Venue abbreviation (PACM HCI)
- Clean bullet separators

### 3. Provenance Collapsed by Default

**Before:**
- Multiple nested expanders with tables
- "Metadata & Provenance" → "Provenance Details"
- Excessive duplication

**After:**
- Single collapsed "Provenance" expander
- Key fields: Full authors, DOI, Source ID, Metadata Quality

## Validation Checklist

- [x] Abstract visually dominant
- [x] Advisory compact
- [x] Metadata truncated properly (2-3 authors)
- [x] Provenance collapsed by default
- [x] No debug-feeling UI
- [x] No operational jargon

## Behavioral Equivalence

**UNCHANGED:**
- EC logic
- Deterministic behavior
- Audit semantics
- Protocol rules
- AI decision pipeline
- Replay guarantees
- Export semantics

**MODIFIED:**
- Rendering order (abstract first)
- Typography hierarchy
- Expander defaults
- Author truncation
- Venue abbreviation