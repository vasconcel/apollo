# Advisory Code Inference Report

**Date:** 2026-05-15
**Status:** COMPLETED

## Problem

Manual IC code selection created operational instability.

## Solution Implemented

IC codes now automatically inferred from AI advisory criterion_evaluations:

```python
def _record_ic_decision(session, article, current_idx: int, decision: str):
    # Get cached advisory
    cached_advice = st.session_state.get(f"ic_advice_{article_id}", None)
    
    # Extract triggered criteria
    triggered_codes = []
    if cached_advice:
        criterion_evals = cached_advice.get("criterion_evaluations", {})
        for cid, eval_data in criterion_evals.items():
            if eval_data.get("triggered", False):
                triggered_codes.append(cid)
    
    # Store in canonical field
    if decision == "include":
        ic_codes = ";".join(triggered_codes) if triggered_codes else "YES"
        article.cis1 = ic_codes
    else:
        ec_codes = ";".join(triggered_codes) if triggered_codes else "N/A"  
        article.ces1 = ec_codes
```

## Deterministic Inference

Uses ONLY explicit criterion evaluation from advisory:
- Triggered criteria already computed by LLM
- No heuristic guessing
- Deterministic based on advisory output

## Export Integration

Export now contains:
- EC codes: EC1;EC2;EC3;EC4;EC5;EC6
- IC codes: IC1;IC2;IC3;IC4;IC5

Format: semicolon-separated list of triggered codes

## Validation

- [x] Advisory parsed for triggered criteria
- [x] Codes stored in canonical article fields
- [x] Export includes IC codes
- [x] Export includes EC codes
- [x] No heuristic inference

## Constraint Compliance

- ✅ Deterministic advisory parsing
- ✅ PRISMA defensible codes
- ✅ Audit trail preserved
- ✅ Protocol traceability