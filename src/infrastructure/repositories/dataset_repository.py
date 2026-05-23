import math
import os
from pathlib import Path

import pandas as pd

from src.domain.enums import SourceType
from src.domain.interfaces import PaperRepository
from src.domain.models import Paper

_MAPPED_COLUMNS = frozenset({
    "Global_ID",
    "Title",
    "URL",
    "Abstract",
    "Year",
    "Provenance_Trace",
})


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


def _source_type_from_provenance(provenance: str) -> SourceType:
    if provenance.startswith("wl:"):
        return SourceType.WL
    if provenance.startswith("gl:"):
        return SourceType.GL
    msg = f"Unknown provenance prefix in: {provenance}"
    raise ValueError(msg)


def _row_to_paper(row: dict) -> Paper:
    provenance = str(row.get("Provenance_Trace", ""))
    return Paper(
        id=str(row["Global_ID"]),
        title=str(row["Title"]),
        url=_coerce_str(row.get("URL")),
        abstract=_coerce_str(row.get("Abstract")),
        source_type=_source_type_from_provenance(provenance),
        publication_year=_coerce_year(row.get("Year")),
        metadata={
            key: _coerce_str(val) if isinstance(val, str) or (isinstance(val, float) and math.isnan(val)) else val
            for key, val in row.items()
            if key not in _MAPPED_COLUMNS
        },
    )


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
        elif ext in (".xls", ".xlsx"):
            df = pd.read_excel(file_path)
        else:
            raise ValueError(f"Unsupported file format: {ext}")

        df = df.where(df.notna(), None)

        papers: list[Paper] = []
        for _, row in df.iterrows():
            row_dict = row.to_dict()
            papers.append(_row_to_paper(row_dict))

        return papers
