"""
APOLLO Evaluation: Experiment Session Management

Provides experiment UUID, timestamp, protocol metadata, config snapshots,
git hash capture, and full experiment manifests for scientific reproducibility.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional
import json
import os
import subprocess
import time
import uuid


def capture_git_hash() -> str:
    """Capture current git commit hash. Returns empty string if not available."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        if result.returncode == 0:
            return result.stdout.strip()[:40]
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        pass
    return ""


def capture_git_diff() -> str:
    """Capture git diff for uncommitted changes. Returns empty string if not available."""
    try:
        result = subprocess.run(
            ["git", "diff", "--stat"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        pass
    return ""


def generate_experiment_id() -> str:
    return str(uuid.uuid4())


@dataclass
class ExperimentManifest:
    experiment_id: str
    session_id: str
    experiment_name: str
    created_at: str
    git_commit_hash: str
    git_diff_summary: str
    protocol_version: str
    stage: str
    dataset_path: str
    dataset_checksum: str
    dataset_row_count: int
    threshold_config: Dict[str, Any]
    model_config: Dict[str, Any]
    seed: int
    tags: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class SessionManifest:
    experiment_id: str
    session_id: str
    experiment_name: str
    created_at: str
    git_commit_hash: str
    git_diff_summary: str
    config: Dict[str, Any]
    protocol_version: str
    stage: str
    dataset_info: Dict[str, Any]
    output_dir: str

    def to_dict(self) -> Dict:
        return asdict(self)


class ExperimentSession:
    """Manages a single experiment session with full reproducibility metadata."""

    def __init__(
        self,
        experiment_name: str = "experiment",
        protocol_version: str = "1.0",
        stage: str = "ec",
        seed: int = 42,
        output_dir: str = "data/evaluation/reports/",
        tags: Optional[Dict[str, str]] = None,
    ):
        self.experiment_id = generate_experiment_id()
        self.session_id = generate_experiment_id()
        self.experiment_name = experiment_name
        self.created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.git_commit_hash = capture_git_hash()
        self.git_diff_summary = capture_git_diff()
        self.protocol_version = protocol_version
        self.stage = stage
        self.seed = seed
        self.output_dir = output_dir
        self.tags = tags or {}

    def to_manifest(self, config: Dict[str, Any]) -> SessionManifest:
        return SessionManifest(
            experiment_id=self.experiment_id,
            session_id=self.session_id,
            experiment_name=self.experiment_name,
            created_at=self.created_at,
            git_commit_hash=self.git_commit_hash,
            git_diff_summary=self.git_diff_summary,
            config=config,
            protocol_version=self.protocol_version,
            stage=self.stage,
            dataset_info={},
            output_dir=self.output_dir,
        )

    def to_experiment_manifest(
        self,
        dataset_path: str = "",
        dataset_checksum: str = "",
        dataset_row_count: int = 0,
        threshold_config: Optional[Dict[str, Any]] = None,
        model_config: Optional[Dict[str, Any]] = None,
    ) -> ExperimentManifest:
        return ExperimentManifest(
            experiment_id=self.experiment_id,
            session_id=self.session_id,
            experiment_name=self.experiment_name,
            created_at=self.created_at,
            git_commit_hash=self.git_commit_hash,
            git_diff_summary=self.git_diff_summary,
            protocol_version=self.protocol_version,
            stage=self.stage,
            dataset_path=dataset_path,
            dataset_checksum=dataset_checksum,
            dataset_row_count=dataset_row_count,
            threshold_config=threshold_config or {},
            model_config=model_config or {},
            seed=self.seed,
        )

    def save_manifest(self, manifest: SessionManifest) -> str:
        os.makedirs(self.output_dir, exist_ok=True)
        path = os.path.join(
            self.output_dir,
            f"{self.experiment_name}_{self.session_id[:8]}_manifest.json",
        )
        with open(path, "w", encoding="utf-8") as f:
            json.dump(manifest.to_dict(), f, indent=2, default=str)
        return path

    @property
    def experiment_dir(self) -> str:
        safe_name = self.experiment_name.replace(" ", "_")
        return os.path.join(
            self.output_dir,
            f"{safe_name}_{self.session_id[:8]}",
        )
