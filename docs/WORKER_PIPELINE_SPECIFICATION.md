# Worker Pipeline Specification

**Date:** 2026-05-15
**Status:** COMPLETED

## Overview

The advisory worker processes the queue and generates advisories offline. This is the ONLY component that invokes LLM generation.

## Worker Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AdvisoryWorker                           │
├─────────────────────────────────────────────────────────────┤
│  __init__(config)                                           │
│  - Load configuration                                        │
│  - Initialize LLM client (lazy)                             │
├─────────────────────────────────────────────────────────────┤
│  process_item(queue_item) → AdvisoryResult                  │
│  - Mark item as PROCESSING                                  │
│  - Generate with retry                                      │
│  - Store to cache                                           │
│  - Mark as COMPLETED/FAILED                                 │
├─────────────────────────────────────────────────────────────┤
│  _generate_with_retry(request) → AdvisoryResult             │
│  - Attempt generation                                       │
│  - Handle 429 with backoff                                  │
│  - Retry up to max_retries                                  │
│  - Return fallback on all failures                          │
├─────────────────────────────────────────────────────────────┤
│  _generate_advisory(request) → AdvisoryResult               │
│  - Check LLM availability                                   │
│  - Load protocol criteria                                   │
│  - Call LLM.suggest_ic()                                    │
│  - Parse and return result                                  │
├─────────────────────────────────────────────────────────────┤
│  process_all(max_items=None) → Dict                         │
│  - Process entire queue                                     │
│  - Apply rate limiting                                      │
│  - Return summary                                           │
└─────────────────────────────────────────────────────────────┘
```

## Processing Flow

```
START
  ↓
Get next pending item from queue
  ↓
Mark as PROCESSING
  ↓
Generate advisory (with retry)
  ↓
Store to cache (session + disk)
  ↓
Mark as COMPLETED/FAILED
  ↓
Apply sleep (rate limit)
  ↓
NEXT ITEM
```

## Configuration

```python
@dataclass
class AdvisoryConfig:
    cache_dir: str = "data/cache/advisories"
    queue_state_path: str = "data/cache/queue_state.json"
    
    # Rate limiting
    max_requests_per_minute: int = 20
    sleep_seconds: float = 3.0
    
    # Retry logic
    max_retries: int = 5
    backoff_base: float = 2.0
    backoff_max: float = 60.0
    jitter: float = 0.1
    
    # Features
    enable_disk_cache: bool = True
    enable_queue_state: bool = True
```

## Rate Limiting

### Request Throttling
- Default: 20 requests per minute
- Sleep: 3 seconds between requests
- Configurable via CLI

### Exponential Backoff
- Base: 2.0 (2, 4, 8, 16, 32, 64 seconds)
- Max: 60 seconds
- Jitter: ±10%

### 429 Handling
- Detect "429" in error message
- Automatic retry with backoff
- Return fallback after all retries

## Retry Logic

```python
for attempt in range(max_retries + 1):
    try:
        advisory = _generate_advisory(request)
        if "429" in advisory.error:
            continue  # Will retry
        return advisory
    except Exception as e:
        last_error = e
        backoff = calculate_backoff(attempt)
        sleep(backoff)

return AdvisoryResult.create_failed(last_error)
```

## Progress Persistence

### Queue State (data/cache/queue_state.json)
```json
{
  "total": 2400,
  "pending": 1800,
  "processing": 0,
  "completed": 600,
  "failed": 0,
  "last_updated": "2026-05-15T12:00:00",
  "items": [...]
}
```

### Advisory Persistence (data/cache/advisories/{key}.json)
```json
{
  "cache_key": "abc123...",
  "protocol_version": "1.0",
  "decision": "INCLUDE",
  "confidence": 0.85,
  "triggered_criteria": ["IC1", "IC3"],
  "criterion_evaluations": [...],
  "justification": "...",
  "generated_at": "2026-05-15T12:00:00"
}
```

## CLI Usage

```bash
# Precompute all articles
python -m src.advisory.precompute_advisories --source data/articles.json

# Limit to first 100
python -m src.advisory.precompute_advisories --source data/articles.json --limit 100

# Custom rate limit
python -m src.advisory.precompute_advisories --rate-limit 10 --sleep 6

# Skip existing (default)
python -m src.advisory.precompute_advisories

# Process all (regenerate)
python -m src.advisory.precompute_advisories --no-skip-existing
```

## Throughput Estimates

For 2400 articles:

| Rate Limit | Sleep | Estimated Time |
|------------|-------|-----------------|
| 20/min | 3s | ~2.5 hours |
| 10/min | 6s | ~5 hours |
| 5/min | 12s | ~10 hours |

With exponential backoff on 429s, actual times may be higher.

## Failure Handling

### Transient Failures
- 429 (rate limit): Retry with backoff
- Timeout: Retry with backoff
- Network: Retry with backoff

### Permanent Failures
- Invalid API key: Fail after retries
- LLM not available: Return fallback
- Parse error: Return failed

### Failed Items
- Persisted to queue state
- Can be reset for retry
- Researcher can still screen manually

## Validation

- [x] Worker generates advisories
- [x] Rate limiting applied
- [x] Retry on 429
- [x] Backoff with jitter
- [x] Progress persisted
- [x] Cache updated
- [x] CLI functional