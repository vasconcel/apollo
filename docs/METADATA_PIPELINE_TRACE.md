# Metadata Pipeline Trace

**APOLLO v2.0.0 Primal - Year Propagation Chain**

---

## Pipeline Overview

```
ATLAS Excel → pandas DataFrame → normalize_wl_metadata() → 
ArticleReview.metadata → UI rendering
```

---

## Stage 1: ATLAS Import (pandas)

```python
# screening_session.py:318-320
wl_df = pd.read_excel(path, sheet_name="White Literature")
row_dict = row.to_dict()  # {'Year': 2025, ...}
```

**Key**: `row.to_dict()` converts pandas Series to dict with column names as keys.

---

## Stage 2: Normalization (article_metadata.py)

```python
# article_metadata.py:214
article.year = _get_year(row)

# _get_year() function
def _get_year(row: Dict[str, Any]) -> Optional[int]:
    year_str = _get_first_matching_value(row, YEAR_ALIASES)
    if year_str:
        try:
            return int(year_str)
        except (ValueError, TypeError):
            pass
    return None
```

**YEAR_ALIASES** (fixed):
```python
YEAR_ALIASES = [
    "year", "Year", "Publication Year", "Publication_Year",
    "date", "Date", "pub_year", "publicationYear", "publish_year",
    "published", "Published", "Year", "yr", "Yr"
]
```

---

## Stage 3: Metadata Construction (screening_session.py)

```python
# screening_session.py:322-337
metadata = {
    "year": str(article.year) if article.year else "",
    "year_source": "atlas",
    ...
}
```

**Critical**: Uses `article.year` from normalization.

---

## Stage 4: ArticleReview Creation

```python
# screening_session.py:338-343
review_article = ArticleReview(
    article_id=...,
    title=article.title,
    abstract=article.abstract,
    metadata=metadata
)
```

---

## Stage 5: UI Rendering

```python
# ec_screening_view.py:321-337
year = metadata.get("year", "")
year_source = metadata.get("year_source", "unknown")

# New logic:
if year and year != "nan" and year != "—":
    year_display = f"{year}"
    if year_source != "unknown":
        year_display += f" ({year_src_labels.get(year_source)})"
elif year_source != "unknown":
    year_display = f"Unknown ({year_src_labels.get(year_source)})"
else:
    year_display = "Unknown"
```

---

## Where Year Was Lost

### Problem 1: Column Name Mismatch
**Original**: `YEAR_ALIASES` missing "Publication_Year" (underscore)
**Result**: _get_year() returned None even when year existed
**Fix**: Added "Publication_Year" to aliases

### Problem 2: Empty String vs None
**Original**: `"year": str(article.year) if article.year else ""`
**Issue**: If article.year was 0 (falsy), becomes ""
**Result**: Shows "Unknown (ATLAS)" when year exists but extraction failed
**Fix**: Added more aliases to catch the year

---

## Trace Verification Points

| Checkpoint | Code | Expected |
|------------|------|----------|
| Excel has "Publication_Year" | row.to_dict() | {'Publication_Year': 2025} |
| _get_year finds column | _get_first_matching_value | 2025 |
| int conversion | int(year_str) | 2025 |
| metadata construction | str(article.year) | "2025" |
| UI rendering | year != "" | True, shows "2025 (ATLAS)" |

---

## Files Involved

1. `src/core/screening_session.py` - Lines 318-344 (import pipeline)
2. `src/core/article_metadata.py` - Lines 33-37 (YEAR_ALIASES), 189-197 (_get_year)
3. `src/ui/modules/ec_screening_view.py` - Lines 321-337 (rendering)

---

## Year Source Propagation

| Source | Source Value | Display |
|--------|-------------|---------|
| ATLAS export | "atlas" | "(ATLAS)" |
| DOI lookup | "doi" | "(DOI)" |
| Manual entry | "manual" | "(Manual)" |
| Unknown | "unknown" | (no suffix) |

---

## Fix Applied

**YEAR_ALIASES expanded** to include all common ATLAS column variations:
- Original: 8 aliases
- Fixed: 14 aliases

This ensures year is found regardless of exact column naming in ATLAS export.

---

## Conclusion

Year was being lost at **Stage 2** (normalization) because the column name "Publication_Year" wasn't in the aliases. Fixed by expanding YEAR_ALIASES to include common variants.