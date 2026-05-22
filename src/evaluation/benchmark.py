"""
APOLLO Evaluation: Gold Standard Benchmark Support

Loads benchmark datasets, compares APOLLO decisions against
human-reviewed gold labels, and produces comparison records.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import csv
import json
import os


@dataclass
class BenchmarkItem:
    article_id: str
    title: str = ""
    abstract: str = ""
    gold_decision: str = ""
    human_rationale: str = ""
    stage: str = "ec"
    protocol_version: str = "1.0"
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_csv_row(cls, row: Dict[str, str]) -> "BenchmarkItem":
        return cls(
            article_id=row.get("article_id", row.get("id", "")),
            title=row.get("title", ""),
            abstract=row.get("abstract", ""),
            gold_decision=row.get("gold_decision", row.get("decision", "")),
            human_rationale=row.get("human_rationale", row.get("rationale", "")),
            stage=row.get("stage", "ec"),
            protocol_version=row.get("protocol_version", "1.0"),
            metadata={k: v for k, v in row.items()
                      if k not in ("article_id", "id", "title", "abstract",
                                   "gold_decision", "decision", "human_rationale",
                                   "rationale", "stage", "protocol_version")},
        )

    @classmethod
    def from_json_item(cls, item: Dict[str, Any]) -> "BenchmarkItem":
        return cls(
            article_id=item.get("article_id", item.get("id", "")),
            title=item.get("title", ""),
            abstract=item.get("abstract", ""),
            gold_decision=item.get("gold_decision", item.get("decision", "")),
            human_rationale=item.get("human_rationale", item.get("rationale", "")),
            stage=item.get("stage", "ec"),
            protocol_version=item.get("protocol_version", "1.0"),
            metadata={k: v for k, v in item.items()
                      if k not in ("article_id", "id", "title", "abstract",
                                   "gold_decision", "decision", "human_rationale",
                                   "rationale", "stage", "protocol_version")},
        )


@dataclass
class ComparisonRecord:
    article_id: str
    title: str
    abstract: str
    gold_decision: str
    human_rationale: str
    apollo_decision: str
    apollo_confidence: float
    apollo_routing: str
    apollo_justification: str
    apollo_grounding_evidence: List[str]
    apollo_uncertainty_reasoning: str
    apollo_domain_alignment_reasoning: str
    apollo_topic_relevance: Dict[str, float]
    apollo_triggered_criteria: List[str]
    apollo_autonomous_eligible: bool
    is_correct: bool
    stage: str
    protocol_version: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "article_id": self.article_id,
            "title": self.title,
            "abstract": self.abstract,
            "gold_decision": self.gold_decision,
            "human_rationale": self.human_rationale,
            "apollo_decision": self.apollo_decision,
            "apollo_confidence": self.apollo_confidence,
            "apollo_routing": self.apollo_routing,
            "apollo_justification": self.apollo_justification,
            "apollo_grounding_evidence": self.apollo_grounding_evidence,
            "apollo_uncertainty_reasoning": self.apollo_uncertainty_reasoning,
            "apollo_domain_alignment_reasoning": self.apollo_domain_alignment_reasoning,
            "apollo_topic_relevance": self.apollo_topic_relevance,
            "apollo_triggered_criteria": self.apollo_triggered_criteria,
            "apollo_autonomous_eligible": self.apollo_autonomous_eligible,
            "is_correct": self.is_correct,
            "stage": self.stage,
            "protocol_version": self.protocol_version,
        }


@dataclass
class BenchmarkDataset:
    name: str
    items: List[BenchmarkItem]
    stage: str
    description: str = ""

    def __len__(self) -> int:
        return len(self.items)

    def filter_by_stage(self, stage: str) -> "BenchmarkDataset":
        filtered = [i for i in self.items if i.stage == stage]
        return BenchmarkDataset(
            name=f"{self.name}_{stage}",
            items=filtered,
            stage=stage,
            description=f"{self.description} (filtered to {stage})",
        )

    def get_gold_decisions(self) -> List[str]:
        return [i.gold_decision for i in self.items]

    def get_article_ids(self) -> List[str]:
        return [i.article_id for i in self.items]


class BenchmarkLoader:
    """Loads gold-standard benchmark datasets from CSV, JSON, or directory."""

    @staticmethod
    def load_csv(path: str, name: str = "", stage: str = "ec") -> BenchmarkDataset:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Benchmark CSV not found: {path}")
        items: List[BenchmarkItem] = []
        with open(path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                item = BenchmarkItem.from_csv_row(row)
                if not item.stage or item.stage == "unknown":
                    item.stage = stage
                items.append(item)
        base = os.path.splitext(os.path.basename(path))[0]
        return BenchmarkDataset(
            name=name or base,
            items=items,
            stage=stage,
            description=f"Loaded from {path} ({len(items)} items)",
        )

    @staticmethod
    def load_json(path: str, name: str = "", stage: str = "ec") -> BenchmarkDataset:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Benchmark JSON not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            items = [BenchmarkItem.from_json_item(item) for item in data]
        elif isinstance(data, dict):
            items = [BenchmarkItem.from_json_item(item) for item in data.get("items", data.get("data", []))]
        else:
            raise ValueError(f"Unexpected JSON structure in {path}")
        for item in items:
            if not item.stage or item.stage == "unknown":
                item.stage = stage
        base = os.path.splitext(os.path.basename(path))[0]
        return BenchmarkDataset(
            name=name or base,
            items=items,
            stage=stage,
            description=f"Loaded from {path} ({len(items)} items)",
        )


class BenchmarkComparator:
    """Compares APOLLO outputs against gold-standard benchmark labels."""

    @staticmethod
    def compare(
        dataset: BenchmarkDataset,
        apollo_results: Dict[str, Any],
        stage: str = "ec",
    ) -> List[ComparisonRecord]:
        records: List[ComparisonRecord] = []
        for item in dataset.items:
            if item.stage != stage:
                continue
            aid = item.article_id
            apollo = apollo_results.get(aid, {})
            apollo_decision = apollo.get("decision", "UNAVAILABLE")
            gold_decision = item.gold_decision
            apollo_include = apollo_decision.upper().strip() in ("INCLUDE", "AUTO_INCLUDE")
            gold_include = gold_decision.upper().strip() in ("INCLUDE", "AUTO_INCLUDE")
            record = ComparisonRecord(
                article_id=aid,
                title=item.title,
                abstract=item.abstract,
                gold_decision=gold_decision,
                human_rationale=item.human_rationale,
                apollo_decision=apollo_decision,
                apollo_confidence=apollo.get("confidence", 0.0),
                apollo_routing=apollo.get("routing", "HUMAN_REVIEW"),
                apollo_justification=apollo.get("justification", ""),
                apollo_grounding_evidence=apollo.get("grounding_evidence", []),
                apollo_uncertainty_reasoning=apollo.get("uncertainty_reasoning", ""),
                apollo_domain_alignment_reasoning=apollo.get("domain_alignment_reasoning", ""),
                apollo_topic_relevance=apollo.get("topic_relevance", {}),
                apollo_triggered_criteria=apollo.get("triggered_criteria", []),
                apollo_autonomous_eligible=apollo.get("autonomous_eligible", False),
                is_correct=apollo_include == gold_include,
                stage=item.stage,
                protocol_version=item.protocol_version,
                metadata=item.metadata,
            )
            records.append(record)
        return records

    @staticmethod
    def compare_from_advisory_results(
        dataset: BenchmarkDataset,
        advisory_results: Dict[str, "AdvisoryResult"],
    ) -> List[ComparisonRecord]:
        from src.advisory.advisory_models import AdvisoryResult
        apollo_dict: Dict[str, Dict] = {}
        for aid, result in advisory_results.items():
            if isinstance(result, AdvisoryResult):
                assessment = getattr(result, "autonomy_assessment", None)
                routing = (assessment.routing.value if assessment and assessment.routing else "HUMAN_REVIEW")
                is_auto = assessment.autonomous_eligible if assessment else False
                tr = result.topic_relevance
                apollo_dict[aid] = {
                    "decision": result.decision.value if result.decision else "UNAVAILABLE",
                    "confidence": result.confidence,
                    "routing": routing,
                    "justification": result.justification,
                    "grounding_evidence": result.grounding_evidence,
                    "uncertainty_reasoning": "",
                    "domain_alignment_reasoning": "",
                    "topic_relevance": tr.to_dict() if tr else {},
                    "triggered_criteria": result.triggered_criteria,
                    "autonomous_eligible": is_auto,
                }
            else:
                apollo_dict[aid] = result if isinstance(result, dict) else {}
        return BenchmarkComparator.compare(dataset, apollo_dict)

    @staticmethod
    def compare_from_flat_dict(
        dataset: BenchmarkDataset,
        apollo_flat: List[Dict],
        id_key: str = "article_id",
    ) -> List[ComparisonRecord]:
        apollo_by_id: Dict[str, Dict] = {}
        for entry in apollo_flat:
            aid = entry.get(id_key, "")
            if aid:
                apollo_by_id[aid] = entry
        return BenchmarkComparator.compare(dataset, apollo_by_id)
