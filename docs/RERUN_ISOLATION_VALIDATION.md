# Rerun Isolation Validation Report

**Date:** 2026-05-15
**Status:** COMPLETED

## Problem

Reruns triggering advisory regeneration despite previous cache.

## Root Causes Fixed

1. **Direct LLM calls in render path** - Now isolated in cache layer
2. **Cache key instability** - Now deterministic based on content
3. **Fallback regenerating** - Now uses cached fallback

## Isolation Guarantees

### UI Rendering Functions

```python
def render_ai_advisory_panel(article):
    # STRICT ISOLATION: Only renders, never generates
    advisory = get_ic_advisory_cached(article)
    render_suggestion_details(advisory)
```

### Cache Access

```python
def get_ic_advisory_cached(article):
    # Centralized - ONLY generates if cache miss
    # Returns cached result if available
    # Uses deterministic key
    # Implements rate limiting
```

## Validation Tests

| Scenario | Expected | Result |
|----------|----------|--------|
| Open IC screen | 1 LLM call/article | ✅ |
| Rerender same article | 0 LLM calls | ✅ |
| Button click (INCLUDE/EXCLUDE) | 0 LLM calls | ✅ |
| Navigate between articles | 0 LLM calls | ✅ |
| App restart | Disk cache reuse | ✅ |
| Rate limit (429) | Graceful fallback | ✅ |

## Constraint Compliance

- ✅ UI never triggers LLM calls
- ✅ Reruns use cached advisories
- ✅ Deterministic key generation