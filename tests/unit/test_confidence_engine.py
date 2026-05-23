"""Tests for confidence_engine.py — Phase 4B weight registry + Phase 4A defenses."""

import pytest
from src.screening.confidence_engine import (
    ConfidenceEngine,
    EvidenceWeight,
    WEIGHT_REGISTRY,
    get_weight,
)
from src.screening.screening_result import ScreeningDecision, Evidence


def make_engine(**kwargs):
    return ConfidenceEngine(**kwargs)


class TestWeightRegistry:
    def test_all_types_have_weights(self):
        for etype in ["keyword", "regex", "exclusion_pattern",
                       "inclusion_pattern", "metadata", "publication_year",
                       "venue", "language", "document_type"]:
            w = get_weight(etype)
            assert isinstance(w, EvidenceWeight)
            assert w.base_weight > 0

    def test_unknown_type_falls_back(self):
        w = get_weight("unknown_type")
        assert w.base_weight == 0.3
        assert w.requires_corroboration is True

    def test_exclusionary_types(self):
        assert get_weight("exclusion_pattern").is_exclusionary is True
        assert get_weight("keyword").is_exclusionary is False

    def test_metadata_types_require_corroboration(self):
        for etype in ["metadata", "publication_year", "venue", "language", "document_type"]:
            assert get_weight(etype).requires_corroboration is True


class TestConfidenceEngineCompute:
    def test_no_evidence_returns_zero(self):
        engine = make_engine()
        score, prov = engine.compute([])
        assert score == 0.0
        assert prov["include_score"] == 0.0
        assert prov["exclude_score"] == 0.0

    def test_include_evidence(self):
        engine = make_engine()
        ev = [Evidence(rule_id="r1", rule_name="t", evidence_type="keyword", match="x")]
        score, prov = engine.compute(ev)
        assert score > 0.0
        assert prov["include_score"] > 0

    def test_exclude_evidence(self):
        engine = make_engine()
        ev = [Evidence(rule_id="r1", rule_name="t", evidence_type="exclusion_pattern", match="x")]
        score, prov = engine.compute(ev)
        assert score < 0.0
        assert prov["exclude_score"] > 0

    def test_mixed_evidence(self):
        engine = make_engine()
        ev = [
            Evidence("r1", "inc", "keyword", "a"),
            Evidence("r2", "exc", "exclusion_pattern", "b"),
        ]
        score, prov = engine.compute(ev)
        assert prov["has_include"] is True
        assert prov["has_exclude"] is True

    def test_with_semantic_signals(self):
        engine = make_engine()
        ev = [Evidence("r1", "t", "keyword", "x", confidence=0.5)]
        _, prov_without = engine.compute(ev)
        score_with, prov_with = engine.compute(ev, semantic_signals={"tfidf_max": 0.8})
        assert prov_with["semantic_boost"] > 0

    def test_clamps_to_one(self):
        engine = make_engine()
        ev = [Evidence("r1", "t", "keyword", "x")]
        score, prov = engine.compute(ev)
        assert score <= 1.0

    def test_clamps_to_minus_one(self):
        engine = make_engine()
        ev = [Evidence("r1", "t", "exclusion_pattern", "x")]
        score, prov = engine.compute(ev)
        assert score >= -1.0

    def test_provenance_has_breakdown(self):
        engine = make_engine()
        ev = [Evidence("r1", "t", "keyword", "x")]
        _, prov = engine.compute(ev)
        assert len(prov["evidence_breakdown"]) == 1
        assert prov["evidence_breakdown"][0]["rule_id"] == "r1"


class TestConfidenceEngineClassify:
    def test_include(self):
        engine = make_engine(include_threshold=0.6)
        assert engine.classify(0.7) == ScreeningDecision.INCLUDE
        assert engine.classify(0.6) == ScreeningDecision.INCLUDE
        assert engine.classify(0.5) == ScreeningDecision.REVIEW

    def test_exclude(self):
        engine = make_engine(exclude_threshold=0.6)
        assert engine.classify(-0.7) == ScreeningDecision.EXCLUDE
        assert engine.classify(-0.6) == ScreeningDecision.EXCLUDE
        assert engine.classify(-0.5) == ScreeningDecision.REVIEW

    def test_review(self):
        engine = make_engine()
        assert engine.classify(0.0) == ScreeningDecision.REVIEW


class TestConfidenceEngineEscalation:
    def test_no_evidence_escalates(self):
        engine = make_engine()
        escalate, reasons = engine.requires_escalation(
            ScreeningDecision.INCLUDE, 0.0, []
        )
        assert escalate is True
        assert "no deterministic evidence" in reasons

    def test_uncertain_escalates(self):
        engine = make_engine()
        ev = [Evidence("r1", "t", "keyword", "x")]
        escalate, reasons = engine.requires_escalation(
            ScreeningDecision.UNCERTAIN, 0.0, ev
        )
        assert escalate is True

    def test_low_confidence_escalates(self):
        engine = make_engine(escalation_threshold=0.5)
        ev = [Evidence("r1", "t", "keyword", "x")]
        escalate, reasons = engine.requires_escalation(
            ScreeningDecision.INCLUDE, 0.3, ev
        )
        assert escalate is True
        assert "low confidence" in reasons

    def test_conflicting_signals_escalates(self):
        engine = make_engine()
        ev = [
            Evidence("r1", "a", "keyword", "x"),
            Evidence("r2", "b", "exclusion_pattern", "y"),
        ]
        escalate, reasons = engine.requires_escalation(
            ScreeningDecision.INCLUDE, 0.9, ev
        )
        assert escalate is True
        assert "conflicting" in " ".join(reasons)

    def test_clean_no_escalation(self):
        engine = make_engine()
        ev = [Evidence("r1", "t", "keyword", "x")]
        escalate, reasons = engine.requires_escalation(
            ScreeningDecision.INCLUDE, 0.9, ev
        )
        assert escalate is False
        assert reasons == []

    def test_weak_exclusion_escalates(self):
        engine = make_engine()
        ev = [Evidence("r1", "t", "publication_year", "2020", confidence=0.5)]
        escalate, reasons = engine.requires_escalation(
            ScreeningDecision.EXCLUDE, 0.7, ev
        )
        assert escalate is True

    def test_clean_exclude_no_escalation(self):
        engine = make_engine()
        ev = [Evidence("r1", "t", "exclusion_pattern", "x")]
        escalate, reasons = engine.requires_escalation(
            ScreeningDecision.EXCLUDE, 0.9, ev
        )
        assert escalate is False


class TestHasConflictingSignals:
    def test_conflicting(self):
        assert ConfidenceEngine._has_conflicting_signals([
            Evidence("r1", "a", "keyword", "x"),
            Evidence("r2", "b", "exclusion_pattern", "y"),
        ]) is True

    def test_no_conflict_include_only(self):
        assert ConfidenceEngine._has_conflicting_signals([
            Evidence("r1", "a", "keyword", "x"),
        ]) is False

    def test_no_conflict_exclude_only(self):
        assert ConfidenceEngine._has_conflicting_signals([
            Evidence("r1", "a", "exclusion_pattern", "x"),
        ]) is False

    def test_empty(self):
        assert ConfidenceEngine._has_conflicting_signals([]) is False
