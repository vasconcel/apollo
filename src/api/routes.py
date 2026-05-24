import asyncio
import os
import random
import shutil
import tempfile
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.domain.criteria_config import DEFAULT_CRITERIA
from src.domain.enums import ScreeningStatus
from src.domain.interfaces import LLMService, PaperRepository, ScreeningDecisionRepository
from src.domain.metrics import compute_metrics, metrics_to_dict
from src.domain.models import Paper, ScreeningDecision
from src.infrastructure.repositories.dataset_repository import DatasetPaperRepository
from src.infrastructure.repositories.sqlite_repository import SQLiteScreeningDecisionRepository
from src.infrastructure.services.ollama_service import OllamaLLMService
from src.use_cases.export_papers import ExportScreenedPapersUseCase
from src.use_cases.heuristic_screening import HeuristicScreeningUseCase
from src.use_cases.run_screening_pipeline import RunScreeningPipelineUseCase
from src.use_cases.screen_paper import ScreenPaperUseCase

router = APIRouter()

_dataset_path: Optional[Path] = None
_screening_active: bool = False
_imported_count: int = 0

_HEURISTIC_CODES = frozenset({"EC1", "EC3", "EC4"})
_IMPORT_DIR = Path("data/imported")
_PROCESSED_DIR = Path("data/processed")


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


async def _run_screening_background() -> None:
    global _screening_active
    _screening_active = True
    try:
        paper_repo = _get_paper_repo()
        decision_repo = _get_decision_repo()
        llm_service = _get_llm_service()
        heuristic = HeuristicScreeningUseCase()
        screen = ScreenPaperUseCase(heuristic, llm_service)
        pipeline = RunScreeningPipelineUseCase(
            paper_repository=paper_repo,
            decision_repository=decision_repo,
            screen_paper_use_case=screen,
            criteria=DEFAULT_CRITERIA,
        )
        await pipeline.execute()
    finally:
        _screening_active = False


@router.post("/api/screening/start")
async def start_screening(background_tasks: BackgroundTasks):
    global _screening_active, _dataset_path

    if _dataset_path is None:
        raise HTTPException(status_code=400, detail="No dataset imported yet.")
    if _screening_active:
        raise HTTPException(status_code=409, detail="Screening is already running.")

    asyncio.create_task(_run_screening_background())
    return {"status": "started", "task_id": "screening_current"}


# ── GET /api/screening/progress ─────────────────────────────────────────────


@router.get("/api/screening/progress")
async def screening_progress():
    global _screening_active

    if _dataset_path is None:
        return {
            "total_papers": 0,
            "screened_count": 0,
            "pending_count": 0,
            "heuristic_exclusions": 0,
            "ai_exclusions": 0,
            "is_active": _screening_active,
        }

    paper_repo = _get_paper_repo()
    decision_repo = _get_decision_repo()

    papers = paper_repo.get_all_papers()
    decisions = decision_repo.get_all_decisions()

    total = len(papers)
    screened = len(decisions)
    pending = total - screened

    heuristic_exclusions = 0
    ai_exclusions = 0
    for d in decisions:
        if d.status == ScreeningStatus.EXCLUDED:
            codes = set(d.applied_criteria_codes)
            if codes & _HEURISTIC_CODES:
                heuristic_exclusions += 1
            else:
                ai_exclusions += 1

    return {
        "total_papers": total,
        "screened_count": screened,
        "pending_count": max(pending, 0),
        "heuristic_exclusions": heuristic_exclusions,
        "ai_exclusions": ai_exclusions,
        "is_active": _screening_active,
    }


# ── GET /api/papers ─────────────────────────────────────────────────────────


@router.get("/api/papers")
async def list_papers(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=500),
    status: Optional[str] = Query(None, pattern="^(INCLUDED|EXCLUDED|NEEDS_REVIEW)$"),
    source_type: Optional[str] = Query(None, pattern="^(WL|GL)$"),
):
    paper_repo = _get_paper_repo()
    decision_repo = _get_decision_repo()

    papers = paper_repo.get_all_papers()
    decisions = decision_repo.get_all_decisions()
    decision_map = {d.paper_id: d for d in decisions}

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


# ── GET /api/audit/metrics ────────────────────────────────────────────────────


@router.get("/api/audit/metrics")
async def audit_metrics():
    decision_repo = _get_decision_repo()
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
        }

    metrics = compute_metrics(ai_decisions, human_decisions)
    return metrics_to_dict(metrics)
