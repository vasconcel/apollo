# Interaction Parity Report

**Date:** 2026-05-15
**Status:** COMPLETED

## Objective

Verify IC and EC interaction workflows are now behaviorally identical (with IC slightly more streamlined due to Clear button removal).

## Parity Matrix

| Interaction Element | EC | IC | Status |
|---------------------|----|----|--------|
| **EXCLUDE button** | Set flag → rerun | Set flag → rerun | ✅ MATCH |
| **INCLUDE button** | record_decision + props + advance | record_decision + props + advance | ✅ MATCH |
| **SKIP button** | record_decision + advance | record_decision + advance | ✅ MATCH |
| **Code selection (exclude)** | props + counter + advance | props + counter + advance | ✅ MATCH |
| **Code selection (include)** | props + counter + advance | props + counter + advance | ✅ MATCH |
| **Progress display** | session counter | session counter | ✅ MATCH |
| **Article advancement** | auto after decision | auto after decision | ✅ MATCH |
| **Rerun trigger** | after all state changes | after all state changes | ✅ MATCH |
| **Clear button** | PRESENT | REMOVED | ✅ STREAMLINED |

## UX Consistency

### Visual Parity
- Same button labels (INCLUDE, EXCLUDE, SKIP)
- Same button order (EXCLUDE, INCLUDE, SKIP)
- Same toast messages
- Same progress bar format
- Same status badge display

### Behavioral Parity
- Same click → persist → advance → rerun flow
- Same counter increment patterns
- Same audit trail recording

### Methodological Parity
- Human makes final decision (not AI)
- Deterministic state transitions
- Reproducible audit chain
- Explicit rationale logging

## Differences (Intentional)

| Aspect | EC | IC | Reason |
|--------|----|----|--------|
| Clear button | Present | Removed | User requirement to remove invalid IC-specific states |

This makes IC MORE streamlined than EC, not less functional.

## Validation Tests

### Test 1: INCLUDE Flow
1. Load article
2. Click INCLUDE
3. Verify: ic_stage="include", counter++, audit event, next article loads

### Test 2: EXCLUDE Flow
1. Load article
2. Click EXCLUDE
3. Verify: ic_stage="exclude", code selection UI appears
4. Select code
5. Verify: ces1=code, counter++, next article loads

### Test 3: SKIP Flow
1. Load article
2. Click SKIP
3. Verify: record_decision called, counter++, next article loads

### Test 4: Progress Accuracy
1. Make 3 decisions
2. Verify progress shows "3/X IC"

### Test 5: Rerun Consistency
1. Make decision
2. Refresh page
3. Verify decision persisted

### Test 6: Export Integrity
1. Complete IC workflow
2. Export results
3. Verify all decisions present in export

## Remaining Operational Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Filtered list index mismatch | LOW | Using original_idx = session.articles.index(article) |
| Session state not persisting | LOW | All mutations target canonical session.articles |
| Counter drift | LOW | Single source of truth (session.ic_completed) |

## Conclusion

IC now behaves as methodological continuation of EC, not independent workflow. Researcher should not perceive EC and IC as different systems.

## Files Modified

- `src/ui/modules/ic_screening_view.py` - Lines 176-259 realigned to EC pattern

## Constraint Compliance

- ✅ IC semantics unchanged
- ✅ Inclusion logic unchanged
- ✅ Protocol rules unchanged
- ✅ Determinism preserved
- ✅ Replay guarantees maintained
- ✅ Audit semantics preserved
- ✅ Export behavior unchanged