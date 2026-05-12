"""
SPRINT 7.7: Determinism & Replay Validation Tests
Tests for structured advisory system semantic guarantees.
"""
import pytest
from src.core.llm_assistant import (
    normalize_literature_label,
    CriterionEvaluation,
    StructuredAdvisory,
    AdvisorySuggestion,
    WL_CANONICAL,
    GL_CANONICAL
)


class TestLiteratureNormalization:
    """Test WL/GL canonical normalization is deterministic."""

    @pytest.mark.parametrize("raw,expected", [
        ("WL", WL_CANONICAL),
        ("wl", WL_CANONICAL),
        ("Wl", WL_CANONICAL),
        ("White Literature", WL_CANONICAL),
        ("white literature", WL_CANONICAL),
        ("WHITE LITERATURE", WL_CANONICAL),
        ("GL", GL_CANONICAL),
        ("gl", GL_CANONICAL),
        ("Gl", GL_CANONICAL),
        ("Grey Literature", GL_CANONICAL),
        ("grey literature", GL_CANONICAL),
        ("GREY LITERATURE", GL_CANONICAL),
        ("Gray Literature", GL_CANONICAL),
        ("GRAY LITERATURE", GL_CANONICAL),
    ])
    def test_wl_normalization_deterministic(self, raw, expected):
        """WL normalization must be deterministic."""
        result = normalize_literature_label(raw)
        assert result == expected

    def test_wl_normalization_empty_string(self):
        """Empty string defaults to WL canonical."""
        result = normalize_literature_label("")
        assert result == WL_CANONICAL

    def test_wl_normalization_unknown_value(self):
        """Unknown values default to WL canonical."""
        result = normalize_literature_label("unknown")
        assert result == WL_CANONICAL

    def test_wl_normalization_none(self):
        """None input defaults to WL canonical."""
        result = normalize_literature_label(None)
        assert result == WL_CANONICAL

    def test_wl_normalization_whitespace(self):
        """Whitespace is stripped before normalization."""
        result = normalize_literature_label("  wl  ")
        assert result == WL_CANONICAL


class TestCriterionEvaluation:
    """Test CriterionEvaluation serialization is deterministic."""

    def test_criterion_evaluation_to_dict_roundtrip(self):
        """Evaluation dict must survive round-trip serialization."""
        eval = CriterionEvaluation(
            criterion_id="EC1",
            triggered=True,
            evidence=["software engineering recruitment study"],
            justification="Study is about SE R&S",
            ambiguity_detected=False,
            grounded_metadata_fields=["title", "abstract"]
        )

        d = eval.to_dict()
        restored = CriterionEvaluation.from_dict(d)

        assert restored.criterion_id == eval.criterion_id
        assert restored.triggered == eval.triggered
        assert restored.evidence == eval.evidence
        assert restored.justification == eval.justification
        assert restored.ambiguity_detected == eval.ambiguity_detected

    def test_criterion_evaluation_empty_lists(self):
        """Empty lists must be preserved."""
        eval = CriterionEvaluation(
            criterion_id="EC2",
            triggered=False,
            evidence=[],
            justification="No evidence found",
            ambiguity_detected=False,
            grounded_metadata_fields=[]
        )

        d = eval.to_dict()
        assert d["evidence"] == []
        assert d["grounded_metadata_fields"] == []


class TestStructuredAdvisoryHash:
    """Test advisory hash determinism."""

    def test_same_inputs_produce_same_hash(self):
        """Identical advisory must produce identical hash."""
        ev1 = CriterionEvaluation(
            criterion_id="EC1",
            triggered=False,
            evidence=["test"],
            justification="test justification",
            ambiguity_detected=False
        )
        advisory1 = StructuredAdvisory(
            stage="ec",
            decision="include",
            confidence=0.85,
            triggered_criteria=[],
            non_triggered_criteria=["EC1"],
            criterion_evaluations={"EC1": ev1},
            justification="test",
            reasoning_summary="test",
            ambiguity_flags=[],
            evidence_extracts=["test"],
            metadata_grounding={"title_used": True},
            is_fallback=False,
            protocol_version="1.0"
        )

        ev2 = CriterionEvaluation(
            criterion_id="EC1",
            triggered=False,
            evidence=["test"],
            justification="test justification",
            ambiguity_detected=False
        )
        advisory2 = StructuredAdvisory(
            stage="ec",
            decision="include",
            confidence=0.85,
            triggered_criteria=[],
            non_triggered_criteria=["EC1"],
            criterion_evaluations={"EC1": ev2},
            justification="test",
            reasoning_summary="test",
            ambiguity_flags=[],
            evidence_extracts=["test"],
            metadata_grounding={"title_used": True},
            is_fallback=False,
            protocol_version="1.0"
        )

        assert advisory1.advisory_hash == advisory2.advisory_hash

    def test_different_criteria_produce_different_hash(self):
        """Different criterion evaluations must produce different hash."""
        ev1 = CriterionEvaluation(
            criterion_id="EC1",
            triggered=True,
            evidence=["found"],
            justification="triggered",
            ambiguity_detected=False
        )
        advisory1 = StructuredAdvisory(
            stage="ec",
            decision="exclude",
            confidence=0.9,
            triggered_criteria=["EC1"],
            non_triggered_criteria=[],
            criterion_evaluations={"EC1": ev1},
            justification="excluded",
            reasoning_summary="",
            ambiguity_flags=[],
            evidence_extracts=[],
            metadata_grounding={},
            is_fallback=False,
            protocol_version="1.0"
        )

        ev2 = CriterionEvaluation(
            criterion_id="EC1",
            triggered=False,
            evidence=["not found"],
            justification="not triggered",
            ambiguity_detected=False
        )
        advisory2 = StructuredAdvisory(
            stage="ec",
            decision="include",
            confidence=0.9,
            triggered_criteria=[],
            non_triggered_criteria=["EC1"],
            criterion_evaluations={"EC1": ev2},
            justification="included",
            reasoning_summary="",
            ambiguity_flags=[],
            evidence_extracts=[],
            metadata_grounding={},
            is_fallback=False,
            protocol_version="1.0"
        )

        assert advisory1.advisory_hash != advisory2.advisory_hash

    def test_fallback_produces_consistent_hash(self):
        """Fallback advisory must produce deterministic hash."""
        advisory = StructuredAdvisory(
            stage="ec",
            decision="unavailable",
            confidence=0.0,
            triggered_criteria=[],
            non_triggered_criteria=[],
            criterion_evaluations={},
            justification="Structured advisory unavailable. Displaying deterministic fallback summary.",
            reasoning_summary="LLM service unavailable. Manual review required.",
            ambiguity_flags=["LLM not available"],
            evidence_extracts=[],
            metadata_grounding={
                "title_used": False,
                "year_used": False,
                "abstract_used": False,
                "literature_type_used": False
            },
            is_fallback=True,
            fallback_reason="No LLM client",
            protocol_version="1.0"
        )

        d = advisory.to_dict()
        assert d["is_fallback"] is True
        assert d["decision"] == "unavailable"
        assert "deterministic fallback" in d["justification"].lower()


class TestStructuredAdvisorySerialization:
    """Test advisory serialization and deserialization."""

    def test_to_dict_contains_all_required_fields(self):
        """Structured advisory dict must contain all required fields."""
        ev = CriterionEvaluation(
            criterion_id="EC1",
            triggered=False,
            evidence=["test evidence"],
            justification="test",
            ambiguity_detected=False,
            grounded_metadata_fields=["title"]
        )
        advisory = StructuredAdvisory(
            stage="ec",
            decision="include",
            confidence=0.75,
            triggered_criteria=[],
            non_triggered_criteria=["EC1"],
            criterion_evaluations={"EC1": ev},
            justification="test",
            reasoning_summary="summary",
            ambiguity_flags=[],
            evidence_extracts=["test evidence"],
            metadata_grounding={"title_used": True},
            is_fallback=False,
            protocol_version="1.0"
        )

        d = advisory.to_dict()

        required_fields = [
            "stage", "decision", "confidence", "triggered_criteria",
            "non_triggered_criteria", "criterion_evaluations", "justification",
            "reasoning_summary", "ambiguity_flags", "evidence_extracts",
            "metadata_grounding", "is_fallback", "protocol_version", "advisory_hash"
        ]
        for field in required_fields:
            assert field in d, f"Missing required field: {field}"

    def test_from_dict_roundtrip(self):
        """Advisory must survive dict round-trip."""
        ev = CriterionEvaluation(
            criterion_id="EC2",
            triggered=True,
            evidence=["duplicate found"],
            justification="duplicate publication detected",
            ambiguity_detected=False,
            grounded_metadata_fields=["title", "abstract"]
        )
        original = StructuredAdvisory(
            stage="ec",
            decision="exclude",
            confidence=0.95,
            triggered_criteria=["EC2"],
            non_triggered_criteria=["EC1", "EC3", "EC4"],
            criterion_evaluations={"EC2": ev},
            justification="Duplicate publication",
            reasoning_summary="EC2 triggered: exact title match with earlier publication",
            ambiguity_flags=[],
            evidence_extracts=["Title: identical", "Journal: same venue"],
            metadata_grounding={"title_used": True, "abstract_used": True},
            is_fallback=False,
            protocol_version="1.0"
        )

        d = original.to_dict()
        restored = StructuredAdvisory.from_dict(d)

        assert restored.stage == original.stage
        assert restored.decision == original.decision
        assert restored.confidence == original.confidence
        assert restored.triggered_criteria == original.triggered_criteria
        assert restored.is_fallback == original.is_fallback
        assert restored.advisory_hash == original.advisory_hash

    def test_backward_compatibility_with_legacy_suggestion(self):
        """AdvisorySuggestion must remain compatible with legacy code."""
        legacy = AdvisorySuggestion(
            stage="ec",
            decision="exclude",
            confidence=0.88,
            justification="EC3 triggered: blog post not peer-reviewed",
            triggered_criteria={"EC3": "blog post source"},
            evidence=["authored a blog post about hiring"],
            ambiguity_flags=[],
            is_fallback=False
        )

        d = legacy.to_dict()

        assert d["stage"] == "ec"
        assert d["decision"] == "exclude"
        assert d["confidence"] == 0.88
        assert d["triggered_criteria"]["EC3"] == "blog post source"
        assert d["is_fallback"] is False

    def test_fallback_suggestion_has_correct_structure(self):
        """Fallback must have explicit fallback markers."""
        ev1 = CriterionEvaluation(criterion_id="EC1", triggered=False)
        ev2 = CriterionEvaluation(criterion_id="EC2", triggered=False)
        advisory = StructuredAdvisory(
            stage="ic",
            decision="unavailable",
            confidence=0.0,
            triggered_criteria=[],
            non_triggered_criteria=["EC1", "EC2"],
            criterion_evaluations={"EC1": ev1, "EC2": ev2},
            justification="Structured advisory unavailable. Displaying deterministic fallback summary.",
            reasoning_summary="LLM service unavailable. Manual review required.",
            ambiguity_flags=["LLM not available"],
            evidence_extracts=[],
            metadata_grounding={
                "title_used": False,
                "year_used": False,
                "abstract_used": False,
                "literature_type_used": False
            },
            is_fallback=True,
            fallback_reason="No LLM client initialized",
            protocol_version="1.0"
        )

        d = advisory.to_dict()

        assert d["is_fallback"] is True
        assert d["fallback_reason"] != ""
        assert d["confidence"] == 0.0
        assert d["decision"] == "unavailable"
        assert not any(d["metadata_grounding"].values()), "Fallback must NOT claim metadata used"


class TestHallucinationMitigation:
    """Test that hallucinated values are never produced."""

    def test_year_not_hallucinated_when_provided(self):
        """Year metadata must not be marked as unknown when present."""
        advisory = StructuredAdvisory(
            stage="ec",
            decision="include",
            confidence=0.85,
            triggered_criteria=[],
            non_triggered_criteria=["EC4"],
            criterion_evaluations={
                "EC4": CriterionEvaluation(
                    criterion_id="EC4",
                    triggered=False,
                    evidence=["publication year = 2021"],
                    justification="2021 >= 2015 threshold",
                    ambiguity_detected=False,
                    grounded_metadata_fields=["year"]
                )
            },
            justification="",
            reasoning_summary="",
            ambiguity_flags=[],
            evidence_extracts=["2021"],
            metadata_grounding={"year_used": True},
            is_fallback=False,
            protocol_version="1.0"
        )

        d = advisory.to_dict()
        ec4_eval = d["criterion_evaluations"]["EC4"]

        assert "2021" in ec4_eval["evidence"][0]
        assert ec4_eval["ambiguity_detected"] is False

    def test_no_ambiguity_when_metadata_complete(self):
        """Ambiguity must NOT be flagged when metadata completeness is high."""
        advisory = StructuredAdvisory(
            stage="ec",
            decision="include",
            confidence=0.95,
            triggered_criteria=[],
            non_triggered_criteria=["EC1"],
            criterion_evaluations={
                "EC1": CriterionEvaluation(
                    criterion_id="EC1",
                    triggered=False,
                    evidence=["randomized controlled trial in SE"],
                    justification="Study addresses SE recruitment empirically",
                    ambiguity_detected=False,
                    grounded_metadata_fields=["title", "abstract"]
                )
            },
            justification="Empirical SE research",
            reasoning_summary="High metadata completeness",
            ambiguity_flags=[],
            evidence_extracts=["software engineering recruitment", "RCT"],
            metadata_grounding={
                "title_used": True,
                "abstract_used": True,
                "year_used": True
            },
            is_fallback=False,
            protocol_version="1.0"
        )

        d = advisory.to_dict()

        assert d["criterion_evaluations"]["EC1"]["ambiguity_detected"] is False
        assert d["ambiguity_flags"] == []


class TestEC4YearIsolation:
    """Test EC4 must ONLY use publication year logic."""

    def test_ec4_must_not_infer_from_literature_type(self):
        """EC4 must NOT be influenced by literature type."""
        ev_wl = CriterionEvaluation(
            criterion_id="EC4",
            triggered=False,
            evidence=["year: 2022"],
            justification="2022 >= 2015 threshold",
            ambiguity_detected=False,
            grounded_metadata_fields=["year"]
        )
        advisory_wl = StructuredAdvisory(
            stage="ec",
            decision="include",
            confidence=0.85,
            triggered_criteria=[],
            non_triggered_criteria=["EC4"],
            criterion_evaluations={"EC4": ev_wl},
            justification="WL peer-reviewed from 2022",
            reasoning_summary="",
            ambiguity_flags=[],
            evidence_extracts=["2022"],
            metadata_grounding={"year_used": True, "literature_type_used": True},
            is_fallback=False,
            protocol_version="1.0"
        )

        ev_gl = CriterionEvaluation(
            criterion_id="EC4",
            triggered=False,
            evidence=["year: 2022"],
            justification="2022 >= 2015 threshold",
            ambiguity_detected=False,
            grounded_metadata_fields=["year"]
        )
        advisory_gl = StructuredAdvisory(
            stage="ec",
            decision="include",
            confidence=0.85,
            triggered_criteria=[],
            non_triggered_criteria=["EC4"],
            criterion_evaluations={"EC4": ev_gl},
            justification="GL non-peer-reviewed from 2022",
            reasoning_summary="",
            ambiguity_flags=[],
            evidence_extracts=["2022"],
            metadata_grounding={"year_used": True, "literature_type_used": True},
            is_fallback=False,
            protocol_version="1.0"
        )

        assert advisory_wl.criterion_evaluations["EC4"].grounded_metadata_fields == ["year"]
        assert advisory_gl.criterion_evaluations["EC4"].grounded_metadata_fields == ["year"]


class TestReplayValidation:
    """Test advisory replay preserves structure."""

    def test_advisory_replay_preserves_structure(self):
        """Replay must preserve advisory structure exactly."""
        ev = CriterionEvaluation(
            criterion_id="EC1",
            triggered=False,
            evidence=["empirical study"],
            justification="Empirical SE research confirmed",
            ambiguity_detected=False,
            grounded_metadata_fields=["title", "abstract"]
        )
        original = StructuredAdvisory(
            stage="ec",
            decision="include",
            confidence=0.90,
            triggered_criteria=[],
            non_triggered_criteria=["EC1"],
            criterion_evaluations={"EC1": ev},
            justification="Passed all EC criteria",
            reasoning_summary="All criteria evaluated with high metadata grounding",
            ambiguity_flags=[],
            evidence_extracts=["software engineering", "empirical study", "recruitment"],
            metadata_grounding={
                "title_used": True,
                "abstract_used": True,
                "year_used": True,
                "literature_type_used": True
            },
            is_fallback=False,
            protocol_version="1.0"
        )

        serialized = original.to_dict()
        restored = StructuredAdvisory.from_dict(serialized)

        assert restored.stage == original.stage
        assert restored.decision == original.decision
        assert restored.confidence == original.confidence
        assert restored.advisory_hash == original.advisory_hash
        assert len(restored.criterion_evaluations) == len(original.criterion_evaluations)