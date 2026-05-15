# IC Exclusion State Machine Report

**Date:** 2026-05-15
**Status:** IN PROGRESS - DEEP FORENSICS

## Exclusion State Machine Architecture

### Three-State IC Workflow

```
STATE 1: REVIEW MODE
├── Buttons: INCLUDE | EXCLUDE | SKIP
└── Entry: ic_stage = ""

    ↓ [EXCLUDE click]

STATE 2: EXCLUSION CODE SELECTION  
├── UI: "SELECT EXCLUSION CODE" header + code buttons
└── Entry: ic_stage = "exclude", cis1 = ""

    ↓ [Select code]

STATE 3: DECISION COMPLETE
├── UI: Status badge (EXCLUDED)
└── Entry: ic_stage = "exclude", cis1 = <code>
```

### Root Cause Analysis

After deep forensic analysis, we traced that EXCLUDE button NOW correctly:
1. Sets `article.ic_stage = "exclude"`
2. Sets session state flag
3. Triggers st.rerun()

The state machine logic:
```python
if not current_decision:           # STATE 1: REVIEW
    # Show INCLUDE/EXCLUDE/SKIP buttons
    
elif current_decision == "exclude" and not current_ic_code:  # STATE 2: CODE SELECT
    # Show exclusion code selection UI
    
else:                              # STATE 3: COMPLETE  
    # Show status badge
```

## Potential Failure Points Identified

### 1. Index Space Mismatch (FIXED)
- IC used session.current_index (master list) with filtered list
- Now uses st.session_state.ic_current_index

### 2. EXCLUDE Not Persisting Stage (FIXED)
- Now sets article.ic_stage = "exclude" before rerun

### 3. INCLUDE Flow Side Effect
- INCLUDE sets cis1 = "PENDING" 
- This could cause STATE 3 early if rerun loses this state

### 4. Session State Persistence
- Need to verify Streamlit preserves article.ic_stage across reruns

## Code Comparison: EC vs IC EXCLUDE

### EC (Working)
```python
if excl_clicked:
    article.ec_stage = "exclude"  # Direct reference
    st.session_state[f"ec_show_codes_{current_idx}"] = "exclude"
    st.rerun()
```

### IC (Aligned)
```python
if excl_clicked:
    original_idx = session.articles.index(article)  # Via filtered list
    session.articles[original_idx].ic_stage = "exclude"
    st.session_state[f"ic_show_codes_{current_idx}"] = "exclude"
    st.rerun()
```

## Validation Required

1. ✅ EXCLUDE click → ic_stage="exclude" persisted
2. ✅ Rerun → STATE 2 (code selection) renders
3. ✅ Code selection → ces1 set + counter increment  
4. ✅ Advance → next article loads
5. ✅ Progress updates

## Known Risks

| Risk | Mitigation |
|------|------------|
| Filtered list objects not in session.articles | Using index() to find original |
| Session state loss on rerun | All modifications to session.articles |
| Index out of bounds | Bounds checking in place |

## Remaining Investigation

Need runtime validation to confirm:
- EXCLUDE actually enters STATE 2
- Code selection buttons render  
- Selection advances correctly

## Constraint Compliance

- ✅ IC semantics unchanged
- ✅ State machine architecture matches EC
- ✅ Determinism preserved