# IC State Machine Forensics Report

**Date:** 2026-05-15
**Status:** COMPLETED

## Executive Summary

Deep forensic analysis revealed TWO critical bugs in IC workflow:

1. **Index Space Mismatch**: Used `session.current_index` (master list) with filtered list
2. **EXCLUDE Button Broken**: Only set session state flag, never set article.ic_stage

## Bug #1: Index Space Mismatch

### Root Cause
IC used `session.get_ec_included_articles()` (filtered list) but tracked position using `session.current_index` (master list space).

### Execution Trace
```
Line 116: articles = session.get_ec_included_articles()  # Filtered list (e.g., 2 items)
Line 117: current_idx = session.current_index             # Master index (e.g., 45)
Line 197: session.current_index = current_idx + 1         # WRONG! Adding filtered index to master counter
```

### Symptom
- Progress counter stale (0/4 instead of 1/4)
- Navigation inconsistent
- Index boundary errors

### Fix Applied
```python
# NEW: Separate filtered index in session state
if "ic_current_index" not in st.session_state:
    st.session_state.ic_current_index = 0

current_idx = min(st.session_state.ic_current_index, total_ec_included - 1)
```

All index advances now use `st.session_state.ic_current_index`:
- Navigation buttons
- INCLUDE/SKIP/EXCLUDE decision handlers
- Code selection handlers

## Bug #2: EXCLUDE Button Not Setting Article Stage

### Root Cause
EXCLUDE button only set session state flag, never set `article.ic_stage`.

```python
# BEFORE (broken):
if excl_clicked:
    st.session_state[f"ic_show_codes_{current_idx}"] = "exclude"
    st.rerun()
```

After rerun:
- `current_decision = article.ic_stage or ""` → returns "" (empty!)
- Code falls through to `if not current_decision:` → infinite loop
- Code selection UI never shows

### Fix Applied (IC):
```python
# AFTER:
if excl_clicked:
    original_idx = session.articles.index(article)
    session.articles[original_idx].ic_stage = "exclude"
    st.session_state[f"ic_show_codes_{current_idx}"] = "exclude"
    st.rerun()
```

### Fix Applied (EC - same bug found):
```python
# BEFORE:
if excl_clicked:
    st.session_state[f"ec_show_codes_{current_idx}"] = "exclude"
    st.rerun()

# AFTER:
if excl_clicked:
    article.ec_stage = "exclude"
    st.session_state[f"ec_show_codes_{current_idx}"] = "exclude"
    st.rerun()
```

## State Mutation Timeline

### Before Fix (Broken)
```
1. Load IC workspace
2. Filter articles: get_ec_included_articles()
3. current_idx from session.current_index (WRONG SPACE)
4. Click INCLUDE → record_decision() + set properties
5. Advance: session.current_index += 1 (WRONG!)
6. Rerun → filtered list changed but counter doesn't match
```

### After Fix (Correct)
```
1. Load IC workspace
2. Filter articles: get_ec_included_articles()  
3. current_idx from st.session_state.ic_current_index (CORRECT SPACE)
4. Click INCLUDE → record_decision() + set properties + advance
5. Advance: st.session_state.ic_current_index += 1 (CORRECT!)
6. Rerun → filtered list index correct, progress updates
```

## Files Modified

- `src/ui/modules/ic_screening_view.py` - Index tracking + EXCLUDE fix
- `src/ui/modules/ec_screening_view.py` - EXCLUDE fix (found same bug)

## Validation

- [x] INCLUDE advances correctly with new index tracking
- [x] EXCLUDE shows code selection UI (article.ic_stage now set)
- [x] SKIP advances correctly
- [x] Progress counter updates immediately
- [x] Counter derived from canonical session.ic_completed

## Constraint Compliance

- ✅ IC semantics unchanged
- ✅ Progress from canonical session state only
- ✅ No local counters
- ✅ Determinism preserved
- ✅ Replay guarantees maintained