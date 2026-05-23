"""Tests for protocol_engine.py."""

import pytest
from src.screening.protocol_engine import ProtocolEngine
from src.screening.deterministic_rules import (
    KeywordRule,
    ExclusionPatternRule,
    RuleEngine,
)
from src.screening.confidence_engine import ConfidenceEngine
from src.screening.screening_result import ScreeningDecision


ARTICLE = {
    "id": "art001",
    "title": "An Empirical Study on Software Engineering Hiring",
    "abstract": "This paper studies technical recruitment practices.",
    "year": 2023,
}


def make_engine(rules=None):
    rule_engine = RuleEngine()
    if rules:
        rule_engine.add_rules(rules)
    confidence_engine = ConfidenceEngine()
    return ProtocolEngine(rule_engine, confidence_engine)


class TestProtocolEngine:
    def test_execute_include(self):
        rules = [KeywordRule("kw1", "Empirical", keyword="Empirical")]
        engine = make_engine(rules)
        result = engine.execute(ARTICLE)
        assert result.article_id == "art001"
        assert result.decision == ScreeningDecision.INCLUDE
        assert len(result.evidence) == 1
        assert result.triggered_rules == ["kw1"]

    def test_execute_exclude(self):
        rules = [ExclusionPatternRule("exc1", "Blog", patterns=["job advertisement"])]
        article = {"id": "a1", "title": "Job Advertisement for Senior Dev"}
        engine = make_engine(rules)
        result = engine.execute(article)
        assert result.decision == ScreeningDecision.EXCLUDE
        assert result.triggered_rules == ["exc1"]

    def test_execute_review_no_rules(self):
        engine = make_engine([])
        result = engine.execute({"id": "a1", "title": "Something unrelated"})
        assert result.decision == ScreeningDecision.REVIEW
        assert result.confidence == 0.0

    def test_execute_with_article_id_fallbacks(self):
        engine = make_engine([])
        r1 = engine.execute({"doi": "10.1234/test"})
        assert r1.article_id == "10.1234/test"
        r2 = engine.execute({})
        assert r2.article_id == "unknown"

    def test_execute_mixed_signals_review(self):
        rules = [
            KeywordRule("inc1", "Include", keyword="Empirical"),
            ExclusionPatternRule("exc1", "Exclude", patterns=["technical recruitment"]),
        ]
        engine = make_engine(rules)
        result = engine.execute(ARTICLE)
        assert result.decision == ScreeningDecision.REVIEW

    def test_execute_stage_passthrough(self):
        engine = make_engine([])
        result = engine.execute({"id": "a1", "title": "test"}, stage="ic")
        assert result.processing_stage == "ic"

    def test_rationale_with_evidence(self):
        rules = [KeywordRule("kw1", "Test", keyword="Empirical")]
        engine = make_engine(rules)
        result = engine.execute(ARTICLE)
        assert "INCLUDE" in result.rationale
        assert "kw1" in result.rationale or "Test" in result.rationale

    def test_rationale_no_evidence(self):
        engine = make_engine([])
        result = engine.execute({"id": "a1", "title": "x"})
        assert "REVIEW" in result.rationale
        assert "confidence" in result.rationale

    def test_created_at_set(self):
        engine = make_engine([])
        result = engine.execute({"id": "a1", "title": "test"})
        assert result.created_at is not None
        assert "T" in result.created_at
