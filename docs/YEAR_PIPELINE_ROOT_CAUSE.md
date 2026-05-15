# Year Pipeline Root Cause Analysis

## Observed Issue
UI displays: `YEAR: Unknown (ATLAS)`
Expected: `YEAR: 2025 (ATLAS)`

Year exists in imported spreadsheet but is not being rendered correctly.

## Root Cause

The year extraction pipeline had a NaN handling issue in the normalization layer.

### Pipeline Flow

```
Excel Spreadsheet
    ↓
pandas DataFrame (read_excel)
    ↓
normalize_wl_metadata() [article_metadata.py]
    ↓
_get_year() - FAILING HERE
    ↓
screening_session.py - stores "" for missing year
    ↓
UI displays "Unknown"
```

### Specific Failure Point

In `article_metadata.py`, the `_get_year()` function was using `_get_first_matching_value()` to find the year column. The function correctly matched column names from `YEAR_ALIASES`, but failed to handle pandas NaN values properly.

When pandas reads an Excel file, year columns may contain:
- `None` (Python None)
- `np.nan` (NumPy NaN)
- `pd.NA` (Pandas NA)
- A valid year (int, float, or string)

The original code:
```python
def _get_year(row: Dict[str, Any]) -> Optional[int]:
    year_str = _get_first_matching_value(row, YEAR_ALIASES)
    if year_str:
        try:
            return int(year_str)
        except (ValueError, TypeError):
            pass
    return None
```

The `_get_first_matching_value` function converts all values to string with `str(row.get(key, ""))`. When the value is `np.nan`, this produces the string `"nan"`, which fails `int("nan")`.

## Fix Applied

Updated `_get_year()` in `article_metadata.py` to handle NaN values explicitly:

```python
def _get_year(row: Dict[str, Any]) -> Optional[int]:
    """Extract year from row with robust NaN handling."""
    import math
    
    for alias in YEAR_ALIASES:
        alias_lower = alias.lower()
        row_lower = {k.lower(): k for k in row.keys()}
        
        if alias_lower in row_lower:
            key = row_lower[alias_lower]
            raw_value = row.get(key)
            
            if raw_value is None:
                continue
            
            if isinstance(raw_value, (int, float)) and not math.isnan(raw_value):
                try:
                    year_val = int(float(raw_value))
                    if 1900 <= year_val <= 2100:
                        return year_val
                except (ValueError, TypeError):
                    pass
            
            year_str = str(raw_value).strip()
            if year_str and year_str.lower() != "nan":
                try:
                    return int(year_str)
                except (ValueError, TypeError):
                    pass
    
    return None
```

Key improvements:
1. Direct value check for int/float types before string conversion
2. Explicit NaN handling using `math.isnan()`
3. String "nan" filtering with `.lower() != "nan"`
4. Preserves year source tracking ("atlas", "regex", "missing")

## Files Modified
- `src/core/article_metadata.py` - `_get_year()` function

## Validation
- Year values from Excel should now correctly propagate
- NaN values in year column are properly handled
- Year source continues to track provenance ("ATLAS" when from spreadsheet)

## Remaining Considerations
- Year extraction fallback to regex still works (year_source = "regex")
- If year column is completely missing, fallback to regex extraction kicks in
- Manual year override via DOI lookup still available (year_source = "doi")