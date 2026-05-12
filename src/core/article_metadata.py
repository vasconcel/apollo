"""
APOLLO Article Metadata Normalization - Schema v2.0

Centralized schema normalization with column aliases for ATLAS exports.
Handles various ATLAS/Zotero export column naming conventions.

V1.0.0 UPDATES:
- Added explicit tagging for missing abstracts (e.g., [MANUAL REVIEW REQUIRED]).
- Strengthened has_abstract property to ignore metadata injection tags.
- Ensures seamless integration with the HITL pending queues.
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

import pandas as pd


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

PROVENANCE_ALIASES = [
    "provenance_trace", "Provenance_Trace", "provenance", "Provenance",
    "source_trace", "data_provenance"
]

DETECTED_SOURCE_ALIASES = [
    "detected_source", "Detected_Source", "source_type", "Source_Type",
    "origin_source", "data_source"
]

PARSER_USED_ALIASES = [
    "parser_used", "Parser_Used", "parser", "Parser",
    "extractor", "extractor_used"
]

COMPLETENESS_SCORE_ALIASES = [
    "completeness_score", "Completeness_Score", "completeness", "Completeness",
    "metadata_score", "quality_score"
]

DUPLICATE_FLAG_ALIASES = [
    "duplicate_flag", "Duplicate_Flag", "is_duplicate", "Is_Duplicate",
    "duplicate", "Duplicate"
]

PUBLISHER_ALIASES = [
    "publisher", "Publisher", "publisher_name", "Publisher_Name",
    "publication_venue", "journal_publisher"
]

LANGUAGE_ALIASES = [
    "language", "Language", "lang", "Lang", "publication_language"
]

SEARCH_STRING_ALIASES = [
    "search_string", "Search_String", "search_query", "Search_Query",
    "query", "Query"
]

RETRIEVAL_DATE_ALIASES = [
    "retrieval_date", "Retrieval_Date", "import_date", "Import_Date",
    "collected_date", "collection_date"
]


@dataclass
class NormalizedArticle:
    """Normalized article metadata for screening - v2.0 with provenance."""
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

    publisher: str = ""
    language: str = ""

    provenance_trace: str = ""
    detected_source: str = ""
    parser_used: str = ""
    completeness_score: str = ""
    duplicate_flag: str = ""
    search_string: str = ""
    retrieval_date: str = ""

    raw_data: Dict[str, Any] = field(default_factory=dict)

    @property
    def year_str(self) -> str:
        return str(self.year) if self.year else "[NOT AVAILABLE]"

    @property
    def has_abstract(self) -> bool:
        """
        Safely determine if a true abstract exists.
        Ignores injected system tags like [MANUAL REVIEW REQUIRED].
        """
        if not self.abstract or self.abstract == "nan" or len(self.abstract.strip()) <= 10:
            return False
        if "[MANUAL REVIEW REQUIRED" in self.abstract or "[ABSTRACT MISSING" in self.abstract:
            return False
        return True

    @property
    def has_title(self) -> bool:
        return bool(self.title and self.title != "nan" and len(self.title.strip()) > 0)

    @property
    def metadata_completeness(self) -> str:
        """Return completeness assessment - considers true abstract existence."""
        if self.completeness_score:
            score = self.completeness_score.lower()
            if score in ["complete", "full", "high"]:
                return "complete"
            elif score in ["partial", "medium"]:
                return "partial"
            elif score in ["minimal", "low", "none"]:
                return "minimal"

        has_title = self.has_title
        has_true_abstract = self.has_abstract
        has_year = self.year is not None

        if has_title and has_true_abstract and has_year:
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
    """Normalize White Literature metadata from ATLAS v2.0 export."""
    article = NormalizedArticle()

    article.title = _get_first_matching_value(row, TITLE_ALIASES)
    
    # METHODOLOGICAL FIX: Handle missing abstract gracefully for WL
    abstract_val = _get_first_matching_value(row, ABSTRACT_ALIASES)
    if not abstract_val:
        article.abstract = "[ABSTRACT MISSING - FULL TEXT REVIEW MAY BE REQUIRED]"
    else:
        article.abstract = abstract_val
        
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

    article.publisher = _get_first_matching_value(row, PUBLISHER_ALIASES)
    article.language = _get_first_matching_value(row, LANGUAGE_ALIASES)

    article.provenance_trace = _get_first_matching_value(row, PROVENANCE_ALIASES)
    article.detected_source = _get_first_matching_value(row, DETECTED_SOURCE_ALIASES)
    article.parser_used = _get_first_matching_value(row, PARSER_USED_ALIASES)
    article.completeness_score = _get_first_matching_value(row, COMPLETENESS_SCORE_ALIASES)
    article.duplicate_flag = _get_first_matching_value(row, DUPLICATE_FLAG_ALIASES)
    article.search_string = _get_first_matching_value(row, SEARCH_STRING_ALIASES)
    article.retrieval_date = _get_first_matching_value(row, RETRIEVAL_DATE_ALIASES)

    article.raw_data = dict(row)

    return article


def normalize_gl_metadata(row: Dict[str, Any]) -> NormalizedArticle:
    """Normalize Grey Literature metadata from ATLAS v2.0 export."""
    article = NormalizedArticle()

    article.title = _get_first_matching_value(row, TITLE_ALIASES)
    
    # METHODOLOGICAL FIX: Explicitly flag GL missing abstract for HITL
    abstract_val = _get_first_matching_value(row, ABSTRACT_ALIASES)
    if not abstract_val:
        article.abstract = "[MANUAL REVIEW REQUIRED - GL ABSTRACT UNAVAILABLE. PLEASE EVALUATE USING THE SOURCE URL]"
    else:
        article.abstract = abstract_val
        
    article.authors = _get_first_matching_value(row, AUTHORS_ALIASES)
    article.year = _get_year(row)
    article.source = _get_first_matching_value(row, SOURCE_ALIASES)
    article.url = _get_first_matching_value(row, URL_ALIASES)
    article.keywords = _get_first_matching_value(row, KEYWORDS_ALIASES)

    article.literature_type = "GL"

    article.provenance_trace = _get_first_matching_value(row, PROVENANCE_ALIASES)
    article.detected_source = _get_first_matching_value(row, DETECTED_SOURCE_ALIASES)
    article.parser_used = _get_first_matching_value(row, PARSER_USED_ALIASES)
    article.completeness_score = _get_first_matching_value(row, COMPLETENESS_SCORE_ALIASES)

    article.raw_data = dict(row)

    return article


def article_to_dict(article: NormalizedArticle) -> Dict[str, Any]:
    """Convert normalized article to screening workspace dict - v2.0."""
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
        "publisher": article.publisher,
        "language": article.language,
        "provenance_trace": article.provenance_trace,
        "detected_source": article.detected_source,
        "parser_used": article.parser_used,
        "completeness_score": article.completeness_score,
        "duplicate_flag": article.duplicate_flag,
        "search_string": article.search_string,
        "retrieval_date": article.retrieval_date,
        "completeness": article.metadata_completeness,
        "_normalized": True,
        "_schema_version": "2.0"
    }


class ATLASSchemaDiagnostics:
    """Diagnostic tool for ATLAS schema detection and validation."""

    WL_OPTIONAL_COLUMNS = {
        "Library", "Global_ID", "Local_ID", "Title", "Authors", "Year",
        "Venue", "Publisher", "DOI", "URL", "Abstract", "Keywords",
        "Literature_Type", "Search_String", "Retrieval_Date", "Language",
        "Completeness_Score", "Duplicate_Flag", "Detected_Source", "Parser_Used",
        "Provenance_Trace"
    }

    GL_OPTIONAL_COLUMNS = {
        "#", "Title", "URL", "Source_File", "Detected_Source", "Parser_Used",
        "Metadata_Completeness", "Provenance_Trace"
    }

    @staticmethod
    def detect_sheets(file_path: str) -> Dict[str, Any]:
        """Detect available sheets in ATLAS export."""
        import pandas as pd
        
        try:
            xl = pd.ExcelFile(file_path)
            available_sheets = xl.sheet_names
        except Exception as e:
            return {"error": str(e), "sheets": []}

        wl_sheet = None
        gl_sheet = None

        for sheet in available_sheets:
            sheet_lower = sheet.lower().strip()
            if sheet_lower in ["wl", "white literature"]:
                wl_sheet = sheet
            elif sheet_lower in ["gl", "grey literature"]:
                gl_sheet = sheet

        return {
            "sheets": available_sheets,
            "wl_sheet": wl_sheet,
            "gl_sheet": gl_sheet,
            "detected_schema": "2.0" if (wl_sheet and gl_sheet) else "unknown"
        }

    @staticmethod
    def validate_columns(df: pd.DataFrame, expected_columns: set, required_columns: set = None) -> Dict[str, Any]:
        """Validate DataFrame columns against expected schema."""
        if required_columns is None:
            required_columns = expected_columns

        actual_columns = set(df.columns)
        missing_required = required_columns - actual_columns
        missing_optional = expected_columns - actual_columns
        available = actual_columns & expected_columns

        return {
            "total_columns": len(actual_columns),
            "required_columns": sorted(required_columns),
            "optional_columns": sorted(expected_columns - required_columns),
            "missing_required": sorted(missing_required),
            "missing_optional": sorted(missing_optional),
            "available_columns": sorted(available),
            "is_valid": len(missing_required) == 0,
            "completeness_pct": round(len(available) / len(expected_columns) * 100, 1) if expected_columns else 0
        }

    @staticmethod
    def generate_diagnostics(file_path: str) -> Dict[str, Any]:
        """Generate comprehensive schema diagnostics."""
        import pandas as pd

        sheet_info = ATLASSchemaDiagnostics.detect_sheets(file_path)
        
        if "error" in sheet_info:
            return {"error": sheet_info["error"], "schema_version": "unknown"}

        diagnostics = {
            "schema_version": "2.0",
            "sheets_detected": sheet_info["sheets"],
            "wl_sheet": sheet_info.get("wl_sheet"),
            "gl_sheet": sheet_info.get("gl_sheet"),
            "warnings": [],
            "info": []
        }

        if not sheet_info.get("wl_sheet"):
            diagnostics["warnings"].append("WL sheet not found - expected 'WL' or 'White Literature'")
        if not sheet_info.get("gl_sheet"):
            diagnostics["warnings"].append("GL sheet not found - expected 'GL' or 'Grey Literature'")

        if sheet_info.get("wl_sheet"):
            try:
                wl_df = pd.read_excel(file_path, sheet_name=sheet_info["wl_sheet"])
                wl_validation = ATLASSchemaDiagnostics.validate_columns(
                    wl_df, 
                    ATLASSchemaDiagnostics.WL_OPTIONAL_COLUMNS,
                    {"Title"}
                )
                diagnostics["wl"] = {
                    "row_count": len(wl_df),
                    "column_validation": wl_validation
                }
                if wl_validation["missing_required"]:
                    diagnostics["warnings"].append(f"WL missing required columns: {wl_validation['missing_required']}")
            except Exception as e:
                diagnostics["warnings"].append(f"WL sheet error: {str(e)}")

        if sheet_info.get("gl_sheet"):
            try:
                gl_df = pd.read_excel(file_path, sheet_name=sheet_info["gl_sheet"])
                gl_validation = ATLASSchemaDiagnostics.validate_columns(
                    gl_df,
                    ATLASSchemaDiagnostics.GL_OPTIONAL_COLUMNS,
                    {"Title", "URL"}
                )
                diagnostics["gl"] = {
                    "row_count": len(gl_df),
                    "column_validation": gl_validation
                }
                if gl_validation["missing_required"]:
                    diagnostics["warnings"].append(f"GL missing required columns: {gl_validation['missing_required']}")
            except Exception as e:
                diagnostics["warnings"].append(f"GL sheet error: {str(e)}")

        diagnostics["info"].append("ATLAS exports are pre-deduplicated - no duplicate removal required")

        return diagnostics