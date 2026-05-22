"""
APOLLO Evaluation: End-to-End Benchmark Runner

Orchestrates the full evaluation pipeline:
  load dataset → generate advisories → route → compare → metrics →
  calibrate → simulate → classify errors → generate reports → persist
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
import os
import time


@dataclass
class RunnerConfig:
    experiment_name: str = "benchmark_run"
    stage: str = "ec"
    protocol_version: str = "1.0"
    dataset_path: str = ""
    output_dir: str = "data/evaluation/reports/"
    artifact_dir: str = "data/evaluation/artifacts/"
    checkpoint_dir: str = "data/evaluation/checkpoints/"
    seed: int = 42
    skip_existing: bool = True
    telemetry_enabled: bool = True
    store_artifacts: bool = True
    store_raw_prompts: bool = False
    generate_report: bool = True
    run_calibration: bool = True
    run_simulation: bool = True
    run_error_analysis: bool = True
    threshold_config: Dict[str, Any] = field(default_factory=lambda: {
        "confidence_min": 0.95, "grounding_strength_min": 0.80,
        "evidence_strength_min": 0.60, "uncertainty_max": 0.20,
        "require_triggered_criteria": True,
    })
    scenarios: List[str] = field(default_factory=lambda: [
        "ultra_conservative", "conservative", "balanced", "aggressive",
    ])

    def to_dict(self) -> Dict:
        return {
            "experiment_name": self.experiment_name,
            "stage": self.stage,
            "protocol_version": self.protocol_version,
            "dataset_path": self.dataset_path,
            "output_dir": self.output_dir,
            "artifact_dir": self.artifact_dir,
            "checkpoint_dir": self.checkpoint_dir,
            "seed": self.seed,
            "skip_existing": self.skip_existing,
            "telemetry_enabled": self.telemetry_enabled,
            "store_artifacts": self.store_artifacts,
            "store_raw_prompts": self.store_raw_prompts,
            "generate_report": self.generate_report,
            "run_calibration": self.run_calibration,
            "run_simulation": self.run_simulation,
            "run_error_analysis": self.run_error_analysis,
            "threshold_config": self.threshold_config,
            "scenarios": self.scenarios,
        }


@dataclass
class RunnerResult:
    experiment_id: str
    session_id: str
    config: RunnerConfig
    total_articles: int
    processed: int
    failed: int
    comparison_records: List[Dict]
    evaluation_metrics: Optional[Dict]
    calibration_result: Optional[Dict]
    simulation_result: Optional[Dict]
    error_analysis: Optional[List[Dict]]
    failure_analysis: Optional[Dict]
    report_paths: Dict[str, str]
    duration_seconds: float
    completed_at: str

    def to_dict(self) -> Dict:
        return {
            "experiment_id": self.experiment_id,
            "session_id": self.session_id,
            "config": self.config.to_dict(),
            "total_articles": self.total_articles,
            "processed": self.processed,
            "failed": self.failed,
            "comparison_records_count": len(self.comparison_records),
            "evaluation_metrics": self.evaluation_metrics,
            "calibration_result": self.calibration_result,
            "simulation_result": self.simulation_result,
            "error_analysis_count": len(self.error_analysis) if self.error_analysis else 0,
            "failure_analysis": self.failure_analysis,
            "report_paths": self.report_paths,
            "duration_seconds": self.duration_seconds,
            "completed_at": self.completed_at,
        }


class BenchmarkRunner:
    """End-to-end benchmark execution and evaluation orchestrator."""

    def __init__(
        self,
        config: RunnerConfig,
        dashboard_hook: Optional[Any] = None,
        progress_callback: Optional[Callable] = None,
    ):
        self.config = config
        self.dashboard = dashboard_hook
        self.progress_callback = progress_callback

    def _init_session(self):
        from src.evaluation.session import ExperimentSession
        self.session = ExperimentSession(
            experiment_name=self.config.experiment_name,
            protocol_version=self.config.protocol_version,
            stage=self.config.stage,
            seed=self.config.seed,
            output_dir=self.config.output_dir,
        )

    def _load_dataset(self):
        from src.evaluation.benchmark import BenchmarkLoader
        from src.evaluation.dataset import analyze_dataset, DatasetRegistry
        path = self.config.dataset_path
        if not path:
            raise ValueError("dataset_path is required in RunnerConfig")
        if path.endswith(".csv"):
            self.dataset = BenchmarkLoader.load_csv(
                path, name=self.config.experiment_name, stage=self.config.stage,
            )
        elif path.endswith(".json"):
            self.dataset = BenchmarkLoader.load_json(
                path, name=self.config.experiment_name, stage=self.config.stage,
            )
        else:
            raise ValueError(f"Unsupported dataset format: {path}")
        self.dataset_metadata = analyze_dataset(path, name=self.config.experiment_name, stage=self.config.stage)

    def _articles_from_dataset(self) -> List[Dict]:
        articles = []
        for item in self.dataset.items:
            articles.append({
                "article_id": item.article_id,
                "title": item.title,
                "abstract": item.abstract,
                "gold_decision": item.gold_decision,
                "stage": item.stage or self.config.stage,
                "protocol_version": item.protocol_version or self.config.protocol_version,
            })
        return articles

    def _generate_advisories(
        self,
        articles: List[Dict],
    ) -> List[Dict]:
        from src.evaluation.executor import BatchExecutor

        def generate_fn(article: Dict) -> Optional[Dict]:
            try:
                from src.advisory.advisory_worker import generate_single_advisory
                result = generate_single_advisory(
                    title=article.get("title", ""),
                    abstract=article.get("abstract", ""),
                    protocol_version=article.get("protocol_version", self.config.protocol_version),
                )
                if result is None:
                    return None
                from src.advisory.advisory_models import AdvisoryResult
                if isinstance(result, AdvisoryResult):
                    d = result.to_dict()
                    d["article_id"] = article.get("article_id", "")
                    d["decision"] = result.decision.value if result.decision else "UNAVAILABLE"
                    d["confidence"] = result.confidence
                    d["error"] = result.error
                    d["grounding_evidence"] = result.grounding_evidence
                    d["grounding_strength"] = result.grounding_strength
                    d["hallucination_risk_score"] = result.hallucination_risk_score
                    d["triggered_criteria"] = result.triggered_criteria
                    if result.topic_relevance:
                        d["topic_relevance"] = result.topic_relevance.to_dict()
                    else:
                        d["topic_relevance"] = {}
                    return d
                if isinstance(result, dict):
                    result["article_id"] = article.get("article_id", result.get("article_id", ""))
                    return result
                return None
            except Exception as e:
                return {
                    "article_id": article.get("article_id", ""),
                    "error": str(e),
                    "decision": "UNAVAILABLE",
                    "confidence": 0.0,
                }

        executor = BatchExecutor(
            progress_callback=self.progress_callback,
            checkpoint_dir=self.config.checkpoint_dir,
        )
        if self.dashboard and hasattr(self.dashboard, 'state'):
            self.dashboard.state.total_articles = len(articles)
            self.dashboard.state.running = True

        existing_ids = []
        if self.config.skip_existing:
            existing_ids = executor.get_completed_ids(
                self.config.experiment_name, self.session.session_id,
            )

        results = executor.execute_batch(
            articles=articles,
            generate_fn=generate_fn,
            experiment_name=self.config.experiment_name,
            session_id=self.session.session_id,
            stage=self.config.stage,
            skip_existing=self.config.skip_existing,
            existing_ids=existing_ids,
        )
        self.executor_progress = executor.progress
        return results

    def _compute_routing(self, advisory: Dict) -> str:
        from src.evaluation.calibration import ThresholdConfig
        tc = ThresholdConfig(
            confidence_min=self.config.threshold_config.get("confidence_min", 0.95),
            grounding_strength_min=self.config.threshold_config.get("grounding_strength_min", 0.80),
            evidence_strength_min=self.config.threshold_config.get("evidence_strength_min", 0.60),
            uncertainty_max=self.config.threshold_config.get("uncertainty_max", 0.20),
            require_triggered_criteria=self.config.threshold_config.get("require_triggered_criteria", True),
        )
        decision = (advisory.get("decision") or "UNAVAILABLE").upper().strip()
        if decision in ("UNCERTAIN", "INSUFFICIENT_EVIDENCE", "CANNOT_DETERMINE", "UNAVAILABLE"):
            return "HUMAN_REVIEW"
        if decision not in ("INCLUDE", "EXCLUDE"):
            return "HUMAN_REVIEW"
        confidence = advisory.get("confidence", 0.0)
        grounding = advisory.get("grounding_strength", advisory.get("grounding_strength", 0.0))
        evidence = 0.6 if advisory.get("grounding_evidence") else 0.0
        uncertainty = 1.0 - confidence
        has_criteria = len(advisory.get("triggered_criteria", [])) > 0
        can_auto = (
            confidence >= tc.confidence_min
            and grounding >= tc.grounding_strength_min
            and evidence >= tc.evidence_strength_min
            and uncertainty < tc.uncertainty_max
        )
        if tc.require_triggered_criteria:
            can_auto = can_auto and has_criteria
        if can_auto:
            return "AUTO_INCLUDE" if decision == "INCLUDE" else "AUTO_EXCLUDE"
        elif uncertainty > 0.7:
            return "ESCALATE"
        else:
            return "HUMAN_REVIEW"

    def _prepare_comparisons(
        self,
        articles: List[Dict],
        advisory_results: List[Dict],
    ) -> List[Dict]:
        results_by_id: Dict[str, Dict] = {}
        for r in advisory_results:
            aid = r.get("article_id", "")
            if aid:
                results_by_id[aid] = r
        comparisons = []
        for article in articles:
            aid = article["article_id"]
            adv = results_by_id.get(aid, {})
            routing = self._compute_routing(adv)
            comparisons.append({
                "article_id": aid,
                "title": article.get("title", ""),
                "abstract": article.get("abstract", ""),
                "gold_decision": article.get("gold_decision", ""),
                "apollo_decision": adv.get("decision", "UNAVAILABLE"),
                "apollo_confidence": adv.get("confidence", 0.0),
                "apollo_routing": routing,
                "apollo_justification": adv.get("justification", ""),
                "apollo_grounding_evidence": adv.get("grounding_evidence", []),
                "apollo_uncertainty_reasoning": adv.get("uncertainty_reasoning", ""),
                "apollo_domain_alignment_reasoning": adv.get("domain_alignment_reasoning", ""),
                "apollo_topic_relevance": adv.get("topic_relevance", {}),
                "apollo_triggered_criteria": adv.get("triggered_criteria", []),
                "apollo_autonomous_eligible": routing in ("AUTO_INCLUDE", "AUTO_EXCLUDE"),
                "is_correct": adv.get("decision", "").upper().strip() in ("INCLUDE", "AUTO_INCLUDE") == article.get("gold_decision", "").upper().strip() in ("INCLUDE", "AUTO_INCLUDE"),
                "stage": article.get("stage", self.config.stage),
                "protocol_version": article.get("protocol_version", self.config.protocol_version),
                "error": adv.get("error"),
            })
        return comparisons

    def _collect_telemetry(self, comparisons: List[Dict]):
        from src.evaluation.telemetry import TelemetryCollector, TelemetryStore
        collector = TelemetryCollector()
        snapshot = collector.snapshot_from_comparisons(comparisons)
        collector.record_snapshot(snapshot)
        store = TelemetryStore()
        store.save_snapshot(snapshot, self.config.experiment_name)
        return collector, snapshot

    def _compute_metrics(self, comparisons: List[Dict]):
        from src.evaluation.metrics import MetricsComputer
        apollo_decisions = [c["apollo_decision"] for c in comparisons]
        gold_decisions = [c["gold_decision"] for c in comparisons]
        routing_labels = [c["apollo_routing"] for c in comparisons]
        confidences = [c["apollo_confidence"] for c in comparisons]
        return MetricsComputer.compute_all(apollo_decisions, gold_decisions, routing_labels, confidences)

    def _run_calibration(self, comparisons: List[Dict]):
        from src.evaluation.calibration import ThresholdCalibrator, DEFAULT_THRESHOLD_GRID
        apollo_decisions = [c["apollo_decision"] for c in comparisons]
        gold_decisions = [c["gold_decision"] for c in comparisons]
        confidences = [c["apollo_confidence"] for c in comparisons]
        n = len(comparisons)
        result = ThresholdCalibrator.grid_search(
            DEFAULT_THRESHOLD_GRID,
            apollo_decisions, gold_decisions, confidences,
            [1.0] * n, [0.6] * n, [0.2] * n, [1] * n,
        )
        return [e.to_dict() for e in result.evaluations]

    def _run_simulation(self, comparisons: List[Dict]):
        from src.evaluation.simulation import WorkloadSimulator
        apollo_decisions = [c["apollo_decision"] for c in comparisons]
        gold_decisions = [c["gold_decision"] for c in comparisons]
        confidences = [c["apollo_confidence"] for c in comparisons]
        n = len(comparisons)
        result = WorkloadSimulator.simulate_all_scenarios(
            apollo_decisions, gold_decisions, confidences,
            [1.0] * n, [0.6] * n, [0.2] * n, [1] * n,
            seed=self.config.seed, scenarios=self.config.scenarios,
        )
        return result.to_dict() if hasattr(result, 'to_dict') else {}

    def _classify_errors(self, comparisons: List[Dict]):
        from src.evaluation.error_taxonomy import ErrorClassifier
        errors = [c for c in comparisons if not c.get("is_correct", True)]
        if not errors:
            return []
        classified = ErrorClassifier.classify_batch(errors)
        return [c.to_dict() for c in classified]

    def _analyze_failures(self, comparisons: List[Dict]):
        from src.evaluation.failures import FailureAnalyzer, classify_advisory_failure
        failures = [c for c in comparisons if c.get("error")]
        if not failures:
            return {"total_failures": 0, "failure_rate": 0.0, "category_counts": {}}
        records = []
        for c in failures:
            record = classify_advisory_failure(
                article_id=c.get("article_id", ""),
                stage=self.config.stage,
                advisory_result={"error": c.get("error"), "decision": c.get("apollo_decision", ""), "confidence": c.get("apollo_confidence", 0.0)},
            )
            records.append(record)
        summary = FailureAnalyzer.analyze(records, len(comparisons))
        return summary.to_dict()

    def _store_artifacts(self, comparisons: List[Dict], articles: List[Dict]):
        from src.evaluation.artifacts import ArtifactStore, ArticleArtifact
        store = ArtifactStore(base_path=self.config.artifact_dir)
        artifacts = []
        for comp in comparisons:
            art = ArticleArtifact(
                article_id=comp["article_id"],
                title=comp.get("title", ""),
                abstract=comp.get("abstract", ""),
                stage=self.config.stage,
                protocol_version=self.config.protocol_version,
                parsed_advisory={
                    "decision": comp.get("apollo_decision", ""),
                    "confidence": comp.get("apollo_confidence", 0.0),
                    "justification": comp.get("apollo_justification", ""),
                    "grounding_evidence": comp.get("apollo_grounding_evidence", []),
                    "triggered_criteria": comp.get("apollo_triggered_criteria", []),
                },
                routing_decision=comp.get("apollo_routing", ""),
                gold_decision=comp.get("gold_decision", ""),
                is_correct=comp.get("is_correct"),
                error=comp.get("error"),
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            )
            artifacts.append(art)
        store.store_combined_artifacts(
            artifacts, self.config.experiment_name, self.session.session_id,
        )

    def _generate_reports(
        self,
        metrics,
        error_analysis: Optional[List[Dict]],
        calibration_evals: Optional[List[Dict]],
    ):
        from src.evaluation.reporting import ReportGenerator
        md = ReportGenerator.generate_markdown(
            metrics,
            experiment_name=self.config.experiment_name,
            protocol_version=self.config.protocol_version,
            dataset_name=self.config.dataset_path,
            dataset_size=len(self.dataset),
            stage=self.config.stage,
            error_analysis=error_analysis,
            threshold_analysis=calibration_evals,
        )
        json_report = ReportGenerator.generate_json_report(
            metrics,
            error_analysis=error_analysis,
            threshold_analysis=calibration_evals,
            experiment_name=self.config.experiment_name,
            dataset_name=self.config.dataset_path,
            dataset_size=len(self.dataset),
            stage=self.config.stage,
        )
        confusion_csv = ReportGenerator.generate_confusion_matrix_csv(
            metrics.classification.true_positives,
            metrics.classification.false_positives,
            metrics.classification.false_negatives,
            metrics.classification.true_negatives,
        )
        error_csv = ReportGenerator.generate_error_csv(error_analysis) if error_analysis else ""
        return ReportGenerator.write_report_files(
            self.config.output_dir,
            self.config.experiment_name,
            md, json_report,
            confusion_csv=confusion_csv,
            error_csv=error_csv,
        )

    def run(self) -> RunnerResult:
        self._init_session()
        start_time = time.time()
        self._load_dataset()
        articles = self._articles_from_dataset()
        advisory_results = self._generate_advisories(articles)
        comparisons = self._prepare_comparisons(articles, advisory_results)
        if self.config.telemetry_enabled:
            self._collect_telemetry(comparisons)
        metrics = self._compute_metrics(comparisons)
        calibration_evals = None
        if self.config.run_calibration:
            calibration_evals = self._run_calibration(comparisons)
        simulation_result = None
        if self.config.run_simulation:
            simulation_result = self._run_simulation(comparisons)
        error_analysis = None
        if self.config.run_error_analysis:
            error_analysis = self._classify_errors(comparisons)
        failure_analysis = self._analyze_failures(comparisons)
        if self.config.store_artifacts:
            self._store_artifacts(comparisons, articles)
        report_paths = {}
        if self.config.generate_report:
            report_paths = self._generate_reports(
                metrics, error_analysis, calibration_evals,
            )
        duration = time.time() - start_time
        if self.dashboard:
            self.dashboard.state.running = False
        processed = self.executor_progress.completed if hasattr(self, 'executor_progress') else 0
        failed = self.executor_progress.failed if hasattr(self, 'executor_progress') else 0
        return RunnerResult(
            experiment_id=self.session.experiment_id,
            session_id=self.session.session_id,
            config=self.config,
            total_articles=len(articles),
            processed=processed,
            failed=failed,
            comparison_records=comparisons,
            evaluation_metrics=metrics.to_dict() if hasattr(metrics, 'to_dict') else {},
            calibration_result={"evaluations": calibration_evals} if calibration_evals else None,
            simulation_result=simulation_result,
            error_analysis=error_analysis,
            failure_analysis=failure_analysis,
            report_paths=report_paths,
            duration_seconds=duration,
            completed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )
