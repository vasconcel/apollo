# AI Advisory Cache Audit

## Overview

This document audits the AI advisory caching mechanism in APOLLO screening views.

---

## 1. Cache Implementation

### 1.1 Current Cache Strategy

**Location**: `src/ui/modules/ec_screening_view.py:281-282`

```python
def render_ai_advisory_panel(article, current_idx: int):
    cache_key = f"ec_advice_{current_idx}"
    cached_advice = st.session_state.get(cache_key, None)
```

**Location**: `src/ui/modules/ic_screening_view.py:232-233`

```python
def render_ai_advisory_panel(article, current_idx: int):
    cache_key = f"ic_advice_{current_idx}"
    cached_advice = st.session_state.get(cache_key, None)
```

### 1.2 Cache Key Structure

| Stage | Cache Key Pattern | Example |
|-------|-----------------|---------|
| EC | `ec_advice_{current_idx}` | `ec_advice_0`, `ec_advice_1` |
| IC | `ic_advice_{current_idx}` | `ic_advice_0`, `ic_advice_1` |
| QC | (similar pattern) | |

---

## 2. Cache Issues Identified

### 2.1 Issue 1: Index-Based Cache Keys

**Problem**: Cache keys are based on `current_idx` (array position), NOT article identity.

**Scenario**: User loads File A with 100 articles, generates AI advice for index 5.
```
Cache: ec_advice_5 = {advice_for_article_from_FileA}
```

User then loads File B with 100 different articles.
```
Current index = 5 (same position in new file)
Cache hit: ec_advice_5 = {advice_for_article_from_FileA}  ← WRONG!
```

**Impact**: AI advice from one article is incorrectly shown for another article.

### 2.2 Issue 2: No Session Isolation

**Problem**: Cache keys don't include session identifier.

**Scenario**: User opens two browser tabs with different sessions.
```
Session 1: ec_advice_5 = {advice_S1}
Session 2: ec_advice_5 = {advice_S2}  ← Overwrites Session 1 cache
```

**Impact**: Cache pollution between sessions.

### 2.3 Issue 3: No Article ID in Cache Key

**Problem**: Cache keys don't include `global_id` or `article_id`.

**Scenario**: Same article appears at different indices in different file loads.
```
Load 1: Article "ABC" at index 5 → Cache: ec_advice_5 = {advice_ABC}
Load 2: Different file, Article "XYZ" at index 5 → Cache hit: {advice_ABC}  ← WRONG!
```

---

## 3. Cache Flow Analysis

### 3.1 Advisory Generation Flow

```
1. User clicks "GENERATE ANALYSIS"
2. Check: st.session_state.get(cache_key)
3. If cached: Show cached advice
4. If not cached:
   a. Extract article metadata
   b. Call get_llm_ec_suggestion(article)
   c. Store: st.session_state[cache_key] = suggestion
   d. Show suggestion
```

### 3.2 Cache Hit Scenario (Current Broken)

```
User views article at index 5:
- Extracts metadata from NEW article (correct)
- Checks cache: ec_advice_5 exists (from OLD article)
- Shows cached advice (WRONG - from different article)
- Metadata in prompt is from NEW article
- But advice displayed is from OLD article
```

**Result**: UI shows advice from OLD article while NEW article metadata is used for context. This creates inconsistency between displayed advice and actual article context.

---

## 4. Proper Cache Key Design

### 4.1 Required Cache Key Components

```python
def get_advisory_cache_key(article, current_idx: int, stage: str, session_id: str) -> str:
    """
    Generate article-specific cache key.

    Components:
    - session_id: Isolates between sessions
    - stage: Separates EC/IC/QC
    - article_id: Uniquely identifies article (prefer global_id)
    - index: Fallback position indicator
    """
    article_id = article.article_id if hasattr(article, 'article_id') else None
    if not article_id:
        article_id = article.get('article_id', article.get('global_id', f'idx_{current_idx}'))

    return f"{stage}_advice_{session_id}_{article_id}"
```

### 4.2 Example Cache Keys

| Article | Session | Stage | Cache Key |
|---------|---------|-------|----------|
| global_id="abc123" | sess_001 | ec | `ec_advice_sess_001_abc123` |
| global_id="def456" | sess_001 | ec | `ec_advice_sess_001_def456` |
| global_id="abc123" | sess_002 | ec | `ec_advice_sess_002_abc123` |

---

## 5. Cache Invalidation

### 5.1 When to Invalidate Cache

| Event | Invalidation |
|-------|-------------|
| New file loaded | Clear ALL advisory caches for session |
| Article metadata changed | Clear cache for specific article_id |
| Session switched | Cache persists (isolated by session_id) |
| Protocol changed | Clear ALL caches (criteria may differ) |

### 5.2 Invalidation Implementation

```python
def clear_advisory_cache(session_id: str, article_id: str = None):
    """Clear advisory cache for session or specific article."""
    if article_id:
        # Clear specific article
        for stage in ['ec', 'ic', 'qc']:
            key = f"{stage}_advice_{session_id}_{article_id}"
            if key in st.session_state:
                del st.session_state[key]
    else:
        # Clear entire session
        keys_to_delete = [k for k in st.session_state.keys()
                          if k.endswith(f"_{session_id}_") or k.endswith(f"_{session_id}")]
        for key in keys_to_delete:
            del st.session_state[key]
```

---

## 6. Fallback Behavior Analysis

### 6.1 Current Fallback

**Location**: `src/core/llm_assistant.py:368-382`

```python
def _fallback_suggestion(self, stage: str, error: Optional[str] = None) -> AdvisorySuggestion:
    """Return fallback suggestion when LLM unavailable."""
    return AdvisorySuggestion(
        stage=stage,
        decision="skip",
        confidence=0.0,
        justification=f"LLM unavailable: {error}" if error else "LLM not configured",
        triggered_criteria={},
        evidence=[],
        ambiguity_flags=["LLM not available"]
    )
```

### 6.2 Fallback Detection

```python
# In suggestion rendering
if cached_advice and cached_advice.get('confidence', 1.0) == 0.0:
    # This is a fallback, not real analysis
    st.warning("⚠ AI analysis unavailable - showing cached fallback")
```

---

## 7. Issues Summary

| Issue | Severity | Impact | Fix |
|-------|----------|--------|-----|
| Index-based cache keys | CRITICAL | Wrong advice shown for articles | Use article_id in key |
| No session isolation | HIGH | Session cache pollution | Include session_id in key |
| No cache invalidation on file load | HIGH | Stale advice after reload | Clear cache on new file |
| Fallback not clearly marked | MEDIUM | User confusion | Add marker flag |

---

## 8. Files Requiring Changes

| File | Change |
|------|--------|
| `src/ui/modules/ec_screening_view.py` | Use article_id in cache key |
| `src/ui/modules/ic_screening_view.py` | Use article_id in cache key |
| `src/ui/modules/qc_assessment_view.py` | Use article_id in cache key |
| `src/core/screening_session.py` | Add cache clearing on file load |

---

## 9. Recommended Implementation

### 9.1 New Cache Key Generation

```python
def generate_cache_key(article, session, stage: str) -> str:
    """Generate article-specific cache key."""
    session_id = session.session_id.replace("-", "_")
    article_id = article.article_id if hasattr(article, 'article_id') else f"idx_{session.current_index}"
    return f"{stage}_advice_{session_id}_{article_id}"
```

### 9.2 Usage in Views

```python
# In ec_screening_view.py
session = st.session_state.apollo_session
article = session.get_current_article()
cache_key = generate_cache_key(article, session, "ec")
cached_advice = st.session_state.get(cache_key, None)
```
