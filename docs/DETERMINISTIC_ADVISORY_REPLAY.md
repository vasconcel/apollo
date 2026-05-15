# Deterministic Advisory Replay Report

**Date:** 2026-05-15
**Status:** COMPLETED

## Problem

Reruns and replays must produce identical advisory results for auditability.

## Solution Guarantees

### Deterministic Cache Key

```python
content = f"{protocol_version}:{title.strip().lower()}:{abstract.strip().lower()}"
cache_key = sha256(content).hexdigest()[:32]
```

Same article → same cache key → same advisory.

### Cache Persistence

- Session state cache - survives reruns
- Disk cache - survives restarts
- Cached fallback - survives rate limits

### Replay Scenarios

| Scenario | Behavior |
|---------|----------|
| Rerun after button click | Cache hit, zero LLM calls |
| Refresh page | Cache hit, zero LLM calls |
| App restart | Disk cache hit, zero LLM calls |
| Resume session | Session cache hit |
| Export results | Uses cached advisory codes |

## Validation

- [x] Same article produces same advisory
- [x] Reruns deterministic
- [x] Replays stable
- [x] Export includes inferred codes

## Constraint Compliance

- ✅ Deterministic replay
- ✅ Audit trail complete
- ✅ PRISMA defensibility
- ✅ Protocol traceability