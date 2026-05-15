# Year Trace Matrix - Runtime Validation

## Instrumentation Added

### 1. article_metadata.py - _get_year()
Added debug logging:
- Available columns
- Checking aliases
- Matched alias → key mapping
- Raw value (repr + type)
- Extracted year values
- Final result

### 2. article_metadata.py - normalize_wl_metadata()
Added debug logging:
- Raw row keys
- Title extraction
- Authors extraction (raw + decoded)
- Final year from _get_year()

### 3. screening_session.py - WL/GL ingestion
Added debug logging:
- Structured year from normalize_wl_metadata/gl_metadata
- Regex fallback result (year, source)
- Final stored year + source

## Validation Matrix

| Ingestion Path | Structured Year | Regex Fallback | Year Source | Status |
|----------------|------------------|----------------|-------------|--------|
| WL Excel | ✅ Logged | ✅ Logged | ✅ Logged | NEEDS RUNTIME |
| GL Excel | ✅ Logged | ✅ Logged | ✅ Logged | NEEDS RUNTIME |
| CSV | ✅ Logged | ✅ Logged | ✅ Logged | NEEDS RUNTIME |
| BibTeX | Not implemented | - | - | UNVERIFIED |
| RIS | Not implemented | - | - | UNVERIFIED |

## Expected Runtime Output (Example)

```
=== WL INGESTION START ===
[WL DEBUG] Raw row keys: ['Library', 'Global_ID', 'Local_ID', 'Title', 'Abstract', 'Keywords']
[WL DEBUG] title: 'Effect of Social Media Visibility...'
[WL DEBUG] raw authors: ''
[WL DEBUG] decoded authors: ''
[YEAR DEBUG] Available columns: ['Library', 'Global_ID', 'Local_ID', 'Title', 'Abstract', 'Keywords']
[YEAR DEBUG] Checking aliases: ['year', 'Year', 'Publication Year', ...]
[YEAR DEBUG] No year found via structured columns
[WL DEBUG] final year: None
[INGEST WL 0] Structured year from normalize_wl_metadata: None
[INGEST WL 0] Regex fallback result: year=2024, source='regex'
[INGEST WL 0] Final stored year: 2024, source: 'regex'
```

## Key Findings from Code Analysis

1. **Test file has NO Year column** - only ['Library', 'Global_ID', 'Local_ID', 'Title', 'Abstract', 'Keywords']
2. **Regex fallback implemented** - `extract_year()` called when structured year is None
3. **Defensive normalization** - `normalize_metadata()` ensures year always has a value

## Verification Required

User must run app and verify:
1. Console shows debug logs during file upload
2. Year extracted via regex from title/abstract (when no Year column)
3. Year source shows "regex" for extracted, "atlas" for structured
4. Year displays correctly in UI (not "Unknown")

## Code Change vs Runtime Validation

| Item | Code Change | Runtime Validation |
|------|-------------|-------------------|
| Year extraction logging | ✅ Added | ❌ Pending |
| Regex fallback | ✅ Added | ❌ Pending |
| Metadata normalization | ✅ Added | ❌ Pending |
| Sidebar debug mode | ✅ Added | ❌ Pending |