import math
import re
from pathlib import Path

import pandas as pd

from src.domain.enums import SourceType
from src.domain.interfaces import PaperRepository
from src.domain.models import Paper

_WL_SHEET_PATTERN = re.compile(r"(white|wl)", re.IGNORECASE)
_GL_SHEET_PATTERN = re.compile(r"(grey|gl)", re.IGNORECASE)


def _coerce_str(value: object) -> str | None:
    if isinstance(value, str):
        return value if value.strip() else None
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return str(value)


def _coerce_year(value: object) -> int | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return int(value)


def _coerce_int(value: object) -> int | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _pick(cols: dict, *candidates: str) -> object:
    for c in candidates:
        if c in cols:
            v = cols[c]
            if v is not None and not (isinstance(v, float) and math.isnan(v)):
                return v
    return None


def _detect_sheet_type(sheet_name: str) -> SourceType | None:
    if _WL_SHEET_PATTERN.search(sheet_name):
        return SourceType.WL
    if _GL_SHEET_PATTERN.search(sheet_name):
        return SourceType.GL
    return None


def _parse_wl_row(sheet_name: str, row: dict, index: int) -> Paper:
    title = _coerce_str(_pick(row, "Title", "Título", "title", "titulo"))
    if not title:
        title = f"Untitled WL-{index + 1}"

    abstract = _coerce_str(
        _pick(row, "Abstract", "Abstract", "abstract", "Resumo", "resumo")
    )

    url = _coerce_str(_pick(row, "URL", "Url", "url", "Link", "link"))

    year = _coerce_year(
        _pick(row, "Year", "year", "Publication Year", "Ano", "Ano de Publicação")
    )

    pub_year = _coerce_int(year)

    paper_id = str(_pick(row, "Global_ID", "global_id", "ID", "id")) or f"WL-{index + 1}"

    metadata = {
        "Library": _coerce_str(_pick(row, "Library", "library", "Source", "source", "Base de Dados")),
        "Keywords": _coerce_str(_pick(row, "Keywords", "keywords", "Palavra-Chave", "Palavra-Chaves")),
        "Sheet": sheet_name,
    }
    metadata = {k: v for k, v in metadata.items() if v is not None}

    return Paper(
        id=paper_id,
        title=title,
        url=url,
        abstract=abstract or "",
        source_type=SourceType.WL,
        publication_year=pub_year,
        metadata=metadata,
    )


def _parse_gl_row(sheet_name: str, row: dict, index: int) -> Paper:
    title = _coerce_str(_pick(row, "Title", "Título", "title", "titulo"))
    if not title:
        title = f"Untitled GL-{index + 1}"

    abstract = _coerce_str(
        _pick(row, "Abstract", "Abstract", "abstract", "Resumo", "resumo", "Summary", "summary")
    )

    url = _coerce_str(_pick(row, "URL", "Url", "url", "Link", "link"))

    year = _coerce_year(
        _pick(row, "Year", "year", "Publication Year", "Ano", "Ano de Publicação")
    )

    pub_year = _coerce_int(year)

    paper_id = str(_pick(row, "Global_ID", "global_id", "ID", "id")) or f"GL-{index + 1}"

    metadata = {
        "Detected_Source": _coerce_str(
            _pick(row, "Detected_Source", "Source_File", "source_file", "Source File", "Library", "source")
        ),
        "Sheet": sheet_name,
    }
    metadata = {k: v for k, v in metadata.items() if v is not None}

    return Paper(
        id=paper_id,
        title=title,
        url=url,
        abstract=abstract or "",
        source_type=SourceType.GL,
        publication_year=pub_year,
        metadata=metadata,
    )


def _parse_sheet(df: pd.DataFrame, sheet_name: str) -> list[Paper]:
    sheet_type = _detect_sheet_type(sheet_name)
    if sheet_type is None:
        return []

    df = df.where(df.notna(), None)
    papers: list[Paper] = []

    parse_fn = _parse_wl_row if sheet_type == SourceType.WL else _parse_gl_row

    for idx, (_, row) in enumerate(df.iterrows()):
        row_dict = row.to_dict()
        try:
            paper = parse_fn(sheet_name, row_dict, idx)
            papers.append(paper)
        except Exception:
            continue

    return papers


class DatasetPaperRepository(PaperRepository):
    def __init__(self, file_path: str | Path) -> None:
        self._file_path = Path(file_path)

    def get_all_papers(self) -> list[Paper]:
        file_path = self._file_path
        if not file_path.exists():
            raise FileNotFoundError(f"Dataset file not found: {file_path}")

        ext = file_path.suffix.lower()
        if ext == ".csv":
            df = pd.read_csv(file_path)
            df = df.where(df.notna(), None)
            papers: list[Paper] = []
            for _, row in df.iterrows():
                row_dict = row.to_dict()
                provenance = str(row_dict.get("Provenance_Trace", ""))
                papers.append(Paper(
                    id=str(row_dict["Global_ID"]),
                    title=str(row_dict["Title"]),
                    url=_coerce_str(row_dict.get("URL")),
                    abstract=_coerce_str(row_dict.get("Abstract")),
                    source_type=SourceType.WL if provenance.startswith("wl:") else SourceType.GL,
                    publication_year=_coerce_year(row_dict.get("Year")),
                    metadata={k: _coerce_str(v) if isinstance(v, str) or (isinstance(v, float) and math.isnan(v)) else v
                              for k, v in row_dict.items()
                              if k not in frozenset({"Global_ID", "Title", "URL", "Abstract", "Year", "Provenance_Trace"})},
                ))
            return papers

        if ext not in (".xls", ".xlsx"):
            raise ValueError(f"Unsupported file format: {ext}")

        xls = pd.ExcelFile(file_path)
        papers: list[Paper] = []
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name)
            papers.extend(_parse_sheet(df, sheet_name))

        return papers
