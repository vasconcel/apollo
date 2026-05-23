"""Tests for screening_result.py."""

import json
import pytest
from src.screening.screening_result import (
    ScreeningDecision,
    Evidence,
    ScreeningResult,
)


class TestScreeningDecision:
    def test_enum_values(self):
        assert ScreeningDecision.INCLUDE.value == "INCLUDE"
        assert ScreeningDecision.EXCLUDE.value == "EXCLUDE"
        assert ScreeningDecision.UNCERTAIN.value == "UNCERTAIN"

    def test_from_string(self):
        assert ScreeningDecision("INCLUDE") == ScreeningDecision.INCLUDE
        assert ScreeningDecision("EXCLUDE") == ScreeningDecision.EXCLUDE
        assert ScreeningDecision("UNCERTAIN") == ScreeningDecision.UNCERTAIN


class TestEvidence:
    def test_create_minimal(self):
        ev = Evidence(rule_id="r1", rule_name="test", evidence_type="keyword", match="foo")
        assert ev.rule_id == "r1"
        assert ev.rule_name == "test"
        assert ev.evidence_type == "keyword"
        assert ev.match == "foo"
        assert ev.context is None
        assert ev.confidence == 1.0

    def test_create_full(self):
        ev = Evidence(
            rule_id="r1",
            rule_name="test",
            evidence_type="keyword",
            match="foo",
            context="matched in title",
            confidence=0.8,
        )
        assert ev.context == "matched in title"
        assert ev.confidence == 0.8

    def test_immutable(self):
        ev = Evidence(rule_id="r1", rule_name="t", evidence_type="k", match="m")
        with pytest.raises(Exception):
            ev.confidence = 0.5

    def test_to_dict_default(self):
        ev = Evidence(rule_id="r1", rule_name="t", evidence_type="k", match="m")
        d = ev.to_dict()
        assert d == {
            "rule_id": "r1",
            "rule_name": "t",
            "evidence_type": "k",
            "match": "m",
        }

    def test_to_dict_with_context_and_confidence(self):
        ev = Evidence(
            rule_id="r1", rule_name="t", evidence_type="k", match="m",
            context="ctx", confidence=0.7,
        )
        d = ev.to_dict()
        assert d["context"] == "ctx"
        assert d["confidence"] == 0.7

    def test_from_dict(self):
        d = {"rule_id": "r1", "rule_name": "t", "evidence_type": "k", "match": "m"}
        ev = Evidence.from_dict(d)
        assert ev.rule_id == "r1"
        assert ev.confidence == 1.0

    def test_from_dict_with_context(self):
        d = {"rule_id": "r1", "rule_name": "t", "evidence_type": "k", "match": "m", "context": "c", "confidence": 0.5}
        ev = Evidence.from_dict(d)
        assert ev.context == "c"
        assert ev.confidence == 0.5

    def test_roundtrip(self):
        ev = Evidence(rule_id="r1", rule_name="t", evidence_type="k", match="m", context="c", confidence=0.9)
        assert Evidence.from_dict(ev.to_dict()) == ev


class TestScreeningResult:
    def test_create_minimal(self):
        result = ScreeningResult(
            article_id="art1",
            decision=ScreeningDecision.INCLUDE,
            confidence=0.85,
        )
        assert result.article_id == "art1"
        assert result.decision == ScreeningDecision.INCLUDE
        assert result.confidence == 0.85
        assert result.evidence == []
        assert result.triggered_rules == []
        assert result.semantic_signals == {}
        assert result.escalation_required is False

    def test_create_with_evidence(self):
        ev = Evidence(rule_id="r1", rule_name="kw", evidence_type="keyword", match="test")
        result = ScreeningResult(
            article_id="art1",
            decision=ScreeningDecision.INCLUDE,
            confidence=0.9,
            evidence=[ev],
            triggered_rules=["r1"],
            escalation_required=True,
            processing_stage="ec",
        )
        assert len(result.evidence) == 1
        assert result.evidence[0] == ev
        assert result.escalation_required is True

    def test_immutable(self):
        result = ScreeningResult(article_id="a", decision=ScreeningDecision.INCLUDE, confidence=0.5)
        with pytest.raises(Exception):
            result.decision = ScreeningDecision.EXCLUDE

    def test_to_dict(self):
        ev = Evidence(rule_id="r1", rule_name="kw", evidence_type="keyword", match="test")
        result = ScreeningResult(
            article_id="art1",
            decision=ScreeningDecision.INCLUDE,
            confidence=0.9,
            evidence=[ev],
            triggered_rules=["r1"],
            semantic_signals={"tfidf_max": 0.8},
            escalation_required=True,
            rationale="test",
            processing_stage="ec",
        )
        d = result.to_dict()
        assert d["article_id"] == "art1"
        assert d["decision"] == "INCLUDE"
        assert d["confidence"] == 0.9
        assert len(d["evidence"]) == 1
        assert d["triggered_rules"] == ["r1"]
        assert d["semantic_signals"] == {"tfidf_max": 0.8}
        assert d["escalation_required"] is True
        assert d["rationale"] == "test"
        assert d["processing_stage"] == "ec"
        assert "created_at" in d

    def test_from_dict(self):
        d = {
            "article_id": "art1",
            "decision": "INCLUDE",
            "confidence": 0.85,
            "evidence": [{"rule_id": "r1", "rule_name": "kw", "evidence_type": "keyword", "match": "test"}],
            "triggered_rules": ["r1"],
            "semantic_signals": {},
            "escalation_required": False,
            "rationale": "",
            "processing_stage": "ec",
            "created_at": "2026-01-01T00:00:00",
        }
        result = ScreeningResult.from_dict(d)
        assert result.article_id == "art1"
        assert result.decision == ScreeningDecision.INCLUDE
        assert result.confidence == 0.85
        assert len(result.evidence) == 1

    def test_roundtrip_dict(self):
        ev = Evidence(rule_id="r1", rule_name="kw", evidence_type="keyword", match="test")
        original = ScreeningResult(
            article_id="art1",
            decision=ScreeningDecision.EXCLUDE,
            confidence=0.75,
            evidence=[ev],
            triggered_rules=["r1"],
            escalation_required=False,
        )
        restored = ScreeningResult.from_dict(original.to_dict())
        assert restored == original

    def test_to_json(self):
        ev = Evidence(rule_id="r1", rule_name="kw", evidence_type="keyword", match="test")
        result = ScreeningResult(
            article_id="art1",
            decision=ScreeningDecision.INCLUDE,
            confidence=0.9,
            evidence=[ev],
        )
        s = result.to_json()
        parsed = json.loads(s)
        assert parsed["article_id"] == "art1"
        assert parsed["decision"] == "INCLUDE"

    def test_from_json(self):
        s = json.dumps({
            "article_id": "art1",
            "decision": "INCLUDE",
            "confidence": 0.85,
            "evidence": [],
            "triggered_rules": [],
            "semantic_signals": {},
            "escalation_required": False,
            "rationale": "",
            "processing_stage": "ec",
            "created_at": "2026-01-01T00:00:00",
        })
        result = ScreeningResult.from_json(s)
        assert result.article_id == "art1"
        assert result.decision == ScreeningDecision.INCLUDE

    def test_roundtrip_json(self):
        ev = Evidence(rule_id="r1", rule_name="kw", evidence_type="keyword", match="test")
        original = ScreeningResult(
            article_id="art1",
            decision=ScreeningDecision.INCLUDE,
            confidence=0.9,
            evidence=[ev],
        )
        restored = ScreeningResult.from_json(original.to_json())
        assert restored == original
