"""
APOLLO Article Metadata Normalization

Centralized schema normalization with column aliases for ATLAS exports.
Handles various ATLAS/Zotero export column naming conventions.

All screening workspaces should use normalize_article_metadata().
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass, field


TITLE_ALIASES = [
    "title", "Title", "Document Title",
    "title_field", "itemTitle", "title_field"
]

ABSTRACT_ALIASES = [
    "abstract", "Abstract", "Abstract Note", "Summary",
    "abstract_field", "abstractNote", "abstract_field"
]

AUTHORS_ALIASES = [
    "authors", "Authors", "Author", "Creator", "Creators",
    "creator", "author", "author_field"
]

YEAR_ALIASES = [
    "year", "Year", "Publication Year", "date", "Date",
    "pub_year", "publicationYear", "publish_year"
]

SOURCE_ALIASES = [
    "source", "Source", "Publication Title", "Journal",
    "Journal Title", "Publication", "venue", "Venue",
    "booktitle", "publication_title", "publicationTitle"
]

DOI_ALIASES = [
    "DOI", "doi", "doi_field", "digitalObjectIdentifier"
]

URL_ALIASES = [
    "url", "URL", "link", "Link", "uri", "URI"
]

KEYWORDS_ALIASES = [
    "keywords", "Keywords", "Tags", "Tag",
    "keyword", "keyword_field", "tags"
]


@dataclass
class NormalizedArticle:
    """Normalized article metadata for screening."""
    title: str = ""
    abstract: str = ""
    authors: str = ""
    year: Optional[int] = None
    source: str = ""
    doi: str = ""
    url: str = ""
    keywords: str = ""

    literature_type: str = "WL"
    global_id: str = ""
    local_id: str = ""
    library: str = ""

    raw_data: Dict[str, Any] = field(default_factory=dict)

    @property
    def year_str(self) -> str:
        return str(self.year) if self.year else "[NOT AVAILABLE]"

    @property
    def has_abstract(self) -> bool:
        return bool(self.abstract and self.abstract != "nan" and len(self.abstract.strip()) > 10)

    @property
    def has_title(self) -> bool:
        return bool(self.title and self.title != "nan" and len(self.title.strip()) > 0)

    @property
    def metadata_completeness(self) -> str:
        """Return completeness assessment."""
        has_title = self.has_title
        has_abstract = self.has_abstract
        has_year = self.year is not None

        if has_title and has_abstract and has_year:
            return "complete"
        elif has_title:
            return "partial"
        else:
            return "minimal"


def _get_first_matching_value(row: Dict[str, Any], aliases: list, default: str = "") -> str:
    """Get first matching value from row using alias list."""
    row_lower = {k.lower(): k for k in row.keys()}
    for alias in aliases:
        alias_lower = alias.lower()
        if alias_lower in row_lower:
            key = row_lower[alias_lower]
            value = str(row.get(key, ""))
            if value and value != "nan" and value.strip():
                return value.strip()
    return default


def _get_year(row: Dict[str, Any]) -> Optional[int]:
    """Extract year from row."""
    year_str = _get_first_matching_value(row, YEAR_ALIASES)
    if year_str:
        try:
            return int(year_str)
        except (ValueError, TypeError):
            pass
    return None


def normalize_wl_metadata(row: Dict[str, Any]) -> NormalizedArticle:
    """Normalize White Literature metadata from ATLAS/Zotero export."""
    article = NormalizedArticle()

    article.title = _get_first_matching_value(row, TITLE_ALIASES)
    article.abstract = _get_first_matching_value(row, ABSTRACT_ALIASES)
    article.authors = _get_first_matching_value(row, AUTHORS_ALIASES)
    article.year = _get_year(row)
    article.source = _get_first_matching_value(row, SOURCE_ALIASES)
    article.doi = _get_first_matching_value(row, DOI_ALIASES)
    article.url = _get_first_matching_value(row, URL_ALIASES)
    article.keywords = _get_first_matching_value(row, KEYWORDS_ALIASES)

    article.literature_type = "WL"
    article.global_id = _get_first_matching_value(row, ["global_id", "Global_ID", "global identifier"])
    article.local_id = _get_first_matching_value(row, ["local_id", "Local_ID"])
    article.library = _get_first_matching_value(row, ["library", "Library"])

    article.raw_data = dict(row)

    return article


def normalize_gl_metadata(row: Dict[str, Any]) -> NormalizedArticle:
    """Normalize Grey Literature metadata from ATLAS/Zotero export."""
    article = NormalizedArticle()

    article.title = _get_first_matching_value(row, TITLE_ALIASES)
    article.abstract = _get_first_matching_value(row, ABSTRACT_ALIASES)
    article.authors = _get_first_matching_value(row, AUTHORS_ALIASES)
    article.year = _get_year(row)
    article.source = _get_first_matching_value(row, SOURCE_ALIASES)
    article.url = _get_first_matching_value(row, URL_ALIASES)
    article.keywords = _get_first_matching_value(row, KEYWORDS_ALIASES)

    article.literature_type = "GL"

    article.raw_data = dict(row)

    return article


def article_to_dict(article: NormalizedArticle) -> Dict[str, Any]:
    """Convert normalized article to screening workspace dict."""
    return {
        "title": article.title,
        "abstract": article.abstract,
        "authors": article.authors,
        "year": article.year_str if article.year else "",
        "source": article.source,
        "doi": article.doi,
        "url": article.url,
        "keywords": article.keywords,
        "literature_type": article.literature_type,
        "global_id": article.global_id,
        "local_id": article.local_id,
        "library": article.library,
        "completeness": article.metadata_completeness,
        "_normalized": True
    }
