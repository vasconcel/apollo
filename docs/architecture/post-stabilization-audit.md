# POST-STABILIZATION ARCHITECTURAL AUDIT

## A. Executive Summary

The Advisory Contract Stabilization phase successfully eliminated schema drift across
6 surfaces, fixed the runtime `non_triggered_criteria` crash, added 49 deterministic
validation tests, and verified 211 tests × 3 identical runs. The semantic contract is
stable.

However, semantic stability does NOT imply operational stability. The orchestration
layer has fundamental architectural fragilities inherited from Streamlit's reactive
programming model, lack of concurrency control, single-process worker architecture,
and absence of backpressure or failure recovery mechanisms.

**Critical risks identified:**

| Risk | Severity | Type |
|------|----------|------|
| No queue write-ahead log → full state loss on crash | **CRITICAL** | Durability |
| No concurrency control on queue operations → race conditions | **CRITICAL** | Correctness |
| Prefilter singleton accumulates titles across sessions → false duplicates | **HIGH** | Determinism |
| Daemon threads with no graceful shutdown → orphaned processing | **HIGH** | Operational |
| 8 global singletons with mutable state → hidden coupling | **HIGH** | Maintainability |
| Cache grows unbounded → OOM on 100k studies | **HIGH** | Scalability |
| `stop_worker()` is effectively a no-op | **HIGH** | Operational |
| 31+ Streamlit session state mutation points → state explosion | **MEDIUM** | Determinism |
| Queue persistence path inconsistency → reset targets wrong file | **MEDIUM** | Correctness |
| `random.uniform` in backoff → non-deterministic retry timing | **LOW** | Determinism |

---

## B. What Was Successfully Stabilized

### B.1. Semantic Contract

- `AdvisoryResult` — `StructuredAdvisory` field parity established
- `non_triggered_criteria` gap closed (was runtime crash)
- `stage_validation` type corrected (was `Dict` but used as `str`)
- `evidence_span` type corrected (was `List[str]` but set as `int`)
- Serialization `to_dict`/`from_dict` defaults aligned with field types
- Backward compatibility with old cache entries preserved

### B.2. Validation Infrastructure

- 49 deterministic contract tests prevent future drift
- 81 replay corpus tests verify session persistence stability
- Stage guard isolation invariant tests (EC↔IC contamination detection)
- Criterion hallucination detection tests
- Serialization roundtrip parity tests
- Backward compatibility tests for legacy cache formats

### B.3. Documentation

- `advisory-contract-inventory.md`: Complete field-by-field surface enumeration
- `advisory-contract-spec.md`: Canonical schema definition with ownership boundaries

---

## C. What Remains Architecturally Fragile

### C.1. Queue Durability (CRITICAL)

The queue persists state via `_save_state()` which performs a plain `json.dump()` +
file write with NO write-ahead log (WAL). A crash mid-write corrupts the entire
JSON file. On reload, corruption is silently handled by falling back to an empty
`QueueState()`, losing all in-flight and pending items.

**Evidence** (`advisory_queue.py:287-295`):
```python
def _save_state(self):
    self.state.last_updated = datetime.utcnow().isoformat()
    with open(self._state_path, 'w', encoding='utf-8') as f:
        json.dump(self.state.to_dict(), f, indent=2)
```

**Impact**: A process crash during `mark_processing` or `mark_completed` causes
loss of the entire queue — not just the current item. All pending, processing, and
completed state for that stage is gone.

Additionally, `reset_queue_for_stage()` uses path
`data/cache/advisory_queue_{stage}.json` while the queue class writes to
`data/cache/queue_state_{stage}.json`. This path mismatch means `reset_queue_for_stage`
deletes a file that the queue never touches, making it completely ineffective.

### C.2. Concurrency (CRITICAL)

There is **zero locking** around queue operations. The worker thread and Streamlit's
main thread both access the same `AdvisoryQueue` instance:

- `process_item()` calls `queue.mark_processing()`, `queue.mark_completed()`,
  `queue.mark_failed()` without acquiring any lock (`advisory_worker.py:450-495`)
- `process_all()` calls `queue.get_next()` without synchronization (`:1000`)
- UI calls `queue.get_pending()` during rerender concurrently with worker mutations
- The race window between `get_next()` and `mark_processing()` allows double-booking
- The race window between `mark_processing()` and `mark_completed()` allows the UI
  to observe transient PROCESSING state as terminal

**Evidence** — only lock in entire worker path:
```python
# advisory_orchestrator.py:41 — guards THREAD CREATION, not queue access
self._start_lock = threading.Lock()
```

### C.3. Streamlit Lifecycle Hazard (HIGH)

Streamlit re-executes the entire view module on every rerun. This means:

1. **Pipeline re-initialization**: `initialize_advisory_pipeline()` is called from
   render code. It creates a new queue (clearing the old one) every time the
   pipeline init guard is bypassed.

2. **Session state mutation surface**: 31+ mutation points in `ec_screening_view.py`
   and `ic_screening_view.py`. Each mutation is a side effect during render.

3. **Auto-refresh loop**: Bounded to 3s, but each rerun triggers:
   - Pipeline status queries
   - Queue state queries  
   - Cache iteration for telemetry counts
   - With 100k studies, each rerun is O(n) on cache iteration

4. **No hydration/dehydration**: Streamlit session state is ephemeral. Browser
   refresh = total runtime state loss. The session persistence service only saves
   screening decisions, not worker progress or queue state.

### C.4. Worker Orchestration (HIGH)

**`stop_worker()` is a no-op** (`advisory_orchestrator.py:113-115`):
```python
def stop_worker(self):
    self._is_running = False
```

The thread's `run_worker_loop()` does NOT check `_is_running`:
```python
def run_worker_loop():
    try:
        self._is_running = True
        self._worker.process_all(max_items, stage=self._stage)  # blocking
    finally:
        self._is_running = False
```

`process_all()` only checks the scheduler for priority changes, NOT the
`_is_running` flag. A worker processing 100k items will process ALL of them
before `_is_running` is ever checked.

Additionally, threads are **daemon threads** — they terminate abruptly on process
exit with no chance to flush queue state, mark items as failed, or persist
checkpoints.

### C.5. Cache Scalability (HIGH)

The session cache is a plain `Dict[str, AdvisoryResult]` that grows unboundedly:
```python
# advisory_cache.py:145
self._session_cache: Dict[str, AdvisoryResult] = {}
```

With 100k studies, each containing an `AdvisoryResult` (~2KB serialized), this
consumes ~200MB in memory. No eviction policy, no TTL, no LRU, no size cap.

The `list_cached()` method iterates ALL keys. The `count_prefiltered()`,
`count_quarantined()`, and `count_llm_generated()` methods each call `list_cached()`
and then iterate all advisories — 3 full scans per rerun for telemetry.

### C.6. Prefilter Deduplication (HIGH)

The `PrefilterEngine` singleton accumulates `_seen_titles` across the entire
application lifetime. The `reset()` method is never called at session boundaries.
This means:

- A title seen during EC screening will be flagged as "duplicate" during IC
  screening for the same study — **silently excluding articles that should pass**
  IC criteria.
- Deduplication persists across protocol versions, batches, and screening stages.
- No mechanism to scope deduplication to a specific screening session or stage.

### C.7. Global Singleton Architecture (HIGH)

| Singleton | Module | Scope | Risk |
|-----------|--------|-------|------|
| `_global_cache` | `advisory_cache.py:425` | Process | Couples stage isolation |
| `_global_queue_ec/ic/qc` | `advisory_queue.py:304-306` | Process | No lifecycle management |
| `_global_orchestrator_ec/ic/qc` | `advisory_orchestrator.py:142-144` | Process | No lifecycle management |
| `_global_prefilter` | `prefilter.py:277` | Process | Cross-session state leak |
| `_global_scheduler` | `advisory_scheduler.py:180` | Process | Global mutable state |

8 singletons with no lifecycle management, no reset protocol, and no isolation
between stages or sessions.

---

## D. Hidden Systemic Risks

### D.1. Timestamp Entropy in Deterministic Artifacts (LOW-MEDIUM)

16+ `datetime.utcnow()` calls embed timestamps into advisory artifacts:
- `generated_at` — varies per generation, making cache entries non-reproducible
- `generation_duration_ms` — varies per run
- Queue timestamps (`created_at`, `started_at`, `completed_at`, `last_updated`) —
  vary per run
- `CalibrationEvent.timestamp` — varies per run

**Impact on determinism**: Two advisories generated at different times differ in
`generated_at` even with identical inputs. This is documented in the contract spec
as acceptable (runtime-only fields), but it means advisory equality cannot be
checked by simple dict comparison.

### D.2. `random.uniform` in Backoff (LOW)

`_calculate_backoff()` at `advisory_worker.py:936` uses `random.uniform()` for
jitter. While this does not affect the advisory output itself, it means retry
timing is non-deterministic. Under rate-limit conditions, different runs may
experience different timing patterns. Combined with LLM non-determinism, this
could produce different advisory outputs on retry.

### D.3. Single-Process Bottleneck

Everything runs in one process:
- Streamlit UI (main thread)
- Advisory worker (background daemon thread)
- Cache (in-memory dictionary, same process)
- Queue (in-memory data structure, same process)

A memory leak in any component affects all. A crash kills everything. CPU-bound
cache iteration blocks the UI.

### D.4. Missing Advisory Lifecycle Ownership

There is no explicit state machine for an advisory's lifecycle:

```
PREFILTER_CHECK → LLM_GENERATION → STAGE_VALIDATION → SAFEGUARD_CHECK → CACHE → UI
```

Every step happens inside `_generate_advisory()` — a single monolithic method.
There is no intermediate persistence between stages. If the process crashes during
stage validation, the prefilter result is lost and must be recomputed. If the LLM
response is cached but stage guard fails, there is no retry without regeneration.

### D.5. Cache-Queue Inconsistency Window

The queue and cache are not transactionally consistent:
1. Worker calls `store_advisory(advisory, stage)` (cache write)
2. Worker calls `queue.mark_completed(item)` (queue state mutation)
3. Between steps 1 and 2, a crash leaves a cached advisory with the item still
   marked as PROCESSING in the queue
4. On restart, the queue is reloaded (or lost), but the cache has a completed
   advisory that no one will read

---

## E. Concurrency Risk Assessment

| Scenario | Risk | Root Cause |
|----------|------|------------|
| Worker thread + UI thread access queue simultaneously | **Race** | No locks on `get_next()`/`mark_processing()`/`mark_completed()` |
| Worker thread + auto-refresh rerun interleave | **Race** | Streamlit reruns main thread while worker thread runs |
| Multiple stage workers (ec+ic) running simultaneously | **Race** | Each orchestrator spawns independent daemon thread |
| Worker processes item while pipeline re-initialized | **Data loss** | `initialize_advisory_pipeline()` clears and rebuilds queue |
| Cache set during cache iteration (count_*) | **Stale read** | No read-write lock on `_session_cache` |
| Queue save during queue mutation | **Partial write** | No WAL, no atomic file write |

**Root cause**: Single-threaded design assumption violated by background worker
thread. Shared mutable state (`AdvisoryQueue`, `AdvisoryCache`, global singletons)
accessed without synchronization.

---

## F. Determinism Risk Assessment

| Guarantee | Status | Risk |
|-----------|--------|------|
| Advisory generation deterministic given same LLM input | ✅ | LLM non-determinism is accepted |
| Cache roundtrip deterministic | ✅ | Verified by contract tests |
| Session replay deterministic | ✅ | 81 corpus tests pass |
| Queue processing order deterministic | ⚠️ | Depends on `get_next()` order — not explicitly guaranteed |
| Prefilter behavior deterministic across sessions | ❌ | `_seen_titles` accumulates indefinitely |
| Backoff timing deterministic | ❌ | `random.uniform()` in `_calculate_backoff()` |
| Cross-run `generated_at` identical | ❌ | Expected — documented as runtime-only |
| Cross-run advisory hash identical | ⚠️ | Not computed for `AdvisoryResult` (only for `StructuredAdvisory`) |

**Critical determinism risk**: The prefilter deduplication (`_seen_titles`) is the
only mechanism that can SILENTLY change advisory output across runs without any
change to input data. A title seen in batch 1 affects batch 2's behavior. This
violates the "replay equivalence" guarantee.

---

## G. Scalability Risk Assessment

| Dimension | 1k studies | 10k studies | 100k studies |
|-----------|-----------|-------------|--------------|
| Cache memory | ~20MB | ~200MB | **~2GB** (likely OOM) |
| Cache iteration (telemetry) | ~1ms | ~10ms | **~100ms per call** |
| Queue state JSON | ~50KB | ~500KB | **~5MB per save** |
| Worker throughput (single) | ~5 min | ~50 min | **~8 hours** |
| UI rerun (full render) | ~100ms | ~1s | **~10s** |
| Disk cache (JSON files) | ~2MB | ~20MB | **~200MB** |

The cache iteration problem is the most acute: each rerun triggers 3 full scans
(`count_prefiltered`, `count_quarantined`, `count_llm_generated`). At 100k studies,
this means iterating 300k advisory objects per rerun.

---

## H. Recommended Architectural Refactors

### H.1. Queue Transaction Log (CRITICAL)

Replace the full-state JSON dump with an append-only operation log:

```
data/queues/{stage}/operations.log  (append-only, line-delimited JSON)
data/queues/{stage}/state.json       (rebuilt from op log on restart)
```

Each operation (enqueue, start, complete, fail) appends a single line. On restart,
replay the log to reconstruct state. The `state.json` is a periodic checkpoint,
not the source of truth.

**This eliminates the crash-corruption vulnerability.**

### H.2. Read-Write Lock on Queue (CRITICAL)

Introduce a `threading.RLock` around all queue mutations:

```python
def mark_processing(self, item):
    with self._lock:
        ...
```

Or use a dedicated `QueueLock` context manager that the worker acquires for the
duration of `get_next() → process_item() → mark_completed()`.

### H.3. Session-Scoped Prefilter (HIGH)

Scope prefilter deduplication to the screening session:

```python
class PrefilterEngine:
    def __init__(self, session_id: str = ""):
        self._session_id = session_id
        self._seen_titles: Dict[str, str] = {}
```

And ensure `reset()` is called at session boundaries by the orchestrator or the
pipeline initialization code. Alternatively, pass `session_id` to scoped instances
and deprecate the singleton.

### H.4. Worker Graceful Shutdown (HIGH)

Replace the daemon thread with a stoppable thread using an `Event`:

```python
class StoppableWorker:
    def __init__(self):
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def process_all(self, ...):
        while not self._stop_event.is_set():
            item = queue.get_next(timeout=1.0)
            if item is None:
                break
            ...
```

Replace `process_all`'s blocking `while True` loop with non-blocking polls that
check the stop event.

### H.5. Cache Eviction Policy (HIGH)

Add LRU eviction or a size cap to `_session_cache`:

```python
from collections import OrderedDict

class AdvisoryCache:
    def __init__(self, max_session_entries: int = 10000):
        self._session_cache: OrderedDict = OrderedDict()
        self._max_entries = max_session_entries

    def _set(self, key, advisory):
        if len(self._session_cache) >= self._max_entries:
            self._session_cache.popitem(last=False)  # evict oldest
        self._session_cache[key] = advisory
```

Or simpler: add TTL-based expiry based on `generated_at`.

### H.6. Atomic Cache Iteration (MEDIUM)

Replace the O(n) per-telemetry scan with precomputed counters:

```python
class AdvisoryCache:
    def __init__(self):
        self._prefiltered_count: int = 0
        self._quarantined_count: int = 0
        self._llm_generated_count: int = 0

    def set(self, advisory, stage):
        # Update counters atomically based on advisory attributes
        ...
```

### H.7. Transactional Cache-Queue Consistency (MEDIUM)

Use a two-phase approach or a combined transaction ID:

```python
transaction_id = uuid4().hex
store_advisory(advisory, stage, transaction_id)
queue.mark_completed(item, transaction_id)
# On restart: detect stale transactions, reconcile
```

### H.8. Remove `stop_worker()` Dead Code (MEDIUM)

Either implement it properly (via Event) or remove it. Leaving a no-op API that
appears to provide shutdown semantics is worse than having no API at all.

### H.9. Fix Queue Reset Path (MEDIUM)

Align the paths used by `reset_queue_for_stage()` and `AdvisoryQueue`:
- `AdvisoryQueue._state_path`: `data/cache/queue_state_{stage}.json`
- `reset_queue_for_stage`: `data/cache/advisory_queue_{stage}.json`

### H.10. Streamlit-Isolated Worker Process (LOW)

For true scalability, move the worker to a separate process:
```
[Streamlit UI] ←IPC/REST→ [Worker Service] ←→ [LLM API]
                                                     ↓
                                             [Cache/Queue store]
```

This would eliminate the single-process bottleneck, allow horizontal scaling,
and provide true isolation. However, this is a significant architectural change
and should be considered only after the above fixes.

---

## I. Priority-Ordered Hardening Roadmap

### Phase I — Crash Safety (Immediate)

| # | Task | Risk Addressed | Effort |
|---|------|---------------|--------|
| 1 | Implement append-only queue operation log (WAL) | Queue corruption on crash | 2d |
| 2 | Add `threading.RLock` to all queue mutations | Concurrency races | 0.5d |
| 3 | Fix `reset_queue_for_stage()` path | Reset ineffectiveness | 0.1d |

### Phase II — Determinism & State Isolation (1-2 weeks)

| # | Task | Risk Addressed | Effort |
|---|------|---------------|--------|
| 4 | Scope prefilter `_seen_titles` to session | Silent cross-session duplicate detection | 0.5d |
| 5 | Call `prefilter.reset()` at pipeline init | Same | 0.1d |
| 6 | Replace daemon thread with `threading.Event`-based stop | Orphaned worker, no-op stop | 1d |
| 7 | Add LRU eviction to session cache | OOM on 100k studies | 0.5d |

### Phase III — Observability (2-3 weeks)

| # | Task | Risk Addressed | Effort |
|---|------|---------------|--------|
| 8 | Precompute cache counters (avoid O(n) iteration) | UI latency on 100k studies | 1d |
| 9 | Add advisory generation latency metrics | No throughput visibility | 1d |
| 10 | Add queue wait time metrics | No bottleneck visibility | 0.5d |
| 11 | Add failure rate tracking per criterion | No error pattern visibility | 1d |

### Phase IV — Resilience (1 month)

| # | Task | Risk Addressed | Effort |
|---|------|---------------|--------|
| 12 | Transactional cache-queue consistency | Inconsistency on crash | 2d |
| 13 | Checkpoint-based worker restart (precompute parity) | No resume after crash | 3d |
| 14 | Circuit breaker for LLM rate limits | No backpressure | 1d |
| 15 | Worker progress persistence (not just queue items) | No recovery on process restart | 2d |

### Phase V — Scalability (2-3 months)

| # | Task | Risk Addressed | Effort |
|---|------|---------------|--------|
| 16 | Extract worker to separate process | Single-process bottleneck | 2w |
| 17 | Add worker pool for parallel processing | Single-threaded throughput | 2w |
| 18 | Replace JSON file cache with SQLite or similar | Disk I/O bottleneck at 100k | 1w |
| 19 | Add horizontal scaling via message queue | 100k+ study throughput | 4w |

---

## J. Production Readiness Assessment

### Current State: NOT PRODUCTION READY

| Criterion | Rating | Justification |
|-----------|--------|---------------|
| Crash survival | ❌ | Queue loss on any crash |
| Concurrency safety | ❌ | No locks on shared state |
| Data integrity | ⚠️ | No WAL, no transaction log |
| Deterministic replay | ⚠️ | Prefilter state leaks across sessions |
| Graceful shutdown | ❌ | Daemon threads, no-op stop |
| Memory bounds | ❌ | Unbounded cache growth |
| Observability | ❌ | No latency/throughput metrics |
| Error recovery | ❌ | No retry beyond per-item backoff |
| Scalability (1k) | ✅ | Acceptable |
| Scalability (10k) | ⚠️ | Marginal — cache iteration becomes visible |
| Scalability (100k) | ❌ | Cache OOM, queue save >5MB, UI rerun >10s |
| Test coverage | ✅ | 211 tests, 3× deterministic |
| Semantic contract | ✅ | Stabilized |
| Documentation | ✅ | Inventory + contract spec |

### Minimum Viable Production Path

1. **Queue WAL + RLock** — eliminates the two CRITICAL risks
2. **Prefilter session scoping** — eliminates the determinism corruption vector
3. **Cache eviction + precomputed counters** — enables 10k-50k studies
4. **Worker graceful shutdown** — eliminates orphaned processing

These 4 changes (Phase I + Phase II items 4-7) would move the system from
"not production ready" to "safe for moderate-scale evaluation."

### Semantic vs Operational Stability

```
Semantic: ████████████████████ 90%  (stable, documented, tested)
Operational: ████░░░░░░░░░░░░ 20%  (fragile, no crash safety, no observability)
```

The semantic contract is production-ready. The runtime orchestration is not.
All 10 "not production ready" failures above are operational, not semantic.
