"""APOLLO Screening Engine — Phase 5A: Deterministic consensus architecture."""

from .screening_result import ScreeningDecision, Evidence, ScreeningResult
from .deterministic_rules import (
    Rule, KeywordRule, RegexRule, InclusionPatternRule, ExclusionPatternRule,
    MetadataRule, PublicationYearRule, VenueRule, LanguageRule, DocumentTypeRule,
    RuleEngine,
)
from .protocol_dsl import ProtocolDefinition, DSLCompiler
from .protocol_engine import ProtocolEngine
from .semantic_ranker import TfidfVectorizer, BM25Ranker, SemanticRanker
from .confidence_engine import ConfidenceEngine
from .hard_negative_filter import HardNegativeFilter
from .study_type_detector import StudyTypeDetector
from .domain_lexicon import DomainLexiconEngine
from .consensus_engine import ConsensusEngine

__all__ = [
    "ScreeningDecision",
    "Evidence",
    "ScreeningResult",
    "Rule",
    "KeywordRule",
    "RegexRule",
    "InclusionPatternRule",
    "ExclusionPatternRule",
    "MetadataRule",
    "PublicationYearRule",
    "VenueRule",
    "LanguageRule",
    "DocumentTypeRule",
    "RuleEngine",
    "ProtocolDefinition",
    "DSLCompiler",
    "ProtocolEngine",
    "TfidfVectorizer",
    "BM25Ranker",
    "SemanticRanker",
    "ConfidenceEngine",
    "HardNegativeFilter",
    "StudyTypeDetector",
    "DomainLexiconEngine",
    "ConsensusEngine",
]
