"""
APOLLO Evaluation: CLI Entry Point

Usage:
    python -m src.evaluation.run --benchmark <path> [options]

Modes:
    single          Run a single benchmark experiment
    sweep           Run a threshold sweep experiment
    simulation      Run workload simulation only
    report-only     Generate reports from existing artifacts
    replay          Replay a previous experiment from artifacts
"""

import argparse
import json
import os
import sys
import time


def _load_config(path: str) -> dict:
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def cmd_single(args):
    from src.evaluation.runner import BenchmarkRunner, RunnerConfig
    config = RunnerConfig(
        experiment_name=args.name or os.path.splitext(os.path.basename(args.benchmark))[0],
        stage=args.stage,
        protocol_version=args.protocol_version,
        dataset_path=args.benchmark,
        output_dir=args.output_dir,
        seed=args.seed,
        skip_existing=not args.no_skip_existing,
        telemetry_enabled=not args.no_telemetry,
        store_artifacts=not args.no_artifacts,
        generate_report=not args.no_report,
        run_calibration=not args.no_calibration,
        run_simulation=not args.no_simulation,
        run_error_analysis=not args.no_error_analysis,
    )
    if args.config:
        cfg_data = _load_config(args.config)
        if "threshold_config" in cfg_data:
            config.threshold_config = cfg_data["threshold_config"]
        if "scenarios" in cfg_data:
            config.scenarios = cfg_data["scenarios"]
    runner = BenchmarkRunner(config)
    print(f"[EVAL] Starting benchmark: {config.experiment_name}")
    print(f"[EVAL] Dataset: {args.benchmark}")
    print(f"[EVAL] Stage: {config.stage}, Seed: {config.seed}")
    print(f"[EVAL] Output: {config.output_dir}")
    print()
    result = runner.run()
    print(f"[EVAL] Completed in {result.duration_seconds:.1f}s")
    print(f"[EVAL] Processed: {result.processed}/{result.total_articles}")
    print(f"[EVAL] Failed: {result.failed}")
    if result.evaluation_metrics:
        cls = result.evaluation_metrics.get("classification", {})
        print(f"[EVAL] F1: {cls.get('f1_score', 0):.3f}")
        aut = result.evaluation_metrics.get("autonomy", {})
        print(f"[EVAL] Auto Coverage: {aut.get('autonomous_coverage', 0):.1%}")
        saf = result.evaluation_metrics.get("safety", {})
        print(f"[EVAL] Catastrophic Exclusions: {saf.get('catastrophic_false_exclusions', 0)}")
    if result.report_paths:
        for fmt, path in result.report_paths.items():
            print(f"[EVAL] Report ({fmt}): {path}")
    result_path = os.path.join(args.output_dir, f"{config.experiment_name}_runner_result.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, indent=2, default=str)
    print(f"[EVAL] Result saved: {result_path}")
    return result


def cmd_sweep(args):
    from src.evaluation.sweep import SweepOrchestrator, SweepConfig
    from src.evaluation.metrics import MetricsComputer
    from src.evaluation.benchmark import BenchmarkLoader

    print(f"[SWEEP] Loading benchmark: {args.benchmark}")
    dataset = BenchmarkLoader.load_csv(args.benchmark, stage=args.stage) if args.benchmark.endswith(".csv") else BenchmarkLoader.load_json(args.benchmark, stage=args.stage)
    print(f"[SWEEP] Loaded {len(dataset)} items")
    sweep_config = SweepConfig(
        name=args.name or "sweep",
        mode=args.mode,
        output_dir=args.output_dir,
        seed=args.seed,
    )
    if args.config:
        cfg_data = _load_config(args.config)
        for field in ("confidence_min_range", "grounding_strength_min_range",
                      "evidence_strength_min_range", "uncertainty_max_range",
                      "require_triggered_criteria_options", "scenarios"):
            if field in cfg_data:
                setattr(sweep_config, field, cfg_data[field])
    print(f"[SWEEP] Mode: {sweep_config.mode}")
    decisions = dataset.get_gold_decisions()
    n = len(decisions)
    if args.mode == "grid":
        result = SweepOrchestrator.run_grid_sweep(
            sweep_config, decisions, decisions,
            [0.95] * n, [1.0] * n, [0.6] * n,
            [0.0] * n, [1] * n,
        )
    elif args.mode == "scenario":
        result = SweepOrchestrator.run_scenario_sweep(
            sweep_config, decisions, decisions,
            [0.95] * n, [1.0] * n, [0.6] * n,
            [0.0] * n, [1] * n,
        )
    elif args.mode == "confidence":
        result = SweepOrchestrator.run_confidence_sweep(
            sweep_config, decisions, decisions,
            [0.95] * n, [1.0] * n, [0.6] * n,
            [0.0] * n, [1] * n,
        )
    else:
        print(f"[SWEEP] Unknown mode: {args.mode}")
        return None
    os.makedirs(args.output_dir, exist_ok=True)
    path = os.path.join(args.output_dir, f"{sweep_config.name}_sweep_result.json")
    result.save(path)
    print(f"[SWEEP] Evaluated {result.total_configs} configurations in {result.duration_seconds:.1f}s")
    if result.best_balanced:
        print(f"[SWEEP] Best balanced: {result.best_balanced.get('config', {}).get('name', 'N/A')}")
    if result.best_by_coverage:
        print(f"[SWEEP] Best coverage: {result.best_by_coverage.get('config', {}).get('name', 'N/A')}")
    if result.best_by_safety:
        print(f"[SWEEP] Best safety: {result.best_by_safety.get('config', {}).get('name', 'N/A')}")
    print(f"[SWEEP] Results saved: {path}")
    return result


def cmd_simulation(args):
    from src.evaluation.simulation import WorkloadSimulator
    from src.evaluation.benchmark import BenchmarkLoader

    print(f"[SIM] Loading benchmark: {args.benchmark}")
    dataset = BenchmarkLoader.load_csv(args.benchmark, stage=args.stage) if args.benchmark.endswith(".csv") else BenchmarkLoader.load_json(args.benchmark, stage=args.stage)
    n = len(dataset)
    print(f"[SIM] Loaded {n} items for simulation")
    decisions = dataset.get_gold_decisions()
    result = WorkloadSimulator.simulate_all_scenarios(
        decisions, decisions,
        [0.95] * n, [1.0] * n, [0.6] * n,
        [0.0] * n, [1] * n,
        seed=args.seed,
    )
    print(f"[SIM] Total papers: {result.total_papers}")
    print(f"[SIM] Recommended scenario: {result.recommended_scenario}")
    for r in result.results:
        reduction = r.human_review_reduction_pct
        coverage = r.autonomous_coverage
        catastrophic = r.catastrophic_errors
        print(f"  {r.scenario:>22}: auto={r.autonomous_resolved:>4}, "
              f"human={r.human_review_required:>4}, "
              f"catastrophic={catastrophic:>2}, "
              f"coverage={coverage:.0%}, reduction={reduction:.0%}")
    os.makedirs(args.output_dir, exist_ok=True)
    path = os.path.join(args.output_dir, f"simulation_{args.name or 'result'}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict() if hasattr(result, 'to_dict') else {"results": [r.to_dict() for r in result.results]}, f, indent=2, default=str)
    print(f"[SIM] Results saved: {path}")
    return result


def cmd_report(args):
    from src.evaluation.metrics import MetricsComputer
    from src.evaluation.reporting import ReportGenerator
    from src.evaluation.error_taxonomy import ErrorClassifier
    from src.evaluation.artifacts import ReplayLoader

    print(f"[REPORT] Loading artifacts from {args.artifacts}")
    if os.path.isdir(args.artifacts):
        all_files = [f for f in os.listdir(args.artifacts) if f.endswith(".json") and f != "artifact_manifest.json"]
        comparisons = []
        for fname in all_files:
            path = os.path.join(args.artifacts, fname)
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                comparisons.extend(data)
            elif isinstance(data, dict):
                comparisons.append(data)
    else:
        with open(args.artifacts, "r", encoding="utf-8") as f:
            data = json.load(f)
        comparisons = data if isinstance(data, list) else data.get("comparison_records", [data])
    print(f"[REPORT] Loaded {len(comparisons)} comparison records")
    apollo_decisions = [c.get("apollo_decision", c.get("decision", "")) for c in comparisons]
    gold_decisions = [c.get("gold_decision", "") for c in comparisons]
    routing_labels = [c.get("apollo_routing", c.get("routing", "HUMAN_REVIEW")) for c in comparisons]
    confidences = [c.get("apollo_confidence", c.get("confidence", 0.0)) for c in comparisons]
    metrics = MetricsComputer.compute_all(apollo_decisions, gold_decisions, routing_labels, confidences)
    errors = [c for c in comparisons if not c.get("is_correct", True)]
    error_analysis = [c.to_dict() for c in ErrorClassifier.classify_batch(errors)] if errors else []
    os.makedirs(args.output_dir, exist_ok=True)
    md = ReportGenerator.generate_markdown(
        metrics, experiment_name=args.name or "report",
        dataset_name=args.artifacts, dataset_size=len(comparisons),
        stage=args.stage, error_analysis=error_analysis,
    )
    json_report = ReportGenerator.generate_json_report(
        metrics, error_analysis=error_analysis,
        experiment_name=args.name or "report",
        dataset_name=args.artifacts, dataset_size=len(comparisons),
        stage=args.stage,
    )
    confusion_csv = ReportGenerator.generate_confusion_matrix_csv(
        metrics.classification.true_positives,
        metrics.classification.false_positives,
        metrics.classification.false_negatives,
        metrics.classification.true_negatives,
    )
    error_csv = ReportGenerator.generate_error_csv(error_analysis) if error_analysis else ""
    paths = ReportGenerator.write_report_files(
        args.output_dir, args.name or "report",
        md, json_report, confusion_csv=confusion_csv, error_csv=error_csv,
    )
    for fmt, path in paths.items():
        print(f"[REPORT] {fmt}: {path}")
    return paths


def cmd_replay(args):
    from src.evaluation.artifacts import ReplayLoader, ArtifactStore
    from src.evaluation.metrics import MetricsComputer
    from src.evaluation.reporting import ReportGenerator
    from src.evaluation.error_taxonomy import ErrorClassifier

    parts = args.experiment_id.rsplit("_", 1)
    if len(parts) == 2:
        experiment_name, session_id = parts
    else:
        experiment_name = args.experiment_id
        session_id = ""
    store = ArtifactStore()
    artifacts = store.load_all_artifacts(experiment_name, session_id)
    print(f"[REPLAY] Loaded {len(artifacts)} artifacts from {experiment_name}/{session_id}")
    if not artifacts:
        print("[REPLAY] No artifacts found")
        return None
    comparisons = ReplayLoader.load_comparison_records(artifacts)
    print(f"[REPLAY] Generated {len(comparisons)} comparison records")
    apollo_decisions = [c["apollo_decision"] for c in comparisons]
    gold_decisions = [c["gold_decision"] for c in comparisons]
    routing_labels = [c.get("apollo_routing", "HUMAN_REVIEW") for c in comparisons]
    confidences = [c["confidence"] for c in comparisons]
    metrics = MetricsComputer.compute_all(apollo_decisions, gold_decisions, routing_labels, confidences)
    errors = [c for c in comparisons if not c.get("is_correct",
        c["apollo_decision"].upper().strip() in ("INCLUDE", "AUTO_INCLUDE") == c["gold_decision"].upper().strip() in ("INCLUDE", "AUTO_INCLUDE"))]
    error_analysis = [e.to_dict() for e in ErrorClassifier.classify_batch(errors)] if errors else []
    os.makedirs(args.output_dir, exist_ok=True)
    md = ReportGenerator.generate_markdown(
        metrics, experiment_name=f"replay_{experiment_name}",
        dataset_name=experiment_name, dataset_size=len(comparisons),
        stage=args.stage, error_analysis=error_analysis,
    )
    json_report = ReportGenerator.generate_json_report(
        metrics, error_analysis=error_analysis,
        experiment_name=f"replay_{experiment_name}",
        dataset_name=experiment_name, dataset_size=len(comparisons),
        stage=args.stage,
    )
    paths = ReportGenerator.write_report_files(
        args.output_dir, f"replay_{experiment_name}",
        md, json_report,
        confusion_csv=ReportGenerator.generate_confusion_matrix_csv(
            metrics.classification.true_positives,
            metrics.classification.false_positives,
            metrics.classification.false_negatives,
            metrics.classification.true_negatives,
        ),
        error_csv=ReportGenerator.generate_error_csv(error_analysis) if error_analysis else "",
    )
    for fmt, path in paths.items():
        print(f"[REPLAY] {fmt}: {path}")
    return paths


def main():
    parser = argparse.ArgumentParser(description="APOLLO Evaluation CLI")
    parser.add_argument("--benchmark", "-b", type=str, default="", help="Path to benchmark dataset")
    parser.add_argument("--config", "-c", type=str, default="", help="Path to experiment config JSON")
    parser.add_argument("--output-dir", "-o", type=str, default="data/evaluation/reports/", help="Output directory")
    parser.add_argument("--name", "-n", type=str, default="", help="Experiment name")
    parser.add_argument("--stage", "-s", type=str, default="ec", help="Screening stage (ec/ic)")
    parser.add_argument("--protocol-version", "-p", type=str, default="1.0", help="Protocol version")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--mode", "-m", type=str, default="single",
                        choices=["single", "sweep", "simulation", "report", "replay"],
                        help="Execution mode")
    parser.add_argument("--no-skip-existing", action="store_true", help="Do not skip existing advisories")
    parser.add_argument("--no-telemetry", action="store_true", help="Disable telemetry collection")
    parser.add_argument("--no-artifacts", action="store_true", help="Disable artifact storage")
    parser.add_argument("--no-report", action="store_true", help="Disable report generation")
    parser.add_argument("--no-calibration", action="store_true", help="Disable calibration analysis")
    parser.add_argument("--no-simulation", action="store_true", help="Disable workload simulation")
    parser.add_argument("--no-error-analysis", action="store_true", help="Disable error classification")
    parser.add_argument("--artifacts", type=str, default="", help="Path to artifact directory/file (for report/replay modes)")
    parser.add_argument("--experiment-id", type=str, default="", help="Experiment ID for replay mode")
    args = parser.parse_args()

    if args.mode == "single":
        if not args.benchmark:
            print("[EVAL] Error: --benchmark is required for single mode")
            sys.exit(1)
        cmd_single(args)
    elif args.mode == "sweep":
        if not args.benchmark:
            print("[SWEEP] Error: --benchmark is required for sweep mode")
            sys.exit(1)
        cmd_sweep(args)
    elif args.mode == "simulation":
        if not args.benchmark:
            print("[SIM] Error: --benchmark is required for simulation mode")
            sys.exit(1)
        cmd_simulation(args)
    elif args.mode == "report":
        if not args.artifacts:
            print("[REPORT] Error: --artifacts is required for report-only mode")
            sys.exit(1)
        cmd_report(args)
    elif args.mode == "replay":
        if not args.experiment_id:
            print("[REPLAY] Error: --experiment-id is required for replay mode")
            sys.exit(1)
        cmd_replay(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
