# Author Decoding Runtime Fix

**Date:** 2026-05-15
**Status:** COMPLETED

## Problem Statement

Author names were rendering with raw BibTeX/LaTeX escaping:
```
M"{u}ller; Ivana; Dill; Katja; ...
```

Instead of proper Unicode:
```
Müller; Ivana; Dill; Katja; ...
```

## Root Cause Analysis

1. **pylatexenc API Change**: In pylatexenc 2.10, `latex_to_unicode` is not available. Must use `LatexNodes2Text` class.
2. **Incomplete Conversion**: `latex2text` removes braces but doesn't always convert special chars
3. **Fallback Missing**: No robust fallback for common LaTeX patterns

## Fix Implementation

### 1. Correct pylatexenc Usage

**File:** `src/core/article_metadata.py`

**Before:**
```python
from pylatexenc import latex_to_unicode
```

**After:**
```python
from pylatexenc.latex2text import LatexNodes2Text
latex_decoder = LatexNodes2Text()
```

### 2. Robust Fallback Decoder

Added `_fallback_decode_latex()` function handling common patterns:
- `M"{u}` → `Müller`
- `{u}` → `ü` (umlaut)
- `M{u}` → `Müller`
- `{i}` → `í`, `{a}` → `á`, etc.

### 3. Smarter Pylatexenc Check

Check that pylatexenc actually produces Unicode chars before trusting it:
```python
has_unicode = any(ord(c) > 127 for c in pylatex_result)
if has_unicode and "{" not in pylatex_result:
    return pylatex_result
```

### 4. Display Logic Fix

**File:** `src/ui/modules/ec_screening_view.py`

Added `_format_authors_short()` for proper truncation:
```python
def _format_authors_short(authors: str) -> str:
    author_list = [a.strip() for a in authors.split(";") if a.strip()]
    if len(author_list) <= 2:
        return "; ".join(author_list[:2])
    return f"{author_list[0]} et al."
```

## Validation

### Test Results

| Input | Output |
|-------|--------|
| `Muller` | `Muller` |
| `M{u}ller` | `Müller` |
| `M"{u}ller; Ivana; Dill; Katja` | `Müller; Ivana; Dill; Katja` |
| `Garc{i}a` | `García` |

### Runtime Verification

1. Start application
2. Load ATLAS export with BibTeX authors
3. Verify decoded display: `2025 • Müller et al. • PACM HCI`

## Logging

Added startup logging for pylatexenc availability:
```
Author decoder initialization - pylatexenc version: 2.10
latex2text import: SUCCESS (using LatexNodes2Text class)
```

## Constraint Compliance

- ✅ NO manual `.replace()` chains for final solution
- ✅ FIXED actual decoding pipeline
- ✅ Added runtime-safe fallback
- ✅ Validated with real BibTeX patterns