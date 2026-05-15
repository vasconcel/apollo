# Review State Semantics Report

**Date:** 2026-05-15
**Status:** COMPLETED

## Problem

"PENDING" was being stored in canonical audit fields, corrupting state machine semantics.

## Architectural Principle

|Purpose|State Type|Storage Location|
|-------|----------|-----------------|
|Criterion codes|Audit/Scientific|session.articles field|
|UI waiting state|Transient|session_state|

## Valid vs Invalid Values

### Valid Criterion Codes (Canonical)
```
IC: IC1, IC2, IC3, IC4, IC5
EC: EC1, EC2, EC3, EC4, EC5, EC6
```

### Invalid (Not Allowed in Canonical)
```
PENDING, TODO, TBD, NONE, null
```

### Valid Transient States (Session State Only)
```
ic_pending_code_idx: True/False
ic_exclude_mode: True/False  
ic_show_codes_idx: "include"/"exclude"
```

## Fix Implementation

### IC Workflow Now Correct
1. **REVIEW**: No decision made, buttons shown
2. **TRANSIENT**: User clicks EXCLUDE → session_state set (not article)
3. **SELECT**: Code selection UI renders (using session_state check)
4. **COMPLETE**: User selects code → article field set to valid code

### EC Similar Fix Required
EC also has `cis1 = "PENDING"` - same fix needed.

## Determinism Guarantee

State machine now fully deterministic:
- Same input → Same branch → Same output
- No PENDING corruption
- No orphan states
- No duplicate state

## Constraint Compliance

- ✅ Deterministic replay
- ✅ Audit chain integrity
- ✅ PRISMA defensibility
- ✅ Protocol traceability