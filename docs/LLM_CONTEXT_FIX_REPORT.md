# LLM Context Fix Report

## Executive Summary

This document details the fixes implemented to resolve metadata degradation in the LLM context assembly.

**Root Cause**: Metadata was extracted but NOT passed to LLM functions in screening views.

**Impact**: Year source and metadata completeness appeared as "unknown" in prompts, causing incorrect advisory reasoning.

---

## Fixes Implemented

### Fix 1: Pass Metadata to suggest_ec()

**File**: `src/ui/modules/ec_screening_view.py`

**Change**: Added `metadata=metadata` parameter to `llm.suggest_ec()` call

**Before**:
```python
suggestion = llm.suggest_ec(
    title=title,
    abstract=abstract,
    literature_type=literature_type,
    protocol_criteria=protocol_criteria
)
```

**After**:
```python
suggestion = llm.suggest_ec(
    title=title,
    abstract=abstract,
    literature_type=literature_type,
    protocol_criteria=protocol_criteria,
    metadata=metadata  # ← ADDED
)
```

---

### Fix 2: Pass Metadata to suggest_ic()

**File**: `src/ui/modules/ic_screening_view.py`

**Change**: Extracted metadata and added `metadata=metadata` parameter

**Before**:
```python
if isinstance(article, ArticleReview):
    title = article.title
    abstract = article.abstract
    literature_type = article.get_literature_type()
    # metadata not extracted

suggestion = llm.suggest_ic(
    title=title,
    abstract=abstract,
    literature_type=literature_type,
    protocol_criteria=protocol_criteria
)
```

**After**:
```python
if isinstance(article, ArticleReview):
    title = article.title
    abstract = article.abstract
    literature_type = article.get_literature_type()
    metadata = article.metadata  # ← EXTRACTED

suggestion = llm.suggest_ic(
    title=title,
    abstract=abstract,
    literature_type=literature_type,
    protocol_criteria=protocol_criteria,
    metadata=metadata  # ← ADDED
)
```

---

### Fix 3: Add Metadata Parameter to suggest_ic()

**File**: `src/core/llm_assistant.py`

**Change**: Extended `suggest_ic()` to accept metadata parameter

**Before**:
```python
def suggest_ic(
    self,
    title: str,
    abstract: str,
    literature_type: str = "WL",
    protocol_criteria: Optional[Dict[str, str]] = None
) -> AdvisorySuggestion:
```

**After**:
```python
def suggest_ic(
    self,
    title: str,
    abstract: str,
    literature_type: str = "WL",
    protocol_criteria: Optional[Dict[str, str]] = None,
    metadata: Optional[Dict[str, Any]] = None  # ← ADDED
) -> AdvisorySuggestion:
```

---

### Fix 4: Add Provenance Context to Prompts

**File**: `src/core/llm_assistant.py`

**Changes**:
1. Added `year_source` to IC prompt
2. Added `metadata_completeness` to IC prompt
3. Added literature type context (WL/GL definitions)

**IC Prompt - Before**:
```
Article Title: {title}
Type: {literature_type}
Abstract: {abstract}
```

**IC Prompt - After**:
```
Article Title: {title}
Type: {literature_type} - White Literature - peer-reviewed academic publications (journals, conferences)
Year Source: {year_source}
Metadata Completeness: {metadata_completeness}
Abstract: {abstract}

IMPORTANT CONTEXT:
- IC criteria assess RELEVANCE to the research question
- Articles that passed EC are already deemed empirical and recent
- Focus on whether the study addresses SE Recruitment & Selection (R&S)
```

---

### Fix 5: Add Literature Context to EC Prompt

**File**: `src/core/llm_assistant.py`

**Before**:
```
Type: {literature_type}
Abstract: {abstract}
```

**After**:
```
Type: {literature_type} - White Literature - peer-reviewed academic publications (journals, conferences)
Metadata Completeness: {metadata_completeness}
Abstract: {abstract}

IMPORTANT CONTEXT:
- WL (White Literature) = PEER-REVIEWED academic sources
- GL (Grey Literature) = NON-PEER-REVIEWED sources (blogs, reports, etc.)
- EC criteria filter out inappropriate sources BEFORE relevance assessment
- Year source indicates data reliability: 'atlas' = reliable, 'manual' = manual entry
```

---

### Fix 6: Fix EC3 Semantic Ambiguity

**File**: `src/core/criteria_registry.py`

**Change**: Rewrote EC3 criterion description

**Before**:
```python
"EC3": "Not peer-reviewed (for WL)",
```

**After**:
```python
"EC3": "Not peer-reviewed - WL sources must be peer-reviewed academic publications",
```

**File**: `src/ui/modules/ec_screening_view.py`

Also updated the fallback criteria to match.

---

### Fix 7: Add LLM Request Logging

**File**: `src/core/llm_assistant.py`

**Change**: Added optional logging for debugging

**Usage**:
```bash
export APOLLO_LLM_LOGGING=1
```

This will log the final prompt before inference for debugging.

---

## Before vs After Payload Comparison

### EC Prompt - Before (Broken)

```
Article Title: Software Engineering Recruitment Practices in Tech Companies
Year: 2023 (source: unknown)          ← year_source = "unknown"
Type: WL
Metadata Completeness: unknown          ← metadata_completeness = "unknown"
Abstract: This study investigates...

ACTIVE EC CRITERIA:
- EC1: Not empirical SE research
- EC2: Published before 2015
- EC3: Not peer-reviewed (for WL)    ← Ambiguous wording
- EC4: Duplicate publication
```

### EC Prompt - After (Fixed)

```
Article Title: Software Engineering Recruitment Practices in Tech Companies
Year: 2023 (source: atlas)            ← year_source = "atlas"
Type: WL - White Literature - peer-reviewed academic publications
Metadata Completeness: complete       ← metadata_completeness = "complete"
Abstract: This study investigates...

IMPORTANT CONTEXT:
- WL (White Literature) = PEER-REVIEWED academic sources
- GL (Grey Literature) = NON-PEER-REVIEWED sources (blogs, reports, etc.)
- EC criteria filter out inappropriate sources BEFORE relevance assessment
- Year source indicates data reliability: 'atlas' = reliable

ACTIVE EC CRITERIA:
- EC1: Not empirical SE research
- EC2: Published before 2015
- EC3: Not peer-reviewed - WL sources must be peer-reviewed academic publications  ← Clear wording
- EC4: Duplicate publication
```

### IC Prompt - Before (Broken)

```
Article Title: Best Practices for Hiring Software Engineers
Type: WL                              ← No literature context
Abstract: This paper describes...

ACTIVE IC CRITERIA:
- IC1: Addresses R&S practices
- IC2: Reports empirical findings
- IC3: Focuses on software industry context
```

### IC Prompt - After (Fixed)

```
Article Title: Best Practices for Hiring Software Engineers
Type: WL - White Literature - peer-reviewed academic publications (journals, conferences)
Year Source: atlas
Metadata Completeness: complete
Abstract: This paper describes...

IMPORTANT CONTEXT:
- IC criteria assess RELEVANCE to the research question
- Articles that passed EC are already deemed empirical and recent
- Focus on whether the study addresses SE Recruitment & Selection (R&S)

ACTIVE IC CRITERIA:
- IC1: Addresses R&S practices
- IC2: Reports empirical findings
- IC3: Focuses on software industry context
```

---

## Expected Behavior Changes

| Issue | Before | After |
|-------|--------|-------|
| Year source in EC prompt | "unknown" | "atlas" (or actual source) |
| Completeness in EC prompt | "unknown" | "complete" (or actual) |
| Year source in IC prompt | N/A (not included) | Actual source |
| Completeness in IC prompt | N/A (not included) | Actual completeness |
| Literature type context | Just "WL" or "GL" | Full definition |
| EC3 wording | "Not peer-reviewed (for WL)" | "Not peer-reviewed - WL sources must be peer-reviewed" |

---

## Testing Recommendations

### Manual Test: Verify Metadata Propagation

1. Load an ATLAS file with known metadata
2. Enter EC screening workspace
3. Click "GENERATE ANALYSIS" on an article
4. Enable `APOLLO_LLM_LOGGING=1`
5. Check logs for prompt with:
   - `Year: 2023 (source: atlas)`
   - `Metadata Completeness: complete`
   - `Type: WL - White Literature...`

### Automated Test: Payload Verification

```python
def test_llm_payload_includes_metadata():
    """Verify metadata is included in LLM prompt."""
    metadata = {
        'year': '2023',
        'year_source': 'atlas',
        'metadata_completeness': 'complete'
    }

    # Mock LLM call and capture prompt
    llm = LLMAssistant()
    # ... capture prompt ...

    assert 'source: atlas' in prompt
    assert 'metadata_completeness: complete' in prompt
    assert 'White Literature' in prompt
```

---

## Files Modified

| File | Changes |
|------|---------|
| `src/ui/modules/ec_screening_view.py` | Pass metadata to suggest_ec() |
| `src/ui/modules/ic_screening_view.py` | Extract and pass metadata to suggest_ic() |
| `src/core/llm_assistant.py` | Accept metadata in suggest_ic(), add context to prompts, add logging |
| `src/core/criteria_registry.py` | Fix EC3 wording |

---

## Verification Checklist

- [x] metadata extracted in ec_screening_view
- [x] metadata passed to suggest_ec()
- [x] metadata extracted in ic_screening_view
- [x] metadata passed to suggest_ic()
- [x] suggest_ic() accepts metadata parameter
- [x] IC prompt includes year_source
- [x] IC prompt includes metadata_completeness
- [x] EC prompt includes literature type context
- [x] IC prompt includes literature type context
- [x] EC3 wording fixed
- [x] LLM logging added
- [ ] Manual verification completed
- [ ] Integration tests added
