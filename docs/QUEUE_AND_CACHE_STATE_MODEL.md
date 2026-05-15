# Queue and Cache State Model

**Date:** 2026-05-15
**Status:** COMPLETED

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                     STATE MODEL                               │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐    │
│  │   QUEUE     │────▶│   CACHE    │────▶│    UI       │    │
│  │   (Worker)  │     │  (Storage) │     │  (Read-Only)│    │
│  └─────────────┘     └─────────────┘     └─────────────┘    │
│         │                   │                   │             │
│         ▼                   ▼                   ▼             │
│  data/cache/         data/cache/          (memory)          │
│  queue_state.json   advisories/                              │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

## Queue State Machine

### States

```
PENDING ──▶ PROCESSING ──▶ COMPLETED
   │           │
   │           └──────▶ FAILED
   │
   └──────────▶ SKIPPED
```

### State Transitions

| From | To | Trigger |
|------|-----|---------|
| PENDING | PROCESSING | Worker picks item |
| PROCESSING | COMPLETED | Advisory generated successfully |
| PROCESSING | FAILED | Generation failed (after retries) |
| PENDING | SKIPPED | Manual skip or duplicate |
| FAILED | PENDING | Retry triggered |

### QueueItem Schema

```python
@dataclass
class QueueItem:
    cache_key: str           # Deterministic key
    protocol_version: str   # Protocol version
    
    article_id: str         # Article identifier
    
    status: AdvisoryStatus # PENDING/PROCESSING/COMPLETED/FAILED/SKIPPED
    priority: int           # FIFO priority
    
    created_at: str         # ISO timestamp
    started_at: Optional[str]
    completed_at: Optional[str]
    
    retry_count: int        # Retry attempts
    last_error: Optional[str]
```

### QueueState Schema

```python
@dataclass
class QueueState:
    total: int               # Total items
    pending: int            # Pending count
    processing: int         # Currently processing
    completed: int          # Completed count
    failed: int             # Failed count
    
    last_updated: str       # Last update timestamp
    
    items: List[QueueItem]  # All queue items
```

### State Persistence

**Location:** `data/cache/queue_state.json`

```json
{
  "total": 2400,
  "pending": 1800,
  "processing": 5,
  "completed": 595,
  "failed": 0,
  "last_updated": "2026-05-15T12:00:00Z",
  "items": [
    {
      "cache_key": "abc123...",
      "protocol_version": "1.0",
      "article_id": "article_001",
      "status": "COMPLETED",
      "priority": 0,
      "created_at": "2026-05-15T10:00:00Z",
      "started_at": "2026-05-15T10:00:01Z",
      "completed_at": "2026-05-15T10:00:15Z",
      "retry_count": 0,
      "last_error": null
    }
  ]
}
```

## Cache State Model

### Cache Layers

```
┌─────────────────────────┐
│    SESSION CACHE        │  (in-memory, fastest)
│    st.session_state     │
└─────────────────────────┘
         │
         ▼ (miss)
┌─────────────────────────┐
│     DISK CACHE          │  (persistent)
│   data/cache/advisories │
└─────────────────────────┘
         │
         ▼ (miss)
┌─────────────────────────┐
│    RETURN UNAVAILABLE   │  (never generate)
└─────────────────────────┘
```

### Cache Key Computation

```python
def compute_cache_key(
    title: str,
    abstract: str,
    protocol_version: str,
    source: str = "",
    year: Optional[int] = None,
    doi: str = ""
) -> str:
    # Normalize content
    normalized = normalize_article_content(
        title=title,
        abstract=abstract,
        source=source,
        year=year,
        doi=doi
    )
    
    # Hash
    content = f"{protocol_version}:{normalized}"
    return sha256(content.encode()).hexdigest()[:32]
```

### Cache File Schema

**Location:** `data/cache/advisories/{cache_key}.json`

```json
{
  "cache_key": "abc123...",
  "protocol_version": "1.0",
  "decision": "INCLUDE",
  "confidence": 0.85,
  "triggered_criteria": ["IC1", "IC3"],
  "criterion_evaluations": [
    {
      "criterion_id": "IC1",
      "criterion_name": "Addresses R&S practices",
      "satisfied": true,
      "evidence": "...",
      "confidence": 0.9
    }
  ],
  "justification": "...",
  "error": null,
  "is_fallback": false,
  "is_placeholder": false,
  "generated_at": "2026-05-15T12:00:00Z",
  "generation_duration_ms": 1250.5
}
```

## Invariants

### Queue Invariants

1. **Total = pending + processing + completed + failed**
   - Always true, enforced by state machine

2. **Processing ≤ max_workers**
   - At most N items in PROCESSING state

3. **Failed items retryable**
   - Can transition FAILED → PENDING via retry

4. **No duplicate cache_keys**
   - Each article has unique cache_key in queue

### Cache Invariants

1. **Deterministic keys**
   - Same article → same cache_key

2. **Immutable after write**
   - Advisory never modified after persistence

3. **Read-after-write consistency**
   - After store, get() returns stored value

4. **Crash recovery**
   - Disk cache survives process death

## State Transition Rules

### Worker Processing Rules

```
1. Get next PENDING item (FIFO by priority)
2. Mark item PROCESSING
3. Generate advisory (with retry)
4. Store to cache (disk + session)
5. Mark COMPLETED or FAILED
6. Apply rate limit sleep
7. Continue to next item
```

### UI Read Rules

```
1. Compute cache_key from article
2. Check session cache
3. Check disk cache
4. If hit: return advisory
5. If miss: return UNAVAILABLE
6. NEVER generate in UI
```

### Retry Rules

```
1. If generation fails and retry_count < max_retries:
   - Increment retry_count
   - Mark PENDING
   - Apply backoff
   - Schedule retry
2. Else:
   - Mark FAILED
   - Persist error
```

## Failure Semantics

### Transient Failures

- 429 Too Many Requests → retry with backoff
- Timeout → retry with backoff
- Network error → retry with backoff

### Permanent Failures

- Invalid API key → fail, no retry
- LLM unavailable → fail, no retry
- Parse error → fail, no retry

### Failure Artifact

```json
{
  "cache_key": "abc123...",
  "decision": "UNAVAILABLE",
  "confidence": 0.0,
  "justification": "Advisory generation failed: ...",
  "error": "API key invalid",
  "is_placeholder": false,
  "generated_at": "2026-05-15T12:00:00Z"
}
```

## Validation

- [x] Queue state machine defined
- [x] Cache state model defined
- [x] State persistence implemented
- [x] Invariants documented
- [x] Transition rules enforced
- [x] Failure semantics defined