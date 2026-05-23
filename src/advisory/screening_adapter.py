"""Phase 5A: LLM-Independent Deterministic Screening Adapter.

LLM is OPTIONAL and DISABLED by default.
REVIEW replaces UNCERTAIN as the low-confidence terminal state.
Human review queue replaces LLM escalation.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from src.screening.protocol_engine import ProtocolEngine
from src.screening.deterministic_rules import (
    RuleEngine,
    RegexRule,
)
from src.screening.confidence_engine import ConfidenceEngine
from src.screening.semantic_ranker import SemanticRanker
from src.screening.screening_result import (
    ScreeningDecision,
    ScreeningResult,
    Evidence,
)
from src.screening.protocol_dsl import DSLCompiler
from src.screening.hard_negative_filter import HardNegativeFilter
from src.screening.study_type_detector import StudyTypeDetector
from src.screening.domain_lexicon import DomainLexiconEngine
from src.screening.consensus_engine import ConsensusEngine


@dataclass
class ScreeningCounters:
    """Lightweight observability counters — no telemetry bus."""

    deterministic_decisions: int = 0
    llm_escalations: int = 0
    deterministic_include: int = 0
    deterministic_exclude: int = 0
    deterministic_review: int = 0
    hard_negative_exclusions: int = 0
    weak_exclusion_escalations: int = 0
    conflict_escalations: int = 0
    empty_metadata_escalations: int = 0
    total_articles: int = 0
    total_time_ms: float = 0.0

    def snapshot(self) -> Dict[str, Any]:
        return {
            "deterministic_decisions": self.deterministic_decisions,
            "llm_escalations": self.llm_escalations,
            "deterministic_include": self.deterministic_include,
            "deterministic_exclude": self.deterministic_exclude,
            "deterministic_review": self.deterministic_review,
            "hard_negative_exclusions": self.hard_negative_exclusions,
            "weak_exclusion_escalations": self.weak_exclusion_escalations,
            "conflict_escalations": self.conflict_escalations,
            "empty_metadata_escalations": self.empty_metadata_escalations,
            "total_articles": self.total_articles,
            "total_time_ms": self.total_time_ms,
            "llm_rate": (
                self.llm_escalations / max(self.total_articles, 1)
            ),
            "deterministic_rate": (
                self.deterministic_decisions / max(self.total_articles, 1)
            ),
        }


class EscalationPolicy:
    """Phase 5A: REVIEW is a valid terminal state — never escalates.

    LLM escalation is disabled by default.
    See Phase 4A for reference (now simplified).
    """

    @staticmethod
    def requires_escalation(
        result: ScreeningResult,
        article: Dict[str, Any],
    ) -> bool:
        if result.hard_negative:
            return False

        if result.decision == ScreeningDecision.REVIEW:
            return False

        if not result.evidence:
            return True

        title = (article.get("title") or "").strip()
        abstract = (article.get("abstract") or "").strip()

        if not title and not abstract:
            return True

        if len(title) < 5 and len(abstract) < 20:
            return True

        if result.decision == ScreeningDecision.INCLUDE:
            if result.confidence >= 0.4:
                return False
            return True

        if result.decision == ScreeningDecision.EXCLUDE:
            if result.confidence >= 0.4:
                if EscalationPolicy._has_only_weak_exclusions(result):
                    return True
                return False
            return True

        return True

    @staticmethod
    def _has_only_weak_exclusions(result: ScreeningResult) -> bool:
        if not result.evidence:
            return False
        all_metadata = all(
            getattr(
                __import__(
                    "src.screening.confidence_engine",
                    fromlist=["get_weight"],
                ).get_weight(ev.evidence_type),
                "requires_corroboration",
                False,
            )
            for ev in result.evidence
        )
        if all_metadata:
            return True
        return False

    @staticmethod
    def escalation_reason(
        result: ScreeningResult, article: Dict[str, Any]
    ) -> str:
        if result.hard_negative:
            return "hard negative exclusion"
        if result.decision == ScreeningDecision.REVIEW:
            return "low confidence — human review"
        reasons = []
        title = (article.get("title") or "").strip()
        abstract = (article.get("abstract") or "").strip()

        if not title and not abstract:
            reasons.append("empty title and abstract")
        elif len(title) < 5 and len(abstract) < 20:
            reasons.append("low-information content")

        if result.decision == ScreeningDecision.EXCLUDE:
            if EscalationPolicy._has_only_weak_exclusions(result):
                reasons.append("weak exclusion without corroboration")

        if not reasons:
            reasons.append("insufficient deterministic evidence")
        return "; ".join(reasons)


class ScreeningAdapter:
    """Phase 5A: Deterministic-first screening adapter.

    LLM is disabled by default. The pipeline produces
    INCLUDE / EXCLUDE / REVIEW decisions deterministically.
    """

    def __init__(self, llm_enabled: bool = False) -> None:
        self._rule_engine: Optional[RuleEngine] = None
        self._protocol_engine: Optional[ProtocolEngine] = None
        self._semantic_ranker: Optional[SemanticRanker] = None
        self._confidence_engine = ConfidenceEngine()
        self._compiler = DSLCompiler()
        self._hard_negative_filter = HardNegativeFilter()
        self._study_type_detector = StudyTypeDetector()
        self._domain_lexicon = DomainLexiconEngine()
        self._consensus_engine = ConsensusEngine()
        self._initialized = False
        self._llm_enabled = llm_enabled
        self.counters = ScreeningCounters()

    @property
    def llm_enabled(self) -> bool:
        return self._llm_enabled

    @llm_enabled.setter
    def llm_enabled(self, value: bool) -> None:
        self._llm_enabled = value

    def initialize(
        self,
        protocol_config: Optional[Dict[str, Any]] = None,
        corpus_texts: Optional[List[str]] = None,
        lexicon_config: Optional[Dict[str, Any]] = None,
    ) -> None:
        rule_engine = RuleEngine()
        self._add_builtin_exclusion_rules(rule_engine)

        if protocol_config:
            protocol = self._compiler.compile(protocol_config)
            rules = self._compiler.to_rules(protocol)
            rule_engine.add_rules(rules)

        if lexicon_config:
            self._domain_lexicon.compile(lexicon_config)

        if corpus_texts:
            ranker = SemanticRanker()
            ranker.fit(corpus_texts)
            self._semantic_ranker = ranker

        self._rule_engine = rule_engine
        self._protocol_engine = ProtocolEngine(
            rule_engine,
            self._confidence_engine,
            hard_negative_filter=self._hard_negative_filter,
            study_type_detector=self._study_type_detector,
            domain_lexicon=self._domain_lexicon,
            consensus_engine=self._consensus_engine,
            semantic_ranker=self._semantic_ranker,
        )
        self._initialized = True

    def _add_builtin_exclusion_rules(self, engine: RuleEngine) -> None:
        try:
            from .prefilter import (
                JOBS_PATTERNS,
                UNIVERSITY_PROGRAM_PATTERNS,
                GENERIC_SE_PATTERNS,
                RECRUITMENT_AD_PATTERNS,
                CONFERENCE_PATTERNS,
                INSTITUTIONAL_PATTERNS,
                EDUCATIONAL_PATTERNS,
            )
            pairs = [
                ("pre_exclude_jobs", "Jobs/careers listing", JOBS_PATTERNS),
                ("pre_exclude_univ", "University program page", UNIVERSITY_PROGRAM_PATTERNS),
                ("pre_exclude_se_intro", "Generic SE overview", GENERIC_SE_PATTERNS),
                ("pre_exclude_recruit", "Recruitment advertisement", RECRUITMENT_AD_PATTERNS),
                ("pre_exclude_conf", "Conference homepage or CfP", CONFERENCE_PATTERNS),
                ("pre_exclude_inst", "Institutional page", INSTITUTIONAL_PATTERNS),
                ("pre_exclude_edu", "Educational content", EDUCATIONAL_PATTERNS),
            ]
            for rid, name, pat in pairs:
                pattern = pat.pattern if hasattr(pat, "pattern") else ""
                if pattern:
                    engine.add_rule(
                        RegexRule(
                            rid, name, pattern,
                            evidence_type="exclusion_pattern",
                        )
                    )
        except ImportError:
            pass

    def run_deterministic(
        self,
        article: Dict[str, Any],
        stage: str = "ec",
    ) -> ScreeningResult:
        start = time.monotonic()
        if not self._initialized:
            self.initialize()

        result = self._protocol_engine.execute(article, stage=stage)
        elapsed = (time.monotonic() - start) * 1000

        self.counters.total_articles += 1
        self.counters.total_time_ms += elapsed

        if result.hard_negative:
            self.counters.hard_negative_exclusions += 1
            self.counters.deterministic_decisions += 1
            self.counters.deterministic_exclude += 1
            return result

        if result.decision == ScreeningDecision.REVIEW:
            self.counters.deterministic_review += 1
            self.counters.deterministic_decisions += 1
            return result

        self.counters.deterministic_decisions += 1
        if result.decision == ScreeningDecision.INCLUDE:
            self.counters.deterministic_include += 1
        elif result.decision == ScreeningDecision.EXCLUDE:
            self.counters.deterministic_exclude += 1

        return result

    def run_with_semantic(
        self,
        article: Dict[str, Any],
        stage: str = "ec",
    ) -> ScreeningResult:
        result = self.run_deterministic(article, stage=stage)
        if self._semantic_ranker:
            query = f"{article.get('title', '')} {article.get('abstract', '')}"
            signals = self._semantic_ranker.aggregate_signals(query)
            sem_support = self._semantic_ranker.multi_signal_agreement(query)

            result_dict = result.to_dict()
            result_dict["semantic_signals"] = signals

            if not sem_support["agreement"] and result.decision not in (
                ScreeningDecision.REVIEW,
                ScreeningDecision.EXCLUDE,
            ):
                result_dict["escalation_required"] = self._llm_enabled

            if sem_support["agreement"]:
                confidence, _ = self._confidence_engine.compute(
                    result.evidence, semantic_signals=signals
                )
                result_dict["confidence"] = confidence
                new_decision = self._confidence_engine.classify(confidence)
                result_dict["decision"] = new_decision.value

            result = ScreeningResult.from_dict(result_dict)
        return result

    def serialize_evidence(self, result: ScreeningResult) -> Dict[str, Any]:
        return {
            "decision": result.decision.value,
            "confidence": result.confidence,
            "evidence": [e.to_dict() for e in result.evidence],
            "triggered_rules": list(result.triggered_rules),
            "semantic_signals": dict(result.semantic_signals),
            "escalation_required": result.escalation_required,
            "rationale": result.rationale,
            "processing_stage": result.processing_stage,
            "study_type": result.study_type,
            "hard_negative": result.hard_negative,
            "consensus_trace": dict(result.consensus_trace),
        }

    def counters_snapshot(self) -> Dict[str, Any]:
        return self.counters.snapshot()


_global_adapter: Optional[ScreeningAdapter] = None


def get_screening_adapter() -> ScreeningAdapter:
    global _global_adapter
    if _global_adapter is None:
        _global_adapter = ScreeningAdapter(llm_enabled=False)
    return _global_adapter


def reset_screening_adapter() -> None:
    global _global_adapter
    _global_adapter = None
