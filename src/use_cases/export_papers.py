import csv
import os
from pathlib import Path

from src.domain.interfaces import PaperRepository, ScreeningDecisionRepository


class ExportScreenedPapersUseCase:
    _HEADERS = [
        "Global_ID",
        "Title",
        "URL",
        "Abstract",
        "Source_Type",
        "Status",
        "Rationale",
        "Applied_Criteria",
    ]

    def __init__(
        self,
        paper_repository: PaperRepository,
        decision_repository: ScreeningDecisionRepository,
    ) -> None:
        self._paper_repo = paper_repository
        self._decision_repo = decision_repository

    def execute(self, output_path: str = "data/processed/apollo_results.csv") -> None:
        papers = self._paper_repo.get_all_papers()
        decisions = self._decision_repo.get_all_decisions()

        paper_map = {p.id: p for p in papers}

        out = Path(output_path)
        os.makedirs(str(out.parent), exist_ok=True)

        with open(out, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(self._HEADERS)

            for decision in decisions:
                paper = paper_map.get(decision.paper_id)
                writer.writerow([
                    decision.paper_id,
                    paper.title if paper else "",
                    paper.url if paper else "",
                    paper.abstract if paper else "",
                    paper.source_type.value if paper else "",
                    decision.status.value,
                    decision.rationale,
                    "; ".join(decision.applied_criteria_codes),
                ])
