# Disk Cache Specification Report

**Date:** 2026-05-15
**Status:** COMPLETED

## Problem

Session state lost on app restart, forcing advisory regeneration.

## Solution Implemented

### Disk Cache Path
```
data/cache/advisories/{cache_key}.json
```

### Cache Structure
```json
{
  "decision": "INCLUDE",
  "confidence": 0.85,
  "criterion_evaluations": {...},
  "triggered_criteria": ["IC1", "IC3"],
  "timestamp": "2026-05-15T12:00:00"
}
```

### Configuration
```python
_ADVISORY_CACHE_CONFIG = {
    "enable_disk_cache": True,
    "cache_dir": "data/cache/advisories"
}
```

## Benefits

1. **Restart Resilience** - Advisories persist across app restarts
2. **Reduced API Costs** - Same article in new session uses cached advisory
3. **Deterministic Replay** - Historical sessions can be replayed
4. **Offline Operation** - Works without LLM availability

## Validation

- [x] Cache file created on first advisory generation
- [x] Cache file read on subsequent sessions
- [x] Cache key deterministic (same content → same key)
- [x] JSON format valid and parseable

## Constraint Compliance

- ✅ Replay stability
- ✅ Restart resilience
- ✅ Reduced API costs