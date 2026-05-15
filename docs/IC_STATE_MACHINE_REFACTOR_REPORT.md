# IC State Machine Refactor Report

**Date:** 2026-05-15
**Status:** COMPLETED

## Root Causes Fixed

1. **PENDING in canonical field** - Was corrupting state machine (resolved)
2. **Manual code selection UI** - Created deadlocks (resolved)
3. **Transient state mixing** - Caused orphan states (resolved)

## Architecture Implemented

### Before (Broken)
- INCLUDE → PENDING → manual code selection → deadlocked
- EXCLUDE → partial state → manual code selection → deadlocked
- Multiple render branches with orphan states

### After (Aligned with EC)
```
INCLUDE button click:
1. ic_stage = "include"
2. record_decision() called
3. IC codes auto-inferred from AI advisory
4. cis1 = triggered IC codes (e.g., "IC1;IC3")
5. progress incremented
6. advance to next article
7. rerun

EXCLUDE button click:
1. ic_stage = "exclude"  
2. record_decision() called
3. EC codes auto-inferred from AI advisory
4. ces1 = triggered EC codes
5. progress incremented
6. advance to next article
7. rerun
```

## Removed States

- EXCLUDE_SELECT branch (manual code selection)
- INCLUDE_SELECT branch (manual code selection)
- PENDING transient state in canonical fields
- All debug forensic artifacts from researcher UI

## Transition Model

| State | Actions Available |
|-------|-------------------|
| REVIEW | INCLUDE, EXCLUDE, SKIP |
| COMPLETE | Next article loads |

NO intermediate states allowed.

## Validation

- [x] INCLUDE single action completes workflow
- [x] EXCLUDE single action completes workflow  
- [x] SKIP single action completes workflow
- [x] No orphan states
- [x] No manual code selection UI
- [x] Codes auto-inferred from advisory

## Constraint Compliance

- ✅ Deterministic replay
- ✅ Audit chain integrity
- ✅ PRISMA defensibility
- ✅ Protocol traceability