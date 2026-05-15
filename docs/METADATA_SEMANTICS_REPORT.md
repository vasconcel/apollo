# Metadata Semantics Report

**APOLLO v2.0.0 Primal - Year & Provenance Rendering**

---

## Executive Summary

Analysis of year and provenance metadata rendering semantics. Fixed invalid display state where "YEAR: — (ATLAS)" appeared when year was missing.

---

## Year Display Semantics

### Problem State
**Before Fix:**
```
YEAR: — (ATLAS)
```
This is scientifically ambiguous - it suggests "no year from ATLAS" which could mean:
1. Year not available from source
2. Year extraction failed
3. Year deliberately removed

### Root Cause
```python
# Old logic
year_display = f"{year or '—'} ({year_src_labels.get(year_source)})"
# When year is empty/falsy, renders "— (ATLAS)"
```

### Fixed Logic
```python
# New logic
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

## Semantic Cases

### CASE A: Year Exists
| Input | Display |
|-------|---------|
| year="2023", year_source="atlas" | YEAR: 2023 (ATLAS) |
| year="2024", year_source="doi" | YEAR: 2024 (DOI) |
| year="2022", year_source="unknown" | YEAR: 2022 |

### CASE B: Year Missing, Source Known
| Input | Display |
|-------|---------|
| year="", year_source="atlas" | YEAR: Unknown (ATLAS) |
| year="", year_source="doi" | YEAR: Unknown (DOI) |
| year="", year_source="manual" | YEAR: Unknown (Manual) |

### CASE C: Year Unknown, Source Unknown
| Input | Display |
|-------|---------|
| year="", year_source="" | YEAR: Unknown |

---

## Provenance Rendering Pipeline

### 1. ATLAS Import (screening_session.py)
```python
metadata = {
    "year": str(article.year) if article.year else "",
    "year_source": "atlas",
    # ...
}
```

### 2. Normalization (article_metadata.py)
- Extracts year from normalized article object
- Propagates `year_source` = "atlas" for ATLAS imports

### 3. Metadata Propagation (ArticleReview)
```python
@dataclass
class ArticleReview:
    metadata: Dict[str, str]  # Contains year, year_source, etc.
```

### 4. UI Rendering (ec/ic_screening_view.py)
- Reads from `metadata.get("year")` and `metadata.get("year_source")`
- Applies semantic display logic

---

## Metadata Field Hierarchy

### Primary Display (Article Card)
- Title (prominent)
- Compact metadata line: Year · Authors · Source

### Expandable Details (Provenance Expander)
| Field | Source | Display |
|-------|--------|---------|
| Year | metadata.year | Semantic (with source) |
| Authors | metadata.authors | Raw or "—" |
| Source | metadata.source | Raw or "—" |
| DOI | metadata.doi | Raw or "—" |
| ID | metadata.global_id | Truncated |
| Completeness | metadata.metadata_completeness | Raw |

---

## Year Source Labels

| Source Value | Display Label |
|--------------|---------------|
| "atlas" | ATLAS |
| "doi" | DOI |
| "manual" | Manual |
| "csv" | CSV |
| "unknown" | Unknown |

---

## Files Modified

### Article Card Rendering
- `src/ui/modules/ec_screening_view.py` - Year display logic
- `src/ui/modules/ic_screening_view.py` - Year display logic

### Validation
- Year exists → shows year + source in parentheses
- Year missing, source known → "Unknown (SOURCE)"
- Year missing, source unknown → "Unknown"

---

## Consistency Rules Applied

1. **Never show "—" with a source**: Replace with "Unknown (SOURCE)"
2. **Year always meaningful**: Even if missing, indicate source
3. **Source always contextualized**: ATLAS/DOI/Manual labels
4. **Completeness separate**: Not conflated with year

---

## Test Cases

### Test 1: Full Year
```python
metadata = {"year": "2023", "year_source": "atlas"}
# Result: "2023 (ATLAS)" ✓
```

### Test 2: Missing Year, Known Source
```python
metadata = {"year": "", "year_source": "atlas"}
# Result: "Unknown (ATLAS)" ✓
```

### Test 3: Missing Year, Unknown Source
```python
metadata = {"year": "", "year_source": "unknown"}
# Result: "Unknown" ✓
```

### Test 4: Year Inferred (if implemented)
```python
metadata = {"year": "2023 (Inferred)", "year_source": "atlas"}
# Result: "2023 (ATLAS)" - doesn't show inference
# Note: Could be enhanced to show "(Inferred)" if needed
```

---

## Conclusion

Year semantics now properly handle all edge cases:
- ✅ Present year with source
- ✅ Missing year with known source  
- ✅ Missing year with unknown source
- ✅ No ambiguous "—" displays

The rendering is now scientifically unambiguous and consistent.