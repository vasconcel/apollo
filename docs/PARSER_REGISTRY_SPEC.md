# APOLLO Parser Registry Specification

## Overview

The Parser Registry is the **SINGLE SOURCE OF TRUTH** for parser selection. It centralizes:

- Extension detection
- MIME detection
- Content sniffing
- Extensionless BibTeX detection
- GL raw txt detection
- Fallback order management

## Registered Parsers

| Parser Name | Capabilities | Extensions | Priority | Confidence |
|------------|-------------|------------|----------|------------|
| atlas_xlsx | XLSX | xlsx, xls | 100 | HIGH |
| atlas_csv | CSV | csv | 90 | HIGH |
| bibtex | BibTeX | bib, bibtex | 80 | HIGH |
| extensionless_bibtex | Extensionless BibTeX | - | 70 | MEDIUM |
| ris | RIS | ris | 75 | HIGH |
| gl_txt | GL TXT | txt, text | 50 | MEDIUM |

## Content Signatures

Each parser may have content signatures for detection:

```python
bibtex.content_signatures = [
    "@article", "@book", "@inproceedings", 
    "@incollection", "@phdthesis", "@mastersthesis"
]

ris.content_signatures = ["TY  -", "ER  -"]

gl_txt.content_signatures = ["http://", "https://", "www."]
```

## Detection Priority

1. High confidence exact extension matches
2. High confidence content signature matches
3. Medium confidence extensionless detection
4. GL text fallback

## Core Functions

### detect_parser()

```python
def detect_parser(file_path: str, content: Optional[str] = None) -> Tuple[Optional[ParserInfo], str]:
    """
    Detect the appropriate parser for the given file.
    Returns (ParserInfo, detection_reason)
    """
```

### get_fallback_parser()

```python
def get_fallback_parser(parser_name: str) -> Optional[ParserInfo]:
    """Get fallback parser for a given parser."""
```

### is_supported_format()

```python
def is_supported_format(file_path: str, content: Optional[str] = None) -> bool:
    """Check if a file format is supported."""
```

## File Location

`src/core/parser_registry.py`

## Usage

```python
from src.core.parser_registry import (
    detect_parser,
    get_fallback_parser,
    is_supported_format,
    PARSER_REGISTRY
)

# Detect parser for file
parser, reason = detect_parser("article.bib")

# Check if supported
if is_supported_format("data.xlsx"):
    print("Supported format")

# Get fallback
fallback = get_fallback_parser("extensionless_bibtex")
```