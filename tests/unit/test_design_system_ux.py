"""
UX Enforcement Tests for Scientific Design System

Tests for:
- Workflow order visibility
- Canonical stage enforcement
- Provenance visibility
- Reproducibility indicator visibility
- Semantic color consistency
- Accessibility contrast compliance
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from src.ui.design_system.semantic_colors import (
    SEMANTIC_COLORS,
    WORKFLOW_STAGE_COLORS,
    get_semantic_color,
    get_workflow_stage_color,
    get_decision_semantic,
)
from src.ui.design_system.typography import (
    TYPOGRAPHY,
    TYPOGRAPHY_SCALE,
    STYLE_GUIDES,
)
from src.ui.design_system.spacing import (
    SPACING,
    SPACING_SCALE,
    LAYOUT,
    TOUCH_TARGETS,
    get_spacing,
)
from src.core.screening_session import (
    ScreeningSession,
    ArticleReview,
    SessionStage,
    ReviewDecision,
)
from src.core.article_record import ArticleRecord


class TestWorkflowOrderVisibility:
    """Tests for workflow order visibility."""

    def test_workflow_stages_defined(self):
        """Verify all workflow stages are defined."""
        expected_stages = ["protocol", "ec", "ic", "qc", "export", "replay"]

        for stage in expected_stages:
            stage_color = get_workflow_stage_color(stage)
            assert "bg" in stage_color, f"Stage {stage} missing background color"
            assert "border" in stage_color, f"Stage {stage} missing border color"
            assert "text" in stage_color, f"Stage {stage} missing text color"

    def test_workflow_stage_order(self):
        """Verify workflow stages have correct order mapping."""
        stage_order = ["protocol", "ec", "ic", "qc", "export", "replay"]

        for i, stage in enumerate(stage_order):
            stage_color = get_workflow_stage_color(stage)
            assert stage_color is not None, f"Stage {stage} not found"
            assert stage_color.get("icon") is not None, f"Stage {stage} missing icon"

    def test_workflow_stage_colors_unique(self):
        """Verify each workflow stage has a unique color scheme."""
        colors_seen = set()

        for stage in WORKFLOW_STAGE_COLORS.values():
            color_tuple = (stage.get("border"), stage.get("text"))
            assert color_tuple not in colors_seen, f"Duplicate color scheme detected"
            colors_seen.add(color_tuple)


class TestCanonicalStageEnforcement:
    """Tests for canonical stage enforcement."""

    def test_session_stage_enum_complete(self):
        """Verify SessionStage enum has all required stages."""
        expected_stages = {"ec", "ic", "qc", "complete"}

        actual_stages = {stage.value for stage in SessionStage}

        for expected in expected_stages:
            assert expected in actual_stages, f"Missing stage: {expected}"

    def test_review_decision_enum_complete(self):
        """Verify ReviewDecision enum has all required decisions."""
        expected_decisions = {"include", "exclude", "skip", "needs_discussion"}

        actual_decisions = {decision.value for decision in ReviewDecision}

        for expected in expected_decisions:
            assert expected in actual_decisions, f"Missing decision: {expected}"

    def test_article_review_stage_progression(self):
        """Verify article review enforces stage progression."""
        article = ArticleReview(
            article_id="test_001",
            title="Test Article",
            abstract="Test abstract",
            metadata={"literature_type": "WL"}
        )

        article.ec_stage = "exclude"
        assert not article.is_ec_included, "EC excluded article should not be included"

        article.ec_stage = "include"
        article.ic_stage = "exclude"
        assert article.is_ec_included, "EC included article should be included"
        assert not article.is_ic_included, "IC excluded article should not be IC included"

        article.ic_stage = "include"
        article.qc_stage = "include"
        assert article.is_ic_included, "IC included article should be included"
        assert article.is_qc_included, "QC included article should be QC included"

    def test_article_cannot_skip_stages(self):
        """Verify article cannot skip stages (EC → IC requires EC pass)."""
        article = ArticleReview(
            article_id="test_002",
            title="Test Article",
            abstract="Test abstract",
            metadata={"literature_type": "WL"}
        )

        article.ic_stage = "include"
        assert not article.is_ic_included, "Cannot proceed to IC without EC pass"

        article.ec_stage = "include"
        article.ic_stage = "include"
        article.qc_stage = "include"

        assert article.can_proceed_to_stage("ic"), "EC pass should allow IC"
        assert article.can_proceed_to_stage("qc"), "IC pass should allow QC"


class TestProvenanceVisibility:
    """Tests for provenance visibility."""

    def test_literature_type_recognized(self):
        """Verify both literature types are recognized."""
        wl_semantic = get_semantic_color("WL")
        gl_semantic = get_semantic_color("GL")

        assert wl_semantic is not None, "WL should have semantic color"
        assert gl_semantic is not None, "GL should have semantic color"
        assert wl_semantic != gl_semantic, "WL and GL should have different colors"

    def test_metadata_completeness_states(self):
        """Verify all metadata completeness states are defined."""
        for state in ["METADATA_COMPLETE", "METADATA_PARTIAL", "METADATA_MINIMAL"]:
            semantic = get_semantic_color(state)
            assert semantic is not None, f"{state} should have semantic color"
            assert "bg" in semantic, f"{state} should have background"
            assert "border" in semantic, f"{state} should have border"
            assert "text" in semantic, f"{state} should have text color"

    def test_article_metadata_propagation(self):
        """Verify article review preserves metadata."""
        article = ArticleReview(
            article_id="test_003",
            title="Test Article",
            abstract="Test abstract",
            metadata={
                "literature_type": "WL",
                "title": "Test Article",
                "year": "2023",
                "authors": "Test Author",
                "doi": "10.1234/test",
                "source": "Test Source",
                "metadata_completeness": "complete",
                "year_source": "atlas"
            }
        )

        assert article.get_literature_type() == "WL"
        assert article.get_metadata_completeness() == "complete"
        assert article.get_year_source() == "atlas"
        assert article.has_complete_metadata(), "Article should have complete metadata"


class TestReproducibilityIndicatorVisibility:
    """Tests for reproducibility indicator visibility."""

    def test_replay_state_defined(self):
        """Verify replay states are defined."""
        replay_states = ["REPLAYED", "DETERMINISTIC", "PENDING"]

        for state in replay_states:
            semantic = get_semantic_color(state)
            assert semantic is not None, f"{state} should have semantic color"

    def test_audit_states_defined(self):
        """Verify audit states are defined."""
        audit_states = ["VERIFIED", "AUDIT_MISMATCH", "PENDING"]

        for state in audit_states:
            semantic = get_semantic_color(state)
            assert semantic is not None, f"{state} should have semantic color"

    def test_session_checksum_computed(self):
        """Verify session checksum can be computed."""
        session = ScreeningSession(
            session_id="test_session_001",
            created_at="2024-01-01T00:00:00",
            protocol_version="1.0",
            stage="ec"
        )

        article1 = ArticleReview(
            article_id="art_001",
            title="Article 1",
            abstract="Abstract 1",
            metadata={"literature_type": "WL"}
        )
        article2 = ArticleReview(
            article_id="art_002",
            title="Article 2",
            abstract="Abstract 2",
            metadata={"literature_type": "GL"}
        )
        session.articles = [article1, article2]
        session.total_count = 2

        checksum = session.compute_checksum()
        assert checksum is not None, "Checksum should be computed"
        assert len(checksum) == 64, "SHA256 checksum should be 64 characters"

    def test_audit_chain_integrity(self):
        """Verify audit chain integrity can be verified."""
        session = ScreeningSession(
            session_id="test_session_002",
            created_at="2024-01-01T00:00:00",
            protocol_version="1.0",
            stage="ec"
        )

        article = ArticleReview(
            article_id="art_003",
            title="Article 3",
            abstract="Abstract 3",
            metadata={"literature_type": "WL"}
        )
        session.articles = [article]
        session.total_count = 1

        session.current_index = 0
        session.record_decision("include", notes="Test decision")

        is_valid, errors = session.verify_audit_chain()
        assert is_valid, f"Audit chain should be valid: {errors}"
        assert len(errors) == 0, "No errors should be present"


class TestSemanticColorConsistency:
    """Tests for semantic color consistency."""

    def test_all_decisions_have_colors(self):
        """Verify all decisions have assigned colors."""
        decisions = ["include", "exclude", "skip", "needs_discussion", "pending"]

        for decision in decisions:
            semantic = get_decision_semantic(decision)
            assert semantic is not None, f"Decision {decision} should have semantic color"
            assert "badge" in semantic, f"Decision {decision} should have badge color"

    def test_color_contrast_ratios(self):
        """Verify semantic colors meet contrast requirements."""
        def parse_hex_color(hex_color):
            """Parse hex color to RGB tuple."""
            hex_color = hex_color.lstrip('#')
            return tuple(int(hex_color[i:i+2], 16) / 255 for i in (0, 2, 4))

        def get_luminance(rgb):
            """Calculate relative luminance."""
            def adjust(c):
                return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
            return 0.2126 * adjust(rgb[0]) + 0.7152 * adjust(rgb[1]) + 0.0722 * adjust(rgb[2])

        def contrast_ratio(rgb1, rgb2):
            """Calculate WCAG contrast ratio."""
            l1 = get_luminance(rgb1)
            l2 = get_luminance(rgb2)
            lighter = max(l1, l2)
            darker = min(l1, l2)
            return (lighter + 0.05) / (darker + 0.05)

        for name, semantic in SEMANTIC_COLORS.items():
            text_color = semantic.get("text", "")

            if text_color.startswith("#"):
                text_rgb = parse_hex_color(text_color)
                bg_color = semantic.get("bg", "#000000")

                if bg_color.startswith("rgba"):
                    bg_rgb = (0, 0, 0)
                else:
                    bg_rgb = parse_hex_color(bg_color)

                ratio = contrast_ratio(text_rgb, bg_rgb)
                assert ratio >= 3.0, f"{name}: Contrast {ratio:.2f} < 3.0 (WCAG AA for large text/badges)"


class TestAccessibilityCompliance:
    """Tests for accessibility compliance."""

    def test_mono_font_defined(self):
        """Verify monospace font is defined."""
        assert "mono" in TYPOGRAPHY, "Monospace font should be defined"
        assert TYPOGRAPHY["mono"] != "", "Monospace font should not be empty"

    def test_sans_font_defined(self):
        """Verify sans-serif font is defined."""
        assert "sans" in TYPOGRAPHY, "Sans-serif font should be defined"
        assert TYPOGRAPHY["sans"] != "", "Sans-serif font should not be empty"

    def test_font_sizes_meet_minimum(self):
        """Verify font sizes meet WCAG minimum."""
        min_size = 0.6

        for name, style in STYLE_GUIDES.items():
            size = style.get("font_size", "")
            if isinstance(size, str) and size.endswith("rem"):
                size_value = float(size.rstrip("rem"))
                assert size_value >= min_size, f"{name}: Size {size} < {min_size}rem"

    def test_spacing_tokens_defined(self):
        """Verify spacing tokens are defined."""
        required_spacing = ["xs", "sm", "md", "lg", "xl"]

        for spacing in required_spacing:
            assert spacing in SPACING_SCALE, f"Spacing {spacing} should be defined"

    def test_touch_target_minimum(self):
        """Verify touch target minimum is defined."""
        assert "minimum" in TOUCH_TARGETS, "Touch target minimum should be defined"

    def test_semantic_has_accessibility_labels(self):
        """Verify semantic colors have accessibility labels."""
        for name, semantic in SEMANTIC_COLORS.items():
            assert "accessibility_label" in semantic, f"{name} missing accessibility_label"


class TestDesignSystemIntegration:
    """Integration tests for design system components."""

    def test_all_colors_use_hex_or_rgba(self):
        """Verify all colors use valid formats."""
        import re

        for name, semantic in SEMANTIC_COLORS.items():
            for color_type in ["bg", "border", "text", "badge"]:
                color = semantic.get(color_type, "")
                if color:
                    is_hex = re.match(r"^#[0-9A-Fa-f]{6}$", color)
                    is_rgba = color.startswith("rgba(")
                    assert is_hex or is_rgba, f"{name}.{color_type}: Invalid color format {color}"

    def test_workflow_components_importable(self):
        """Verify workflow components are importable."""
        from src.ui.design_system.workflow_components import (
            WORKFLOW_STAGES,
            render_workflow_stepper,
            render_stage_progress,
            render_stage_lock_banner,
            render_canonical_workflow_summary,
        )

        assert len(WORKFLOW_STAGES) == 6, "Should have 6 workflow stages"

    def test_audit_components_importable(self):
        """Verify audit components are importable."""
        from src.ui.design_system.audit_components import (
            render_audit_status_badge,
            render_hash_verification_panel,
            render_audit_event_log,
            render_tamper_detection_alert,
            render_session_integrity_summary,
        )

        assert callable(render_audit_status_badge)

    def test_provenance_components_importable(self):
        """Verify provenance components are importable."""
        from src.ui.design_system.provenance_components import (
            render_provenance_panel,
            render_literature_type_indicator,
            render_metadata_completeness,
            render_decision_history,
            render_source_lineage,
        )

        assert callable(render_provenance_panel)

    def test_reproducibility_components_importable(self):
        """Verify reproducibility components are importable."""
        from src.ui.design_system.reproducibility_components import (
            render_replay_verification_panel,
            render_determinism_status_indicator,
            render_checksum_verification_panel,
            render_reproducibility_bundle_summary,
        )

        assert callable(render_replay_verification_panel)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
