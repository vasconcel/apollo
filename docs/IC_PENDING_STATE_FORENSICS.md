# IC Pending State Forensics Report

**Date:** 2026-05-15
**Status:** COMPLETED

## Problem Statement

"PENDING" was being interpreted as a finalized IC code, causing:
- Exclusion code selection to never render
- Workflow to jump directly to COMPLETE state
- Buttons to disappear permanently
- Next article to never load

## Runtime Evidence

```json
{
  "ic_stage": "exclude",
  "cis1": "PENDING",
  "render_branch": "COMPLETE"
}
```

## Why This Happened

The INCLUDE button was storing PENDING in the canonical field:
```python
session.articles[original_idx].cis1 = "PENDING"
```

Then the condition:
```python
elif current_decision == "include" and not current_ic_code:
```

Evaluated as:
- current_decision = "include" (truthy)
- not current_ic_code = not "PENDING" = False

Therefore condition FALSE → skipped to else (COMPLETE)!

## Fix Implemented

### 1. INCLUDE Button Fix
Changed from setting canonical field to setting transient session state:
```python
# BEFORE (broken)
session.articles[original_idx].cis1 = "PENDING"

# AFTER (fixed)  
st.session_state[f"ic_pending_code_{current_idx}"] = True
```

### 2. Branch Logic Fix
Now checks transient state, not canonical:
```python
in_pending_include = st.session_state.get(f"ic_pending_code_{current_idx}", False)
render_branch = "INCLUDE_SELECT" if current_decision == "include" and (not current_ic_code or in_pending_include)
```

## Validation Tests

1. **INCLUDE click** → code selection appears (not PENDING in canonical)
2. **EXCLUDE click** → code selection appears  
3. **Select code** → canonical field set, counter++, advance
4. **Rerun** → proper state restored, no PENDING corruption

## Export Implications

Now export contains ONLY valid criterion codes:
- IC: IC1, IC2, IC3, IC4, IC5
- EC: EC1, EC2, EC3, EC4, EC5, EC6

No more "PENDING" in exported data!

## Constraint Compliance

- ✅ No semantic corruption
- ✅ Deterministic replay
- ✅ Audit chain integrity
- ✅ PRISMA defensibility