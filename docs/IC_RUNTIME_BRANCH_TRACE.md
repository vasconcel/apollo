# IC Runtime Branch Trace Report

**Date:** 2026-05-15
**Status:** AWAITING RUNTIME VALIDATION

## Purpose

Capture actual runtime branch traces to identify why EXCLUDE flow deadlocks.

## Diagnostic Points Added

### 1. Pre-Flight Diagnostics (Line ~116)
Shows:
- Number of filtered articles
- Number of master articles
- Sample article's ic_stage, cis1, ces1, ec_stage

### 2. Branch Diagnostics (Line ~183)
Shows:
- Current RENDER_BRANCH
- ic_stage value
- cis1_code value  
- ces1_code value
- current_idx
- total articles
- available IC codes

### 3. EXCLUDE Button Handler (Line ~198)
Shows:
- Master index found
- State mutations executed
- Rerun trigger

### 4. Branch Execution Markers
- `[BRANCH] EXCLUDE_SELECT` - Entered when code selection should show
- `[BRANCH] INCLUDE_SELECT` - Entered when include code selection shows
- `[BRANCH] COMPLETE` - Entered when final state reached

## Expected vs Actual

### Expected EXCLUDE Flow
```
REVIEW → click EXCLUDE → [EXCLUDE] debug output → rerun
→ [BRANCH] EXCLUDE_SELECT → code buttons render
→ click code → ces1 set, counter++, advance → rerun
→ [BRANCH] COMPLETE on next article
```

### Observed (Frozen)
```
REVIEW → click EXCLUDE → [EXCLUDE] debug output → rerun  
→ EXCLUDE badge appears (COMPLETE branch)
→ No code selection buttons
→ Workflow deadlocked
```

## Runtime Questions to Answer

1. What is RENDER_BRANCH value BEFORE clicking EXCLUDE?
2. What are the article state values?
3. After clicking EXCLUDE, does [EXCLUDE] debug show?
4. After rerun, what RENDER_BRANCH shows?
5. Which branch diagnostic appears?
6. What are ic_stage and cis1 values at each step?

## Common Failure Modes

| Mode | Indicator | Fix Required |
|------|-----------|--------------|
| ic_stage already set | RENDER_BRANCH=COMPLETE on load | Filter out completed articles |
| cis1 pre-populated | current_ic_code != "" | Don't set PENDING, use different state |
| session state lost | State reverts on rerun | Ensure mutations target session.articles |
| index mismatch | Wrong article loaded | Verify current_idx matches correct article |

## What to Look For

When user runs with diagnostics:

1. Load IC workspace → check RENDER_BRANCH
   - Should be "REVIEW" for fresh articles

2. Click EXCLUDE → check [EXCLUDE] output
   - Should show "Set ic_stage='exclude'"

3. After rerun → check RENDER_BRANCH
   - Should be "EXCLUDE_SELECT"

4. If RENDER_BRANCH = "COMPLETE" after EXCLUDE click:
   - Check ic_stage and cis1 values
   - If cis1 is non-empty → that's why code selection skipped!

## Constraint Compliance

- ✅ Diagnostics added without changing behavior
- ✅ No hidden state introduced
- ✅ All mutations traceable via debug output

## Next Steps

Once user runs and provides output, update this report with:
- Actual runtime values captured
- Root cause identified
- Fix plan determined