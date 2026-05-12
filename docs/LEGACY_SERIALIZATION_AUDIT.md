# Legacy Serialization Audit

## Overview

This document audits legacy serialization patterns that may cause metadata degradation in the LLM context assembly.

---

## 1. Legacy Dict Access Patterns

### 1.1 article.get() Usage

**Pattern**: `article.get("field", default)`

**Found in**:

| File | Line | Usage | Risk |
|------|------|-------|------|
| `ec_screening_view.py` | 338-342 | Fallback for non-ArticleReview | LOW |
| `ic_screening_view.py` | 286-288 | Fallback for non-ArticleReview | LOW |
| `review_view.py` | Various | Article dict access | MEDIUM |

**Audit Finding**: Legacy dict fallback exists for backward compatibility but is NOT the root cause of metadata loss.

### 1.2 row.get() Usage

**Pattern**: `row.get("column_name", default)`

**Found in**:

| File | Line | Usage | Risk |
|------|------|-------|------|
| `atlas_processor.py` | Various | DataFrame row access | LOW |
| `article_metadata.py` | 176-186 | Alias-based field extraction | LOW |

**Audit Finding**: Row access patterns are correct for ATLAS processing.

---

## 2. Metadata Fallback Values

### 2.1 "unknown" Fallback Pattern

**Pattern**: `metadata.get("field", "unknown")`

**Found in**:

```python
# src/core/llm_assistant.py
year_source = metadata.get("year_source", "unknown") if metadata else "unknown"
metadata_completeness = metadata.get("metadata_completeness", "unknown") if metadata else "unknown"

# src/ui/modules/ec_screening_view.py
completeness = metadata.get("metadata_completeness", "unknown")

# src/ui/modules/review_view.py
year_source = meta.get('year_source', 'unknown')
```

**Audit Finding**: "unknown" fallback is used consistently but creates BAD context for LLM when metadata IS available but NOT passed.

### 2.2 str() Conversion

**Pattern**: `str(article.get("field", ""))`

**Found in**: `atlas_processor.py`, `article_metadata.py`

**Audit Finding**: Used for ATLAS processing, not for LLM assembly. Safe.

---

## 3. ArticleReview Object Conversion

### 3.1 ArticleReview → Dict

**Location**: `src/core/screening_session.py`

```python
def to_dict(self) -> Dict:
    """Convert to dictionary."""
    return asdict(self)  # ✓ Uses dataclass.asdict

def to_review_dict(self) -> Dict:
    """Export as review-ready dict with explicit metadata fields."""
    return {
        "article_id": self.article_id,
        "title": self.title,
        "abstract": self.abstract,
        "year": self.metadata.get("year"),
        "year_source": self.get_year_source(),
        "authors": self.metadata.get("authors", ""),
        "literature_type": self.get_literature_type(),
        # ... complete metadata
    }
```

**Audit Finding**: ✓ Correctly preserves metadata in to_review_dict()

### 3.2 ArticleRecord → ArticleReview

**Location**: `src/core/screening_session.py`

```python
@classmethod
def from_article_record(cls, record) -> "ArticleReview":
    """Create from ArticleRecord with full metadata propagation."""
    base_metadata = {
        "library": record.library,
        "global_id": record.global_id,
        # ... all fields
    }
    
    if record.metadata:
        base_metadata.update(record.metadata)  # ✓ Preserves additional metadata
    
    return cls(
        article_id=record.global_id or record.local_id or ...,
        title=record.title,
        abstract=record.abstract,
        metadata=base_metadata  # ✓ Full metadata passed
    )
```

**Audit Finding**: ✓ Metadata correctly propagated from ArticleRecord to ArticleReview

---

## 4. Dict-to-Object Conversion Paths

### 4.1 screening_session.py ArticleReview Creation

```python
# From JSON load
self.articles = [ArticleReview(**a) for a in data.get("articles", [])]
```

**Audit Finding**: ✓ Correctly reconstructs ArticleReview from dict

### 4.2 DynamicProtocol Reconstruction

```python
# From dict
DynamicProtocol.from_dict(data["dynamic_protocol"])
```

**Audit Finding**: ✓ Protocol correctly reconstructed

---

## 5. UI Article Access Patterns

### 5.1 EC Screening View Article Access

**Location**: `src/ui/modules/ec_screening_view.py:331-342`

```python
if isinstance(article, ArticleReview):
    title = article.title              # ✓ Object attribute
    abstract = article.abstract         # ✓ Object attribute
    literature_type = article.get_literature_type()  # ✓ Method call
    year = article.metadata.get("year", "")  # ✓ Metadata dict access
    metadata = article.metadata         # ✓ Full metadata dict
else:
    # Legacy dict fallback
    title = article.get("title", "")
    abstract = article.get("abstract", "")
    literature_type = article.get("literature_type", "WL")
    year = article.get("year")
    metadata = article
```

**Audit Finding**: 
- ✓ ArticleReview object access is correct
- ⚠ Legacy dict fallback exists but is not the issue
- ❌ **Metadata extracted but NOT passed to LLM**

### 5.2 Review View Article Access

**Location**: `src/ui/modules/review_view.py`

```python
suggestion = llm.suggest(
    title=title,
    abstract=abstract,
    literature_type=literature_type,
    stage=stage,
    metadata=metadata  # ✓ Review view DOES pass metadata
)
```

**Audit Finding**: Review view CORRECTLY passes metadata to unified `suggest()` method.

---

## 6. Serialization Integrity

### 6.1 Session Checksum

```python
def compute_checksum(self) -> str:
    """Compute SHA256 checksum of session canonical JSON."""
    data = self._to_dict_full()
    # ...
    canonical_json = json.dumps(data_for_check, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical_json.encode()).hexdigest()
```

**Audit Finding**: ✓ Deterministic checksum includes articles with metadata

### 6.2 Article Metadata in Checksum

```python
fields_for_checksum = [
    "session_id", "created_at", "protocol_version", "stage",
    "current_index", "total_count", "ec_completed", "ic_completed",
    "qc_completed", "included_count", "excluded_count", "skip_count",
    "discussion_count", "researcher_id", "last_saved", "schema_version",
    "articles",  # ✓ Articles included
    "dynamic_protocol"
]
```

**Audit Finding**: ✓ Article metadata included in session checksum

---

## 7. Export Serialization

### 7.1 ArticleReview to Review Dict

```python
def to_review_dict(self) -> Dict:
    """Export as review-ready dict with explicit metadata fields."""
    return {
        "article_id": self.article_id,
        "title": self.title,
        "abstract": self.abstract,
        "year": self.metadata.get("year"),
        "year_source": self.get_year_source(),  # ✓ Includes year_source
        "authors": self.metadata.get("authors", ""),
        "literature_type": self.get_literature_type(),
        "metadata_completeness": self.get_metadata_completeness(),  # ✓ Includes completeness
        # ...
    }
```

**Audit Finding**: ✓ All provenance fields in export dict

### 7.2 Export Engine

```python
def export_decisions_excel(self, session, output_path):
    # Uses article.to_review_dict() for each article
```

**Audit Finding**: ✓ Exports preserve metadata

---

## 8. Summary: Where Degradation Occurs

### 8.1 NOT the Problem

| Path | Status | Notes |
|------|--------|-------|
| ATLAS → NormalizedArticle | ✓ OK | Metadata normalized correctly |
| NormalizedArticle → ArticleRecord | ✓ OK | Metadata preserved |
| ArticleRecord → ArticleReview | ✓ OK | Full metadata propagation |
| ArticleReview → Session storage | ✓ OK | Metadata in session |
| Session → JSON export | ✓ OK | All metadata preserved |
| Session → Checksum | ✓ OK | Metadata included |

### 8.2 THE PROBLEM

| Path | Status | Issue |
|------|--------|-------|
| ArticleReview → LLM suggest_ec() | ❌ BROKEN | metadata NOT passed |
| ArticleReview → LLM suggest_ic() | ❌ BROKEN | metadata NOT passed, missing year entirely |

### 8.3 Code Evidence

```python
# ec_screening_view.py - BROKEN
suggestion = llm.suggest_ec(
    title=title,
    abstract=abstract,
    literature_type=literature_type,
    protocol_criteria=protocol_criteria
    # metadata=metadata ← MISSING!
)

# review_view.py - CORRECT
suggestion = llm.suggest(
    title=title,
    abstract=abstract,
    literature_type=literature_type,
    stage=stage,
    metadata=metadata  # ← CORRECTLY PASSED
)
```

---

## 9. Conclusion

**The metadata degradation is NOT caused by legacy serialization.**

The issue is a **simple parameter omission** in the screening views:
- `ec_screening_view.py`: metadata extracted at line 336, not passed at line 367
- `ic_screening_view.py`: metadata never extracted, year never passed

**The serialization paths are intact and correct.**

The fix is simply adding `metadata=metadata` to the LLM function calls.
