import asyncio
import logging
import re
from collections.abc import Callable
from typing import Optional, TYPE_CHECKING

from tqdm import tqdm

from src.domain.enums import ScreeningStatus
from src.domain.interfaces import (
    PaperRepository,
    ScreeningDecisionRepository,
)
from src.domain.models import Criterion, Paper, ScreeningDecision
from src.infrastructure.services.scraper import (
    fetch_abstract_from_crossref,
    fetch_url_content,
)
from src.use_cases.screen_paper import ScreenPaperUseCase

if TYPE_CHECKING:
    from src.infrastructure.services.svm_service import SVMService

logger = logging.getLogger(__name__)


def normalize_title(title: str) -> str:
    text = title.lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


class RunScreeningPipelineUseCase:
    def __init__(
        self,
        paper_repository: PaperRepository,
        decision_repository: ScreeningDecisionRepository,
        screen_paper_use_case: ScreenPaperUseCase,
        criteria: list[Criterion],
        progress_callback: Callable[[str], None] | None = None,
        settings_provider: Callable[[str, str], str] | None = None,
        cooldown_callback: Callable[[float], None] | None = None,
    ) -> None:
        self._paper_repo = paper_repository
        self._decision_repo = decision_repository
        self._screen = screen_paper_use_case
        self._criteria = criteria
        self._progress_callback = progress_callback
        self._settings_provider = settings_provider
        self._cooldown_callback = cooldown_callback

    async def execute(
        self,
        calibration_paper_ids: Optional[set[str]] = None,
        target: str = "ALL",
        svm_service: Optional["SVMService"] = None,
    ) -> int:
        papers = await asyncio.to_thread(self._paper_repo.get_all_papers)
        processed = 0
        seen_titles: dict[str, str] = {}
        provider = (
            self._settings_provider("llm_provider", "ollama")
            if self._settings_provider
            else "ollama"
        )
        needs_throttle = provider != "ollama"
        semaphore = asyncio.Semaphore(1 if needs_throttle else 3)

        # Sequential pass: filter, skip existing decisions, mark duplicates
        to_screen: list[Paper] = []
        for paper in papers:
            # Strict calibration isolation: skip any paper not in the set
            if calibration_paper_ids and paper.id not in calibration_paper_ids:
                continue

            # Filter by target source type
            if target != "ALL" and paper.source_type.value != target:
                continue

            norm = normalize_title(paper.title)

            existing = self._decision_repo.get_decision(paper.id)
            if existing is not None:
                # In calibration mode, only reprocess placeholder decisions (NEEDS_REVIEW).
                # Skip papers that already have a definitive INCLUDED/EXCLUDED decision
                # so that resume picks up exactly where it left off.
                if calibration_paper_ids and paper.id in calibration_paper_ids:
                    if existing.status == ScreeningStatus.NEEDS_REVIEW:
                        to_screen.append(paper)
                        continue
                    seen_titles[norm] = paper.id
                    continue
                # In full mode, skip ONLY if the decision is definitive (INCLUDED/EXCLUDED).
                # Reprocess if it's still a placeholder (NEEDS_REVIEW)
                if existing.status == ScreeningStatus.NEEDS_REVIEW:
                    to_screen.append(paper)
                    continue
                seen_titles[norm] = paper.id
                continue

            if norm in seen_titles:
                decision = self._make_ec6_decision(paper)
                self._decision_repo.save_decision(
                    decision,
                    publication_year=paper.publication_year or 0,
                )
                processed += 1
                continue

            seen_titles[norm] = paper.id
            to_screen.append(paper)

        # Fetch human-audited examples for few-shot prompting
        few_shot_examples = self._decision_repo.get_few_shot_examples(limit=3)

        # Sequential batch pass: screen papers in batches of 3 for instant cancellation
        batch_size = 3
        BATCH_COMMIT_SIZE = 1
        last_commit_count = 0
        interrupted = False

        supports_batching = hasattr(self._decision_repo, "begin_batch")
        if supports_batching:
            try:
                self._decision_repo.begin_batch()
            except Exception as _bb_exc:
                logger.warning("begin_batch suppressed: %s", _bb_exc)

        if to_screen:
            try:
                with tqdm(
                    total=len(to_screen),
                    desc="Screening papers",
                    unit="paper",
                ) as pbar:
                    async def screen_one_with_progress(paper: Paper) -> None:
                        nonlocal processed, interrupted

                        if interrupted:
                            return
                        if self._progress_callback is not None:
                            self._progress_callback(paper.title)

                        # SVM cascade: fast-track CPU exclusion, bypass LLM
                        if svm_service is not None:
                            should_exclude, conf = svm_service.predict_exclusion(paper)
                            if should_exclude:
                                decision = ScreeningDecision(
                                    paper_id=paper.id,
                                    status=ScreeningStatus.EXCLUDED,
                                    confidence_score=conf,
                                    rationale=f"SVM_AUTO_EXCLUDE (Confidence: {conf:.2f}). Bypassed LLM for speed.",
                                    applied_criteria_codes=["SVM_FAST"],
                                )
                                self._decision_repo.save_decision(
                                    decision,
                                    title=paper.title,
                                    abstract=paper.abstract or "",
                                    publication_year=paper.publication_year or 0,
                                )
                                processed += 1
                                pbar.set_postfix_str(f"{paper.id} [SVM_FAST]")
                                pbar.update(1)
                                return

                        if needs_throttle:
                            delay = float(self._settings_provider("llm_delay", "0.0"))
                            if delay > 0:
                                if self._cooldown_callback:
                                    self._cooldown_callback(delay)
                                await asyncio.sleep(delay)
                                if self._cooldown_callback:
                                    self._cooldown_callback(0.0)

                        async with semaphore:
                            try:
                                # GL web scraping: fetch content for GL papers with no abstract
                                scraped_text: Optional[str] = None
                                if not paper.abstract and paper.source_type.value == "GL" and paper.url:
                                    cached = self._decision_repo.get_pdf_metadata(paper.id)
                                    if cached and cached.get("full_text"):
                                        paper = paper.model_copy(update={"abstract": cached["full_text"]})
                                    else:
                                        scraped_text = await fetch_url_content(paper.url)
                                        if scraped_text:
                                            paper = paper.model_copy(update={"abstract": scraped_text})

                                # WL Crossref fallback: fetch missing abstracts for WL papers
                                if not paper.abstract and paper.source_type.value == "WL":
                                    fetched = await fetch_abstract_from_crossref(paper.title)
                                    if fetched:
                                        paper = paper.model_copy(update={"abstract": fetched})
                                        logger.info(
                                            "Crossref abstract recovered for WL paper: %s",
                                            paper.title[:30],
                                        )

                                decision = await self._screen.execute(
                                    paper=paper,
                                    criteria=self._criteria,
                                    few_shot_examples=few_shot_examples,
                                )
                            except KeyboardInterrupt:
                                interrupted = True
                                return
                            self._decision_repo.save_decision(
                                decision,
                                title=paper.title,
                                abstract=paper.abstract or "",
                                publication_year=paper.publication_year or 0,
                            )
                            if scraped_text:
                                self._decision_repo.save_pdf_metadata(paper.id, scraped_text, None)
                            processed += 1
                            pbar.set_postfix_str(
                                f"{paper.id} [{decision.status.value}]"
                            )
                            pbar.update(1)

                    for i in range(0, len(to_screen), batch_size):
                        if interrupted:
                            break

                        batch = to_screen[i : i + batch_size]
                        await asyncio.gather(
                            *(screen_one_with_progress(p) for p in batch)
                        )

                        if supports_batching and processed - last_commit_count >= BATCH_COMMIT_SIZE:
                            try:
                                self._decision_repo.end_batch()
                            except Exception as _eb_exc:
                                logger.warning("end_batch suppressed: %s", _eb_exc)
                            try:
                                self._decision_repo.begin_batch()
                            except Exception as _bb_exc:
                                logger.warning("begin_batch suppressed: %s", _bb_exc)
                            last_commit_count = processed

                    if interrupted:
                        raise KeyboardInterrupt()
            except asyncio.CancelledError:
                if supports_batching:
                    try:
                        self._decision_repo.end_batch()
                    except Exception as _eb_exc:
                        logger.warning("end_batch suppressed: %s", _eb_exc)
                logger.info(
                    "Screening pipeline natively cancelled. Progress saved for %d papers.",
                    processed,
                )
                raise
            except KeyboardInterrupt:
                if supports_batching:
                    try:
                        self._decision_repo.end_batch()
                    except Exception as _eb_exc:
                        logger.warning("end_batch suppressed: %s", _eb_exc)
                logger.warning(
                    "Interrupted by user after %d papers. Progress saved.",
                    processed,
                )

        if supports_batching:
            try:
                self._decision_repo.end_batch()
            except Exception as _eb_exc:
                logger.warning("end_batch suppressed: %s", _eb_exc)
        return processed

    @staticmethod
    def _make_ec6_decision(paper: Paper) -> ScreeningDecision:
        return ScreeningDecision(
            paper_id=paper.id,
            status=ScreeningStatus.EXCLUDED,
            confidence_score=1.0,
            rationale="Duplicate study detected.",
            applied_criteria_codes=["EC6"],
        )
