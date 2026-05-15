"""
APOLLO Parser Registry

Centralized parser selection logic for:
- Extension detection
- MIME detection  
- Content sniffing
- Extensionless BibTeX detection
- GL raw txt detection
- Fallback order management

This is the SINGLE SOURCE OF TRUTH for parser selection.
"""
import os
import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

from src.core.logging_config import get_logger

logger = get_logger("parser")


class ParserCapability(Enum):
    """Parser capability flags."""
    XLSX = "xlsx"
    CSV = "csv"
    BIBTEX = "bibtex"
    RIS = "ris"
    EXTENSIONLESS_BIBTEX = "extensionless_bibtex"
    GL_TXT = "gl_txt"
    PDF = "pdf"


class ParserConfidence(Enum):
    """Parser confidence levels."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    FALLBACK = "fallback"


@dataclass
class ParserInfo:
    """Parser registration information."""
    name: str
    capabilities: List[ParserCapability]
    extensions: List[str]
    mime_types: List[str]
    content_signatures: List[str]
    confidence: ParserConfidence
    priority: int
    fallback_for: Optional[str] = None
    
    def can_parse(self, file_path: str, content: Optional[str] = None) -> Tuple[bool, str]:
        """
        Check if this parser can handle the given input.
        
        Returns:
            Tuple of (can_parse, reason)
        """
        if self._check_extension(file_path):
            return True, f"Extension match: {os.path.splitext(file_path)[1]}"
        
        if self._check_mime(file_path):
            return True, "MIME type match"
        
        if content and self._check_content_signature(content):
            return True, "Content signature match"
        
        return False, "No match"
    
    def _check_extension(self, file_path: str) -> bool:
        """Check file extension."""
        ext = os.path.splitext(file_path)[1].lower().lstrip('.')
        return ext in [e.lower().lstrip('.') for e in self.extensions]
    
    def _check_mime(self, file_path: str) -> bool:
        """Check if file might have matching MIME type."""
        ext = os.path.splitext(file_path)[1].lower()
        return ext in ['.xlsx', '.xls', '.csv', '.bib', '.ris', '.txt']
    
    def _check_content_signature(self, content: str) -> bool:
        """Check content for known signatures."""
        content_lower = content[:500].lower() if content else ""
        
        for signature in self.content_signatures:
            if signature.lower() in content_lower:
                return True
        return False


PARSER_REGISTRY: Dict[str, ParserInfo] = {
    "atlas_xlsx": ParserInfo(
        name="atlas_xlsx",
        capabilities=[ParserCapability.XLSX],
        extensions=["xlsx", "xls"],
        mime_types=["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"],
        content_signatures=[],
        confidence=ParserConfidence.HIGH,
        priority=100,
    ),
    
    "atlas_csv": ParserInfo(
        name="atlas_csv",
        capabilities=[ParserCapability.CSV],
        extensions=["csv"],
        mime_types=["text/csv", "application/csv"],
        content_signatures=[],
        confidence=ParserConfidence.HIGH,
        priority=90,
    ),
    
    "bibtex": ParserInfo(
        name="bibtex",
        capabilities=[ParserCapability.BIBTEX],
        extensions=["bib", "bibtex"],
        mime_types=["application/x-bibtex", "text/x-bibtex"],
        content_signatures=["@article", "@book", "@inproceedings", "@incollection", "@phdthesis", "@mastersthesis"],
        confidence=ParserConfidence.HIGH,
        priority=80,
    ),
    
    "extensionless_bibtex": ParserInfo(
        name="extensionless_bibtex",
        capabilities=[ParserCapability.EXTENSIONLESS_BIBTEX],
        extensions=[],
        mime_types=[],
        content_signatures=["@article", "@book", "@inproceedings", "@incollection", "year =", "author ="],
        confidence=ParserConfidence.MEDIUM,
        priority=70,
        fallback_for="bibtex",
    ),
    
    "ris": ParserInfo(
        name="ris",
        capabilities=[ParserCapability.RIS],
        extensions=["ris"],
        mime_types=["application/x-research-info-systems"],
        content_signatures=["TY  -", "ER  -"],
        confidence=ParserConfidence.HIGH,
        priority=75,
    ),
    
    "gl_txt": ParserInfo(
        name="gl_txt",
        capabilities=[ParserCapability.GL_TXT],
        extensions=["txt", "text"],
        mime_types=["text/plain"],
        content_signatures=["http://", "https://", "www."],
        confidence=ParserConfidence.MEDIUM,
        priority=50,
    ),
}


def detect_parser(file_path: str, content: Optional[str] = None) -> Tuple[Optional[ParserInfo], str]:
    """
    Detect the appropriate parser for the given file.
    
    Priority order:
    1. High confidence exact extension matches
    2. High confidence content signature matches
    3. Medium confidence extensionless detection
    4. GL text fallback
    
    Args:
        file_path: Path to the file
        content: Optional file content for sniffing
    
    Returns:
        Tuple of (ParserInfo, detection_reason)
    """
    candidates: List[Tuple[ParserInfo, str]] = []
    
    for parser in PARSER_REGISTRY.values():
        can_parse, reason = parser.can_parse(file_path, content)
        if can_parse:
            candidates.append((parser, reason))
    
    if not candidates:
        logger.warning(f"No parser found for: {file_path}")
        return None, "No parser available"
    
    candidates.sort(key=lambda x: (x[0].priority, x[0].confidence.value), reverse=True)
    
    best_parser, reason = candidates[0]
    logger.info(f"Detected parser: {best_parser.name} ({reason})")
    
    return best_parser, reason


def get_fallback_parser(parser_name: str) -> Optional[ParserInfo]:
    """Get fallback parser for a given parser."""
    parser = PARSER_REGISTRY.get(parser_name)
    if parser and parser.fallback_for:
        return PARSER_REGISTRY.get(parser.fallback_for)
    return PARSER_REGISTRY.get("gl_txt")


def list_available_parsers() -> List[str]:
    """List all available parser names."""
    return list(PARSER_REGISTRY.keys())


def get_parser_info(parser_name: str) -> Optional[ParserInfo]:
    """Get information about a specific parser."""
    return PARSER_REGISTRY.get(parser_name)


def is_supported_format(file_path: str, content: Optional[str] = None) -> bool:
    """Check if a file format is supported."""
    parser, _ = detect_parser(file_path, content)
    return parser is not None