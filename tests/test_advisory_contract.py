"""
Deterministic advisory contract validation tests.

Validates the canonical advisory schema contract across all surfaces:
- AdvisoryResult field ownership
- Serialization roundtrip parity
- Stage guard isolation invariants
- Cache roundtrip parity
- Missing/unknown field behavior
- Deterministic invariants
"""

import json
import hashlib
import copy
import pytest

from dataclasses import fields
from src.advisory.advisory_models import (
    AdvisoryResult,
    AdvisoryDecision,
    AdvisoryStatus,
    CriterionEvaluation,
    TopicRelevance,
    RiskClassification,
    ValidationQueue,
    QueueItem,
    ALL_ADVISORY_STATUSES,
    is_known_status,
    check_advisory_invariant,
    check_methodological_safeguards,
    check_criterion_hallucination,
)
from src.advisory.stage_guard import (
    validate_criteria_stage_isolation,
    strip_contaminated_criteria,
    quarantine_advisory,
    StageIsolationReport,
    get_stage_prefixes,
    get_opposite_stage_prefixes,
)
from src.advisory.advisory_cache import (
    validate_advisory_structure,
    AdvisoryCache,
    get_advisory_cache,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def valid_criterion_evaluations():
    return [
        CriterionEvaluation(
            criterion_id="EC1",
            criterion_name="Population",
            satisfied=True,
            evidence="study examined adults over 65",
            confidence=0.85,
        ),
        CriterionEvaluation(
            criterion_id="EC2",
            criterion_name="Intervention",
            satisfied=False,
            evidence="no intervention described",
            confidence=0.75,
        ),
    ]


@pytest.fixture
def ec_advisory(valid_criterion_evaluations):
    return AdvisoryResult(
        cache_key="abcdef1234567890abcdef1234567890",
        protocol_version="1.0",
        decision=AdvisoryDecision.INCLUDE,
        confidence=0.85,
        triggered_criteria=["EC1"],
        non_triggered_criteria=["EC2"],
        criterion_evaluations=valid_criterion_evaluations,
        justification="Study meets EC1 criteria for population.",
        grounding_evidence=["study examined adults over 65"],
        grounding_strength=0.9,
        unsupported_claims_detected=False,
        hallucination_risk_score=0.1,
        prefilter_applied=False,
        prefilter_reason="",
    )


@pytest.fixture
def ic_advisory(valid_criterion_evaluations):
    return AdvisoryResult(
        cache_key="fedcba0987654321fedcba0987654321",
        protocol_version="1.0",
        decision=AdvisoryDecision.EXCLUDE,
        confidence=0.92,
        triggered_criteria=["IC3"],
        non_triggered_criteria=["IC1", "IC2"],
        criterion_evaluations=valid_criterion_evaluations,
        justification="Study does not meet IC3 criteria.",
        grounding_evidence=["no intervention described"],
        grounding_strength=0.95,
        unsupported_claims_detected=False,
        hallucination_risk_score=0.05,
        prefilter_applied=False,
        prefilter_reason="",
    )


@pytest.fixture
def cache():
    c = AdvisoryCache()
    c.clear_all()
    return c


# =============================================================================
# TEST: CANONICAL FIELD INVENTORY
# =============================================================================

class TestCanonicalFields:
    """Every field listed in advisory-contract-spec.md MUST exist on AdvisoryResult."""

    REQUIRED_FIELDS = {
        "cache_key",
        "protocol_version",
        "decision",
        "confidence",
        "triggered_criteria",
        "non_triggered_criteria",
        "criterion_evaluations",
        "justification",
        "error",
        "is_fallback",
        "is_placeholder",
    }

    REPLAY_VISIBLE_FIELDS = {
        "risk_classification",
        "risk_reason",
        "validation_queue",
        "requires_validation",
        "grounding_evidence",
        "criterion_grounding",
        "grounding_strength",
        "unsupported_claims_detected",
        "hallucination_risk_score",
        "generated_at",
        "generation_duration_ms",
        "topic_relevance",
        "raw_confidence",
        "parser_confidence",
        "routing_confidence",
        "evidence_confidence",
        "decision_confidence",
        "calibration_provenance",
        "prefilter_applied",
        "prefilter_reason",
        "model_used",
        "stage_validation",
    }

    RUNTIME_FIELDS = {
        "evidence_span",
        "metadata_fields_used",
        "heuristic_contributions",
        "prompt_hash",
        "routing_rationale",
    }

    def test_all_required_fields_exist(self):
        actual = {f.name for f in fields(AdvisoryResult)}
        missing = self.REQUIRED_FIELDS - actual
        assert not missing, f"Missing required fields: {missing}"

    def test_all_replay_visible_fields_exist(self):
        actual = {f.name for f in fields(AdvisoryResult)}
        missing = self.REPLAY_VISIBLE_FIELDS - actual
        assert not missing, f"Missing replay-visible fields: {missing}"

    def test_all_runtime_fields_exist(self):
        actual = {f.name for f in fields(AdvisoryResult)}
        missing = self.RUNTIME_FIELDS - actual
        assert not missing, f"Missing runtime fields: {missing}"

    def test_no_undeclared_fields_in_to_dict(self, ec_advisory):
        """to_dict() output keys must be a subset of dataclass fields."""
        dataclass_field_names = {f.name for f in fields(AdvisoryResult)}
        dict_keys = set(ec_advisory.to_dict().keys())
        extra = dict_keys - dataclass_field_names
        # 'empty' is not a field, but it may appear in some serialization.
        # Let's explicitly allow only known extra keys used for backward compat.
        known_extras = set()
        unexpected = extra - known_extras
        assert not unexpected, f"to_dict() has keys not in dataclass fields: {unexpected}"


# =============================================================================
# TEST: SERIALIZATION ROUNDTRIP
# =============================================================================

class TestSerializationRoundtrip:
    """to_dict() → from_dict() must produce an identical object (modulo JSON)."""

    def test_roundtrip_ec_advisory(self, ec_advisory):
        d = ec_advisory.to_dict()
        restored = AdvisoryResult.from_dict(d)
        for f in fields(AdvisoryResult):
            original = getattr(ec_advisory, f.name)
            revived = getattr(restored, f.name)
            assert type(original) == type(revived), (
                f"Type mismatch for {f.name}: {type(original)} vs {type(revived)}"
            )
        assert restored.cache_key == ec_advisory.cache_key
        assert restored.decision == ec_advisory.decision
        assert restored.triggered_criteria == ec_advisory.triggered_criteria
        assert restored.non_triggered_criteria == ec_advisory.non_triggered_criteria

    def test_roundtrip_with_none_error(self, ec_advisory):
        ec_advisory.error = None
        d = ec_advisory.to_dict()
        restored = AdvisoryResult.from_dict(d)
        assert restored.error is None or restored.error == "None"
        # None serializes as null, from_dict returns data.get("error") → None

    def test_roundtrip_with_topic_relevance(self, ec_advisory):
        ec_advisory.topic_relevance = TopicRelevance(
            domain_relevance_score=0.8,
            topical_alignment=0.7,
            rq_alignment_strength=0.6,
        )
        d = ec_advisory.to_dict()
        restored = AdvisoryResult.from_dict(d)
        assert restored.topic_relevance is not None
        assert restored.topic_relevance.domain_relevance_score == 0.8

    def test_json_serializable(self, ec_advisory):
        d = ec_advisory.to_dict()
        json_str = json.dumps(d, indent=2, ensure_ascii=False)
        parsed = json.loads(json_str)
        restored = AdvisoryResult.from_dict(parsed)
        assert restored.cache_key == ec_advisory.cache_key
        assert restored.decision == ec_advisory.decision

    def test_deserialize_missing_field_failsafe(self):
        """Missing field in dict must not raise — should use default."""
        minimal = {"cache_key": "test", "protocol_version": "1.0"}
        restored = AdvisoryResult.from_dict(minimal)
        assert restored.decision == AdvisoryDecision.UNAVAILABLE
        assert restored.confidence == 0.0
        assert restored.non_triggered_criteria == []

    def test_deserialize_unknown_field_silent(self):
        """Unknown field in dict must be silently ignored."""
        data = {
            "cache_key": "test",
            "protocol_version": "1.0",
            "decision": "INCLUDE",
            "confidence": 0.9,
            "hypothetical_future_field": "should be ignored",
        }
        restored = AdvisoryResult.from_dict(data)
        assert restored.decision == AdvisoryDecision.INCLUDE
        assert not hasattr(restored, "hypothetical_future_field")


# =============================================================================
# TEST: STAGE GUARD ISOLATION
# =============================================================================

class TestStageGuard:
    def test_ec_rejects_ic_criteria(self):
        """EC stage with IC criteria must fail isolation."""
        report = validate_criteria_stage_isolation(
            ["EC1", "IC3"], ["EC2"], [], "ec"
        )
        assert not report.passed
        assert "IC3" in report.contaminated_criteria

    def test_ic_rejects_ec_criteria(self):
        """IC stage with EC criteria must fail isolation."""
        report = validate_criteria_stage_isolation(
            ["IC1"], ["EC2", "EC5"], [], "ic"
        )
        assert not report.passed
        assert "EC2" in report.contaminated_criteria
        assert "EC5" in report.contaminated_criteria

    def test_clean_advisory_passes(self):
        """EC stage with only EC criteria must pass."""
        report = validate_criteria_stage_isolation(
            ["EC1", "EC3"], ["EC2"], [], "ec"
        )
        assert report.passed
        assert not report.contamination_found

    def test_strip_contaminated_removes_opposite_criteria(self):
        clean_t, clean_nt = strip_contaminated_criteria(
            ["EC1", "IC3"], ["EC2", "IC5"], "ec"
        )
        assert "IC3" not in clean_t
        assert "IC5" not in clean_nt
        assert "EC1" in clean_t
        assert "EC2" in clean_nt

    def test_quarantine_advisory_sets_correct_state(self, ec_advisory):
        ec_advisory.triggered_criteria = ["EC1", "IC3"]
        ec_advisory.non_triggered_criteria = ["EC2"]
        ec_advisory.justification = "Original text"
        quarantined = quarantine_advisory(
            ec_advisory, "ec", "IC3 contamination detected"
        )
        assert quarantined.decision == AdvisoryDecision.UNCERTAIN
        assert "[QUARANTINED]" in quarantined.justification
        assert quarantined.triggered_criteria == []
        assert quarantined.non_triggered_criteria == []
        assert "STAGE_CONTAMINATION" in (quarantined.error or "")

    def test_criterion_evaluations_dict_checked_for_contamination(self):
        """criterion_evaluations passed as dict must be scanned."""
        report = validate_criteria_stage_isolation(
            ["EC1"],
            [],
            {"EC1": {}, "IC3": {}},
            "ec"
        )
        assert not report.passed
        assert "IC3" in report.contaminated_criteria

    def test_criterion_evaluations_list_checked_for_contamination(self):
        """criterion_evaluations passed as list of dicts must be scanned."""
        report = validate_criteria_stage_isolation(
            ["EC1"],
            [],
            [{"criterion_id": "IC3", "triggered": True}],
            "ec"
        )
        assert not report.passed
        assert "IC3" in report.contaminated_criteria

    def test_stage_prefixes_correct(self):
        assert "EC1" in get_stage_prefixes("ec")
        assert "IC3" not in get_stage_prefixes("ec")
        assert "IC3" in get_opposite_stage_prefixes("ec")
        assert "EC1" not in get_stage_prefixes("ic")
        assert "IC3" in get_stage_prefixes("ic")


# =============================================================================
# TEST: CACHE ROUNDTRIP
# =============================================================================

class TestCacheRoundtrip:
    def test_store_and_retrieve(self, cache, ec_advisory):
        cache.set(ec_advisory, stage="ec")
        retrieved = cache.get(ec_advisory.cache_key, ec_advisory.protocol_version, stage="ec")
        assert retrieved.decision == ec_advisory.decision
        assert retrieved.confidence == ec_advisory.confidence
        assert retrieved.non_triggered_criteria == ec_advisory.non_triggered_criteria

    def test_cache_key_deterministic(self):
        key1 = AdvisoryCache.compute_cache_key("Title", "Abstract", "1.0")
        key2 = AdvisoryCache.compute_cache_key("Title", "Abstract", "1.0")
        assert key1 == key2

    def test_cache_key_different_content(self):
        key1 = AdvisoryCache.compute_cache_key("Title A", "Abstract A", "1.0")
        key2 = AdvisoryCache.compute_cache_key("Title B", "Abstract B", "1.0")
        assert key1 != key2

    def test_miss_returns_unavailable(self, cache):
        result = cache.get("nonexistent_key", "1.0")
        assert result.decision == AdvisoryDecision.UNAVAILABLE
        assert result.is_placeholder

    def test_validate_advisory_structure_valid(self, ec_advisory):
        valid, msg, normalized = validate_advisory_structure(ec_advisory)
        assert valid
        assert normalized is not None
        assert "non_triggered_criteria" in normalized

    def test_validate_advisory_structure_none(self):
        valid, msg, normalized = validate_advisory_structure(None)
        assert not valid
        assert "None" in msg

    def test_disk_roundtrip(self, cache, ec_advisory, tmp_path):
        """Verify advisory persists to disk and reloads identically."""
        cache.config.cache_dir = str(tmp_path)
        cache.config.enable_disk_cache = True
        cache.clear_all()

        cache.set(ec_advisory, stage="ec")

        cache2 = AdvisoryCache()
        cache2.config.cache_dir = str(tmp_path)
        cache2.config.enable_disk_cache = True

        retrieved = cache2.get(ec_advisory.cache_key, ec_advisory.protocol_version, stage="ec")
        assert retrieved.decision == ec_advisory.decision
        assert retrieved.non_triggered_criteria == ec_advisory.non_triggered_criteria


# =============================================================================
# TEST: INVARIANTS
# =============================================================================

class TestInvariants:
    def test_check_advisory_invariant_passes(self, ec_advisory):
        violations = check_advisory_invariant(ec_advisory)
        assert violations == []

    def test_check_advisory_invariant_none_decision(self):
        a = AdvisoryResult(
            cache_key="test", protocol_version="1.0",
            decision=None, confidence=0.5,
        )
        violations = check_advisory_invariant(a)
        assert any("decision is None" in v for v in violations)

    def test_check_advisory_invariant_out_of_range_confidence(self):
        a = AdvisoryResult(
            cache_key="test", protocol_version="1.0",
            decision=AdvisoryDecision.INCLUDE, confidence=1.5,
        )
        violations = check_advisory_invariant(a)
        assert any("out of range" in v for v in violations)

    def test_methodological_safeguards_high_confidence_no_evidence(self):
        a = AdvisoryResult(
            cache_key="test", protocol_version="1.0",
            decision=AdvisoryDecision.INCLUDE, confidence=0.96,
            justification="Study meets criteria.",
            triggered_criteria=["EC1"],
        )
        warnings = check_methodological_safeguards(a)
        assert any("OVERCONFIDENT_INCLUDE" in w for w in warnings)

    def test_methodological_safeguards_empty_justification(self):
        """INCLUDE with confidence>=0.90 and no justification must warn."""
        a = AdvisoryResult(
            cache_key="test", protocol_version="1.0",
            decision=AdvisoryDecision.INCLUDE, confidence=0.92,
            justification="",
            triggered_criteria=["EC1"],
        )
        warnings = check_methodological_safeguards(a)
        assert any("EMPTY_JUSTIFICATION" in w for w in warnings)

    def test_criterion_hallucination_detects_unsupported_citations(self):
        warnings = check_criterion_hallucination(
            ["IC14"], "Study meets criteria.", "Title", "Abstract about topic"
        )
        assert any("CRITERION_HALLUCINATION" in w for w in warnings)

    def test_criterion_hallucination_no_false_positive(self):
        """EC1 mentioned in title must NOT trigger hallucination warning."""
        warnings = check_criterion_hallucination(
            ["EC1"], "Study meets EC1 criteria.", "EC1 evaluation", "About EC1 topic"
        )
        assert not warnings

    def test_decision_enum_all_values_known(self):
        """All values in AdvisoryDecision must be known by parser."""
        known = {"INCLUDE", "EXCLUDE", "SKIP", "UNCERTAIN",
                 "INSUFFICIENT_EVIDENCE", "CANNOT_DETERMINE", "UNAVAILABLE",
                 "INSUFFICIENT_METADATA"}
        actual = {e.value for e in AdvisoryDecision}
        assert actual == known

    def test_status_enum_all_values_known(self):
        assert is_known_status("PENDING")
        assert is_known_status("COMPLETED")
        assert is_known_status("PREFILTERED")
        assert is_known_status("QUARANTINED")
        assert is_known_status("FALLBACK")
        assert is_known_status("UNAVAILABLE")
        assert not is_known_status("HYPOTHETICAL_FUTURE_STATUS")


# =============================================================================
# TEST: DETERMINISM
# =============================================================================

class TestDeterminism:
    def test_same_input_same_advisory(self, ec_advisory):
        """Same AdvisoryResult must produce same dict across calls."""
        d1 = ec_advisory.to_dict()
        d2 = ec_advisory.to_dict()
        json1 = json.dumps(d1, sort_keys=True)
        json2 = json.dumps(d2, sort_keys=True)
        assert json1 == json2

    def test_cache_key_deterministic_across_instances(self):
        k1 = AdvisoryCache.compute_cache_key("Test Title", "Test Abstract", "1.0")
        k2 = AdvisoryCache.compute_cache_key("Test Title", "Test Abstract", "1.0")
        assert k1 == k2
        assert len(k1) == 32  # SHA256 hex digest first 32 chars

    def test_roundtrip_identity_across_multiple_cycles(self, ec_advisory):
        """Three roundtrips must produce identical result."""
        current = ec_advisory
        for i in range(3):
            d = current.to_dict()
            current = AdvisoryResult.from_dict(d)
        assert current.decision == ec_advisory.decision
        assert current.confidence == ec_advisory.confidence
        assert current.triggered_criteria == ec_advisory.triggered_criteria
        assert current.non_triggered_criteria == ec_advisory.non_triggered_criteria

    def test_stage_guard_deterministic(self):
        """Same inputs must produce same StageIsolationReport."""
        r1 = validate_criteria_stage_isolation(["EC1", "IC3"], ["EC2"], [], "ec")
        r2 = validate_criteria_stage_isolation(["EC1", "IC3"], ["EC2"], [], "ec")
        assert r1.passed == r2.passed
        assert r1.contaminated_criteria == r2.contaminated_criteria


# =============================================================================
# TEST: EDGE CASES
# =============================================================================

class TestEdgeCases:
    def test_empty_triggered_criteria_serializes_as_empty_list(self):
        a = AdvisoryResult(
            cache_key="test", protocol_version="1.0",
            decision=AdvisoryDecision.INCLUDE, confidence=0.5,
        )
        d = a.to_dict()
        assert d["triggered_criteria"] == []
        assert d["non_triggered_criteria"] == []

    def test_empty_criterion_evaluations_serializes_as_empty_list(self):
        a = AdvisoryResult(
            cache_key="test", protocol_version="1.0",
            decision=AdvisoryDecision.INCLUDE, confidence=0.5,
        )
        d = a.to_dict()
        assert d["criterion_evaluations"] == []

    def test_decision_normalization_from_dict(self):
        """from_dict must handle decision string correctly."""
        data = {
            "cache_key": "test", "protocol_version": "1.0",
            "decision": "INCLUDE", "confidence": 0.8,
        }
        restored = AdvisoryResult.from_dict(data)
        assert restored.decision == AdvisoryDecision.INCLUDE

    def test_decision_normalization_invalid_fallback(self):
        """Invalid decision string must fall back to UNAVAILABLE."""
        data = {
            "cache_key": "test", "protocol_version": "1.0",
            "decision": "BOGUS_VALUE", "confidence": 0.8,
        }
        restored = AdvisoryResult.from_dict(data)
        assert restored.decision == AdvisoryDecision.UNAVAILABLE

    def test_create_unavailable(self):
        a = AdvisoryResult.create_unavailable("Not yet generated")
        assert a.decision == AdvisoryDecision.UNAVAILABLE
        assert a.is_placeholder
        assert a.error == "Not yet generated"

    def test_create_failed(self):
        a = AdvisoryResult.create_failed("LLM timeout", cache_key="test")
        assert a.decision == AdvisoryDecision.UNAVAILABLE
        assert not a.is_placeholder
        assert "LLM timeout" in (a.error or "")

    def test_is_available_returns_false_for_unavailable(self):
        a = AdvisoryResult.create_unavailable("test")
        assert not a.is_available()

    def test_is_available_returns_true_for_include(self, ec_advisory):
        assert ec_advisory.is_available()


# =============================================================================
# TEST: QUEUE ITEM CONTRACT
# =============================================================================

class TestQueueItemContract:
    def test_queue_item_has_title_abstract(self):
        qi = QueueItem(
            cache_key="k", protocol_version="1.0",
            article_id="a1", title="Test Title", abstract="Test Abstract",
        )
        assert qi.title == "Test Title"
        assert qi.abstract == "Test Abstract"

    def test_queue_item_roundtrip(self):
        qi = QueueItem(
            cache_key="k", protocol_version="1.0",
            article_id="a1", title="Title", abstract="Abstract",
        )
        d = qi.to_dict()
        qi2 = QueueItem.from_dict(d)
        assert qi2.title == "Title"
        assert qi2.abstract == "Abstract"

    def test_queue_item_empty_title_default(self):
        qi = QueueItem.from_dict({
            "cache_key": "k", "protocol_version": "1.0", "article_id": "a1",
        })
        assert qi.title == ""
        assert qi.abstract == ""
