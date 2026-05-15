"""
APOLLO Metadata Contract

Centralized metadata normalization layer ensuring:
- Required canonical fields
- Normalization rules
- Provenance enforcement
- Defensive defaults
- Metadata validation

This is the SINGLE SOURCE OF TRUTH for metadata handling.
"""
from typing import Dict, Any, Optional, Set, List
from dataclasses import dataclass, field
from datetime import datetime
import uuid
import hashlib

from src.core.logging_config import get_logger

logger = get_logger("metadata")


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


YEAR_SOURCES: List[str] = [
    "atlas",
    "regex",
    "doi",
    "csv",
    "bibtex",
    "ris",
    "manual",
    "missing",
]

AUTHOR_NORMALIZATION_SOURCES: List[str] = [
    "raw",
    "pylatexenc",
    "manual",
    "unknown",
]


LITERATURE_TYPES: List[str] = [
    "WL",
    "GL",
]


COMPLETENESS_LEVELS: List[str] = [
    "complete",
    "partial",
    "minimal",
    "unknown",
]


@dataclass
class MetadataContract:
    """
    Validated metadata structure for APOLLO articles.
    """
    title: str = ""
    abstract: str = ""
    authors: str = ""
    author_normalization_source: str = "unknown"
    year: str = "Unknown"
    year_source: str = "missing"
    source: str = ""
    source_type: str = "unknown"
    doi: str = ""
    url: str = ""
    keywords: str = ""
    literature_type: str = "WL"
    global_id: str = ""
    local_id: str = ""
    library: str = ""
    provenance_trace: str = ""
    parser_used: str = "unknown"
    metadata_completeness: str = "unknown"
    completeness_score: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "abstract": self.abstract,
            "authors": self.authors,
            "author_normalization_source": self.author_normalization_source,
            "year": self.year,
            "year_source": self.year_source,
            "source": self.source,
            "source_type": self.source_type,
            "doi": self.doi,
            "url": self.url,
            "keywords": self.keywords,
            "literature_type": self.literature_type,
            "global_id": self.global_id,
            "local_id": self.local_id,
            "library": self.library,
            "provenance_trace": self.provenance_trace,
            "parser_used": self.parser_used,
            "metadata_completeness": self.metadata_completeness,
            "completeness_score": self.completeness_score,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MetadataContract":
        """Create from dictionary with defaults."""
        contract = cls()
        for field_name in CANONICAL_METADATA_FIELDS:
            if field_name in data and data[field_name]:
                setattr(contract, field_name, data[field_name])
        return contract


def validate_metadata(metadata: Dict[str, Any]) -> tuple[bool, List[str]]:
    """
    Validate metadata against contract.
    
    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors: List[str] = []
    
    for field in CANONICAL_METADATA_FIELDS:
        if field not in metadata:
            errors.append(f"Missing required field: {field}")
    
    if metadata.get("year_source") and metadata["year_source"] not in YEAR_SOURCES:
        errors.append(f"Invalid year_source: {metadata['year_source']}")
    
    if metadata.get("author_normalization_source") and metadata["author_normalization_source"] not in AUTHOR_NORMALIZATION_SOURCES:
        errors.append(f"Invalid author_normalization_source: {metadata['author_normalization_source']}")
    
    if metadata.get("literature_type") and metadata["literature_type"] not in LITERATURE_TYPES:
        errors.append(f"Invalid literature_type: {metadata['literature_type']}")
    
    if metadata.get("metadata_completeness") and metadata["metadata_completeness"] not in COMPLETENESS_LEVELS:
        errors.append(f"Invalid metadata_completeness: {metadata['metadata_completeness']}")
    
    return (len(errors) == 0, errors)


def normalize_metadata(metadata: Dict[str, Any], parser_name: str = "unknown") -> Dict[str, Any]:
    """
    Normalize metadata according to contract.
    
    This is the SINGLE ENTRY POINT for metadata normalization.
    All ingestion paths MUST use this function.
    
    Args:
        metadata: Raw metadata dictionary
        parser_name: Name of parser used
    
    Returns:
        Normalized metadata dictionary
    """
    normalized = dict(DEFAULT_METADATA_VALUES)
    
    for field in CANONICAL_METADATA_FIELDS:
        if field in metadata and metadata[field]:
            normalized[field] = metadata[field]
    
    if parser_name != "unknown":
        normalized["parser_used"] = parser_name
    
    if not normalized.get("provenance_trace"):
        normalized["provenance_trace"] = generate_provenance_trace(normalized)
    
    is_valid, errors = validate_metadata(normalized)
    if not is_valid:
        logger.warning(f"Metadata validation warnings: {errors}")
    
    return normalized


def generate_provenance_trace(metadata: Dict[str, Any]) -> str:
    """
    Generate deterministic provenance trace for metadata.
    """
    components = [
        metadata.get("literature_type", "WL"),
        metadata.get("parser_used", "unknown"),
        metadata.get("year_source", "missing"),
        metadata.get("author_normalization_source", "unknown"),
        metadata.get("source_type", "unknown"),
    ]
    
    trace_string = "|".join(components)
    trace_hash = hashlib.sha256(trace_string.encode()).hexdigest()[:12]
    
    return f"APOLLO_v2.0|{trace_hash}"


def ensure_metadata_integrity(article_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Runtime safety check: ensure article has required fields.
    
    Args:
        article_id: Article identifier
        metadata: Article metadata
    
    Returns:
        Validated metadata (with defaults if missing)
    
    Raises:
        ValueError: If critical fields cannot be determined
    """
    required_for_screening = ["title", "provenance_trace"]
    
    missing_critical = []
    for field in required_for_screening:
        if not metadata.get(field):
            missing_critical.append(field)
    
    if missing_critical and not metadata.get("title"):
        raise ValueError(f"Article {article_id} missing critical fields: {missing_critical}")
    
    return normalize_metadata(metadata, metadata.get("parser_used", "unknown"))


def get_metadata_summary(metadata: Dict[str, Any]) -> str:
    """
    Get human-readable metadata summary for debugging.
    """
    return (
        f"Title: {metadata.get('title', 'N/A')[:50]}... "
        f"Year: {metadata.get('year', 'N/A')} "
        f"({metadata.get('year_source', 'unknown')}) "
        f"Authors: {metadata.get('authors', 'N/A')[:30]}... "
        f"Source: {metadata.get('source', 'N/A')[:20]}... "
        f"Parser: {metadata.get('parser_used', 'unknown')}"
    )