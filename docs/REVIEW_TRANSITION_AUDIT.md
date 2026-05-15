# Review Transition Audit Report

**Date:** 2026-05-15
**Status:** COMPLETED

## Scope

Audit of all review mode transitions in IC workflow.

## Transition Types

### 1. INCLUDE Transition

**Flow:**
```
REVIEW → (click INCLUDE) → INCLUDE with PENDING code → (select code) → COMPLETE
```

**State Changes:**
```python
# Click INCLUDE
article.ic_stage = "include"
article.cis1 = "PENDING"  # ← Note: This may block code selection UI
session.record_decision("include")

# On rerun: enters INCLUDE code selection (if cis1 not pre-set)
```

### 2. EXCLUDE Transition

**Flow:**
```
REVIEW → (click EXCLUDE) → EXCLUDE pending code → (select code) → COMPLETE
```

**State Changes:**
```python
# Click EXCLUDE
article.ic_stage = "exclude"
st.rerun()

# On rerun: enters EXCLUDE code selection (cis1 empty)
# Select code: ces1 = code, counter++, advance
```

### 3. SKIP Transition

**Flow:**
```
REVIEW → (click SKIP) → COMPLETE (advances)
```

**State Changes:**
```python
# Click SKIP
session.record_decision("skip")
advance_index
st.rerun()
```

## Transition Validation Matrix

| From State | Action | To State | Valid? |
|------------|--------|----------|--------|
| REVIEW | INCLUDE | CODE_SELECT (PENDING) | ⚠️ May block |
| REVIEW | EXCLUDE | CODE_SELECT | ✅ |
| REVIEW | SKIP | COMPLETE | ✅ |
| CODE_SELECT (EXCLUDE) | Select code | COMPLETE | ✅ |
| CODE_SELECT (INCLUDE) | Select code | COMPLETE | ✅ |
| COMPLETE | - | Next article | ✅ |

## Critical Path Analysis

### Path 1: EXCLUDE (Primary Investigation Target)

1. User in REVIEW state
2. Clicks EXCLUDE button
3. State mutation: ic_stage = "exclude"
4. Session flag set
5. st.rerun() called
6. Script re-executes
7. current_decision = "exclude" (from article)
8. current_ic_code = "" (not yet set)
9. Condition TRUE: enters EXCLUDE code selection
10. Code buttons render
11. User selects code
12. Final state set (ces1, counter, advance)

This path is now aligned with EC.

### Path 2: INCLUDE (Side Investigation)

1. User in REVIEW state  
2. Clicks INCLUDE button
3. State mutation: ic_stage = "include", cis1 = "PENDING"
4. record_decision() called
5. st.rerun() called
6. Script re-executes
7. current_decision = "include"
8. current_ic_code = "PENDING" (NOT empty!)
9. Condition FALSE: skips to else → shows badge

**POTENTIAL ISSUE**: Setting cis1="PENDING" prevents code selection UI from showing!

## Recommendation

Either:
A. Remove cis1="PENDING" setting (let code selection set it)
OR  
B. Update condition check: `current_ic_code != "PENDING"` not just `not current_ic_code`

## Export Behavior

All transitions preserve:
- ic_stage value
- cis1/ces1 codes  
- revisor1 researcher ID
- ic_completed counter

Export validates all these fields.

## Constraint Compliance

- ✅ All transitions traceable
- ✅ No hidden state transitions
- ✅ Deterministic replay maintained
- ✅ Audit chain complete