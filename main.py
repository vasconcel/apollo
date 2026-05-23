import asyncio
import logging
import sys

from dotenv import load_dotenv

load_dotenv()

from src.domain.criteria_config import DEFAULT_CRITERIA
from src.infrastructure.repositories.dataset_repository import (
    DatasetPaperRepository,
)
from src.infrastructure.repositories.sqlite_repository import (
    SQLiteScreeningDecisionRepository,
)
from src.infrastructure.services.ollama_service import OllamaLLMService
from src.use_cases.export_papers import ExportScreenedPapersUseCase
from src.use_cases.heuristic_screening import HeuristicScreeningUseCase
from src.use_cases.run_screening_pipeline import RunScreeningPipelineUseCase
from src.use_cases.screen_paper import ScreenPaperUseCase

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(message)s",
)


async def main() -> None:
    dataset_path = "ATLAS_Initial_Search_20260511_224108.xlsx"
    db_path = "screening.db"
    output_path = "data/processed/apollo_results.csv"

    paper_repo = DatasetPaperRepository(dataset_path)
    decision_repo = SQLiteScreeningDecisionRepository(db_path)
    heuristic = HeuristicScreeningUseCase()
    llm = OllamaLLMService()
    screen = ScreenPaperUseCase(heuristic_use_case=heuristic, llm_service=llm)

    pipeline = RunScreeningPipelineUseCase(
        paper_repository=paper_repo,
        decision_repository=decision_repo,
        screen_paper_use_case=screen,
        criteria=DEFAULT_CRITERIA,
    )

    try:
        processed = await pipeline.execute()
        print(f"\nDone. Processed {processed} new papers.")
    except Exception as exc:
        print(f"\nUnexpected error: {exc}", file=sys.stderr)
        raise
    finally:
        print("\nExporting results...")
        export = ExportScreenedPapersUseCase(paper_repo, decision_repo)
        export.execute(output_path=output_path)
        print(f"Exported to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
