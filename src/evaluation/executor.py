"""
APOLLO Evaluation: Batch Advisory Execution Engine

Scalable advisory execution with configurable batch size, retry policy,
rate-limit handling, checkpointing, and crash recovery.
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Any
import json
import os
import time


@dataclass
class ExecutionProgress:
    total: int = 0
    completed: int = 0
    failed: int = 0
    skipped: int = 0
    current_index: int = 0
    started_at: float = 0.0
    last_updated: float = 0.0

    @property
    def progress_pct(self) -> float:
        return self.completed / self.total if self.total > 0 else 0.0

    @property
    def elapsed_seconds(self) -> float:
        if self.started_at == 0:
            return 0.0
        return time.time() - self.started_at

    def to_dict(self) -> Dict:
        return {
            "total": self.total,
            "completed": self.completed,
            "failed": self.failed,
            "skipped": self.skipped,
            "current_index": self.current_index,
            "progress_pct": self.progress_pct,
            "elapsed_seconds": self.elapsed_seconds,
            "started_at": self.started_at,
            "last_updated": self.last_updated,
        }


@dataclass
class CheckpointState:
    experiment_name: str
    session_id: str
    stage: str
    progress: Dict
    completed_ids: List[str]
    failed_ids: List[str]
    timestamp: str = ""

    def to_dict(self) -> Dict:
        return {
            "experiment_name": self.experiment_name,
            "session_id": self.session_id,
            "stage": self.stage,
            "progress": self.progress,
            "completed_ids": self.completed_ids,
            "failed_ids": self.failed_ids,
            "timestamp": self.timestamp,
        }


BATCH_SIZE_DEFAULT = 5
MAX_RETRIES_DEFAULT = 3
RATE_LIMIT_SLEEP_DEFAULT = 3.0


class BatchExecutor:
    """Executes advisory generation for a list of articles with resilience."""

    def __init__(
        self,
        batch_size: int = BATCH_SIZE_DEFAULT,
        max_retries: int = MAX_RETRIES_DEFAULT,
        rate_limit_sleep: float = RATE_LIMIT_SLEEP_DEFAULT,
        checkpoint_dir: str = "data/evaluation/checkpoints/",
        progress_callback: Optional[Callable] = None,
    ):
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.rate_limit_sleep = rate_limit_sleep
        self.checkpoint_dir = checkpoint_dir
        self.progress_callback = progress_callback
        self.progress = ExecutionProgress()

    def execute_batch(
        self,
        articles: List[Dict],
        generate_fn: Callable[[Dict], Any],
        experiment_name: str = "experiment",
        session_id: str = "",
        stage: str = "ec",
        checkpoint: bool = True,
        skip_existing: bool = False,
        existing_ids: Optional[List[str]] = None,
    ) -> List[Dict]:
        existing_ids = existing_ids or []
        self.progress = ExecutionProgress(
            total=len(articles),
            started_at=time.time(),
            last_updated=time.time(),
        )
        results: List[Dict] = []
        total = len(articles)
        for idx, article in enumerate(articles):
            self.progress.current_index = idx
            article_id = article.get("article_id", str(idx))
            if skip_existing and article_id in existing_ids:
                self.progress.skipped += 1
                self.progress.last_updated = time.time()
                if self.progress_callback:
                    self.progress_callback(self.progress)
                continue
            last_error = None
            result = None
            for attempt in range(self.max_retries + 1):
                try:
                    result = generate_fn(article)
                    if result is not None:
                        break
                except Exception as e:
                    last_error = str(e)
                    if "429" in str(e) or "rate" in str(e).lower():
                        sleep_time = self.rate_limit_sleep * (attempt + 1)
                        time.sleep(sleep_time)
                    elif attempt < self.max_retries:
                        time.sleep(1.0 * (attempt + 1))
                    continue
            if result is not None:
                self.progress.completed += 1
                results.append(result)
            else:
                self.progress.failed += 1
                results.append({
                    "article_id": article_id,
                    "error": last_error or "execution_failed",
                    "decision": "UNAVAILABLE",
                    "confidence": 0.0,
                })
            self.progress.last_updated = time.time()
            if self.progress_callback:
                self.progress_callback(self.progress)
            if checkpoint and (idx + 1) % max(1, self.batch_size) == 0:
                self._save_checkpoint(
                    experiment_name, session_id, stage,
                    [r.get("article_id", "") for r in results if r.get("error") is None],
                    [r.get("article_id", "") for r in results if r.get("error") is not None],
                )
        return results

    def _save_checkpoint(
        self,
        experiment_name: str,
        session_id: str,
        stage: str,
        completed_ids: List[str],
        failed_ids: List[str],
    ):
        os.makedirs(self.checkpoint_dir, exist_ok=True)
        ckpt = CheckpointState(
            experiment_name=experiment_name,
            session_id=session_id,
            stage=stage,
            progress=self.progress.to_dict(),
            completed_ids=completed_ids,
            failed_ids=failed_ids,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )
        path = os.path.join(
            self.checkpoint_dir,
            f"{experiment_name}_{session_id[:8]}_checkpoint.json",
        )
        with open(path, "w", encoding="utf-8") as f:
            json.dump(ckpt.to_dict(), f, indent=2)

    def load_checkpoint(
        self,
        experiment_name: str,
        session_id: str,
    ) -> Optional[CheckpointState]:
        path = os.path.join(
            self.checkpoint_dir,
            f"{experiment_name}_{session_id[:8]}_checkpoint.json",
        )
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return CheckpointState(**{
            k: v for k, v in data.items()
            if k in CheckpointState.__dataclass_fields__
        })

    def get_completed_ids(
        self,
        experiment_name: str,
        session_id: str,
    ) -> List[str]:
        ckpt = self.load_checkpoint(experiment_name, session_id)
        return ckpt.completed_ids if ckpt else []

    def get_failed_ids(
        self,
        experiment_name: str,
        session_id: str,
    ) -> List[str]:
        ckpt = self.load_checkpoint(experiment_name, session_id)
        return ckpt.failed_ids if ckpt else []
