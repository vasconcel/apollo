"""
APOLLO Evaluation: Calibration Reporting

Generates structured, publication-ready evaluation reports
in Markdown, JSON, and CSV formats.
"""

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
import csv
import io
import json
import os


REPORT_HEADER = """# APOLLO Autonomous Screening Evaluation Report

**Generated:** {timestamp}
**Experiment:** {experiment_name}
**Protocol Version:** {protocol_version}
**Dataset:** {dataset_name} ({dataset_size} items)
**Stage:** {stage}

---

"""


def _fmt_pct(value: float) -> str:
    return f"{value:.1%}"


def _fmt_num(value: float, decimals: int = 4) -> str:
    return f"{value:.{decimals}f}"


class ReportGenerator:
    """Generates evaluation reports in multiple formats."""

    @staticmethod
    def generate_markdown(
        metrics: Any,
        experiment_name: str = "default",
        protocol_version: str = "1.0",
        dataset_name: str = "benchmark",
        dataset_size: int = 0,
        stage: str = "ec",
        error_analysis: Optional[List[Dict]] = None,
        threshold_analysis: Optional[List[Dict]] = None,
    ) -> str:
        lines = [REPORT_HEADER.format(
            timestamp=__import__("datetime").datetime.now().isoformat(),
            experiment_name=experiment_name,
            protocol_version=protocol_version,
            dataset_name=dataset_name,
            dataset_size=dataset_size,
            stage=stage,
        )]
        cls = getattr(metrics, 'classification', None)
        if cls:
            lines.append("## Classification Metrics\n")
            lines.append(f"| Metric | Value |")
            lines.append(f"|--------|-------|")
            lines.append(f"| Precision | {_fmt_pct(cls.precision)} |")
            lines.append(f"| Recall | {_fmt_pct(cls.recall)} |")
            lines.append(f"| F1 Score | {_fmt_pct(cls.f1_score)} |")
            lines.append(f"| Specificity | {_fmt_pct(cls.specificity)} |")
            lines.append(f"| Balanced Accuracy | {_fmt_pct(cls.balanced_accuracy)} |")
            lines.append(f"| True Positives | {cls.true_positives} |")
            lines.append(f"| True Negatives | {cls.true_negatives} |")
            lines.append(f"| False Positives | {cls.false_positives} |")
            lines.append(f"| False Negatives | {cls.false_negatives} |")
            lines.append(f"| Total | {cls.total} |")
            lines.append("")
            lines.append("### Confusion Matrix\n")
            lines.append("```")
            lines.append(f"              Gold INCLUDE  Gold EXCLUDE")
            lines.append(f"APOLLO INCLUDE  {cls.true_positives:>6}      {cls.false_positives:>6}")
            lines.append(f"APOLLO EXCLUDE  {cls.false_negatives:>6}      {cls.true_negatives:>6}")
            lines.append("```\n")
        saf = getattr(metrics, 'safety', None)
        if saf:
            lines.append("## Safety Metrics\n")
            lines.append(f"| Metric | Value |")
            lines.append(f"|--------|-------|")
            lines.append(f"| False Inclusion Rate | {_fmt_pct(saf.false_inclusion_rate)} |")
            lines.append(f"| False Exclusion Rate | {_fmt_pct(saf.false_exclusion_rate)} |")
            lines.append(f"| Catastrophic False Exclusions | {saf.catastrophic_false_exclusions} |")
            lines.append(f"| Catastrophic Exclusion Rate | {_fmt_pct(saf.catastrophic_false_exclusion_rate)} |")
            lines.append(f"| Total Human-Included Papers | {saf.total_human_included} |")
            lines.append(f"| Safe Autonomous Rate | {_fmt_pct(saf.safe_autonomous_rate)} |")
            lines.append("")
        aut = getattr(metrics, 'autonomy', None)
        if aut:
            lines.append("## Autonomy Metrics\n")
            lines.append(f"| Metric | Value |")
            lines.append(f"|--------|-------|")
            lines.append(f"| Autonomous Coverage | {_fmt_pct(aut.autonomous_coverage)} |")
            lines.append(f"| Human Review Reduction | {_fmt_pct(aut.human_review_reduction_pct)} |")
            lines.append(f"| Abstention Rate | {_fmt_pct(aut.abstention_rate)} |")
            lines.append(f"| Escalation Rate | {_fmt_pct(aut.escalation_rate)} |")
            lines.append(f"| Autonomous Precision | {_fmt_pct(aut.autonomous_precision)} |")
            lines.append(f"| Autonomous Recall | {_fmt_pct(aut.autonomous_recall)} |")
            lines.append(f"| Autonomous F1 | {_fmt_pct(aut.autonomous_f1)} |")
            lines.append(f"| Autonomous Agreement | {_fmt_pct(aut.autonomous_agreement_rate)} |")
            lines.append(f"| Total Autonomous | {aut.total_autonomous} |")
            lines.append(f"| Total Human Review | {aut.total_human_review} |")
            lines.append(f"| Total Abstained | {aut.total_abstained} |")
            lines.append(f"| Total Escalated | {aut.total_escalated} |")
            lines.append("")
        cal = getattr(metrics, 'calibration', None)
        if cal:
            lines.append("## Calibration Metrics\n")
            lines.append(f"| Metric | Value |")
            lines.append(f"|--------|-------|")
            lines.append(f"| Expected Calibration Error (ECE) | {_fmt_num(cal.expected_calibration_error)} |")
            lines.append(f"| Maximum Calibration Error (MCE) | {_fmt_num(cal.maximum_calibration_error)} |")
            lines.append(f"| Confidence-Correctness Correlation | {_fmt_num(cal.confidence_correctness_correlation)} |")
            lines.append(f"| Number of Bins | {cal.bin_count} |")
            lines.append("")
            lines.append("### Calibration Bin Details\n")
            lines.append(f"| Bin | Range | Count | Avg Confidence | Accuracy | Gap |")
            lines.append(f"|-----|-------|-------|----------------|----------|-----|")
            for b in cal.bins:
                lines.append(
                    f"| {b['bin']} | [{b['low']:.1f}, {b['high']:.1f}) | "
                    f"{b['count']} | {_fmt_pct(b['avg_confidence'])} | "
                    f"{_fmt_pct(b['accuracy'])} | {_fmt_pct(b['gap'])} |"
                )
            lines.append("")
        que = getattr(metrics, 'queue', None)
        if que:
            lines.append("## Queue Distribution\n")
            lines.append(f"| Routing | Count | Percentage |")
            lines.append(f"|---------|-------|------------|")
            lines.append(f"| AUTO_INCLUDE | {que.auto_include} | {_fmt_pct(que.auto_include / que.total) if que.total else 'N/A'} |")
            lines.append(f"| AUTO_EXCLUDE | {que.auto_exclude} | {_fmt_pct(que.auto_exclude / que.total) if que.total else 'N/A'} |")
            lines.append(f"| HUMAN_REVIEW | {que.human_review} | {_fmt_pct(que.human_review / que.total) if que.total else 'N/A'} |")
            lines.append(f"| ESCALATE | {que.escalate} | {_fmt_pct(que.escalate / que.total) if que.total else 'N/A'} |")
            lines.append(f"| UNCERTAIN | {que.uncertain} | {_fmt_pct(que.uncertain / que.total) if que.total else 'N/A'} |")
            lines.append("")
        if error_analysis:
            lines.append("## Error Analysis\n")
            cat_counts: Dict[str, int] = {}
            cat_severity: Dict[str, List[str]] = {}
            for err in error_analysis:
                for cat in err.get("categories", []):
                    cat_counts[cat] = cat_counts.get(cat, 0) + 1
                    sev = err.get("severity", "unknown")
                    if cat not in cat_severity:
                        cat_severity[cat] = []
                    cat_severity[cat].append(sev)
            lines.append("### Error Category Distribution\n")
            lines.append(f"| Category | Count | Percentage | Most Common Severity |")
            lines.append(f"|----------|-------|------------|---------------------|")
            sorted_cats = sorted(cat_counts.items(), key=lambda x: x[1], reverse=True)
            total_errors = sum(cat_counts.values())
            for cat, count in sorted_cats:
                sevs = cat_severity.get(cat, [])
                most_common = max(set(sevs), key=sevs.count) if sevs else "unknown"
                lines.append(f"| {cat} | {count} | {_fmt_pct(count / total_errors) if total_errors else 'N/A'} | {most_common} |")
            lines.append("")
            lines.append("### Detailed Error List\n")
            for i, err in enumerate(error_analysis[:20]):
                lines.append(f"{i+1}. **{err.get('article_id', 'unknown')}** — {err.get('description', '')}")
                lines.append(f"   - APOLLO: `{err.get('apollo_decision', '')}` → Gold: `{err.get('gold_decision', '')}`")
                lines.append(f"   - Categories: {', '.join(err.get('categories', []))}")
                lines.append(f"   - Severity: {err.get('severity', '')}")
                lines.append(f"   - Rationale: {err.get('rationale', '')}")
                lines.append("")
            if len(error_analysis) > 20:
                lines.append(f"... and {len(error_analysis) - 20} more errors\n")
        if threshold_analysis:
            lines.append("## Threshold Comparison\n")
            lines.append("| Config | Coverage | Safety | Agreement | FP Rate | FN Rate |")
            lines.append("|--------|----------|--------|-----------|---------|---------|")
            for ta in threshold_analysis:
                cfg = ta.get("config", {})
                cov = ta.get("autonomous_coverage", 0)
                safe = ta.get("safety_score", 0)
                agree = ta.get("autonomous_agreement", 0)
                fp = ta.get("false_positive_rate", 0)
                fn = ta.get("false_negative_rate", 0)
                lines.append(
                    f"| {cfg.get('name', 'unknown')} | {_fmt_pct(cov)} | "
                    f"{_fmt_pct(safe)} | {_fmt_pct(agree)} | "
                    f"{_fmt_pct(fp)} | {_fmt_pct(fn)} |"
                )
            lines.append("")
        lines.append("---\n")
        lines.append("*Report generated by APOLLO Evaluation Framework*\n")
        return "\n".join(lines)

    @staticmethod
    def generate_json_report(
        metrics: Any,
        error_analysis: Optional[List[Dict]] = None,
        threshold_analysis: Optional[List[Dict]] = None,
        experiment_name: str = "default",
        protocol_version: str = "1.0",
        dataset_name: str = "benchmark",
        dataset_size: int = 0,
        stage: str = "ec",
    ) -> str:
        report = {
            "report_type": "apollo_evaluation",
            "experiment_name": experiment_name,
            "protocol_version": protocol_version,
            "dataset_name": dataset_name,
            "dataset_size": dataset_size,
            "stage": stage,
            "generated_at": __import__("datetime").datetime.now().isoformat(),
            "metrics": metrics.to_dict() if hasattr(metrics, 'to_dict') else {},
            "error_analysis": error_analysis or [],
            "threshold_comparison": threshold_analysis or [],
        }
        return json.dumps(report, indent=2, default=str)

    @staticmethod
    def generate_confusion_matrix_csv(
        true_positives: int, false_positives: int,
        false_negatives: int, true_negatives: int,
    ) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["", "Gold INCLUDE", "Gold EXCLUDE"])
        writer.writerow(["APOLLO INCLUDE", true_positives, false_positives])
        writer.writerow(["APOLLO EXCLUDE", false_negatives, true_negatives])
        return output.getvalue()

    @staticmethod
    def generate_error_csv(error_analysis: List[Dict]) -> str:
        if not error_analysis:
            return ""
        output = io.StringIO()
        fieldnames = [
            "article_id", "apollo_decision", "gold_decision",
            "confidence", "severity", "categories", "description", "rationale",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for err in error_analysis:
            row = dict(err)
            if isinstance(row.get("categories"), list):
                row["categories"] = "; ".join(row["categories"])
            writer.writerow(row)
        return output.getvalue()

    @staticmethod
    def write_report_files(
        output_dir: str,
        experiment_name: str,
        markdown_content: str,
        json_content: str,
        confusion_csv: str = "",
        error_csv: str = "",
        simulation_report: Optional[Dict] = None,
    ) -> Dict[str, str]:
        os.makedirs(output_dir, exist_ok=True)
        paths = {}
        md_path = os.path.join(output_dir, f"{experiment_name}_report.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        paths["markdown"] = md_path
        json_path = os.path.join(output_dir, f"{experiment_name}_report.json")
        with open(json_path, "w", encoding="utf-8") as f:
            f.write(json_content)
        paths["json"] = json_path
        if confusion_csv:
            csv_path = os.path.join(output_dir, f"{experiment_name}_confusion_matrix.csv")
            with open(csv_path, "w", encoding="utf-8") as f:
                f.write(confusion_csv)
            paths["confusion_csv"] = csv_path
        if error_csv:
            err_path = os.path.join(output_dir, f"{experiment_name}_errors.csv")
            with open(err_path, "w", encoding="utf-8") as f:
                f.write(error_csv)
            paths["error_csv"] = err_path
        if simulation_report:
            sim_path = os.path.join(output_dir, f"{experiment_name}_simulation.json")
            with open(sim_path, "w", encoding="utf-8") as f:
                json.dump(simulation_report, f, indent=2, default=str)
            paths["simulation"] = sim_path
        return paths
