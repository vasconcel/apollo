"""
APOLLO Evaluation: Dataset Versioning

Tracks benchmark dataset provenance, checksums, and metadata
to prevent silent benchmark drift across experimental runs.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import csv
import hashlib
import json
import os


def compute_dataset_checksum(path: str) -> str:
    """Compute SHA-256 checksum of dataset file content."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()[:32]


def compute_dataset_row_checksum(items: List[Dict]) -> str:
    """Compute checksum from list of dict items (sorted by article_id)."""
    sorted_items = sorted(items, key=lambda x: x.get("article_id", ""))
    content = json.dumps(sorted_items, sort_keys=True, default=str)
    return hashlib.sha256(content.encode()).hexdigest()[:32]


@dataclass
class DatasetMetadata:
    name: str
    path: str
    stage: str
    protocol_version: str
    checksum: str
    row_count: int
    description: str = ""
    created_at: str = ""
    source: str = ""
    gold_decision_distribution: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "path": self.path,
            "stage": self.stage,
            "protocol_version": self.protocol_version,
            "checksum": self.checksum,
            "row_count": self.row_count,
            "description": self.description,
            "created_at": self.created_at,
            "source": self.source,
            "gold_decision_distribution": self.gold_decision_distribution,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "DatasetMetadata":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class DatasetRegistry:
    """Simple registry of known datasets with their checksums."""
    entries: Dict[str, DatasetMetadata] = field(default_factory=dict)
    registry_path: str = "data/evaluation/dataset_registry.json"

    def register(self, metadata: DatasetMetadata):
        self.entries[metadata.checksum] = metadata

    def lookup(self, checksum: str) -> Optional[DatasetMetadata]:
        return self.entries.get(checksum)

    def has_checksum(self, checksum: str) -> bool:
        return checksum in self.entries

    def has_path(self, path: str) -> bool:
        return any(m.path == path for m in self.entries.values())

    def get_by_name(self, name: str) -> Optional[DatasetMetadata]:
        for m in self.entries.values():
            if m.name == name:
                return m
        return None

    def save(self):
        os.makedirs(os.path.dirname(self.registry_path), exist_ok=True)
        data = {k: v.to_dict() for k, v in self.entries.items()}
        with open(self.registry_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    @classmethod
    def load(cls, registry_path: str = "data/evaluation/dataset_registry.json") -> "DatasetRegistry":
        registry = cls(registry_path=registry_path)
        if os.path.exists(registry_path):
            with open(registry_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for checksum, item in data.items():
                registry.entries[checksum] = DatasetMetadata.from_dict(item)
        return registry

    def get_decision_distribution(self, dataset) -> Dict[str, int]:
        """Compute gold decision distribution from a BenchmarkDataset."""
        dist: Dict[str, int] = {}
        for item in dataset.items:
            d = item.gold_decision.upper().strip()
            dist[d] = dist.get(d, 0) + 1
        return dist


def analyze_dataset(path: str, name: str = "", stage: str = "ec", protocol_version: str = "1.0") -> DatasetMetadata:
    """Analyze a dataset file and return metadata with checksum."""
    from src.evaluation.benchmark import BenchmarkLoader
    if not os.path.exists(path):
        raise FileNotFoundError(f"Dataset not found: {path}")
    if path.endswith(".csv"):
        dataset = BenchmarkLoader.load_csv(path, name=name, stage=stage)
    elif path.endswith(".json"):
        dataset = BenchmarkLoader.load_json(path, name=name, stage=stage)
    else:
        raise ValueError(f"Unsupported dataset format: {path}")
    checksum = compute_dataset_checksum(path)
    dist: Dict[str, int] = {}
    for item in dataset.items:
        d = item.gold_decision.upper().strip()
        dist[d] = dist.get(d, 0) + 1
    import time
    base = os.path.basename(path)
    return DatasetMetadata(
        name=name or os.path.splitext(base)[0],
        path=path,
        stage=stage,
        protocol_version=protocol_version,
        checksum=checksum,
        row_count=len(dataset.items),
        description=f"Auto-analyzed dataset: {base}",
        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        source=path,
        gold_decision_distribution=dist,
    )


def verify_dataset_integrity(path: str, expected_checksum: str) -> bool:
    """Verify dataset file integrity against expected checksum."""
    actual = compute_dataset_checksum(path)
    return actual == expected_checksum
