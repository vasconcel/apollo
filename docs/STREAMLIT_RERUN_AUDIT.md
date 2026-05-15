# Streamlit Rerun Audit Report

**Date:** 2026-05-15
**Status:** COMPLETED

## Rerun Lifecycle Analysis

### Button Click → Rerun Sequence

```
1. User clicks button (INCLUDE/EXCLUDE/SKIP)
2. Button callback executes:
   a. Modify session state (article properties)
   b. Call record_decision() if applicable
   c. Advance index
   d. Call st.rerun()
3. Streamlit frontend:
   a. Current script execution aborts
   b. Full script re-executes from top
   c. Session state preserved across reruns
4. New render:
   a. Read updated article properties
   b. Read updated index
   c. Display updated progress
```

### Timing Issues Identified

#### Issue #1: Index Before Persistence

**Broken Pattern:**
```python
session.current_index = current_idx + 1  # Advance first
st.rerun()
# On rerun: article might not be persisted yet!
```

**Fixed Pattern:**
```python
# Persist decision
session.record_decision("include", notes="")
# THEN advance
if current_idx < total - 1:
    st.session_state.ic_current_index = current_idx + 1
st.rerun()
```

#### Issue #2: Session State Flag Not Set

**Broken Pattern (EXCLUDE):**
```python
st.session_state[f"ic_show_codes_{current_idx}"] = "exclude"
st.rerun()
# On rerun: article.ic_stage still empty → current_decision = "" → loop!
```

**Fixed Pattern:**
```python
session.articles[original_idx].ic_stage = "exclude"  # PERSIST FIRST
st.session_state[f"ic_show_codes_{current_idx}"] = "exclude"
st.rerun()
```

### Index State Preservation

| State | Preserved? | How |
|-------|------------|-----|
| session.articles | ✅ | Python object in memory |
| session.ic_completed | ✅ | Int in session object |
| st.session_state.ic_current_index | ✅ | Streamlit session state |
| st.session_state flags | ✅ | Streamlit session state |

### Rerun Order Verification

1. ✅ Button clicked → callback runs
2. ✅ Article properties modified in session.articles
3. ✅ record_decision() called (INCLUDE/SKIP)
4. ✅ Counter incremented manually (code selection)
5. ✅ Index advanced
6. ✅ st.rerun() called
7. ✅ Script re-executes with updated state
8. ✅ Progress bar reads from session.ic_completed (updated)
9. ✅ Article shows with updated ic_stage

### Critical Execution Order

For INCLUDE button:
```
1. original_idx = session.articles.index(article)
2. session.articles[original_idx].ic_stage = "include"
3. session.record_decision("include", notes="")
4. session.articles[original_idx].cis1 = "PENDING"
5. session.articles[original_idx].ces1 = "NO"  
6. session.articles[original_idx].revisor1 = session.researcher_id
7. st.toast(...)
8. if condition: st.session_state.ic_current_index = current_idx + 1
9. st.rerun()
```

All state mutations MUST complete before rerun to ensure deterministic behavior.

## Validation

- [x] All state changes happen before st.rerun()
- [x] Index state preserved in st.session_state
- [x] Article state preserved in session.articles
- [x] Counter state preserved in session.ic_completed
- [x] Rerun triggers full script re-execution

## Constraint Compliance

- ✅ No race conditions
- ✅ No lost state
- ✅ Deterministic rerun behavior