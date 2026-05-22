"""
APOLLO Evaluation: Experimental Reproducibility Framework

Ensures experiments are reproducible through deterministic seeds,
versioned config snapshots, and protocol-aware experiment tracking.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
import copy
import hashlib
import json
import os
import random as _random
import time


def _compute_checksum(data: Dict) -> str:
    content = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class ExperimentConfig:
    name: str = "default_experiment"
    description: str = ""
    seed: int = 42
    protocol_version: str = "1.0"
    stage: str = "ec"
    dataset_path: str = ""
    dataset_name: str = "benchmark"
    threshold_config: Dict[str, Any] = field(default_factory=lambda: {
        "confidence_min": 0.95,
        "grounding_strength_min": 0.80,
        "evidence_strength_min": 0.60,
        "uncertainty_max": 0.20,
        "require_triggered_criteria": True,
    })
    scenarios: List[str] = field(default_factory=lambda: [
        "ultra_conservative", "conservative", "balanced", "aggressive",
    ])
    telemetry_enabled: bool = True
    output_dir: str = "data/evaluation/reports/"
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def checksum(self) -> str:
        return _compute_checksum(asdict(self))

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "ExperimentConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ExperimentResult:
    config_checksum: str
    config: ExperimentConfig
    evaluation_metrics: Optional[Dict] = None
    threshold_evaluations: Optional[List[Dict]] = None
    simulation_results: Optional[List[Dict]] = None
    error_analysis: Optional[List[Dict]] = None
    telemetry_snapshots: Optional[List[Dict]] = None
    recommended_scenario: str = ""
    completed_at: str = ""
    duration_seconds: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "config_checksum": self.config_checksum,
            "config": self.config.to_dict(),
            "evaluation_metrics": self.evaluation_metrics,
            "threshold_evaluations": self.threshold_evaluations,
            "simulation_results": self.simulation_results,
            "error_analysis": self.error_analysis,
            "telemetry_snapshots": self.telemetry_snapshots,
            "recommended_scenario": self.recommended_scenario,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
        }

    def save(self, output_dir: str) -> str:
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, f"{self.config.name}_experiment_result.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)
        return path


class ExperimentRunner:
    """Orchestrates reproducible evaluation experiments."""

    def __init__(self, config: ExperimentConfig):
        self.config = config
        self._start_time: float = 0.0

    def _set_seed(self):
        _random.seed(self.config.seed)

    def run(
        self,
        apollo_decisions: List[str],
        gold_decisions: List[str],
        confidences: List[float],
        routing_labels: List[str],
        grounding_strengths: Optional[List[float]] = None,
        evidence_strengths: Optional[List[float]] = None,
        uncertainty_scores: Optional[List[float]] = None,
        triggered_criteria_counts: Optional[List[int]] = None,
        comparison_records: Optional[List[Dict]] = None,
        article_data: Optional[List[Dict]] = None,
    ) -> ExperimentResult:
        self._set_seed()
        self._start_time = time.time()
        from src.evaluation.metrics import MetricsComputer
        from src.evaluation.calibration import (
            ThresholdCalibrator, ThresholdConfig, DEFAULT_THRESHOLD_GRID,
        )
        from src.evaluation.simulation import WorkloadSimulator
        from src.evaluation.error_taxonomy import ErrorClassifier
        from src.evaluation.telemetry import TelemetryCollector
        metrics = MetricsComputer.compute_all(
            apollo_decisions, gold_decisions, routing_labels, confidences,
        )
        threshold_configs = [
            ThresholdConfig(**{
                "confidence_min": self.config.threshold_config.get("confidence_min", 0.95),
                "grounding_strength_min": self.config.threshold_config.get("grounding_strength_min", 0.80),
                "evidence_strength_min": self.config.threshold_config.get("evidence_strength_min", 0.60),
                "uncertainty_max": self.config.threshold_config.get("uncertainty_max", 0.20),
                "require_triggered_criteria": self.config.threshold_config.get("require_triggered_criteria", True),
                "name": "experiment_default",
            }),
            *DEFAULT_THRESHOLD_GRID,
        ]
        gs = grounding_strengths or [1.0] * len(apollo_decisions)
        es = evidence_strengths or [1.0] * len(apollo_decisions)
        us = uncertainty_scores or [0.0] * len(apollo_decisions)
        tcc = triggered_criteria_counts or [1] * len(apollo_decisions)
        cal_result = ThresholdCalibrator.grid_search(
            threshold_configs, apollo_decisions, gold_decisions,
            confidences, gs, es, us, tcc,
        )
        sim_result = WorkloadSimulator.simulate_all_scenarios(
            apollo_decisions, gold_decisions, confidences,
            gs, es, us, tcc,
            seed=self.config.seed,
            scenarios=self.config.scenarios,
        )
        error_analysis: List[Dict] = []
        if comparison_records:
            classified = ErrorClassifier.classify_batch(comparison_records)
            error_analysis = [c.to_dict() for c in classified]
        telemetry = TelemetryCollector()
        telemetry_snapshot = telemetry.snapshot_from_comparisons(
            comparison_records or [],
        )
        telemetry.record_snapshot(telemetry_snapshot)
        completed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        duration = time.time() - self._start_time
        sim_dicts = [r.to_dict() for r in sim_result.results] if sim_result.results else []
        cal_dicts = [e.to_dict() for e in cal_result.evaluations] if cal_result.evaluations else []
        return ExperimentResult(
            config_checksum=self.config.checksum(),
            config=self.config,
            evaluation_metrics=metrics.to_dict(),
            threshold_evaluations=cal_dicts,
            simulation_results=sim_dicts,
            error_analysis=error_analysis,
            telemetry_snapshots=[telemetry_snapshot.to_dict()],
            recommended_scenario=sim_result.recommended_scenario,
            completed_at=completed_at,
            duration_seconds=duration,
        )


def load_experiment_config(path: str) -> ExperimentConfig:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return ExperimentConfig.from_dict(data)


DEFAULT_EXPERIMENT_CONFIG = ExperimentConfig(
    name="benchmark_evaluation",
    description="Default benchmark evaluation of APOLLO autonomous screening performance",
    seed=42,
    protocol_version="1.0",
    stage="ec",
    dataset_name="benchmark",
    threshold_config={
        "confidence_min": 0.95,
        "grounding_strength_min": 0.80,
        "evidence_strength_min": 0.60,
        "uncertainty_max": 0.20,
        "require_triggered_criteria": True,
    },
    scenarios=["ultra_conservative", "conservative", "balanced", "aggressive"],
    telemetry_enabled=True,
    output_dir="data/evaluation/reports/",
)
