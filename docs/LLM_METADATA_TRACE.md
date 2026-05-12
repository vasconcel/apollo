# LLM Metadata Trace

## Executive Summary

This document traces the complete metadata lifecycle from ATLAS ingestion through to LLM inference.

**FINDING**: Metadata degradation occurs at the **screening view → LLM call boundary**. Critical provenance data exists canonically but is **NOT passed to the LLM**.

---

## Phase 1: Canonical Metadata Objects

### 1.1 ATLAS Export → NormalizedArticle

**Location**: `src/core/article_metadata.py`

```python
@dataclass
class NormalizedArticle:
    title: str = ""
    abstract: str = ""
    authors: str = ""
    year: Optional[int] = None          # ✓ Canonical
    source: str = ""
    doi: str = ""
    url: str = ""
    keywords: str = ""
    literature_type: str = "WL"          # ✓ Canonical
    global_id: str = ""                 # ✓ Canonical
    local_id: str = ""
    library: str = ""
    publisher: str = ""
    language: str = ""
    provenance_trace: str = ""
    detected_source: str = ""
    parser_used: str = ""
    completeness_score: str = ""
    duplicate_flag: str = ""
    search_string: str = ""
    retrieval_date: str = ""
    raw_data: Dict[str, Any]            # ✓ Canonical
```

### 1.2 ArticleReview (Screening Session)

**Location**: `src/core/screening_session.py`

```python
@dataclass
class ArticleReview:
    article_id: str
    title: str
    abstract: str
    metadata: Dict[str, str]            # ✓ Contains all provenance
    
    # Stage decisions
    ec_stage: str = ""
    ec_notes: str = ""
    ec_timestamp: str = ""
    
    ic_stage: str = ""
    qc_stage: str = ""
```

**Metadata preservation in ArticleReview**:
```python
# ArticleReview.from_article_record() preserves:
metadata = {
    "library": record.library,
    "global_id": record.global_id,
    "local_id": record.local_id,
    "keywords": record.keywords,
    "literature_type": record.literature_type,  # ✓ Preserved
    "url": record.url,
    "source_file": record.source_file,
    "year": record.year,                        # ✓ Preserved (as str)
    "authors": record.authors,
    "ec_decision": record.ec_decision,
    "ic_decision": record.ic_decision,
    "qc_score": record.qc_score,
    "final_decision": record.final_decision
}
```

### 1.3 Provenance Fields in ArticleReview.metadata

| Field | Source | Preserved? | Type | Content |
|-------|--------|-------------|------|---------|
| `literature_type` | ATLAS | ✓ | str | "WL" or "GL" |
| `year` | ATLAS/Year extraction | ✓ | str | "2023" |
| `year_source` | Year extraction | ✓ | str | "atlas", "doi", "manual" |
| `metadata_completeness` | Computed | ✓ | str | "complete", "partial", "minimal" |
| `authors` | ATLAS | ✓ | str | Author names |
| `doi` | ATLAS | ✓ | str | DOI |
| `source` | ATLAS | ✓ | str | Journal/source |
| `library` | ATLAS | ✓ | str | Library name |
| `global_id` | ATLAS | ✓ | str | Unique ID |
| `keywords` | ATLAS | ✓ | str | Keywords |
| `raw_data` | ATLAS | ✓ | dict | Full row |

**VERIFIED**: All canonical metadata fields exist in ArticleReview.metadata.

---

## Phase 2: Screening Session Storage

### 2.1 Session State

```python
ScreeningSession:
    session_id: str
    articles: List[ArticleReview]  # ✓ Full metadata preserved
    dynamic_protocol: Dict
    _audit_chain: List[Dict]
```

### 2.2 Article Review State

```python
article.ec_stage = "include"
article.ec_notes = ""
article.ec_timestamp = "2024-01-15T10:30:00"
article.metadata = {
    "literature_type": "WL",
    "year": "2023",
    "year_source": "atlas",
    "metadata_completeness": "complete",
    # ... all other fields preserved
}
```

**VERIFIED**: Metadata preserved in session state.

---

## Phase 3: UI Rendering

### 3.1 Article Card Rendering

**Location**: `src/ui/modules/ec_screening_view.py` → `render_article_card()`

```python
def render_article_card(article, index: int):
    if isinstance(article, ArticleReview):
        lit_type = article.get_literature_type()  # ✓ Used
        metadata = article.metadata                 # ✓ Used
        
        # Displays: authors, year, source, doi, url, keywords, completeness
```

**VERIFIED**: Metadata used correctly for UI rendering.

### 3.2 Provenance Display

```python
# Year source display
year_source = metadata.get("year_source", "unknown")  # ✓ Shows "atlas"

# Metadata completeness
completeness = metadata.get("metadata_completeness", "unknown")  # ✓ Shows status
```

**VERIFIED**: Provenance fields visible in UI.

---

## Phase 4: LLM Request Assembly ← **BREAKDOWN POINT**

### 4.1 Current Implementation (BROKEN)

**Location**: `src/ui/modules/ec_screening_view.py` → `get_llm_ec_suggestion()`

```python
def get_llm_ec_suggestion(article) -> Optional[Dict]:
    if isinstance(article, ArticleReview):
        title = article.title              # ✓ Extracted
        abstract = article.abstract         # ✓ Extracted
        literature_type = article.get_literature_type()  # ✓ Extracted
        year = article.metadata.get("year", "")  # ⚠ Extracted as STRING
        metadata = article.metadata        # ⚠ Extracted BUT...
    # ...
    
    protocol_criteria = get_protocol_ec_criteria()
    
    suggestion = llm.suggest_ec(
        title=title,
        abstract=abstract,
        literature_type=literature_type,
        protocol_criteria=protocol_criteria
        # ❌ MISSING: metadata parameter NOT PASSED!
    )
```

### 4.2 LLM Function Signature

**Location**: `src/core/llm_assistant.py` → `suggest_ec()`

```python
def suggest_ec(
    self,
    title: str,
    abstract: str,
    literature_type: str = "WL",
    year: Optional[int] = None,
    protocol_criteria: Optional[Dict[str, str]] = None,
    metadata: Optional[Dict[str, Any]] = None  # ✓ Accepts metadata
) -> AdvisorySuggestion:
```

### 4.3 What Happens Without Metadata

When `metadata=None` (current broken state):

```python
year_source = metadata.get("year_source", "unknown") if metadata else "unknown"
# Result: "unknown"

metadata_completeness = metadata.get("metadata_completeness", "unknown") if metadata else "unknown"
# Result: "unknown"
```

**PROMPT OUTPUT (BROKEN)**:
```
Article Title: Example Paper
Year: Unknown (source: unknown)        # ❌ Year and source are UNKNOWN
Type: WL
Metadata Completeness: unknown        # ❌ Completeness UNKNOWN
Abstract: ...
```

---

## Phase 5: LLM Prompt Construction

### 5.1 Current Prompt (BROKEN)

```python
prompt = f"""You are an expert systematic review assistant. Analyze this article for EXCLUSION CRITERIA (EC).

Article Title: {title}
Year: {year or 'Unknown'} (source: {year_source})  # ❌ year_source = "unknown"
Type: {literature_type}
Metadata Completeness: {metadata_completeness}       # ❌ = "unknown"
Abstract: {abstract[:800] if abstract else 'No abstract available'}

ACTIVE EC CRITERIA:
- EC1: Not empirical SE research
- EC2: Published before 2015
- EC3: Not peer-reviewed (for WL)
- EC4: Duplicate publication
```

### 5.2 What LLM Receives (BROKEN)

| Field | Expected | Actual (Broken) | Root Cause |
|-------|----------|----------------|-----------|
| `year` | 2023 | Unknown | metadata not passed |
| `year_source` | atlas | unknown | metadata not passed |
| `metadata_completeness` | complete | unknown | metadata not passed |
| `literature_type` | WL | WL | ✓ Correctly passed |

---

## Root Cause Analysis

### Issue 1: Metadata Parameter Not Passed

**Location**: `src/ui/modules/ec_screening_view.py:367-372`

```python
# BROKEN CODE
suggestion = llm.suggest_ec(
    title=title,
    abstract=abstract,
    literature_type=literature_type,
    protocol_criteria=protocol_criteria
)
# metadata is extracted at line 336 but NEVER used!

# FIX REQUIRED
suggestion = llm.suggest_ec(
    title=title,
    abstract=abstract,
    literature_type=literature_type,
    protocol_criteria=protocol_criteria,
    metadata=metadata  # ← ADD THIS
)
```

### Issue 2: Year Type Mismatch

**Location**: `src/ui/modules/ec_screening_view.py:335`

```python
year = article.metadata.get("year", "")  # Returns STRING "2023"
```

**LLM expects**: `Optional[int]`

```python
# In suggest_ec()
prompt += f"Year: {year or 'Unknown'} (source: {year_source})"
# If year is string "2023", this works (Python coerces)
# But year_source is "unknown" because metadata not passed
```

### Issue 3: EC3 Semantic Ambiguity

**Location**: `src/core/criteria_registry.py:50`

```python
EC_DESCRIPTIONS: Dict[str, str] = {
    "EC3": "Not peer-reviewed (for WL)",  # ⚠ Ambiguous wording
}
```

**Problem**: "Not peer-reviewed (for WL)" could be interpreted as:
- "This paper is not peer-reviewed" (correct for exclusion)
- "This criterion only applies to WL" (correct)

The parenthetical creates semantic ambiguity that the LLM may interpret incorrectly.

---

## Summary of Findings

| Stage | Metadata Status | Notes |
|-------|---------------|-------|
| ATLAS → NormalizedArticle | ✓ Complete | All fields normalized |
| → ArticleReview | ✓ Complete | metadata dict preserved |
| → ScreeningSession | ✓ Complete | Session stores full articles |
| → UI Rendering | ✓ Complete | Displays all provenance |
| → LLM Request | ❌ BROKEN | metadata NOT passed |
| → LLM Prompt | ❌ DEGRADED | year_source="unknown" |

### Critical Fields Lost in LLM Context

1. `year_source` → becomes "unknown"
2. `metadata_completeness` → becomes "unknown"

### Fields Preserved

1. `title` → ✓
2. `abstract` → ✓
3. `literature_type` → ✓

### Fields Partially Preserved

1. `year` → ✓ Value passed, but type is string not int

---

## Recommended Fixes

1. **Pass metadata to LLM functions** in all screening views
2. **Add year_source to IC prompts** (currently missing entirely)
3. **Clarify EC3 wording** to eliminate semantic ambiguity
4. **Add logging** to capture final prompt before inference
