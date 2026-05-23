"""Phase 5A: Deterministic consensus protocol engine.

Primary pipeline:
  RULES -> HARD NEGATIVES -> STUDY TYPE -> LEXICON -> SEMANTIC -> CONSENSUS
  => INCLUDE / EXCLUDE / REVIEW

LLM is never required. REVIEW is a valid terminal state.
"""

from typing import Dict, List, Optional, Any

from .screening_result import ScreeningDecision, ScreeningResult, Evidence
from .deterministic_rules import RuleEngine
from .confidence_engine import ConfidenceEngine
from .hard_negative_filter import HardNegativeFilter
from .study_type_detector import StudyTypeDetector
from .domain_lexicon import DomainLexiconEngine
from .consensus_engine import ConsensusEngine
from .semantic_ranker import SemanticRanker


class ProtocolEngine:
    """Phase 5A: Orchestrates the full deterministic consensus pipeline.

    Combines rule-based, semantic, hard-negative, study-type, and lexicon
    evidence into a single consensus decision. Never requires LLM.
    """

    def __init__(
        self,
        rule_engine: RuleEngine,
        confidence_engine: ConfidenceEngine,
        hard_negative_filter: Optional[HardNegativeFilter] = None,
        study_type_detector: Optional[StudyTypeDetector] = None,
        domain_lexicon: Optional[DomainLexiconEngine] = None,
        consensus_engine: Optional[ConsensusEngine] = None,
        semantic_ranker: Optional[SemanticRanker] = None,
    ) -> None:
        self._rule_engine = rule_engine
        self._confidence_engine = confidence_engine
        self._hard_negative_filter = hard_negative_filter or HardNegativeFilter()
        self._study_type_detector = study_type_detector or StudyTypeDetector()
        self._domain_lexicon = domain_lexicon or DomainLexiconEngine()
        self._consensus_engine = consensus_engine or ConsensusEngine()
        self._semantic_ranker = semantic_ranker

    def execute(
        self,
        article: Dict[str, Any],
        stage: str = "ec",
    ) -> ScreeningResult:
        """Execute the full deterministic consensus pipeline."""
        article_id = (
            article.get("id")
            or article.get("article_id")
            or article.get("doi", "unknown")
        )

        title = article.get("title") or ""
        abstract = article.get("abstract") or ""

        # 1. Rule-based evidence
        rule_evidence, triggered_ids = self._rule_engine.evaluate_all(article)
        rule_confidence, rule_provenance = self._confidence_engine.compute(
            rule_evidence
        )

        # 2. Hard-negative filter
        hn_title = article.get("title") or ""
        hn_abstract = article.get("abstract") or ""
        hn_full = article.get("full_text") or article.get("text") or ""
        is_hard_neg, hn_evidence, hn_count = (
            self._hard_negative_filter.evaluate(hn_title, hn_abstract, hn_full)
        )

        hard_negative_evidence = hn_evidence if is_hard_neg else None

        # 3. Study type detection
        doc_type = article.get("document_type") or article.get("type") or ""
        venue = article.get("venue") or article.get("journal") or ""
        study_type, type_scores, type_rationale = (
            self._study_type_detector.classify(
                title=title,
                abstract=abstract,
                document_type=doc_type,
                venue=venue,
            )
        )
        study_type_bonus = self._study_type_detector.get_confidence_bonus(
            study_type
        )

        # 4. Domain lexicon
        lexicon_evidence = self._domain_lexicon.evaluate(
            title=title,
            abstract=abstract,
            stage=stage,
        )
        lexicon_score = self._domain_lexicon.compute_lexicon_score(
            title=title,
            abstract=abstract,
            stage=stage,
        )

        # 5. Semantic signals
        semantic_signals: Dict[str, float] = {}
        if self._semantic_ranker:
            query = f"{title} {abstract}"
            try:
                semantic_signals = self._semantic_ranker.aggregate_signals(
                    query
                )
            except Exception:
                semantic_signals = {}

        # 6. Compute metadata boost
        metadata_boost = 0.0
        for ev in rule_evidence:
            if ev.evidence_type in (
                "metadata", "publication_year", "venue",
                "language", "document_type",
            ):
                metadata_boost += ev.confidence * 0.1
        metadata_boost = min(metadata_boost, 0.3)

        # 7. Consensus
        result = self._consensus_engine.build_result(
            article_id=article_id,
            rule_evidence=rule_evidence,
            triggered_rules=triggered_ids,
            rule_confidence=rule_confidence,
            semantic_signals=semantic_signals,
            hard_negative_evidence=hard_negative_evidence,
            study_type=study_type,
            study_type_bonus=study_type_bonus,
            lexicon_evidence=lexicon_evidence,
            lexicon_score=lexicon_score,
            metadata_boost=metadata_boost,
            processing_stage=stage,
            rationale_extra=type_rationale if study_type != "unknown" else "",
        )

        return result

    def set_semantic_ranker(
        self, ranker: SemanticRanker
    ) -> None:
        self._semantic_ranker = ranker

    def set_domain_lexicon(self, lexicon: DomainLexiconEngine) -> None:
        self._domain_lexicon = lexicon
