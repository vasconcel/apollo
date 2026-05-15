# APOLLO Metadata Contract Specification

## Overview

The Metadata Contract is the **SINGLE SOURCE OF TRUTH** for all metadata handling in APOLLO. It centralizes:

- Required canonical fields
- Normalization rules
- Provenance enforcement
- Defensive defaults
- Metadata validation

## Canonical Fields

```python
CANONICAL_METADATA_FIELDS: Set[str] = {
    "title",
    "abstract", 
    "authors",
    "author_normalization_source",
    "year",
    "year_source",
    "source",
    "source_type",
    "doi",
    "url",
    "keywords",
    "literature_type",
    "global_id",
    "local_id",
    "library",
    "provenance_trace",
    "parser_used",
    "metadata_completeness",
    "completeness_score",
}
```

## Default Values

```python
DEFAULT_METADATA_VALUES: Dict[str, Any] = {
    "year": "Unknown",
    "year_source": "missing",
    "authors": "",
    "author_normalization_source": "unknown",
    "source": "",
    "source_type": "unknown",
    "doi": "",
    "url": "",
    "keywords": "",
    "literature_type": "WL",
    "global_id": "",
    "local_id": "",
    "library": "",
    "provenance_trace": "",
    "parser_used": "unknown",
    "metadata_completeness": "unknown",
    "completeness_score": "",
    "abstract": "[ABSTRACT MISSING]",
    "title": "[TITLE MISSING]",
}
```

## Valid Enumerations

| Field | Valid Values |
|-------|-------------|
| year_source | atlas, regex, doi, csv, bibtex, ris, manual, missing |
| author_normalization_source | raw, pylatexenc, manual, unknown |
| literature_type | WL, GL |
| metadata_completeness | complete, partial, minimal, unknown |

## Core Functions

### normalize_metadata()

```python
def normalize_metadata(metadata: Dict[str, Any], parser_name: str = "unknown") -> Dict[str, Any]:
    """
    Normalize metadata according to contract.
    ALL ingestion paths MUST use this function.
    """
```

### validate_metadata()

```python
def validate_metadata(metadata: Dict[str, Any]) -> tuple[bool, List[str]]:
    """
    Validate metadata against contract.
    Returns (is_valid, error_messages)
    """
```

### ensure_metadata_integrity()

```python
def ensure_metadata_integrity(article_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Runtime safety check: ensure article has required fields.
    Raises ValueError if critical fields cannot be determined.
    """
```

## Provenance Trace

Each article receives a deterministic provenance trace:

```
APOLLO_v2.0|<hash>
```

Generated from: literature_type | parser_used | year_source | author_normalization_source | source_type

## File Location

`src/core/metadata_contract.py`

## Usage

```python
from src.core.metadata_contract import (
    normalize_metadata,
    validate_metadata,
    ensure_metadata_integrity,
    CANONICAL_METADATA_FIELDS
)

# Normalize incoming metadata
normalized = normalize_metadata(raw_metadata, parser_name="atlas_xlsx")

# Validate
is_valid, errors = validate_metadata(normalized)

# Ensure integrity before screening
safe_metadata = ensure_metadata_integrity(article_id, normalized)
```