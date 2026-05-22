"""
APOLLO Evaluation: Replayable Artifact Persistence

Stores raw prompts, raw LLM responses, parsed advisories, routing decisions,
calibration outputs, and telemetry snapshots for complete auditability.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import json
import os
import time


@dataclass
class ArticleArtifact:
    article_id: str
    title: str
    abstract: str
    stage: str
    protocol_version: str
    raw_prompt: str = ""
    raw_llm_response: str = ""
    parsed_advisory: Optional[Dict] = None
    routing_decision: str = ""
    gold_decision: str = ""
    is_correct: Optional[bool] = None
    generation_duration_ms: Optional[float] = None
    error: Optional[str] = None
    timestamp: str = ""

    def to_dict(self) -> Dict:
        return {
            "article_id": self.article_id,
            "title": self.title,
            "abstract": self.abstract,
            "stage": self.stage,
            "protocol_version": self.protocol_version,
            "raw_prompt": self.raw_prompt,
            "raw_llm_response": self.raw_llm_response,
            "parsed_advisory": self.parsed_advisory,
            "routing_decision": self.routing_decision,
            "gold_decision": self.gold_decision,
            "is_correct": self.is_correct,
            "generation_duration_ms": self.generation_duration_ms,
            "error": self.error,
            "timestamp": self.timestamp,
        }


@dataclass
class ArtifactManifest:
    experiment_id: str
    session_id: str
    experiment_name: str
    total_articles: int
    artifacts_stored: int
    storage_path: str
    created_at: str

    def to_dict(self) -> Dict:
        return {
            "experiment_id": self.experiment_id,
            "session_id": self.session_id,
            "experiment_name": self.experiment_name,
            "total_articles": self.total_articles,
            "artifacts_stored": self.artifacts_stored,
            "storage_path": self.storage_path,
            "created_at": self.created_at,
        }


class ArtifactStore:
    """Persists all experiment artifacts for replay and audit."""

    def __init__(self, base_path: str = "data/evaluation/artifacts/"):
        self.base_path = base_path

    def _experiment_path(self, experiment_name: str, session_id: str) -> str:
        safe = experiment_name.replace(" ", "_")
        return os.path.join(self.base_path, f"{safe}_{session_id[:8]}")

    def store_article_artifact(
        self,
        artifact: ArticleArtifact,
        experiment_name: str,
        session_id: str,
    ) -> str:
        exp_path = self._experiment_path(experiment_name, session_id)
        os.makedirs(exp_path, exist_ok=True)
        path = os.path.join(exp_path, f"{artifact.article_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(artifact.to_dict(), f, indent=2, default=str)
        return path

    def store_article_artifact_batch(
        self,
        artifacts: List[ArticleArtifact],
        experiment_name: str,
        session_id: str,
    ) -> List[str]:
        paths = []
        for art in artifacts:
            path = self.store_article_artifact(art, experiment_name, session_id)
            paths.append(path)
        return paths

    def store_combined_artifacts(
        self,
        artifacts: List[ArticleArtifact],
        experiment_name: str,
        session_id: str,
    ) -> str:
        exp_path = self._experiment_path(experiment_name, session_id)
        os.makedirs(exp_path, exist_ok=True)
        data = [a.to_dict() for a in artifacts]
        path = os.path.join(exp_path, "all_artifacts.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        return path

    def store_raw_prompts(
        self,
        prompts: Dict[str, str],
        experiment_name: str,
        session_id: str,
    ) -> str:
        exp_path = self._experiment_path(experiment_name, session_id)
        os.makedirs(exp_path, exist_ok=True)
        path = os.path.join(exp_path, "raw_prompts.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(prompts, f, indent=2)
        return path

    def store_artifact_manifest(
        self,
        manifest: ArtifactManifest,
    ) -> str:
        exp_path = self._experiment_path(
            manifest.experiment_name, manifest.session_id
        )
        os.makedirs(exp_path, exist_ok=True)
        path = os.path.join(exp_path, "artifact_manifest.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(manifest.to_dict(), f, indent=2)
        return path

    def load_article_artifact(self, path: str) -> Optional[ArticleArtifact]:
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return ArticleArtifact(**{
            k: v for k, v in data.items()
            if k in ArticleArtifact.__dataclass_fields__
        })

    def load_all_artifacts(self, experiment_name: str, session_id: str) -> List[ArticleArtifact]:
        exp_path = self._experiment_path(experiment_name, session_id)
        combined = os.path.join(exp_path, "all_artifacts.json")
        if os.path.exists(combined):
            with open(combined, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [ArticleArtifact(**{k: v for k, v in item.items()
                                        if k in ArticleArtifact.__dataclass_fields__})
                    for item in data]
        artifacts = []
        if not os.path.isdir(exp_path):
            return artifacts
        for fname in sorted(os.listdir(exp_path)):
            if fname.endswith(".json") and fname != "all_artifacts.json" and fname != "artifact_manifest.json" and fname != "raw_prompts.json":
                path = os.path.join(exp_path, fname)
                art = self.load_article_artifact(path)
                if art:
                    artifacts.append(art)
        return artifacts


class ReplayLoader:
    """Loads stored artifacts for replaying previous experiments."""

    @staticmethod
    def load_artifacts(experiment_name: str, session_id: str) -> List[ArticleArtifact]:
        store = ArtifactStore()
        return store.load_all_artifacts(experiment_name, session_id)

    @staticmethod
    def load_comparison_records(
        artifacts: List[ArticleArtifact],
    ) -> List[Dict]:
        records = []
        for art in artifacts:
            if art.parsed_advisory:
                records.append({
                    "article_id": art.article_id,
                    "title": art.title,
                    "abstract": art.abstract,
                    "apollo_decision": art.parsed_advisory.get("decision", ""),
                    "gold_decision": art.gold_decision,
                    "confidence": art.parsed_advisory.get("confidence", 0.0),
                    "apollo_routing": art.routing_decision,
                    "justification": art.parsed_advisory.get("justification", ""),
                    "grounding_evidence": art.parsed_advisory.get("grounding_evidence", []),
                    "triggered_criteria": art.parsed_advisory.get("triggered_criteria", []),
                })
        return records
