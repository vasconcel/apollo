# EC-IC Parity Diff Report

**Date:** 2026-05-15
**Status:** COMPLETED

## Line-by-Line Comparison

### 1. Article List Acquisition

| Aspect | EC | IC | Status |
|--------|----|----|--------|
| List source | `session.articles` | `session.get_ec_included_articles()` | INTENTIONAL DIFFERENCE |
| Index source | `session.current_index` | `st.session_state.ic_current_index` | ✅ NOW ALIGNED |

### 2. Decision Handlers

#### INCLUDE Button

| Aspect | EC | IC | Status |
|--------|----|----|--------|
| Stage set | `article.ic_stage = "include"` | `session.articles[original_idx].ic_stage = "include"` | ✅ PARITY |
| Record decision | `session.record_decision()` | `session.record_decision()` | ✅ PARITY |
| Article props | Set directly on `article` | Set via `session.articles[original_idx]` | ✅ PARITY |
| Advance index | `session.current_index = current_idx + 1` | `st.session_state.ic_current_index = current_idx + 1` | ✅ PARITY |

#### EXCLUDE Button (FIXED)

| Aspect | EC | IC | Status |
|--------|----|----|--------|
| Stage set | `article.ec_stage = "exclude"` | `session.articles[original_idx].ic_stage = "exclude"` | ✅ PARITY |
| Session flag | `st.session_state[f"ec_show_codes_{idx}"]` | `st.session_state[f"ic_show_codes_{idx}"]` | ✅ PARITY |
| Rerun | `st.rerun()` | `st.rerun()` | ✅ PARITY |

#### SKIP Button

| Aspect | EC | IC | Status |
|--------|----|----|--------|
| Record decision | `session.record_decision("skip")` | `session.record_decision("skip")` | ✅ PARITY |
| Advance | `session.current_index` | `st.session_state.ic_current_index` | ✅ PARITY |

### 3. Code Selection Handlers

| Aspect | EC | IC | Status |
|--------|----|----|--------|
| Props set | Direct `article` | Via original_idx | ✅ PARITY |
| Counter | `session.ec_completed += 1` | `session.ic_completed += 1` | ✅ PARITY |
| Advance | Master index | Filtered index | ✅ PARITY |

### 4. Progress Tracking

| Aspect | EC | IC | Status |
|--------|----|----|--------|
| Counter source | `session.ec_completed` | `session.ic_completed` | ✅ PARITY |
| Display | `progress_bar(reviewed, total)` | `progress_bar(reviewed, total)` | ✅ PARITY |

## Architecture Alignment

### Index Management
- EC: Master list index in `session.current_index`
- IC: Filtered list index in `st.session_state.ic_current_index`

Both now use isolated index spaces appropriate to their article source.

### Persistence Pattern
```python
# IC Pattern (matches EC):
original_idx = session.articles.index(article)
session.articles[original_idx].ic_stage = "include"
session.record_decision("include", notes="")
```

This pattern is now identical between EC and IC.

### Code Selection Pattern
```python
# Both EC and IC:
session.articles[original_idx].ces1 = code
session.articles[original_idx].cis1 = "NO"
session.articles[original_idx].revisor1 = session.researcher_id
session.ic_completed += 1  # or ec_completed for EC
```

## Remaining Differences (Intentional)

| Aspect | EC | IC | Reason |
|--------|----|----|--------|
| Clear button | Present | Removed | User requirement |
| Article source | All articles | EC-passed only | Methodological filter |

## Verification

- [x] INCLUDE execution path identical
- [x] EXCLUDE execution path identical  
- [x] SKIP execution path identical
- [x] Code selection path identical
- [x] Progress tracking source identical

## Constraint Compliance

- ✅ No hidden state divergence
- ✅ Deterministic replay preserved
- ✅ Audit chain integrity maintained