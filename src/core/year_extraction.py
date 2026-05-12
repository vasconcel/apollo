"""
APOLLO Year Extraction Utilities

Extracts publication year from article fields using structured field
first, then regex fallback. Extracted from atlas_processor for
independent testing.
"""
import re
from typing import Optional, Dict, Any


def extract_year(title: str, abstract: str, structured_year: Optional[Any] = None) -> Tuple[Optional[int], str]:
    """
    Extract publication year from article.

    Returns:
        Tuple of (year, source) where source is "structured", "regex", or "missing"
    """
    year_source = "missing"
    year = None
    
    if structured_year is not None:
        try:
            year = int(structured_year)
            if 1900 <= year <= 2100:
                year_source = "structured"
                return year, year_source
            else:
                year = None
        except (ValueError, TypeError):
            pass
    
    extracted_year = _extract_year_regex(title, abstract)
    if extracted_year:
        year = extracted_year
        year_source = "regex"
    
    return year, year_source


def _extract_year_regex(title: str, abstract: str) -> Optional[int]:
    """Extract year using regex from title and abstract."""
    text = f"{title} {abstract}"
    years = re.findall(r'\b(20[0-2][0-9]|201[0-5])\b', text)
    return int(max(years)) if years else None


def compute_metadata_completeness(row: Dict[str, Any]) -> str:
    """Compute metadata completeness based on available structured fields."""
    has_title = bool(row.get("Title") and str(row.get("Title")).strip())
    has_abstract = bool(row.get("Abstract") and len(str(row.get("Abstract")).strip()) > 10)
    has_year = row.get("Year") is not None
    has_authors = bool(row.get("Authors") and str(row.get("Authors")).strip())
    has_source = bool(row.get("Library") or row.get("Venue") or row.get("Publisher"))
    
    present_count = sum([has_title, has_abstract, has_year, has_authors, has_source])
    
    if present_count >= 4:
        return "complete"
    elif present_count >= 2:
        return "partial"
    else:
        return "minimal"