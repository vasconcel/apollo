# Advisory Cache Architecture Report

**Date:** 2026-05-15
**Status:** COMPLETED

## Problem

Streamlit reruns triggered excessive LLM calls, causing HTTP 429 errors.

## Solution Implemented

Centralized advisory cache layer with deterministic key generation:

### Cache Flow
```
article_id → compute cache key → check session cache → check disk cache → LLM call (if miss) → persist result
```

### Key Components

1. **Deterministic Cache Key**
```python
content = f"{protocol_version}:{title.strip().lower()}:{abstract.strip().lower()}"
cache_key = hashlib.sha256(content.encode()).hexdigest()[:32]
```
Based on article content, NOT runtime state.

2. **Multi-Layer Cache**
- Session cache (fastest)
- Disk cache (persistent)
- LLM generation (only on miss)

3. **Rate Limit Protection**
- Exponential backoff on 429
- Automatic retry with backoff
- Fallback cached on failure

## Architecture

### Advisory Lifecycle

```
FIRST ACCESS:
article → cache_key → session_cache? → disk_cache? → LLM → persist → return

ALL RERUNS:
article → cache_key → HIT → render only → ZERO LLM calls
```

### Strict Separation

- `get_ic_advisory_cached()` - ONLY function that generates advisories
- `render_ai_advisory_panel()` - ONLY renders, never generates

## Validation

- [x] Cache key stable across reruns
- [x] Session cache prevents rerun LLM calls
- [x] Disk cache provides restart resilience
- [x] Rate limit handled gracefully
- [x] No LLM calls on rerender after first access

## Constraint Compliance

- ✅ Deterministic replay
- ✅ Zero LLM calls on rerun
- ✅ Rate limit protection
- ✅ Restart resilience