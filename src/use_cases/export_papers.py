import os
from pathlib import Path

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from src.domain.criteria_config import DEFAULT_CRITERIA
from src.domain.enums import CriterionType, ScreeningStatus
from src.domain.interfaces import PaperRepository, ScreeningDecisionRepository

_HEADER_FILL = PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid")
_HEADER_FONT = Font(bold=True)
_THIN_BORDER = Border(
    left=Side(style="thin", color="000000"),
    right=Side(style="thin", color="000000"),
    top=Side(style="thin", color="000000"),
    bottom=Side(style="thin", color="000000"),
)
_WRAP_ALIGN = Alignment(wrap_text=True, vertical="top", horizontal="left")

_MAX_COL_WIDTH = 50
_MIN_COL_WIDTH = 10

WL_HEADERS = [
    "Library",
    "",
    "#",
    "Title",
    "Abstract",
    "Palavra-Chaves",
    "CIs1",
    "CEs1",
    "Revisor 1",
    "CIs2",
    "CEs2",
    "Revisor 2",
    "Decision",
]

GL_HEADERS_ROW1 = ["#", "Title", "", "", "Decision"]
GL_HEADERS_ROW2 = ["", "", "Revisor 1", "Revisor 2", ""]


def _get_inclusion_criteria_text() -> str:
    criteria = [c for c in DEFAULT_CRITERIA if c.type == CriterionType.INCLUSION]
    return "\n".join(f"{c.code}: {c.description}" for c in criteria)


def _get_exclusion_criteria_text() -> str:
    criteria = [c for c in DEFAULT_CRITERIA if c.type == CriterionType.EXCLUSION]
    return "\n".join(f"{c.code}: {c.description}" for c in criteria)


def _get_full_protocol_text() -> str:
    ic_text = _get_inclusion_criteria_text()
    ec_text = _get_exclusion_criteria_text()
    return f"Inclusion Criteria (IC):\n{ic_text}\n\nExclusion Criteria (EC):\n{ec_text}"


def _auto_column_width(ws) -> None:
    for col_cells in ws.columns:
        col_letter = get_column_letter(col_cells[0].column)
        lengths = []
        for cell in col_cells:
            if cell.value is not None:
                val = str(cell.value)
                max_line_len = max(len(line) for line in val.split("\n")) if val else 0
                lengths.append(max_line_len)
        max_len = max(lengths) if lengths else _MIN_COL_WIDTH
        width = min(max_len + 3, _MAX_COL_WIDTH)
        ws.column_dimensions[col_letter].width = max(width, _MIN_COL_WIDTH)


def _get_library(paper) -> str:
    return paper.metadata.get("Detected_Source") or paper.metadata.get("Library") or "Unknown Database"


def _get_keywords(paper) -> str:
    keywords = paper.metadata.get("Keywords") or paper.metadata.get("Palavra-Chaves")
    if isinstance(keywords, list):
        return "; ".join(keywords)
    return keywords or ""


def _map_status_to_revisor(status: ScreeningStatus) -> str:
    if status == ScreeningStatus.INCLUDED:
        return "YES"
    elif status == ScreeningStatus.EXCLUDED:
        return "NO"
    return "NEEDS_REVIEW"


def _map_status_to_numeric(status: ScreeningStatus) -> int | str:
    if status == ScreeningStatus.INCLUDED:
        return 1
    elif status == ScreeningStatus.EXCLUDED:
        return 0
    return "NEEDS_REVIEW"


class ExportScreenedPapersUseCase:
    def __init__(
        self,
        paper_repository: PaperRepository,
        decision_repository: ScreeningDecisionRepository,
    ) -> None:
        self._paper_repo = paper_repository
        self._decision_repo = decision_repository

    def execute(self, output_path: str = "data/processed/apollo_results.xlsx") -> None:
        papers = self._paper_repo.get_all_papers()
        decisions = self._decision_repo.get_all_decisions()
        paper_map = {p.id: p for p in papers}

        wl_papers = []
        gl_papers = []
        for decision in decisions:
            paper = paper_map.get(decision.paper_id)
            if paper:
                if paper.source_type.value == "WL":
                    wl_papers.append((paper, decision))
                else:
                    gl_papers.append((paper, decision))

        out = Path(output_path)
        os.makedirs(str(out.parent), exist_ok=True)

        wb = Workbook()
        wb.remove(wb.active)

        self._create_wl_sheet(wb, wl_papers)
        self._create_gl_sheet(wb, gl_papers)

        wb.save(str(out))

    def _create_wl_sheet(self, wb, wl_papers: list) -> None:
        ws = wb.create_sheet("White Literature")

        for col_idx, header in enumerate(WL_HEADERS, start=1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.fill = _HEADER_FILL
            cell.font = _HEADER_FONT
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = _THIN_BORDER

        ic_comment_text = _get_inclusion_criteria_text()
        ec_comment_text = _get_exclusion_criteria_text()

        ws["G1"].comment = Comment(ic_comment_text, "APOLLO")
        ws["J1"].comment = Comment(ic_comment_text, "APOLLO")
        ws["H1"].comment = Comment(ec_comment_text, "APOLLO")
        ws["K1"].comment = Comment(ec_comment_text, "APOLLO")

        for row_idx, (paper, decision) in enumerate(wl_papers, start=2):
            ws.cell(row=row_idx, column=1, value=_get_library(paper))
            ws.cell(row=row_idx, column=2, value=paper.id)
            ws.cell(row=row_idx, column=3, value=row_idx - 1)
            ws.cell(row=row_idx, column=4, value=paper.title)
            ws.cell(row=row_idx, column=5, value=paper.abstract or "")
            ws.cell(row=row_idx, column=6, value=_get_keywords(paper))

            inclusion_codes = [c for c in decision.applied_criteria_codes if c.startswith("IC")]
            exclusion_codes = [c for c in decision.applied_criteria_codes if c.startswith("EC")]

            ws.cell(row=row_idx, column=7, value="; ".join(inclusion_codes) if inclusion_codes else "")
            ws.cell(row=row_idx, column=8, value="; ".join(exclusion_codes) if exclusion_codes else "")
            ws.cell(row=row_idx, column=9, value=_map_status_to_revisor(decision.status))

            for col_idx in range(1, 14):
                cell = ws.cell(row=row_idx, column=col_idx)
                cell.border = _THIN_BORDER
                if col_idx in (4, 5):
                    cell.alignment = _WRAP_ALIGN

        _auto_column_width(ws)

    def _create_gl_sheet(self, wb, gl_papers: list) -> None:
        ws = wb.create_sheet("Grey Literature")

        for col_idx, header in enumerate(GL_HEADERS_ROW1, start=1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.fill = _HEADER_FILL
            cell.font = _HEADER_FONT
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = _THIN_BORDER

        for col_idx, header in enumerate(GL_HEADERS_ROW2, start=1):
            cell = ws.cell(row=2, column=col_idx, value=header)
            cell.fill = _HEADER_FILL
            cell.font = _HEADER_FONT
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = _THIN_BORDER

        ws.merge_cells("A1:A2")
        ws.merge_cells("B1:B2")
        ws.merge_cells("E1:E2")

        protocol_comment_text = _get_full_protocol_text()
        ws["C2"].comment = Comment(protocol_comment_text, "APOLLO")
        ws["D2"].comment = Comment(protocol_comment_text, "APOLLO")

        for row_idx, (paper, decision) in enumerate(gl_papers, start=3):
            ws.cell(row=row_idx, column=1, value=row_idx - 2)
            ws.cell(row=row_idx, column=2, value=paper.title)
            ws.cell(row=row_idx, column=3, value=_map_status_to_numeric(decision.status))

            for col_idx in range(1, 6):
                cell = ws.cell(row=row_idx, column=col_idx)
                cell.border = _THIN_BORDER
                if col_idx == 2:
                    cell.alignment = _WRAP_ALIGN

        _auto_column_width(ws)