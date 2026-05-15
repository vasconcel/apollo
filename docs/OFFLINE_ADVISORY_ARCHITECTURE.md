# Offline Advisory Architecture

**Date:** 2026-05-15
**Status:** COMPLETED

## Problem Statement

Previous architecture coupled LLM generation with UI rendering:
- Streamlit reruns triggered advisory generation
- HTTP 429 errors on reruns
- Unstable runtime behavior
- No offline preprocessing capability

## Target Architecture

```
ATLAS Upload
    ↓
Normalize Articles
    ↓
Build Advisory Queue
    ↓
Background Advisory Generation (Worker)
    ↓
Persist Advisories to Disk
    ↓
Researcher Screening UI
    ↓
Export
```

## New Components

### src/advisory/

```
src/advisory/
├── __init__.py              # Module exports
├── advisory_models.py       # Typed dataclasses
├── advisory_cache.py        # Centralized cache (read-only for UI)
├── advisory_queue.py        # Queue management
├── advisory_worker.py       # Background generation pipeline
└── precompute_advisories.py # CLI entrypoint
```

### AdvisoryModels
- `AdvisoryResult` - Canonical advisory artifact
- `AdvisoryRequest` - Input for generation
- `QueueItem` - Queue entry
- `QueueState` - Progress tracking
- `AdvisoryConfig` - Configuration

### AdvisoryCache
- Session cache (memory, fastest)
- Disk cache (persistent)
- Read-only API for UI
- Deterministic cache keys

### AdvisoryQueue
- FIFO processing
- Progress tracking
- State persistence
- Retry management

### AdvisoryWorker
- Rate limiting (20 req/min default)
- Exponential backoff
- Retry logic
- Progress persistence

### PrecomputeEntrypoint
- CLI interface
- Multiple input formats (JSON/CSV/directory)
- Batch processing
- Statistics reporting

## Data Flow

```
Article → Cache Key → Check Session Cache
                       ↓ (miss)
                     Check Disk Cache
                       ↓ (miss)
                     Return UNAVAILABLE
                       ↓ (worker)
                     Generate Advisory
                       ↓
                     Persist to Disk
                       ↓
                     Return to UI
```

## Key Design Decisions

1. **Deterministic Cache Keys**
   - Based on article content, not runtime state
   - Enables replay stability
   
2. **Multi-Layer Cache**
   - Session → Disk → Generation
   - Fastest first, slowest last
   
3. **Strict Isolation**
   - UI only reads, never generates
   - Worker only generates, never reads from UI
   
4. **Offline-First**
   - Precomputation before screening
   - Zero LLM calls during UI usage

## Constraint Compliance

| Constraint | Status |
|-----------|--------|
| No LLM in UI path | ✅ |
| Deterministic replay | ✅ |
| Restart resilience | ✅ |
| Rate limit handling | ✅ |
| Optional/non-authoritative | ✅ |
| Human decision final | ✅ |

## Performance Targets

| Scenario | LLM Calls |
|----------|-----------|
| Open screening page | 0 |
| Change article | 0 |
| Button click | 0 |
| Rerun | 0 |
| App restart | 0 |

Only worker process may invoke LLMs.