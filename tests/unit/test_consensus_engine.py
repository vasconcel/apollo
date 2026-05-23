"""Phase 5A: ConsensusEngine tests."""

from src.screening.consensus_engine import ConsensusEngine
from src.screening.screening_result import (
    ScreeningDecision, Evidence, ScreeningResult
)


def make_evidence(rule_id="r1", etype="keyword", match="test", confidence=1.0):
    return [Evidence(rule_id, f"Rule-{rule_id}", etype, match,
                     confidence=confidence)]


class TestConsensusEngine:
    def test_rule_confidence_passthrough(self):
        """Rule confidence is the base — strong rule signals produce correct decisions."""
        engine = ConsensusEngine()
        conf, decision, trace = engine.evaluate(
            rule_evidence=make_evidence("r1", "keyword", "empirical"),
            rule_confidence=0.6,
        )
        assert decision == ScreeningDecision.INCLUDE
        assert conf >= 0.6

    def test_strong_exclude_from_rules(self):
        engine = ConsensusEngine()
        conf, decision, trace = engine.evaluate(
            rule_evidence=make_evidence("r1", "exclusion_pattern", "job"),
            rule_confidence=-0.7,
        )
        assert decision == ScreeningDecision.EXCLUDE
        assert conf <= -0.6

    def test_review_when_uncertain(self):
        engine = ConsensusEngine()
        conf, decision, trace = engine.evaluate(
            rule_evidence=make_evidence("r1", "keyword", "maybe"),
            rule_confidence=0.3,
        )
        assert decision == ScreeningDecision.REVIEW

    def test_hard_negative_overrides(self):
        engine = ConsensusEngine()
        conf, decision, trace = engine.evaluate(
            rule_evidence=[],
            rule_confidence=0.0,
            hard_negative_evidence=[
                Evidence("hn1", "HN", "exclusion_pattern",
                         "job posting", confidence=0.95)
            ],
        )
        assert decision == ScreeningDecision.EXCLUDE
        assert conf >= 0.95
        assert trace.get("hard_negative_override") is True

    def test_semantic_signals_boost_include(self):
        engine = ConsensusEngine()
        conf, decision, trace = engine.evaluate(
            rule_evidence=make_evidence("r1", "keyword", "study"),
            rule_confidence=0.5,
            semantic_signals={"tfidf_max": 0.8, "bm25_max": 0.7},
        )
        assert trace["source_contributions"]["semantic_signals"]["contribution"] > 0

    def test_study_type_bonus_increases_confidence(self):
        engine = ConsensusEngine()
        conf_base, _, _ = engine.evaluate(
            rule_evidence=make_evidence("r1"),
            rule_confidence=0.5,
        )
        conf_bonus, _, _ = engine.evaluate(
            rule_evidence=make_evidence("r1"),
            rule_confidence=0.5,
            study_type="empirical_study",
            study_type_bonus=0.05,
        )
        assert conf_bonus > conf_base

    def test_lexicon_contribution(self):
        engine = ConsensusEngine()
        _, _, trace = engine.evaluate(
            rule_evidence=make_evidence("r1"),
            rule_confidence=0.5,
            lexicon_evidence=[
                Evidence("lx1", "Lex+", "lexicon", "test", confidence=0.6)
            ],
            lexicon_score=0.6,
        )
        assert trace["source_contributions"]["lexicon"]["score"] == 0.6

    def test_provenance_trace_contains_all_sources(self):
        engine = ConsensusEngine()
        _, _, trace = engine.evaluate(
            rule_evidence=make_evidence("r1"),
            rule_confidence=0.5,
            semantic_signals={"tfidf_max": 0.5},
            study_type="systematic_review",
            study_type_bonus=0.05,
            lexicon_evidence=[],
            lexicon_score=0.0,
            metadata_boost=0.1,
        )
        assert "rule_evidence" in trace["source_contributions"]
        assert "semantic_signals" in trace["source_contributions"]
        assert "study_type" in trace["source_contributions"]
        assert "lexicon" in trace["source_contributions"]
        assert "metadata" in trace["source_contributions"]

    def test_build_result_include(self):
        engine = ConsensusEngine()
        result = engine.build_result(
            article_id="a1",
            rule_evidence=make_evidence("r1", "keyword", "empirical"),
            triggered_rules=["r1"],
            rule_confidence=0.6,
        )
        assert result.decision == ScreeningDecision.INCLUDE
        assert result.article_id == "a1"
        assert result.confidence >= 0.6
        assert len(result.evidence) >= 1

    def test_build_result_review(self):
        engine = ConsensusEngine()
        result = engine.build_result(
            article_id="a1",
            rule_evidence=[],
            triggered_rules=[],
            rule_confidence=0.0,
        )
        assert result.decision == ScreeningDecision.REVIEW
        assert result.confidence == 0.0

    def test_build_result_hard_negative(self):
        engine = ConsensusEngine()
        result = engine.build_result(
            article_id="a1",
            rule_evidence=[],
            triggered_rules=[],
            rule_confidence=0.0,
            hard_negative_evidence=[
                Evidence("hn1", "HN", "exclusion_pattern",
                         "job posting", confidence=0.95)
            ],
        )
        assert result.decision == ScreeningDecision.EXCLUDE
        assert result.confidence >= 0.95
        assert result.hard_negative is True

    def test_build_result_study_type_included(self):
        engine = ConsensusEngine()
        result = engine.build_result(
            article_id="a1",
            rule_evidence=make_evidence("r1", "keyword", "review"),
            triggered_rules=["r1"],
            rule_confidence=0.5,
            study_type="systematic_review",
            study_type_bonus=0.05,
        )
        assert result.study_type == "systematic_review"
        assert result.consensus_trace["source_contributions"]["study_type"]["type"] == "systematic_review"

    def test_build_result_rationale_contains_decision(self):
        engine = ConsensusEngine()
        result = engine.build_result(
            article_id="a1",
            rule_evidence=make_evidence("r1"),
            triggered_rules=["r1"],
            rule_confidence=0.6,
        )
        assert "INCLUDE" in result.rationale
        assert "Consensus" in result.rationale

    def test_custom_weights(self):
        engine = ConsensusEngine(weights={"semantic_signals": 0.5})
        _, _, trace = engine.evaluate(
            rule_evidence=make_evidence("r1"),
            rule_confidence=0.5,
            semantic_signals={"tfidf_max": 1.0},
        )
        # semantic contribution = 0.5 * 0.6 = 0.3
        assert trace["source_contributions"]["semantic_signals"]["weight"] == 0.5

    def test_empty_evidence_zero_confidence(self):
        engine = ConsensusEngine()
        conf, decision, trace = engine.evaluate(
            rule_evidence=[],
            rule_confidence=0.0,
        )
        assert conf == 0.0
        assert decision == ScreeningDecision.REVIEW
