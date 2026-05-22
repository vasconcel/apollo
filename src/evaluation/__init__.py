"""
APOLLO Evaluation Framework - Autonomous Screening Evaluation

Provides metrics computation, gold-standard benchmarking, threshold calibration,
workload simulation, error classification, telemetry, reproducible experiments,
and end-to-end benchmark orchestration for scientifically validating APOLLO's
autonomous screening architecture.
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
from .dataset import (
    compute_dataset_checksum, compute_dataset_row_checksum,
    DatasetMetadata, DatasetRegistry,
    analyze_dataset, verify_dataset_integrity,
)
from .statistics import (
    compute_confidence_interval, bootstrap_metric,
    bootstrap_classification_metrics, aggregate_runs, compare_threshold_pairs,
    ConfidenceInterval,
)
from .failures import (
    FailureRecord, FailureSummary, FailureAnalyzer,
    classify_advisory_failure, check_routing_consistency,
)
from .session import (
    ExperimentSession, ExperimentManifest, SessionManifest,
    capture_git_hash, generate_experiment_id,
)
from .artifacts import (
    ArtifactStore, ArticleArtifact, ArtifactManifest, ReplayLoader,
)
from .executor import (
    BatchExecutor, ExecutionProgress, CheckpointState,
    BATCH_SIZE_DEFAULT, MAX_RETRIES_DEFAULT, RATE_LIMIT_SLEEP_DEFAULT,
)
from .sweep import (
    SweepOrchestrator, SweepConfig, SweepResult,
)
from .dashboard import (
    DashboardState, DashboardHook,
)
from .runner import (
    BenchmarkRunner, RunnerConfig, RunnerResult,
)

__all__ = [
    # Metrics
    "MetricsComputer", "EvaluationMetrics", "ClassificationMetrics",
    "SafetyMetrics", "AutonomyMetrics", "CalibrationMetrics", "QueueMetrics",
    # Benchmark
    "BenchmarkLoader", "BenchmarkComparator", "BenchmarkDataset",
    "BenchmarkItem", "ComparisonRecord",
    # Calibration
    "ThresholdCalibrator", "ThresholdConfig", "ThresholdEvaluation",
    "CalibrationResult", "DEFAULT_THRESHOLD_GRID",
    # Simulation
    "WorkloadSimulator", "SimulationResult", "SimulationReport",
    "AutonomyScenario", "SCENARIO_THRESHOLDS",
    # Error Taxonomy
    "ErrorClassifier", "ErrorCategory", "ClassifiedError",
    "ERROR_DESCRIPTIONS", "ERROR_SEVERITY",
    # Telemetry
    "TelemetryCollector", "TelemetryStore", "TelemetrySnapshot",
    "TelemetryHistory",
    # Experiment
    "ExperimentRunner", "ExperimentConfig", "ExperimentResult",
    "load_experiment_config", "DEFAULT_EXPERIMENT_CONFIG",
    # Reporting
    "ReportGenerator",
    # Dataset Versioning
    "compute_dataset_checksum", "compute_dataset_row_checksum",
    "DatasetMetadata", "DatasetRegistry",
    "analyze_dataset", "verify_dataset_integrity",
    # Statistics
    "compute_confidence_interval", "bootstrap_metric",
    "bootstrap_classification_metrics", "aggregate_runs", "compare_threshold_pairs",
    "ConfidenceInterval",
    # Failures
    "FailureRecord", "FailureSummary", "FailureAnalyzer",
    "classify_advisory_failure", "check_routing_consistency",
    # Session
    "ExperimentSession", "ExperimentManifest", "SessionManifest",
    "capture_git_hash", "generate_experiment_id",
    # Artifacts
    "ArtifactStore", "ArticleArtifact", "ArtifactManifest", "ReplayLoader",
    # Executor
    "BatchExecutor", "ExecutionProgress", "CheckpointState",
    "BATCH_SIZE_DEFAULT", "MAX_RETRIES_DEFAULT", "RATE_LIMIT_SLEEP_DEFAULT",
    # Sweep
    "SweepOrchestrator", "SweepConfig", "SweepResult",
    # Dashboard
    "DashboardState", "DashboardHook",
    # Runner
    "BenchmarkRunner", "RunnerConfig", "RunnerResult",
]
