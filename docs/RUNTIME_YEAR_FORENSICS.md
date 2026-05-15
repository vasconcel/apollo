# Runtime Year Pipeline Forensics

## Runtime Observations

### Test File Analysis
Tested with: `ATLAS_Master_Initial_Search.xlsx`

**Finding**: Spreadsheet has NO Year column.
```
Available columns: ['Library', 'Global_ID', 'Local_ID', 'Title', 'Abstract', 'Keywords']
```

### Root Cause Identified

The ATLAS file used for testing contains only:
- Library
- Global_ID
- Local_ID
- Title
- Abstract
- Keywords

**There is NO Year column in the source data.**

### Pipeline Analysis

| Stage | Expected Behavior | Actual Behavior |
|-------|-------------------|-----------------|
| Excel load | Read Year column | No Year column exists |
| normalize_wl_metadata | Extract year via _get_year() | Returns None (no column) |
| ingest_from_upload | Store year in metadata | Sets "" (empty string) |
| UI rendering | Display year | Shows "Unknown (ATLAS)" |

### Failed Assumptions

1. **Assumption**: Year column exists in ATLAS spreadsheet
   - **Reality**: No Year column in test file

2. **Assumption**: `_get_year()` handles missing column correctly
   - **Reality**: Function returns None correctly, but no fallback to regex

3. **Assumption**: Year extraction fallback (regex) is used
   - **Reality**: The `extract_year()` function from `year_extraction.py` was NOT being called in `ingest_from_upload()`

### Fix Applied

Updated `screening_session.py` to use regex fallback:

```python
year_value = article.year if article.year else None
year_source = "atlas"

if year_value is None:
    extracted_year, extracted_source = extract_year(
        article.title, 
        article.abstract,
        None
    )
    if extracted_year:
        year_value = extracted_year
        year_source = extracted_source
```

This was applied to:
- WL Excel ingestion (lines 318-360)
- GL Excel ingestion (lines 361-403)
- CSV ingestion (lines 288-313)

### Actual Validated Behavior (After Fix)

1. Check for structured Year column
2. If missing, use `extract_year()` regex fallback from title/abstract
3. Track actual source: "atlas" (structured), "regex" (extracted), or "csv"

### Unresolved Risks

1. **No test data with Year column**: Cannot verify if structured year works
2. **Regex may extract wrong year**: If paper mentions multiple years, regex picks largest
3. **User's actual file may differ**: User's ATLAS file might have Year column (unlike test file)

### Validation Required

User must verify with their actual ATLAS file that:
1. Year displays correctly when Year column exists
2. Year extracts correctly from title/abstract when column missing
3. Year source shows "ATLAS" vs "regex" appropriately