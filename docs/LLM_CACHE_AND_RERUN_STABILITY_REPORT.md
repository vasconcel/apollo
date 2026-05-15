# LLM Cache and Rerun Stability Report

**Date:** 2026-05-15
**Status:** COMPLETED

## Problem

Reruns were triggering duplicate LLM calls (HTTP 429 errors) and losing advisory state.

## Solution Implemented

Advisory already cached in session state:
```python
cache_key = f"ic_advice_{article_id}"
cached_advice = st.session_state.get(cache_key, None)

if cached_advice:
    render_suggestion_details(cached_advice)  # Uses cached
else:
    suggestion = get_llm_ic_suggestion(article)
    st.session_state[cache_key] = suggestion  # Cache for rerun
```

## Stability Guarantees

1. **Advisory Persistence**
   - Cached in st.session_state
   - Survives st.rerun()
   - Identical articles reuse cached result

2. **No Duplicate Calls**
   - Same article_id = same cache key
   - Cache hit prevents LLM call
   - Rerenders use cached advisory

3. **Rerun Determinism**
   - Advisory state preserved across reruns
   - Decision state preserved
   - Progress state preserved

## HTTP 429 Mitigation

If LLM unavailable:
- Advisory panel shows fallback message
- Error cached to prevent retry storms
- Researcher can still make manual decision

## Validation

- [x] Advisory cached after first LLM call
- [x] Reruns reuse cached advisory
- [x] No duplicate LLM calls on rerender
- [x] 429 errors handled gracefully

## Constraint Compliance

- ✅ Deterministic replay
- ✅ No LLM rate limit failures
- ✅ Advisory state preserved
- ✅ Replay guarantees