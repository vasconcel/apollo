"""
APOLLO Evaluation: Threshold Sweep Orchestration

Automates grid sweeps, scenario sweeps, and threshold variation experiments
to compare operating points and generate tradeoff analysis.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import copy
import json
import os


@dataclass
class SweepConfig:
    name: str = "sweep"
    description: str = ""
    mode: str = "grid"
    confidence_min_range: List[float] = field(default_factory=lambda: [0.80, 0.85, 0.90, 0.95, 0.99])
    grounding_strength_min_range: List[float] = field(default_factory=lambda: [0.5, 0.6, 0.7, 0.8, 0.9])
    evidence_strength_min_range: List[float] = field(default_factory=lambda: [0.3, 0.4, 0.5, 0.6])
    uncertainty_max_range: List[float] = field(default_factory=lambda: [0.10, 0.20, 0.30, 0.40, 0.50])
    require_triggered_criteria_options: List[bool] = field(default_factory=lambda: [True, False])
    scenarios: List[str] = field(default_factory=lambda: [
        "ultra_conservative", "conservative", "balanced", "aggressive",
    ])
    output_dir: str = "data/evaluation/sweeps/"
    seed: int = 42

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "mode": self.mode,
            "confidence_min_range": self.confidence_min_range,
            "grounding_strength_min_range": self.grounding_strength_min_range,
            "evidence_strength_min_range": self.evidence_strength_min_range,
            "uncertainty_max_range": self.uncertainty_max_range,
            "require_triggered_criteria_options": self.require_triggered_criteria_options,
            "scenarios": self.scenarios,
            "seed": self.seed,
        }


@dataclass
class SweepResult:
    sweep_name: str
    mode: str
    evaluations: List[Dict]
    best_by_coverage: Optional[Dict]
    best_by_safety: Optional[Dict]
    best_balanced: Optional[Dict]
    total_configs: int
    duration_seconds: float

    def to_dict(self) -> Dict:
        return {
            "sweep_name": self.sweep_name,
            "mode": self.mode,
            "evaluations": self.evaluations,
            "best_by_coverage": self.best_by_coverage,
            "best_by_safety": self.best_by_safety,
            "best_balanced": self.best_balanced,
            "total_configs": self.total_configs,
            "duration_seconds": self.duration_seconds,
        }

    def save(self, path: str) -> str:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)
        return path


class SweepOrchestrator:
    """Orchestrates threshold sweep experiments."""

    @staticmethod
    def run_grid_sweep(
        config: SweepConfig,
        apollo_decisions: List[str],
        gold_decisions: List[str],
        confidences: List[float],
        grounding_strengths: List[float],
        evidence_strengths: List[float],
        uncertainty_scores: List[float],
        triggered_criteria_counts: List[int],
    ) -> SweepResult:
        from src.evaluation.calibration import ThresholdCalibrator, ThresholdConfig
        import time
        start = time.time()
        evaluations: List[Dict] = []
        total_configs = (
            len(config.confidence_min_range)
            * len(config.grounding_strength_min_range)
            * len(config.evidence_strength_min_range)
            * len(config.uncertainty_max_range)
            * len(config.require_triggered_criteria_options)
        )
        for conf_min in config.confidence_min_range:
            for gs_min in config.grounding_strength_min_range:
                for ev_min in config.evidence_strength_min_range:
                    for unc_max in config.uncertainty_max_range:
                        for req_criteria in config.require_triggered_criteria_options:
                            tc = ThresholdConfig(
                                confidence_min=conf_min,
                                grounding_strength_min=gs_min,
                                evidence_strength_min=ev_min,
                                uncertainty_max=unc_max,
                                require_triggered_criteria=req_criteria,
                                name=f"conf{conf_min:.2f}_gs{gs_min:.2f}_ev{ev_min:.2f}_unc{unc_max:.2f}_req{req_criteria}",
                            )
                            ev = ThresholdCalibrator.evaluate_threshold(
                                tc, apollo_decisions, gold_decisions,
                                confidences, grounding_strengths, evidence_strengths,
                                uncertainty_scores, triggered_criteria_counts,
                            )
                            evaluations.append(ev.to_dict())
        evaluations.sort(key=lambda e: e.get("autonomous_coverage", 0), reverse=True)
        best_coverage = evaluations[0] if evaluations else None
        evaluations.sort(key=lambda e: e.get("safety_score", 0), reverse=True)
        best_safety = evaluations[0] if evaluations else None
        scored = sorted(
            evaluations,
            key=lambda e: e.get("safety_score", 0) * 0.5 + e.get("autonomous_coverage", 0) * 0.3 + e.get("autonomous_agreement", 0) * 0.2,
            reverse=True,
        )
        best_balanced = scored[0] if scored else None
        duration = time.time() - start
        return SweepResult(
            sweep_name=config.name,
            mode="grid",
            evaluations=evaluations,
            best_by_coverage=best_coverage,
            best_by_safety=best_safety,
            best_balanced=best_balanced,
            total_configs=total_configs,
            duration_seconds=duration,
        )

    @staticmethod
    def run_scenario_sweep(
        config: SweepConfig,
        apollo_decisions: List[str],
        gold_decisions: List[str],
        confidences: List[float],
        grounding_strengths: List[float],
        evidence_strengths: List[float],
        uncertainty_scores: List[float],
        triggered_criteria_counts: List[int],
    ) -> SweepResult:
        from src.evaluation.simulation import WorkloadSimulator, SCENARIO_THRESHOLDS
        import time
        start = time.time()
        evaluations: List[Dict] = []
        for scenario in config.scenarios:
            sr = WorkloadSimulator.simulate_scenario(
                scenario, apollo_decisions, gold_decisions,
                confidences, grounding_strengths, evidence_strengths,
                uncertainty_scores, triggered_criteria_counts,
                seed=config.seed,
            )
            evaluations.append(sr.to_dict())
        evaluations.sort(key=lambda e: e.get("autonomous_coverage", 0), reverse=True)
        best_coverage = evaluations[0] if evaluations else None
        evaluations.sort(key=lambda e: 1.0 - e.get("catastrophic_error_rate", 1.0), reverse=True)
        best_safety = evaluations[0] if evaluations else None
        scored = sorted(
            evaluations,
            key=lambda e: (1.0 - e.get("catastrophic_error_rate", 1.0) * 10) * 0.5
            + e.get("autonomous_coverage", 0) * 0.3
            + e.get("autonomous_agreement", 0) * 0.2,
            reverse=True,
        )
        best_balanced = scored[0] if scored else None
        duration = time.time() - start
        return SweepResult(
            sweep_name=config.name,
            mode="scenario",
            evaluations=evaluations,
            best_by_coverage=best_coverage,
            best_by_safety=best_safety,
            best_balanced=best_balanced,
            total_configs=len(config.scenarios),
            duration_seconds=duration,
        )

    @staticmethod
    def run_confidence_sweep(
        config: SweepConfig,
        apollo_decisions: List[str],
        gold_decisions: List[str],
        confidences: List[float],
        grounding_strengths: List[float],
        evidence_strengths: List[float],
        uncertainty_scores: List[float],
        triggered_criteria_counts: List[int],
    ) -> SweepResult:
        from src.evaluation.calibration import ThresholdCalibrator, ThresholdConfig
        import time
        start = time.time()
        base = ThresholdConfig(
            grounding_strength_min=config.grounding_strength_min_range[0] if config.grounding_strength_min_range else 0.8,
            evidence_strength_min=config.evidence_strength_min_range[0] if config.evidence_strength_min_range else 0.6,
            uncertainty_max=config.uncertainty_max_range[0] if config.uncertainty_max_range else 0.2,
            require_triggered_criteria=True,
        )
        evaluations = ThresholdCalibrator.sweep_confidence(
            apollo_decisions, gold_decisions, confidences,
            grounding_strengths, evidence_strengths,
            uncertainty_scores, triggered_criteria_counts,
            base_config=base, step=0.05,
        )
        ev_dicts = [e.to_dict() for e in evaluations]
        ev_dicts.sort(key=lambda e: e.get("autonomous_coverage", 0), reverse=True)
        best_coverage = ev_dicts[0] if ev_dicts else None
        ev_dicts.sort(key=lambda e: e.get("safety_score", 0), reverse=True)
        best_safety = ev_dicts[0] if ev_dicts else None
        duration = time.time() - start
        return SweepResult(
            sweep_name=config.name,
            mode="confidence_sweep",
            evaluations=ev_dicts,
            best_by_coverage=best_coverage,
            best_by_safety=best_safety,
            best_balanced=None,
            total_configs=len(evaluations),
            duration_seconds=duration,
        )
