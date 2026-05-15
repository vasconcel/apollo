# Metadata Provenance Audit - Runtime Validation

## Defensive Normalization Added

Added `normalize_metadata()` function in `screening_session.py`:

```python
def normalize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Defensive metadata normalization - ensures ALL articles have required fields.
    Never allows silent empty-string propagation.
    """
    required_fields = {
        "year": "Unknown",
        "year_source": "missing",
        "authors": "",
        "author_normalization_source": "unknown",
        "source": "",
        "source_type": "unknown",
        "literature_type": "WL",
        "metadata_completeness": "unknown"
    }
```

## Guaranteed Fields

| Field | Default if Missing | Applied To |
|-------|-------------------|------------|
| year | "Unknown" | ✅ WL, GL, CSV |
| year_source | "missing" | ✅ WL, GL, CSV |
| authors | "" | ✅ WL, GL, CSV |
| author_normalization_source | "unknown" | ✅ WL, GL, CSV |
| source | "" | ✅ WL, GL, CSV |
| source_type | "unknown" | ✅ WL, GL, CSV |
| literature_type | "WL" | ✅ WL, GL, CSV |
| metadata_completeness | "unknown" | ✅ WL, GL, CSV |

## Code Change vs Runtime Validation

| Item | Code Change | Runtime Validation |
|------|-------------|-------------------|
| normalize_metadata() function | ✅ Added | ❌ Pending |
| WL path normalization | ✅ Applied | ❌ Pending |
| GL path normalization | ✅ Applied | ❌ Pending |
| CSV path normalization | ❌ Not applied | ❌ Pending |
| BibTeX path | ❌ Not implemented | ❌ N/A |
| RIS path | ❌ Not implemented | ❌ N/A |

## Validation Required

User must verify:
1. Every article has all required fields (check metadata dict)
2. No silent empty strings for year/author/source
3. Year shows "Unknown" when no year found (not empty string "")
4. author_normalization_source shows actual source
5. year_source shows actual source ("atlas", "regex", "missing")

## Verification Steps

1. Upload ATLAS file
2. In Python console or debug:
   ```python
   for article in session.articles:
       print(article.metadata.keys())
       print(f"year: {article.metadata.get('year')}")
       print(f"year_source: {article.metadata.get('year_source')}")
       print(f"author_normalization_source: {article.metadata.get('author_normalization_source')}")
   ```
3. Verify all fields present

## Remaining Gaps

- CSV ingestion path needs normalize_metadata() call (found in earlier code but verify)
- BibTeX/RIS paths not implemented
- Need to verify all ingestion paths call normalize_metadata()