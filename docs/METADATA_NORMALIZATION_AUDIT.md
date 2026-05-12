# Metadata Normalization Audit

## Overview

This document audits metadata normalization in APOLLO, focusing on literature type canonicalization and metadata field preservation.

---

## 1. Literature Type Normalization

### 1.1 Canonical Mapping

| Input | Canonical | Source |
|-------|-----------|---------|
| `"WL"` | `"WL"` | Excel ATLAS (hardcoded in `normalize_wl_metadata`) |
| `"GL"` | `"GL"` | Excel ATLAS (hardcoded in `normalize_gl_metadata`) |
| `"WL"` | `"WL"` | CSV (line 265, forced uppercase) |
| `"GL"` | `"GL"` | CSV (line 265, forced uppercase) |
| `"White Literature"` | **NOT NORMALIZED** | CSV fallback defaults to "WL" |
| `"Grey Literature"` | **NOT NORMALIZED** | CSV fallback defaults to "WL" |

### 1.2 CSV Normalization Issue

**Location**: `src/core/screening_session.py:265-267`

```python
lit_type = str(row_dict.get("Literature_Type", "WL")).upper()
if lit_type not in ("WL", "GL"):
    lit_type = "WL"  # ← "White Literature" becomes "WL"
```

**Problem**: The CSV loader does NOT normalize full names like "White Literature" to "WL". It only handles uppercase variants.

### 1.3 Excel Normalization

**Location**: `src/core/article_metadata.py:220, 260`

```python
# WL sheet
article.literature_type = "WL"  # ← Hardcoded

# GL sheet
article.literature_type = "GL"  # ← Hardcoded
```

**Status**: Excel ingestion correctly assigns literature type based on sheet name.

---

## 2. Critical Metadata Fields

### 2.1 Excel Ingestion (ATLAS)

**Location**: `src/core/screening_session.py:300-315, 328-341`

```python
# WL Articles
metadata = {
    "year": str(article.year) if article.year else "",
    "authors": article.authors,
    "literature_type": article.literature_type,  # ✓
    "year_source": "atlas",                       # ✓
    "metadata_completeness": article.metadata_completeness,  # ✓
    # ... other fields
}

# GL Articles
metadata = {
    "year_source": "atlas",                       # ✓
    "metadata_completeness": article.metadata_completeness,  # ✓
    # ...
}
```

**Status**: Excel ingestion CORRECTLY includes `year_source` and `metadata_completeness`.

### 2.2 CSV Ingestion (BROKEN)

**Location**: `src/core/screening_session.py:268-275`

```python
metadata = {
    "year": str(row_dict.get("Year", "")),
    "authors": str(row_dict.get("Authors", "")),
    "literature_type": lit_type,
    "title": str(row_dict.get("Title", "")),
    "abstract": str(row_dict.get("Abstract", "")),
    "global_id": str(row_dict.get("global_id", str(uuid.uuid4())[:8])),
    # ❌ MISSING: "year_source"
    # ❌ MISSING: "metadata_completeness"
}
```

**Status**: CSV ingestion is MISSING `year_source` and `metadata_completeness`.

---

## 3. Root Cause: CSV Metadata Incompleteness

### 3.1 What Happens with CSV Data

1. User uploads CSV file
2. `ingest_from_upload()` processes each row
3. Metadata dict is created WITHOUT `year_source` and `metadata_completeness`
4. ArticleReview stores incomplete metadata
5. LLM receives metadata with missing fields
6. `metadata.get("year_source", "unknown")` returns "unknown"
7. LLM prompt shows `Year: 2023 (source: unknown)`

### 3.2 Payload Comparison

**Excel Upload**:
```
Year: 2023 (source: atlas)
Metadata Completeness: complete
```

**CSV Upload (BROKEN)**:
```
Year: 2023 (source: unknown)
Metadata Completeness: unknown
```

---

## 4. Normalization Canonical Map

### 4.1 Literature Type

```python
LITERATURE_TYPE_MAP = {
    "WL": "WL",
    "wl": "WL",
    "Wl": "WL",
    "WHITE LITERATURE": "WL",
    "White Literature": "WL",
    "white literature": "WL",
    "GL": "GL",
    "gl": "GL",
    "Gl": "GL",
    "GREY LITERATURE": "GL",
    "Grey Literature": "GL",
    "grey literature": "GL",
}
```

### 4.2 Year Source

```python
YEAR_SOURCE_MAP = {
    "atlas": "atlas",           # From ATLAS export
    "doi": "doi",               # Parsed from DOI
    "manual": "manual",          # Manually entered
    "extracted": "extracted",   # Extracted from title/abstract
    None: "unknown",             # Missing
    "": "unknown",              # Empty
}
```

### 4.3 Metadata Completeness

```python
COMPLETENESS_MAP = {
    "complete": "complete",
    "full": "complete",
    "high": "complete",
    "partial": "partial",
    "medium": "partial",
    "minimal": "minimal",
    "low": "minimal",
    "none": "minimal",
    None: "unknown",
    "": "unknown",
}
```

---

## 5. Recommended Fixes

### 5.1 Fix CSV Literature Type Normalization

```python
# Add to screening_session.py ingest_from_upload()
LITERATURE_TYPE_MAP = {
    "WL": "WL", "wl": "WL", "Wl": "WL",
    "WHITE LITERATURE": "WL", "White Literature": "WL",
    "GL": "GL", "gl": "GL", "Gl": "GL",
    "GREY LITERATURE": "GL", "Grey Literature": "GL",
}

lit_type_raw = str(row_dict.get("Literature_Type", "WL")).strip()
lit_type = LITERATURE_TYPE_MAP.get(lit_type_raw, LITERATURE_TYPE_MAP.get(lit_type_raw.upper(), "WL"))
```

### 5.2 Add Missing Fields to CSV Ingestion

```python
# In CSV ingestion loop
metadata = {
    # ... existing fields ...
    "year_source": "csv",  # ← ADD
    "metadata_completeness": compute_completeness(row_dict),  # ← ADD
}
```

### 5.3 Add Completeness Computation for CSV

```python
def compute_completeness(row: dict) -> str:
    """Compute metadata completeness for CSV rows."""
    has_title = bool(row.get("Title"))
    has_abstract = bool(row.get("Abstract"))
    has_year = bool(row.get("Year"))

    if has_title and has_abstract and has_year:
        return "complete"
    elif has_title:
        return "partial"
    return "minimal"
```

---

## 6. Verification Checklist

- [x] Excel WL normalization verified
- [x] Excel GL normalization verified
- [ ] CSV WL normalization fixed
- [ ] CSV GL normalization fixed
- [ ] CSV year_source field added
- [ ] CSV metadata_completeness field added
- [ ] Normalization tests added

---

## 7. Impact Assessment

| Source | Literature Type | Year Source | Completeness | Status |
|--------|---------------|------------|-------------|--------|
| Excel WL | ✓ Correct | ✓ atlas | ✓ Computed | OK |
| Excel GL | ✓ Correct | ✓ atlas | ✓ Computed | OK |
| CSV | ⚠ Partial | ❌ Missing | ❌ Missing | BROKEN |

---

## 8. Files Requiring Changes

| File | Change |
|------|--------|
| `src/core/screening_session.py` | Add year_source and metadata_completeness to CSV ingestion |
| `src/core/screening_session.py` | Add literature type normalization map |
| `tests/` | Add CSV normalization tests |
