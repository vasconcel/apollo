# FINAL ADVISORY HARDENING REPORT

**Date:** 2026-05-15
**Status:** COMPLETED

## Executive Summary

APOLLO advisory system has been refactored to a **strict offline-first architecture**.
- UI NEVER generates advisories (ZERO LLM calls in render path)
- Worker pipeline handles all generation
- Deterministic cache keys enable replay stability
- Rate limit protection prevents HTTP 429 cascading

## Files Modified

### New Advisory Module (src/advisory/)
- `__init__.py` - Module exports
- `advisory_models.py` - Typed dataclasses (AdvisoryResult, QueueItem, etc.)
- `advisory_cache.py` - Centralized read-only cache API
- `advisory_queue.py` - Queue management and progress tracking
- `advisory_worker.py` - Background generation pipeline
- `precompute_advisories.py` - CLI entrypoint for preprocessing

### Updated UI Modules
- `src/ui/modules/ic_screening_view.py` - Uses `get_advisory()` read-only API
- `src/ui/modules/ec_screening_view.py` - Uses `get_ec_advisory()` read-only API

## Runtime Isolation Status

| Component | Status | Notes |
|-----------|--------|-------|
| IC Screening UI | ✅ READ-ONLY | Uses `get_advisory()` |
| EC Screening UI | ✅ READ-ONLY | Uses `get_ec_advisory()` |
| Advisory Cache | ✅ STRICT API | `get()`/`exists()` for UI, `persist()` for worker |
| Worker Pipeline | ✅ GENERATION ONLY | Calls LLM, persists to cache |

## Validation Results

### Zero LLM Calls in UI

| Scenario | Expected | Result |
|----------|----------|--------|
| Open IC screen | 0 LLM calls | ✅ Pass |
| Click INCLUDE | 0 LLM calls | ✅ Pass |
| Click EXCLUDE | 0 LLM calls | ✅ Pass |
| Streamlit rerun | 0 LLM calls | ✅ Pass |
| Refresh page | 0 LLM calls | ✅ Pass |
| App restart | 0 LLM calls | ✅ Pass (load from disk) |

### Cache Invariants

| Invariant | Status |
|-----------|--------|
| Same article + same protocol = same key | ✅ |
| Advisory immutable after write | ✅ |
| Restart resilience (disk cache) | ✅ |
| Replay produces identical output | ✅ |

## Queue Semantics

### State Machine
```
PENDING → PROCESSING → COMPLETED
  │           │
  │           └─→ FAILED
  └─→ SKIPPED
```

### State Persistence
- Location: `data/cache/queue_state.json`
- Tracks: total, pending, processing, completed, failed, items

### Retry Logic
- Max retries: 5 (configurable)
- Backoff: exponential with jitter (base 2.0, max 60s)
- Adaptive: slows after consecutive 429s

## Rate Limit Protections

### Token Bucket
- Capacity: 20 requests/minute (configurable)
- Refill: continuous

### Sliding Window
- Window: 60 seconds
- Max: 20 requests

### Backoff Coordinator
- Base: 2.0 (2, 4, 8, 16, 32, 64 seconds)
- Max: 60 seconds
- Jitter: ±10%
- Adaptive slowdown after 3 consecutive 429s

### Cascade Prevention
1. Token bucket prevents burst
2. Sliding window enforces hard limit
3. Adaptive backoff slows after 429s
4. Jitter desynchronizes retries
5. Fallback advisory provides graceful degradation

## Worker Resilience

### Checkpointing
- Completed advisories never regenerated
- Failed advisories retryable
- Queue state persisted to disk

### Recovery
- Interrupted worker resumes from last checkpoint
- Partial completion supported
- Deterministic replay preserved

## Scalability Assessment

### 2400 Papers

| Metric | Value |
|--------|-------|
| Precompute time | ~2.5 hours (20 req/min, 3s sleep) |
| Cache size | ~50MB (advisories JSON) |
| Memory (session) | ~500KB (cached keys) |
| Disk I/O | ~2400 writes |

### Performance Targets
- Opening screening page: ZERO LLM calls
- Changing article: ZERO LLM calls
- Button click: ZERO LLM calls
- Rerun: ZERO LLM calls

## Scientific Defensibility

### Requirements Met

| Requirement | Status |
|-------------|--------|
| Reproducibility | ✅ Same article → same advisory |
| Traceability | ✅ Persisted with metadata |
| Auditability | ✅ Cache file integrity |
| Transparency | ✅ Advisory is optional |
| Non-determinism elimination | ✅ No runtime generation |

### Constraint Compliance

- Advisory remains OPTIONAL
- Advisory remains NON-AUTHORITATIVE  
- Human researcher remains FINAL authority
- NO auto-accept or auto-reject
- NO bypass of human screening

## Remaining Operational Risks

| Risk | Mitigation |
|------|------------|
| Protocol version change | Different cache keys (intentional) |
| Corrupted cache file | Graceful fallback to UNAVAILABLE |
| Disk full | Advisory still works (session + memory) |
| Missing advisory | Show "not yet generated", allow manual review |

## Usage Instructions

### Precompute Advisories

```bash
# Process entire corpus
python -m src.advisory.precompute_advisories --source data/articles.json

# Limit to first 100
python -m src.advisory.precompute_advisories --source data/articles.json --limit 100

# Custom rate limit
python -m src.advisory.precompute_advisories --rate-limit 10 --sleep 6
```

### Screening Workflow

1. **Precompute** - Run precompute script before screening
2. **Screening** - Open APOLLO, advisories load from cache
3. **Review** - Human makes INCLUDE/EXCLUDE/SKIP decisions
4. **Export** - Export uses cached codes, no regeneration

### Advisory Status

```python
from src.advisory import get_advisory_status, AdvisoryStatus

status = get_advisory_status(title, abstract, protocol_version, stage="ic")

if status == AdvisoryStatus.COMPLETED:
    # Show cached advisory
elif status == AdvisoryStatus.PENDING:
    # Show "run precompute"
elif status == AdvisoryStatus.FAILED:
    # Show error, allow manual review
```

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    APOLLO ADVISORY                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────┐    ┌─────────────────┐                 │
│  │   UPLOAD        │───▶│   PRECOMPUTE   │                 │
│  │   (Articles)    │    │   (Worker)     │                 │
│  └─────────────────┘    └────────┬────────┘                 │
│                                   │                          │
│                                   ▼                          │
│                          ┌─────────────────┐                 │
│                          │   CACHE        │                 │
│                          │   (Disk)       │                 │
│                          └────────┬────────┘                 │
│                                   │                          │
│                                   ▼                          │
│  ┌─────────────────┐    ┌─────────────────┐                 │
│  │   EXPORT        │◀───│   SCREENING    │                 │
│  │   (Cached)      │    │   (UI Read)    │                 │
│  └─────────────────┘    └─────────────────┘                 │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Conclusion

The advisory system is now:
- **Offline-first** - Precompute before screening
- **Read-only UI** - Zero LLM calls in render path
- **Deterministic** - Replay produces identical outputs
- **Rate-limited** - Protected against 429 cascading
- **Resilient** - Survives restarts and failures
- **Scientific** - Maintains human authority

The system is ready for production use with 2400+ paper corpora.