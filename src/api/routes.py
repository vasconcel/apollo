import asyncio
import logging
import os
import random
import shutil
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

import httpx
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.domain.enums import ScreeningStatus
from src.domain.interfaces import LLMService, PaperRepository, ScreeningDecisionRepository
from src.domain.metrics import compute_metrics, metrics_to_dict
from src.domain.models import Paper, ScreeningDecision
from src.infrastructure.repositories.dataset_repository import DatasetPaperRepository
from src.infrastructure.repositories.sqlite_repository import SQLiteScreeningDecisionRepository
from src.infrastructure.services.ollama_service import OllamaLLMService
from src.infrastructure.services.scraper import fetch_pdf_metadata_by_doi
from src.use_cases.export_papers import ExportScreenedPapersUseCase
from src.use_cases.heuristic_screening import HeuristicScreeningUseCase
from src.use_cases.run_screening_pipeline import RunScreeningPipelineUseCase
from src.use_cases.screen_paper import ScreenPaperUseCase

router = APIRouter()

_dataset_path: Optional[Path] = None
_screening_active: bool = False
_imported_count: int = 0
_calibration_mode: bool = False
_qa_active: bool = False
_current_qa_paper_id: Optional[str] = None

_HEURISTIC_CODES = frozenset({"EC1", "EC3", "EC4"})
_IMPORT_DIR = Path("data/imported")
_PROCESSED_DIR = Path("data/processed")


class _FilteredPaperRepository:
    def __init__(self, inner: PaperRepository, paper_ids: set[str]) -> None:
        self._inner = inner
        self._paper_ids = paper_ids

    def get_all_papers(self) -> list[Paper]:
        return [p for p in self._inner.get_all_papers() if p.id in self._paper_ids]


class RetryLLMService(LLMService):
    def __init__(self, inner: LLMService, max_retries: int = 3):
        self._inner = inner
        self._max_retries = max_retries

    async def screen_paper(
        self,
        paper: Paper,
        criteria: list,
    ) -> ScreeningDecision:
        for attempt in range(self._max_retries):
            try:
                return await self._inner.screen_paper(paper, criteria)
            except (httpx.TimeoutException, httpx.ConnectError):
                if attempt == self._max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)
        return await self._inner.screen_paper(paper, criteria)

    async def evaluate_quality(self, paper: Paper) -> dict:
        for attempt in range(self._max_retries):
            try:
                return await self._inner.evaluate_quality(paper)
            except (httpx.TimeoutException, httpx.ConnectError):
                if attempt == self._max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)
        return await self._inner.evaluate_quality(paper)


def _get_paper_repo() -> PaperRepository:
    global _dataset_path
    if _dataset_path is None:
        raise HTTPException(status_code=400, detail="No dataset imported yet.")
    return DatasetPaperRepository(_dataset_path)


def _get_decision_repo() -> ScreeningDecisionRepository:
    db_path = os.getenv("APOLLO_DB_PATH", str(_PROCESSED_DIR / "screening.db"))
    os.makedirs(str(Path(db_path).parent), exist_ok=True)
    return SQLiteScreeningDecisionRepository(db_path)


def _get_llm_service() -> LLMService:
    base_url = os.getenv("APOLLO_LLM_BASE_URL")
    model = os.getenv("APOLLO_LLM_MODEL")
    inner = OllamaLLMService(base_url=base_url, model=model)
    return RetryLLMService(inner)


# ── POST /api/system/reset ───────────────────────────────────────────────────


@router.post("/api/system/reset")
async def system_reset():
    global _dataset_path, _screening_active, _qa_active, _current_qa_paper_id, _imported_count, _calibration_mode

    if _dataset_path is not None:
        _dataset_path.unlink(missing_ok=True)
        _dataset_path = None

    decision_repo = _get_decision_repo()
    decision_repo.clear_all()

    _screening_active = False
    _qa_active = False
    _current_qa_paper_id = None
    _imported_count = 0
    _calibration_mode = False

    return {
        "status": "success",
        "message": "Database cleared successfully.",
    }


# ── POST /api/import ────────────────────────────────────────────────────────


@router.post("/api/import")
async def import_papers(file: UploadFile = File(...)):
    global _dataset_path, _imported_count

    _IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    dest = _IMPORT_DIR / f"imported_dataset{Path(file.filename or 'dataset.xlsx').suffix}"

    with tempfile.NamedTemporaryFile(delete=False, suffix=dest.suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    shutil.move(str(tmp_path), str(dest))

    repo = DatasetPaperRepository(dest)
    try:
        papers = repo.get_all_papers()
    except Exception as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Failed to parse file: {exc}")

    _dataset_path = dest
    _imported_count = len(papers)

    return {
        "status": "success",
        "imported_count": _imported_count,
        "skipped_duplicates": 0,
    }


# ── POST /api/screening/start ───────────────────────────────────────────────


async def _run_screening_background(
    calibration_paper_ids: Optional[set[str]] = None,
    target: str = "ALL",
) -> None:
    global _screening_active
    _screening_active = True
    try:
        paper_repo = _get_paper_repo()
        if calibration_paper_ids:
            paper_repo = _FilteredPaperRepository(paper_repo, calibration_paper_ids)
        decision_repo = _get_decision_repo()
        llm_service = _get_llm_service()
        heuristic = HeuristicScreeningUseCase()
        screen = ScreenPaperUseCase(heuristic, llm_service)
        criteria = decision_repo.get_criteria_for_pipeline()
        pipeline = RunScreeningPipelineUseCase(
            paper_repository=paper_repo,
            decision_repository=decision_repo,
            screen_paper_use_case=screen,
            criteria=criteria,
        )
        await pipeline.execute(
            calibration_paper_ids=calibration_paper_ids,
            target=target,
        )
    finally:
        _screening_active = False


@router.post("/api/screening/start")
async def start_screening(
    mode: str = Query("full", pattern="^(full|calibration)$"),
    target: str = Query("ALL", pattern="^(ALL|WL|GL)$"),
):
    global _screening_active, _dataset_path, _calibration_mode

    if _dataset_path is None:
        raise HTTPException(status_code=400, detail="No dataset imported yet.")
    if _screening_active:
        raise HTTPException(status_code=409, detail="Screening is already running.")

    cal_paper_ids: Optional[set[str]] = None

    if mode == "calibration":
        paper_repo = _get_paper_repo()
        papers = paper_repo.get_all_papers()
        decision_repo = _get_decision_repo()
        decision_repo.mark_calibration_sample(papers, 100)
        cal_ids = decision_repo.get_calibration_papers()
        cal_paper_ids = set(cal_ids)
        _calibration_mode = True
    else:
        _calibration_mode = False

    asyncio.create_task(_run_screening_background(cal_paper_ids, target))
    return {"status": "started", "task_id": "screening_current"}


# ── GET /api/screening/progress ─────────────────────────────────────────────


@router.get("/api/screening/progress")
async def screening_progress():
    global _screening_active, _calibration_mode, _qa_active, _current_qa_paper_id

    if _dataset_path is None:
        return {
            "total_papers": 0,
            "screened_count": 0,
            "pending_count": 0,
            "heuristic_exclusions": 0,
            "ai_exclusions": 0,
            "duplicates_count": 0,
            "included_count": 0,
            "is_active": _screening_active,
            "in_calibration": _calibration_mode,
            "qa_active": _qa_active,
            "current_qa_paper_id": _current_qa_paper_id,
        }

    paper_repo = _get_paper_repo()
    decision_repo = _get_decision_repo()

    papers = paper_repo.get_all_papers()
    decisions = decision_repo.get_all_decisions()

    if _calibration_mode:
        cal_ids = set(decision_repo.get_calibration_papers())
        papers = [p for p in papers if p.id in cal_ids]
        decisions = [d for d in decisions if d.paper_id in cal_ids]
        total = len(cal_ids)
        screened = sum(1 for d in decisions if d.status != ScreeningStatus.NEEDS_REVIEW)
        pending = total - screened
    else:
        total = len(papers)
        screened = len(decisions)
        pending = total - screened

    heuristic_exclusions = 0
    ai_exclusions = 0
    duplicates_count = 0
    included_count = 0
    for d in decisions:
        if d.status == ScreeningStatus.NEEDS_REVIEW:
            continue
        codes = set(d.applied_criteria_codes)
        if d.status == ScreeningStatus.EXCLUDED:
            if "EC6" in codes:
                duplicates_count += 1
            elif codes & _HEURISTIC_CODES:
                heuristic_exclusions += 1
            else:
                ai_exclusions += 1
        elif d.status == ScreeningStatus.INCLUDED:
            included_count += 1

    return {
        "total_papers": total,
        "screened_count": screened,
        "pending_count": max(pending, 0),
        "heuristic_exclusions": heuristic_exclusions,
        "ai_exclusions": ai_exclusions,
        "duplicates_count": duplicates_count,
        "included_count": included_count,
        "is_active": _screening_active,
        "in_calibration": _calibration_mode,
        "qa_active": _qa_active,
        "current_qa_paper_id": _current_qa_paper_id,
    }


# ── GET /api/papers ─────────────────────────────────────────────────────────


@router.get("/api/papers")
async def list_papers(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=500),
    status: Optional[str] = Query(None, pattern="^(INCLUDED|EXCLUDED|NEEDS_REVIEW)$"),
    source_type: Optional[str] = Query(None, pattern="^(WL|GL)$"),
    search: Optional[str] = Query(None),
    title_contains: Optional[str] = Query(None),
    abstract_contains: Optional[str] = Query(None),
    year_from: Optional[int] = Query(None, ge=1900, le=2100),
    year_to: Optional[int] = Query(None, ge=1900, le=2100),
):
    paper_repo = _get_paper_repo()
    decision_repo = _get_decision_repo()

    papers = paper_repo.get_filtered_papers(
        search=search,
        title_contains=title_contains,
        abstract_contains=abstract_contains,
        year_from=year_from,
        year_to=year_to,
    )
    decisions = decision_repo.get_all_decisions()
    decision_map = {d.paper_id: d for d in decisions}
    human_map = decision_repo.get_human_decision_map()
    quality_map = decision_repo.get_quality_map()

    results = []
    for p in papers:
        if source_type is not None and p.source_type.value != source_type:
            continue
        d = decision_map.get(p.id)
        merged_status = d.status.value if d else None
        if status is not None and merged_status != status:
            continue
        results.append({
            "id": p.id,
            "title": p.title,
            "abstract": p.abstract,
            "source_library": p.metadata.get("Detected_Source") or p.metadata.get("Library") or "Unknown",
            "source_type": p.source_type.value,
            "publication_year": p.publication_year,
            "url": p.url,
            "status": merged_status,
            "rationale": d.rationale if d else None,
            "confidence_score": d.confidence_score if d else None,
            "applied_criteria_codes": d.applied_criteria_codes if d else [],
            "human_decision": human_map.get(p.id),
            **quality_map.get(p.id, {}),
        })

    total = len(results)
    start = (page - 1) * size
    end = start + size
    page_results = results[start:end]

    return {
        "page": page,
        "size": size,
        "total": total,
        "total_pages": (total + size - 1) // size if total > 0 else 1,
        "items": page_results,
    }


# ── POST /api/papers/bulk-audit ──────────────────────────────────────────────


@router.post("/api/papers/bulk-audit")
async def bulk_audit_papers(body: BulkAuditBody):
    if body.verdict not in ("YES", "NO", "RESET", "CLEAR"):
        raise HTTPException(status_code=422, detail="Verdict must be 'YES', 'NO', 'RESET', or 'CLEAR'.")
    if not body.paper_ids:
        raise HTTPException(status_code=422, detail="paper_ids must be a non-empty list.")
    decision_repo = _get_decision_repo()
    if body.verdict in ("RESET", "CLEAR"):
        decision_repo.delete_decisions(body.paper_ids)
        return {"status": "success", "count": len(body.paper_ids)}
    decision_repo.save_bulk_audit(body.paper_ids, body.verdict)
    return {"status": "success", "count": len(body.paper_ids)}


# ── GET /api/export ─────────────────────────────────────────────────────────


@router.get("/api/export")
async def export_results():
    paper_repo = _get_paper_repo()
    decision_repo = _get_decision_repo()

    out_dir = _PROCESSED_DIR / "export"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "APOLLO_Screening_Results.xlsx"

    use_case = ExportScreenedPapersUseCase(
        paper_repository=paper_repo,
        decision_repository=decision_repo,
    )
    use_case.execute(str(out_path))

    return FileResponse(
        path=str(out_path),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="APOLLO_Screening_Results.xlsx",
    )


# ── Audit models ─────────────────────────────────────────────────────────────


class AuditVerdict(BaseModel):
    verdict: str


class BulkAuditBody(BaseModel):
    paper_ids: list[str]
    verdict: str


class QualityAssessmentBody(BaseModel):
    q1: float
    q2: float
    q3: float
    q4: float


# ── GET /api/calibration/papers ──────────────────────────────────────────────


@router.get("/api/calibration/papers")
async def list_calibration_papers():
    if _dataset_path is None:
        raise HTTPException(status_code=400, detail="No dataset imported yet.")

    decision_repo = _get_decision_repo()
    cal_ids = set(decision_repo.get_calibration_papers())

    if not cal_ids:
        return {"total": 0, "items": []}

    paper_repo = _get_paper_repo()
    all_papers = paper_repo.get_all_papers()

    # Strictly filter to active calibration IDs only
    calibration_papers = [p for p in all_papers if p.id in cal_ids]

    decision_map = {d.paper_id: d for d in decision_repo.get_all_decisions()}
    human_map = decision_repo.get_human_decision_map()

    items = []
    for p in calibration_papers:
        d = decision_map.get(p.id)
        items.append({
            "paper_id": p.id,
            "title": p.title,
            "abstract": p.abstract,
            "source_type": p.source_type.value,
            "ai_decision": (
                "YES" if d and d.status == ScreeningStatus.INCLUDED
                else "NO" if d and d.status == ScreeningStatus.EXCLUDED
                else "NEEDS_REVIEW"
            ) if d else "PENDING",
            "ai_rationale": d.rationale if d else None,
            "applied_criteria_codes": d.applied_criteria_codes if d else [],
            "human_decision": human_map.get(p.id),
        })

    items.sort(key=lambda x: x["paper_id"])
    return {"total": len(items), "items": items}


# ── GET /api/audit/sample ────────────────────────────────────────────────────


@router.get("/api/audit/sample")
async def audit_sample(
    size: int = Query(100, ge=1, le=1000),
):
    if _dataset_path is None:
        raise HTTPException(status_code=400, detail="No dataset imported yet.")

    decision_repo = _get_decision_repo()
    decisions = decision_repo.get_all_decisions()
    if not decisions:
        raise HTTPException(status_code=400, detail="No screened papers available for audit.")

    strata: dict[str, list[ScreeningDecision]] = {
        "INCLUDED": [],
        "EXCLUDED": [],
        "NEEDS_REVIEW": [],
    }
    for d in decisions:
        strata[d.status.value].append(d)

    total = len(decisions)
    sampled: list[ScreeningDecision] = []
    for status_key, group in strata.items():
        if not group:
            continue
        proportion = len(group) / total
        stratum_size = max(1, round(proportion * size))
        stratum_size = min(stratum_size, len(group))
        sampled.extend(random.sample(group, stratum_size))

    if len(sampled) > size:
        sampled = random.sample(sampled, size)

    # Shuffle so strata don't appear in blocks
    random.shuffle(sampled)

    paper_repo = _get_paper_repo()
    paper_map = {p.id: p for p in paper_repo.get_all_papers()}

    items = []
    for d in sampled:
        p = paper_map.get(d.paper_id)
        ai_decision = (
            "YES"
            if d.status == ScreeningStatus.INCLUDED
            else "NO"
            if d.status == ScreeningStatus.EXCLUDED
            else "NEEDS_REVIEW"
        )
        items.append({
            "paper_id": d.paper_id,
            "title": p.title if p else "?",
            "abstract": p.abstract if p else "",
            "ai_decision": ai_decision,
            "ai_rationale": d.rationale,
            "applied_criteria_codes": d.applied_criteria_codes,
            "source_library": (
                p.metadata.get("Detected_Source")
                or p.metadata.get("Library")
                or "Unknown"
            )
            if p
            else "?",
        })

    return {"total_screened": total, "sample_size": len(items), "items": items}


# ── POST /api/papers/{paper_id}/audit ────────────────────────────────────────


@router.post("/api/papers/{paper_id}/audit")
async def audit_paper(paper_id: str, body: AuditVerdict):
    if body.verdict not in ("YES", "NO"):
        raise HTTPException(status_code=422, detail="Verdict must be 'YES' or 'NO'.")

    decision_repo = _get_decision_repo()
    existing = decision_repo.get_decision(paper_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Decision not found for this paper.")

    decision_repo.save_audit(paper_id, body.verdict)
    return {"status": "saved", "paper_id": paper_id}


# ── POST /api/papers/{paper_id}/quality ────────────────────────────────────────


@router.post("/api/papers/{paper_id}/quality")
async def quality_assessment(paper_id: str, body: QualityAssessmentBody):
    decision_repo = _get_decision_repo()
    existing = decision_repo.get_decision(paper_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Decision not found for this paper.")
    paper_repo = _get_paper_repo()
    paper = next((p for p in paper_repo.get_all_papers() if p.id == paper_id), None)
    source_type = paper.source_type.value if paper else "GL"
    score = decision_repo.save_quality_assessment(paper_id, body.q1, body.q2, body.q3, body.q4, source_type=source_type)
    return {"status": "success", "score": score}


# ── POST /api/quality/assess-all ──────────────────────────────────────────────


async def _quality_assessment_background() -> None:
    global _qa_active, _current_qa_paper_id
    _qa_active = True
    _current_qa_paper_id = None
    try:
        paper_repo = _get_paper_repo()
        decision_repo = _get_decision_repo()
        llm_service = _get_llm_service()

        papers = paper_repo.get_all_papers()
        paper_map = {p.id: p for p in papers}
        decisions = decision_repo.get_all_decisions()

        included_papers: list[Paper] = []
        for d in decisions:
            if d.status == ScreeningStatus.INCLUDED:
                p = paper_map.get(d.paper_id)
                if p is not None:
                    included_papers.append(p)

        papers_sorted = sorted(included_papers, key=lambda p: int(p.id) if p.id.isdigit() else p.id)

        for paper in papers_sorted:
            _current_qa_paper_id = paper.id
            if paper.source_type.value == "WL":
                doi = None
                for k, v in paper.metadata.items():
                    if k.lower() == "doi":
                        doi = v
                        break
                if doi:
                    try:
                        pdf_result = await fetch_pdf_metadata_by_doi(doi)
                        if pdf_result is not None:
                            decision_repo.save_pdf_metadata(
                                paper.id, pdf_result["full_text"], pdf_result["pdf_url"]
                            )
                    except Exception:
                        logger.exception("PDF fetch failed for paper %s", paper.id)
            try:
                result = await llm_service.evaluate_quality(paper)
                decision_repo.save_quality_assessment(
                    paper.id,
                    result["q1"],
                    result["q2"],
                    result["q3"],
                    result["q4"],
                    source_type=paper.source_type.value,
                )
            except Exception:
                logger.exception("Quality assessment failed for paper %s", paper.id)
    finally:
        _qa_active = False
        _current_qa_paper_id = None


@router.post("/api/quality/assess-all")
async def assess_all_quality():
    if _dataset_path is None:
        raise HTTPException(status_code=400, detail="No dataset imported yet.")
    asyncio.create_task(_quality_assessment_background())
    return {"status": "started", "task_id": "quality_assessment"}


# ── GET /api/audit/metrics ────────────────────────────────────────────────────


@router.get("/api/audit/metrics")
async def audit_metrics():
    decision_repo = _get_decision_repo()

    # Prioritise calibration audited papers
    audited = decision_repo.get_all_audited(calibration_only=True)
    calibration_used = bool(audited)

    if not audited:
        audited = decision_repo.get_all_audited()

    if not audited:
        return {
            "total_audited": 0,
            "confusion_matrix": {"tp": 0, "tn": 0, "fp": 0, "fn": 0},
            "precision": 0.0,
            "recall": 0.0,
            "f1_score": 0.0,
            "cohens_kappa": 0.0,
            "interpretation": "No audited samples available.",
            "quality_stats": {"avg_score": 0.0, "count": 0},
        }

    ai_decisions: list[str] = []
    human_decisions: list[str] = []
    for row in audited:
        if row["human_decision"] is None:
            continue
        if row["status"] == ScreeningStatus.NEEDS_REVIEW:
            continue
        ai = "YES" if row["status"] == ScreeningStatus.INCLUDED else "NO"
        ai_decisions.append(ai)
        human_decisions.append(row["human_decision"])

    if not ai_decisions:
        return {
            "total_audited": len(audited),
            "confusion_matrix": {"tp": 0, "tn": 0, "fp": 0, "fn": 0},
            "precision": 0.0,
            "recall": 0.0,
            "f1_score": 0.0,
            "cohens_kappa": 0.0,
            "interpretation": "No audited samples with human decisions available.",
            "quality_stats": {"avg_score": 0.0, "count": 0},
        }

    # Aggregate quality scores
    quality_map = decision_repo.get_quality_map()
    quality_scores = [qm["quality_score"] for qm in quality_map.values() if qm.get("quality_score") is not None]
    avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0

    metrics = compute_metrics(ai_decisions, human_decisions)
    result = metrics_to_dict(metrics)
    result["calibration_used"] = calibration_used
    result["quality_stats"] = {
        "avg_score": round(avg_quality, 2),
        "count": len(quality_scores),
    }
    return result


# ── GET /api/criteria ─────────────────────────────────────────────────────────


@router.get("/api/criteria")
async def list_criteria():
    decision_repo = _get_decision_repo()
    return {"items": decision_repo.get_all_criteria()}


# ── PUT /api/criteria/{criterion_id} ──────────────────────────────────────────


class UpdateCriterionBody(BaseModel):
    title: str
    description: str


@router.put("/api/criteria/{criterion_id}")
async def update_criterion(criterion_id: str, body: UpdateCriterionBody):
    decision_repo = _get_decision_repo()
    decision_repo.update_criterion(criterion_id, body.title, body.description)
    return {"status": "updated", "id": criterion_id}
