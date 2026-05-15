# State Transition Audit Report

**Date:** 2026-05-15
**Status:** COMPLETED

## Scope

Audit of state transitions in IC workflow after alignment with EC.

## Transition States

### 1. No Decision (ic_stage = "")

**Entry:** Article loaded in IC workspace

**Actions Available:**
- INCLUDE → transition to "include"
- EXCLUDE → transition to "exclude" (pending code)
- SKIP → advance to next article

**Exit Conditions:**
- Any button clicked triggers rerun
- State machine proceeds to next state

### 2. Exclude Pending Code (ic_stage = "exclude", cis1 = "")

**Entry:** EXCLUDE button clicked

**Actions Available:**
- Select IC code → finalize exclusion
- (No Clear in IC - streamlined)

**Exit Conditions:**
- Code button clicked → advance to next article
- Counter incremented

### 3. Include Pending Code (ic_stage = "include", cis1 = "")

**Entry:** INCLUDE button clicked (without code)

**Actions Available:**
- Select IC code → finalize inclusion

**Exit Conditions:**
- Code button clicked → advance to next article
- Counter incremented

### 4. Decision Complete (ic_stage set, cis1 set)

**Entry:** Code selected

**Display:** Status badge only (no Clear in IC)

**Next:** Automatic advance to next article

## Invalid States Removed

| Invalid State | Why Invalid | Resolution |
|--------------|-------------|------------|
| Clear button | Creates dangling reset state | Removed |
| Manual counter decrement | Undermines determinism | Not present in EC |
| Partial exclusion staging | UI-only state not persisted | Removed |

## Index Handling

**Critical Fix:** IC works with filtered list (`session.get_ec_included_articles()`). To persist decisions:

```python
original_idx = session.articles.index(article)
session.articles[original_idx].ic_stage = "include"
```

This ensures modifications target the canonical session list, not a filtered copy.

## Progress Counter Flow

| Event | Counter Update |
|-------|-----------------|
| INCLUDE button | `record_decision()` increments internally |
| SKIP button | `record_decision()` increments internally |
| Code selection | Manual `session.ic_completed += 1` (matches EC) |

Note: EC and IC both use manual counter increment at code selection (not record_decision).

## Audit Trail

`record_decision()` called at:
- INCLUDE button (with notes="")
- SKIP button (with notes="")

Not called at code selection (matches EC behavior - only increments counter).

## Replay Determinism

State transitions are deterministic because:
1. Same input (button click) → same output (state change + advance)
2. No randomness in transitions
3. Progress computed from canonical session state
4. Audit events appended in order

## Validation

- [x] No orphan states
- [x] No invalid transitions
- [x] No duplicate persistence
- [x] No UI-only shadow state
- [x] Index resolution correct
- [x] Counter updates match EC

## Constraint Compliance

- ✅ No hidden state introduced
- ✅ No auto-decisions
- ✅ No silent advancement without persistence
- ✅ No heuristic-only transitions