# Transient vs Canonical State Audit Report

**Date:** 2026-05-15
**Status:** COMPLETED

## Root Cause Identified

The PENDING value was incorrectly stored in canonical IC code field (cis1):

```python
# BROKEN - PENDING in canonical field
article.cis1 = "PENDING"  # ← CORRUPTS SEMANTICS!
```

This caused the condition check:
```python
elif current_decision == "include" and not current_ic_code:
    # FALSE because current_ic_code = "PENDING" (truthy!)
    # Skip code selection, go directly to COMPLETE
```

## Semantic Corruption Explanation

| Field | Purpose | Valid Values |
|-------|---------|---------------|
| article.cis1 | Canonical IC code audit | IC1, IC2, IC3, IC4, IC5, YES, NO |
| article.ces1 | Canonical EC code audit | EC1, EC2, EC3, EC4, EC5, EC6, YES, NO |

"PENDING" is NOT a valid criterion code. It's transient UI state.

## Architectural Fix Applied

### Before (Broken)
```python
if incl_clicked:
    article.cis1 = "PENDING"  # ← INVALID - corrupts canonical state
```

### After (Fixed)
```python
if incl_clicked:
    st.session_state[f"ic_pending_code_{current_idx}"] = True  # TRANSIENT ONLY
    # Canonical state NOT modified until code selection
```

## State Separation Principle

```
TRANSIENT (session state):
├── st.session_state["ic_exclude_mode"]
├── st.session_state["ic_pending_code_idx"]
└── st.session_state["ic_show_codes_idx"]

CANONICAL (article properties):
├── article.ic_stage
├── article.cis1 (IC code: IC1, IC2, etc.)
├── article.ces1 (EC code: EC1, EC2, etc.)
└── article.revisor1
```

## Validation

- [x] PENDING never stored in canonical fields
- [x] Code selection UI now renders for EXCLUDE
- [x] Code selection UI now renders for INCLUDE
- [x] Transient state cleared after selection complete
- [x] Export preserves only valid criterion codes

## Constraint Compliance

- ✅ PRISMA defensible audit trail
- ✅ Methodological traceability preserved
- ✅ Deterministic replay maintained
- ✅ No hidden state corruption