# Ingestion Pipeline Unification Report

## Current State

Ingestion paths still behave differently. This document specifies the unified architecture.

## Target Architecture

```
RawInput (file/bytes)
    ↓
Parser Detection (parser_registry.detect_parser)
    ↓
Parser Execution (parser-specific)
    ↓
ParsedRecord (raw dictionary)
    ↓
Metadata Normalization (metadata_contract.normalize_metadata)
    ↓
ArticleReview (complete with all canonical fields)
```

## Required Canonical Output

ALL ingestion paths must emit:

```python
{
    # Title handling
    "title": str,              # Required
    
    # Abstract handling  
    "abstract": str,           # Required (or "[ABSTRACT MISSING]")
    
    # Author handling
    "authors": str,
    "author_normalization_source": str,  # raw, pylatexenc, manual, unknown
    
    # Year handling
    "year": str,              # "Unknown" or actual year
    "year_source": str,       # atlas, regex, doi, csv, bibtex, ris, manual, missing
    
    # Source handling
    "source": str,
    "source_type": str,       # unknown, scopus, wos, etc.
    
    # Identifiers
    "doi": str,
    "url": str,
    "global_id": str,
    "local_id": str,
    
    # Classification
    "literature_type": str,  # WL or GL
    "keywords": str,
    "library": str,
    
    # Provenance
    "provenance_trace": str,  # Auto-generated
    "parser_used": str,       # Which parser handled this
    
    # Completeness
    "metadata_completeness": str,  # complete, partial, minimal, unknown
    "completeness_score": str,
}
```

## Implementation Status

| Path | Status | Notes |
|------|--------|-------|
| XLSX (WL) | ✅ Working | Needs contract integration |
| XLSX (GL) | ✅ Working | Needs contract integration |
| CSV | ✅ Working | Needs contract integration |
| BibTeX | ❌ Not implemented | Needs parser + contract |
| RIS | ❌ Not implemented | Needs parser + contract |
| Extensionless BibTeX | ⚠️ Parser ready | Needs integration |
| GL TXT | ⚠️ Parser ready | Needs integration |

## Integration Required

To complete unification:

1. Update `ingest_from_upload()` in screening_session.py to use:
   - `detect_parser()` for parser selection
   - `normalize_metadata()` for all paths
   - Set `parser_used` field

2. Add parser-specific handling for:
   - BibTeX records
   - RIS records
   - Extensionless files
   - GL raw text batches

## File Location

- Ingestion: `src/core/screening_session.py`
- Contract: `src/core/metadata_contract.py`
- Registry: `src/core/parser_registry.py`