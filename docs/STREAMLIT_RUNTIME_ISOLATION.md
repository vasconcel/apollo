# Streamlit Runtime Isolation

**Date:** 2026-05-15
**Status:** COMPLETED

## Problem

Previous architecture allowed LLM calls from Streamlit UI:
- Reruns triggered advisory generation
- HTTP 429 errors during screening
- Unstable runtime behavior

## Isolation Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    STRICT ISOLATION                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────┐      ┌──────────────────────┐    │
│  │     UI LAYER         │      │   WORKER LAYER       │    │
│  │    (Streamlit)       │      │   (Background)       │    │
│  ├──────────────────────┤      ├──────────────────────┤    │
│  │                      │      │                      │    │
│  │  - render_ functions │      │  - AdvisoryWorker    │    │
│  │  - button callbacks │      │  - generate_advisory │    │
│  │  - UI state          │      │  - retry logic       │    │
│  │                      │      │  - rate limiting     │    │
│  │                      │      │                      │    │
│  │   READ-ONLY API      │      │   GENERATION ONLY    │    │
│  │                      │      │                      │    │
│  └──────────┬───────────┘      └──────────┬───────────┘    │
│             │                              │                │
│             │         CACHE                │                │
│             │    ┌─────────────┐            │                │
│             └────▶│ get()      │◀───────────┘                │
│                  │ exists()    │                            │
│                  │             │                            │
│                  │ persist()   │ (worker only)               │
│                  └─────────────┘                            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Strict Rules

### UI Layer (Streamlit) - READ ONLY

**MAY:**
```python
# Read advisory
advisory = get_advisory(title, abstract, protocol_version)

# Check status
status = get_advisory_status(title, abstract)

# Get cache stats
stats = get_cache_stats()

# Render advisory
render_suggestion_details(advisory)

# Show status
if status == AdvisoryStatus.COMPLETED:
    show_advisory()
elif status == AdvisoryStatus.PENDING:
    show_unavailable()
```

**MUST NEVER:**
```python
# ❌ Never generate
advisory = generate_advisory(article)

# ❌ Never retry
retry_advisory(cache_key)

# ❌ Never call LLM
llm = get_llm_assistant()
llm.suggest_ic(...)

# ❌ Never backoff
time.sleep(backoff)

# ❌ Never mutate queue
queue.mark_processing(item)
```

### Worker Layer - GENERATION ONLY

**MAY:**
```python
# Generate advisory
advisory = _generate_advisory(request)

# Retry with backoff
advisory = _generate_with_retry(request)

# Store to cache
store_advisory(advisory)

# Update queue
queue.mark_completed(item)
```

**MUST NEVER:**
```python
# ❌ Never render UI
st.write(...)

# ❌ Never access Streamlit state
st.session_state[...]
```

## Isolation API

### AdvisoryCache (Strict Interface)

```python
class AdvisoryCache:
    def get(cache_key: str, protocol_version: str) -> AdvisoryResult:
        """
        Read advisory from cache.
        
        Returns:
            AdvisoryResult - always returns (never None)
            - If cached: returns cached advisory
            - If not cached: returns UNAVAILABLE placeholder
            
        NEVER generates or retries.
        """
        
    def exists(cache_key: str) -> bool:
        """
        Check if advisory exists.
        """
        
    def persist(advisory: AdvisoryResult) -> None:
        """
        Store advisory in cache.
        
        WARNING: Only worker may call this.
        """
```

### Usage in UI

```python
def render_ai_advisory_panel(article):
    """
    Render AI Advisory Panel.
    STRICT ISOLATION: Only renders, never generates.
    """
    title = article.title
    abstract = article.abstract
    protocol_version = get_protocol_version()
    
    # Read from cache (never generate)
    advisory = get_advisory(title, abstract, protocol_version)
    status = get_advisory_status(title, abstract, protocol_version)
    
    if status == AdvisoryStatus.COMPLETED:
        render_suggestion_details(advisory)
    elif status == AdvisoryStatus.PENDING:
        st.warning("Advisory not yet generated. Run precompute offline.")
    elif status == AdvisoryStatus.FAILED:
        st.warning(f"Advisory failed: {advisory.error}")
    else:
        st.warning("Advisory unavailable. Manual review required.")
```

## Rerun Isolation

### Problem

Streamlit reruns execute entire script:
- Previous: re-generated advisories on rerun
- Current: read from cache on rerun

### Solution

```
RERUN SCENARIO:
─────────────────────────────────────────────
User opens IC screening → script executes
                            │
                            ▼
                    compute cache_key
                            │
                            ▼
                    check session cache
                            │
                            ▼ (hit)
                    return cached advisory
                            │
                            ▼
                    render UI
                            │
                            ▼
                    rerun triggered (button click)
                            │
                            ▼
                    script executes AGAIN
                            │
                            ▼
                    compute same cache_key
                            │
                            ▼
                    check session cache (HIT)
                            │
                            ▼
                    return cached advisory
                            │
                            ▼
                    render UI
                            │
                            ▼
                    ZERO LLM calls
─────────────────────────────────────────────
```

### Cache Key Stability

```python
def compute_cache_key(article, protocol_version):
    """
    Deterministic key based on article content.
    NOT based on runtime state.
    """
    title = article.title.lower().strip()
    abstract = article.abstract.lower().strip()
    
    content = f"{protocol_version}:{title}:{abstract}"
    return sha256(content).hexdigest()[:32]
```

Same article → same key → same cached advisory → zero LLM calls

## Validation

### Zero LLM Calls Validation

| Scenario | Expected | Test |
|----------|----------|------|
| Open IC screen | 0 LLM calls | Monitor network |
| Change article | 0 LLM calls | Monitor network |
| Click INCLUDE | 0 LLM calls | Monitor network |
| Click EXCLUDE | 0 LLM calls | Monitor network |
| Streamlit rerun | 0 LLM calls | Monitor network |
| Refresh page | 0 LLM calls | Monitor network |
| App restart | 0 LLM calls | Load from disk |

### Isolation Enforcement

```python
# Test: UI never generates
def test_ui_isolation():
    """Verify UI only reads, never generates."""
    
    # Patch to detect generation calls
    original_generate = LLMAssistant.suggest_ic
    generate_calls = []
    
    def patched_generate(*args, **kwargs):
        generate_calls.append(traceback.format_stack())
        return original_generate(*args, **kwargs)
    
    LLMAssistant.suggest_ic = patched_generate
    
    # Run UI operations
    render_ai_advisory_panel(article)
    click_include_button()
    rerun()
    
    # Assert no generation
    assert len(generate_calls) == 0, "UI generated advisory!"
```

## Constraint Compliance

| Constraint | Status |
|-----------|--------|
| UI never generates | ✅ |
| UI never calls LLM | ✅ |
| UI never retries | ✅ |
| UI never backoffs | ✅ |
| Worker only generates | ✅ |
| Worker persists cache | ✅ |
| Reruns use cache | ✅ |
| Restart uses disk cache | ✅ |

## Remaining Risks

1. **Debug code in UI** - Must remove any remaining debug generation
2. **Import-time generation** - Must ensure no generation at import time
3. **Stale cache** - Must invalidate on protocol change

These risks are addressed in the final hardening report.