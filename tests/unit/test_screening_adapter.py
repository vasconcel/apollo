"""Tests for screening_adapter.py — Phase 4 reliability hardening."""

import pytest
from src.advisory.screening_adapter import (
    ScreeningAdapter,
    EscalationPolicy,
    get_screening_adapter,
    reset_screening_adapter,
)
from src.screening.screening_result import (
    ScreeningDecision,
    ScreeningResult,
    Evidence,
)
from src.screening.confidence_engine import ConfidenceEngine


class TestEscalationPolicy:
    def test_no_escalation_include_high_confidence(self):
        article = {"title": "Empirical study on software engineering"}
        result = ScreeningResult(
            article_id="a1",
            decision=ScreeningDecision.INCLUDE,
            confidence=0.8,
            evidence=[Evidence("r1", "Rule", "keyword", "study")],
        )
        assert EscalationPolicy.requires_escalation(result, article) is False

    def test_no_escalation_exclude_strong(self):
        article = {"title": "Job posting for senior developer"}
        result = ScreeningResult(
            article_id="a1",
            decision=ScreeningDecision.EXCLUDE,
            confidence=0.9,
            evidence=[Evidence("r1", "Rule", "exclusion_pattern", "job")],
        )
        assert EscalationPolicy.requires_escalation(result, article) is False

    def test_escalation_uncertain(self):
        article = {"title": "Some paper"}
        result = ScreeningResult(
            article_id="a1",
            decision=ScreeningDecision.UNCERTAIN,
            confidence=0.0,
        )
        assert EscalationPolicy.requires_escalation(result, article) is True

    def test_escalation_low_confidence(self):
        article = {"title": "Ambiguous title"}
        result = ScreeningResult(
            article_id="a1",
            decision=ScreeningDecision.INCLUDE,
            confidence=0.2,
            evidence=[Evidence("r1", "Rule", "keyword", "vague")],
        )
        assert EscalationPolicy.requires_escalation(result, article) is True

    def test_escalation_empty_article(self):
        article = {"title": "", "abstract": ""}
        result = ScreeningResult(
            article_id="a1",
            decision=ScreeningDecision.INCLUDE,
            confidence=0.9,
        )
        assert EscalationPolicy.requires_escalation(result, article) is True

    def test_escalation_low_info_content(self):
        article = {"title": "AB", "abstract": "short"}
        result = ScreeningResult(
            article_id="a1",
            decision=ScreeningDecision.EXCLUDE,
            confidence=0.9,
            evidence=[Evidence("r1", "Rule", "exclusion_pattern", "x")],
        )
        assert EscalationPolicy.requires_escalation(result, article) is True

    def test_escalation_weak_exclusion_no_corroboration(self):
        article = {"title": "Something about 2020"}
        result = ScreeningResult(
            article_id="a1",
            decision=ScreeningDecision.EXCLUDE,
            confidence=0.7,
            evidence=[Evidence("r1", "Rule", "publication_year", "2020")],
        )
        assert EscalationPolicy.requires_escalation(result, article) is True

    def test_no_evidence_escalates(self):
        article = {"title": "Something"}
        result = ScreeningResult(
            article_id="a1",
            decision=ScreeningDecision.INCLUDE,
            confidence=0.5,
        )
        assert EscalationPolicy.requires_escalation(result, article) is True

    def test_escalation_reason(self):
        article = {"title": "", "abstract": ""}
        result = ScreeningResult(
            article_id="a1",
            decision=ScreeningDecision.UNCERTAIN,
            confidence=0.0,
        )
        reason = EscalationPolicy.escalation_reason(result, article)
        assert reason

    def test_weak_exclusion_reason(self):
        article = {"title": "Year 2020 paper"}
        result = ScreeningResult(
            article_id="a1",
            decision=ScreeningDecision.EXCLUDE,
            confidence=0.7,
            evidence=[Evidence("r1", "Rule", "publication_year", "2020")],
        )
        reason = EscalationPolicy.escalation_reason(result, article)
        assert "weak exclusion" in reason


class TestScreeningAdapter:
    def test_initialize_default(self):
        reset_screening_adapter()
        adapter = get_screening_adapter()
        adapter.initialize()
        assert adapter._initialized is True

    def test_run_deterministic_include(self):
        adapter = ScreeningAdapter()
        adapter.initialize()
        result = adapter.run_deterministic(
            {"id": "a1", "title": "Empirical study on software hiring practices"}
        )
        assert result.article_id == "a1"

    def test_run_deterministic_exclude_job_posting(self):
        adapter = ScreeningAdapter()
        adapter.initialize()
        result = adapter.run_deterministic(
            {"id": "a1", "title": "Job Posting: Senior Software Engineer at Google"}
        )
        assert result.decision == ScreeningDecision.EXCLUDE

    def test_run_deterministic_with_protocol_include(self):
        adapter = ScreeningAdapter()
        adapter.initialize(protocol_config={
            "include": ["systematic literature review"],
        })
        result = adapter.run_deterministic(
            {"id": "a1", "title": "A systematic literature review of agile methods"}
        )
        assert result.decision == ScreeningDecision.INCLUDE

    def test_run_deterministic_with_protocol_exclude(self):
        adapter = ScreeningAdapter()
        adapter.initialize(protocol_config={
            "exclude": ["blog post"],
        })
        result = adapter.run_deterministic(
            {"id": "a1", "title": "My Blog Post About Programming"}
        )
        assert result.decision == ScreeningDecision.EXCLUDE

    def test_serialize_evidence(self):
        adapter = ScreeningAdapter()
        adapter.initialize()
        result = adapter.run_deterministic({"id": "a1", "title": "Test"})
        serialized = adapter.serialize_evidence(result)
        assert "decision" in serialized
        assert "evidence" in serialized
        assert "triggered_rules" in serialized

    def test_conference_cfp_excludes(self):
        adapter = ScreeningAdapter()
        adapter.initialize()
        result = adapter.run_deterministic(
            {"id": "a1", "title": "Call for Papers: International Conference on SE"}
        )
        assert result.decision == ScreeningDecision.EXCLUDE

    def test_counters_initialized(self):
        adapter = ScreeningAdapter()
        adapter.initialize()
        snap = adapter.counters_snapshot()
        assert snap["total_articles"] == 0
        assert snap["deterministic_decisions"] == 0
        assert snap["llm_escalations"] == 0

    def test_counters_increment(self):
        adapter = ScreeningAdapter()
        adapter.initialize()
        adapter.run_deterministic(
            {"id": "a1", "title": "Job Posting: Senior Software Engineer at Google"}
        )
        snap = adapter.counters_snapshot()
        assert snap["total_articles"] == 1
        assert snap["deterministic_exclude"] == 1

    def test_get_screening_adapter_singleton(self):
        reset_screening_adapter()
        a1 = get_screening_adapter()
        a2 = get_screening_adapter()
        assert a1 is a2

    def test_reset_screening_adapter(self):
        reset_screening_adapter()
        a1 = get_screening_adapter()
        reset_screening_adapter()
        a2 = get_screening_adapter()
        assert a1 is not a2
