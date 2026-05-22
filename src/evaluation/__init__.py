"""
APOLLO Evaluation Framework - Autonomous Screening Evaluation

Provides metrics computation, gold-standard benchmarking, threshold calibration,
workload simulation, error classification, telemetry, and reproducible experiments
for scientifically validating APOLLO's autonomous screening architecture.
"""

from .metrics import (
    MetricsComputer, EvaluationMetrics, ClassificationMetrics,
    SafetyMetrics, AutonomyMetrics, CalibrationMetrics, QueueMetrics,
)
from .benchmark import (
    BenchmarkLoader, BenchmarkComparator, BenchmarkDataset,
    BenchmarkItem, ComparisonRecord,
)
from .calibration import (
    ThresholdCalibrator, ThresholdConfig, ThresholdEvaluation,
    CalibrationResult, DEFAULT_THRESHOLD_GRID,
)
from .simulation import (
    WorkloadSimulator, SimulationResult, SimulationReport,
    AutonomyScenario, SCENARIO_THRESHOLDS,
)
from .error_taxonomy import (
    ErrorClassifier, ErrorCategory, ClassifiedError,
    ERROR_DESCRIPTIONS, ERROR_SEVERITY,
)
from .telemetry import (
    TelemetryCollector, TelemetryStore, TelemetrySnapshot, TelemetryHistory,
)
from .experiment import (
    ExperimentRunner, ExperimentConfig, ExperimentResult,
    load_experiment_config, DEFAULT_EXPERIMENT_CONFIG,
)
from .reporting import ReportGenerator

__all__ = [
    "MetricsComputer", "EvaluationMetrics", "ClassificationMetrics",
    "SafetyMetrics", "AutonomyMetrics", "CalibrationMetrics", "QueueMetrics",
    "BenchmarkLoader", "BenchmarkComparator", "BenchmarkDataset",
    "BenchmarkItem", "ComparisonRecord",
    "ThresholdCalibrator", "ThresholdConfig", "ThresholdEvaluation",
    "CalibrationResult", "DEFAULT_THRESHOLD_GRID",
    "WorkloadSimulator", "SimulationResult", "SimulationReport",
    "AutonomyScenario", "SCENARIO_THRESHOLDS",
    "ErrorClassifier", "ErrorCategory", "ClassifiedError",
    "ERROR_DESCRIPTIONS", "ERROR_SEVERITY",
    "TelemetryCollector", "TelemetryStore", "TelemetrySnapshot",
    "TelemetryHistory",
    "ExperimentRunner", "ExperimentConfig", "ExperimentResult",
    "load_experiment_config", "DEFAULT_EXPERIMENT_CONFIG",
    "ReportGenerator",
]
