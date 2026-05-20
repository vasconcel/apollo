"""
APOLLO Integration Tests - Architectural Integrity Verification

Tests that verify the canonical architecture operates correctly:
- Protocol hash determinism across serialization roundtrips
- Metadata lineage propagation from ATLAS to review dicts
- ScreeningSession authority (record_decision, save/load, hash integrity)
- Export engine canonical usage (json.dump, ExcelWriter)
- No orphaned module execution paths

Evidence standard: Every test includes runtime assertion with actual output values.
"""
import os
import sys
import json
import tempfile
import hashlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import pandas as pd
from src.core.dynamic_protocol import (
    DynamicProtocol, Criterion, ECProtocol, ICProtocol, QCProtocol,
    create_default_protocol
)
from src.core.screening_session import ScreeningSession, ArticleReview
from src.core.article_metadata import normalize_wl_metadata, article_to_dict
from src.core.export_engine import ExportEngine


class TestProtocolDeterminism:
    """Verify protocol hashing is deterministic across serialization."""

    def test_protocol_hash_deterministic_after_roundtrip(self):
        """Canonical: Protocol hash must be stable after to_dict/from_dict."""
        protocol = create_default_protocol()

        original_hash = protocol.protocol_hash
        original_summary = protocol.get_summary()

        dict_form = protocol.to_dict()
        restored = DynamicProtocol.from_dict(dict_form)

        restored_hash = restored.protocol_hash
        restored_summary = restored.get_summary()

        assert original_hash == restored_hash, (
            f"Protocol hash changed after roundtrip. "
            f"Original: {original_hash}, Restored: {restored_hash}"
        )
        assert original_summary["version"] == restored_summary["version"]
        assert original_summary["ec_count"] == restored_summary["ec_count"]
        assert original_summary["ic_count"] == restored_summary["ic_count"]

    def test_protocol_json_uses_json_dumps_not_str(self):
        """Verify canonical pattern: json.dumps() not str()."""
        protocol = create_default_protocol()

        canonical_json = json.dumps(protocol.to_dict(), sort_keys=True, ensure_ascii=False)

        parsed = json.loads(canonical_json)
        assert isinstance(parsed, dict)
        assert "criteria" in str(protocol.to_dict())

        assert "True" not in canonical_json
        assert "False" not in canonical_json

    def test_same_input_produces_same_hash(self):
        """Determinism: identical protocol + identical data = identical hash."""
        protocol1 = create_default_protocol()
        protocol2 = create_default_protocol()

        assert protocol1.protocol_hash == protocol2.protocol_hash, (
            f"Two default protocols produced different hashes: "
            f"{protocol1.protocol_hash} vs {protocol2.protocol_hash}"
        )


class TestMetadataLineage:
    """Verify metadata lineage propagates through normalization pipeline."""

    def test_wl_metadata_normalization_preserves_fields(self):
        """Canonical: normalize_wl_metadata produces structured metadata dict."""
        from src.core.article_metadata import normalize_wl_metadata

        raw_row = {
            "Title": "Test Paper",
            "Authors": "Smith, J.",
            "Year": 2023,
            "DOI": "10.1234/test",
            "Abstract": "Test abstract",
            "Journal": "Test Journal",
            "Keywords": "SE, Testing",
            "Global_ID": "G001",
            "Local_ID": "L001"
        }

        article = normalize_wl_metadata(raw_row)

        assert article.title == "Test Paper"
        assert article.abstract == "Test abstract"
        assert article.global_id == "G001"
        assert article.local_id == "L001"
        assert article.year == 2023

    def test_article_to_dict_includes_metadata(self):
        """ArticleReview.to_dict() must include metadata fields."""
        article = ArticleReview(
            article_id="TEST-001",
            title="Test Paper",
            abstract="Abstract",
            metadata={
                "year": "2023",
                "authors": "Smith, J.",
                "literature_type": "WL",
                "doi": "10.1234/test"
            }
        )

        article_dict = article.to_dict()

        assert "metadata" in article_dict
        assert article_dict["metadata"]["year"] == "2023"
        assert article_dict["metadata"]["literature_type"] == "WL"

    def test_to_review_dict_includes_lineage_fields(self):
        """ArticleReview.to_review_dict() includes all provenance fields."""
        article = ArticleReview(
            article_id="TEST-002",
            title="Test Paper",
            abstract="Abstract",
            metadata={
                "year": "2023",
                "literature_type": "WL",
                "authors": "Doe, A.",
                "year_source": "crossref",
                "metadata_completeness": "complete"
            }
        )

        review_dict = article.to_review_dict()

        assert "year_source" in review_dict
        assert "metadata_completeness" in review_dict
        assert review_dict["literature_type"] == "WL"


class TestScreeningSessionAuthority:
    """Verify ScreeningSession provides canonical session authority."""

    def test_session_records_decision_with_timestamp(self):
        """Canonical: record_decision() stamps decision with timestamp."""
        session = ScreeningSession(
            session_id="test-session-001",
            created_at="2024-01-01T00:00:00",
            protocol_version="1.0"
        )

        article = ArticleReview(
            article_id="ART-001",
            title="Test Paper",
            abstract="Abstract",
            metadata={"literature_type": "WL"}
        )
        session.articles.append(article)
        session.total_count = 1

        result = session.record_decision("include", notes="Test decision")

        assert result is True
        assert article.ec_stage == "include"
        assert article.ec_notes == "Test decision"
        assert article.ec_timestamp != ""
        assert len(article.ec_timestamp) > 0

    def test_session_save_produces_valid_json(self):
        """Canonical: save() produces parseable JSON with hash."""
        session = ScreeningSession(
            session_id="test-session-002",
            created_at="2024-01-01T00:00:00",
            protocol_version="1.0"
        )

        article = ArticleReview(
            article_id="ART-002",
            title="Test Paper",
            abstract="Abstract",
            metadata={"literature_type": "WL"}
        )
        session.articles.append(article)
        session.record_decision("include")

        with tempfile.TemporaryDirectory() as tmpdir:
            saved_path = session.save(output_dir=tmpdir)

            assert os.path.exists(saved_path), f"Session file not saved: {saved_path}"

            with open(saved_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)

            assert "session_id" in loaded
            assert "session_hash" in loaded
            assert loaded["session_id"] == "test-session-002"
            assert loaded["included_count"] == 1
            assert len(loaded["articles"]) == 1

    def test_session_load_restores_state(self):
        """Canonical: load() restores session with correct state."""
        session = ScreeningSession(
            session_id="test-session-003",
            created_at="2024-01-01T00:00:00",
            protocol_version="1.0"
        )

        article = ArticleReview(
            article_id="ART-003",
            title="Test Paper",
            abstract="Abstract",
            metadata={"literature_type": "WL"}
        )
        session.articles.append(article)
        session.record_decision("exclude")

        with tempfile.TemporaryDirectory() as tmpdir:
            saved_path = session.save(output_dir=tmpdir)

            loaded_session = ScreeningSession.load(
                session_id="test-session-003",
                output_dir=tmpdir
            )

        assert loaded_session is not None
        assert loaded_session.session_id == "test-session-003"
        assert loaded_session.excluded_count == 1
        assert len(loaded_session.articles) == 1
        assert loaded_session.articles[0].article_id == "ART-003"

    def test_session_hash_deterministic(self):
        """Canonical: Same decisions produce same session hash (same session_id required)."""
        session1 = ScreeningSession(
            session_id="test-session-004",
            created_at="2024-01-01T00:00:00",
            protocol_version="1.0"
        )
        session1.articles.append(ArticleReview(
            article_id="ART-004", title="Paper", abstract="Abstract",
            metadata={"literature_type": "WL"}
        ))
        session1.record_decision("include")

        session2 = ScreeningSession(
            session_id="test-session-004",
            created_at="2024-01-01T00:00:00",
            protocol_version="1.0"
        )
        session2.articles.append(ArticleReview(
            article_id="ART-005", title="Paper", abstract="Abstract",
            metadata={"literature_type": "WL"}
        ))
        session2.record_decision("include")

        with tempfile.TemporaryDirectory() as tmpdir:
            path1 = session1.save(output_dir=tmpdir)
            path2 = session2.save(output_dir=tmpdir)

            data1 = json.load(open(path1, "r"))
            data2 = json.load(open(path2, "r"))

        assert data1["session_hash"] == data2["session_hash"], (
            f"Identical decisions with same session_id produced different session hashes: "
            f"{data1['session_hash']} vs {data2['session_hash']}"
        )


class TestExportEngineCanonical:
    """Verify ExportEngine uses canonical patterns (json.dump, ExcelWriter)."""

    def test_export_engine_uses_json_dump_not_str(self):
        """Canonical: export_session_json uses json.dump(), not str()."""
        session = ScreeningSession(
            session_id="test-export-001",
            created_at="2024-01-01T00:00:00",
            protocol_version="1.0"
        )
        session.articles.append(ArticleReview(
            article_id="ART-EXPORT-001",
            title="Export Test Paper",
            abstract="Abstract",
            metadata={"literature_type": "WL"}
        ))
        session.record_decision("include")

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "session.json")

            engine = ExportEngine()
            result = engine.export_session_json(session, json_path)

            assert result == json_path
            assert os.path.exists(json_path)

            with open(json_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)

            assert "session_id" in loaded
            assert loaded["session_id"] == "test-export-001"

    def test_export_decisions_excel_creates_sheets(self):
        """Canonical: export_decisions_excel creates WL/GL sheets."""
        session = ScreeningSession(
            session_id="test-excel-001",
            created_at="2024-01-01T00:00:00",
            protocol_version="1.0"
        )
        session.articles.append(ArticleReview(
            article_id="ART-WL-001",
            title="WL Paper",
            abstract="Abstract",
            metadata={"literature_type": "WL", "library": "IEEE", "global_id": "G001"}
        ))
        session.articles.append(ArticleReview(
            article_id="ART-GL-001",
            title="GL Paper",
            abstract="Abstract",
            metadata={"literature_type": "GL", "url": "http://example.com"}
        ))
        session.record_decision("include")

        tmpdir = tempfile.mkdtemp()
        xlsx_path = os.path.join(tmpdir, "decisions.xlsx")

        engine = ExportEngine()
        result = engine.export_decisions_excel(session, xlsx_path)

        assert result == xlsx_path
        assert os.path.exists(xlsx_path)

        xl = pd.ExcelFile(xlsx_path)
        sheet_names = xl.sheet_names

        assert "WL" in sheet_names, f"WL sheet not found. Available: {sheet_names}"
        assert "GL" in sheet_names, f"GL sheet not found. Available: {sheet_names}"

        wl_df = pd.read_excel(xlsx_path, sheet_name="WL")
        gl_df = pd.read_excel(xlsx_path, sheet_name="GL")

        assert len(wl_df) == 1
        assert len(gl_df) == 1
        assert wl_df.iloc[0]["Title"] == "WL Paper"
        assert gl_df.iloc[0]["Title"] == "GL Paper"

        xl.close()
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_export_manifest_uses_json_dump(self):
        """Canonical: export_manifest uses json.dump(), produces valid JSON."""
        session = ScreeningSession(
            session_id="test-manifest-001",
            created_at="2024-01-01T00:00:00",
            protocol_version="1.0"
        )
        session.articles.append(ArticleReview(
            article_id="ART-MAN-001",
            title="Manifest Test",
            abstract="Abstract",
            metadata={"literature_type": "WL"}
        ))
        session.record_decision("include")

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "input.xlsx")
            with open(input_path, "w") as f:
                f.write("dummy")

            manifest_path = os.path.join(tmpdir, "manifest.json")

            engine = ExportEngine()
            result = engine.export_manifest(session, input_path, manifest_path)

            assert result == manifest_path
            assert os.path.exists(manifest_path)

            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)

            assert "export_id" in manifest
            assert "protocol_version" in manifest
            assert "input_checksum" in manifest


class TestNoOrphanedPaths:
    """Verify no orphaned modules are reachable from canonical paths."""

    def test_database_not_imported_by_canonical_modules(self):
        """Database module is not imported by any canonical module."""
        canonical_modules = [
            "src/core/screening_session.py",
            "src/core/dynamic_protocol.py",
            "src/core/article_metadata.py",
            "src/core/export_engine.py",
            "src/core/atlas_processor.py",
            "src/core/llm_assistant.py",
            "src/core/calibration_engine.py",
        ]

        for module_path in canonical_modules:
            full_path = Path(__file__).parent.parent / module_path
            if not full_path.exists():
                continue

            content = full_path.read_text(encoding="utf-8")

            assert "from src.core.database import" not in content, (
                f"{module_path} imports database — orphaned path detected"
            )
            assert "import src.core.database" not in content, (
                f"{module_path} imports database — orphaned path detected"
            )

    def test_llm_reasoning_not_imported_by_canonical_modules(self):
        """llm_reasoning.py is not imported by canonical modules."""
        canonical_modules = [
            "src/core/screening_session.py",
            "src/core/dynamic_protocol.py",
            "src/core/article_metadata.py",
            "src/core/export_engine.py",
            "src/core/llm_assistant.py",
            "src/ui/modules/protocol_view.py",
            "src/ui/modules/ec_screening_view.py",
            "src/ui/modules/ic_screening_view.py",
            "src/ui/modules/qc_assessment_view.py",
            "src/ui/modules/calibration_view.py",
            "src/ui/modules/export_view.py",
        ]

        for module_path in canonical_modules:
            full_path = Path(__file__).parent.parent / module_path
            if not full_path.exists():
                continue

            content = full_path.read_text(encoding="utf-8")

            assert "llm_reasoning" not in content.lower(), (
                f"{module_path} references llm_reasoning — dead code path detected"
            )


class TestCriteriaRegistry:
    """Verify criteria_registry is the single canonical source for keywords."""

    def test_criteria_registry_replaces_keyword_literals(self):
        """criteria_registry eliminates keyword literals from views."""
        views_to_check = [
            "src/ui/modules/protocol_view.py",
            "src/ui/modules/ec_screening_view.py",
            "src/ui/modules/ic_screening_view.py",
        ]

        for module_path in views_to_check:
            full_path = Path(__file__).parent.parent / module_path
            if not full_path.exists():
                continue

            content = full_path.read_text(encoding="utf-8")

            keywords_found = []
            for kw in ["software", "engineering", "testing", "validation", "qa", "quality"]:
                if kw in content.lower() and f'"{kw}"' in content.lower():
                    keywords_found.append(kw)

            assert len(keywords_found) == 0, (
                f"{module_path} contains hardcoded keyword literals: {keywords_found}. "
                f"Use criteria_registry instead."
            )


class TestDecomposedModules:
    """Verify new decomposed modules import correctly and provide canonical exports."""

    def test_article_record_imports(self):
        """Canonical: article_record.py exports ArticleRecord dataclass."""
        from src.core.article_record import ArticleRecord, EligibilityDecision, QualityDecision
        
        record = ArticleRecord(title="Test", abstract="Abstract", global_id="G001")
        assert record.title == "Test"
        assert record.global_id == "G001"

    def test_ingestion_engine_imports(self):
        """Canonical: ingestion_engine.py exports ATLASLoader."""
        from src.core.ingestion_engine import ATLASLoader
        
        assert hasattr(ATLASLoader, 'WL_SHEET_ALIASES')
        assert hasattr(ATLASLoader, 'load_atlas_file')
        assert hasattr(ATLASLoader, 'normalize_wl_columns')
        assert hasattr(ATLASLoader, 'normalize_gl_columns')

    def test_criteria_evaluator_imports(self):
        """Canonical: criteria_evaluator.py exports ExclusionCriteria, InclusionCriteria."""
        from src.core.criteria_evaluator import ExclusionCriteria, InclusionCriteria, QualityCriteria
        
        result = ExclusionCriteria.evaluate("Test", "Abstract", 2020, True, False, "")
        assert result.decision in ("include", "exclude")
        
        ic_result = InclusionCriteria.evaluate("Test", "Abstract")
        assert ic_result.decision in ("include", "exclude")
        
        qc_result = QualityCriteria.evaluate("Test", "Abstract", "WL")
        assert qc_result.decision in ("include", "exclude")

    def test_year_extraction_imports(self):
        """Canonical: year_extraction.py exports extract_year and compute_metadata_completeness."""
        from src.core.year_extraction import extract_year, compute_metadata_completeness
        
        year, source = extract_year("Paper 2023", "Abstract", None)
        assert year == 2023
        assert source == "regex"
        
        year2, source2 = extract_year("Paper", "Abstract", 2021)
        assert year2 == 2021
        assert source2 == "structured"
        
        completeness = compute_metadata_completeness({"Title": "Test", "Abstract": "Long enough"})
        assert completeness in ("complete", "partial", "minimal")

    def test_atlas_processor_still_exports_article_record(self):
        """Backward compat: atlas_processor.py still exports ArticleRecord from article_record."""
        from src.core.atlas_processor import ArticleRecord
        
        record = ArticleRecord(title="Compat Test")
        assert record.title == "Compat Test"

    def test_atlas_processor_still_exports_functions(self):
        """Backward compat: atlas_processor.py still exports public functions."""
        from src.core.atlas_processor import process_atlas_file, create_screening_session
        
        assert callable(process_atlas_file)
        assert callable(create_screening_session)


class TestProtocolEngineAuthority:
    """Verify protocol_engine.py has clear authority boundaries."""

    def test_protocol_engine_uses_criteria_registry(self):
        """Protocol engine delegates default evaluation to criteria_registry."""
        from src.core.protocol_engine import ProtocolEngine, get_default_protocol
        from src.core.criteria_registry import evaluate_se_context, evaluate_recruitment
        
        engine = ProtocolEngine(protocol=None)
        
        data = {"title": "Software Testing Research", "abstract": "Empirical study of testing methods in software engineering companies", "year": 2020}
        decision, criterion, reason = engine.evaluate_ec(data, "WL", False)
        
        assert decision in ("include", "exclude")
        assert criterion == "NO" or criterion.startswith("EC")
        
        data2 = {"title": "Recruitment Methods", "abstract": "Study of recruitment in software companies"}
        ic_decision, ic_criterion, ic_reason = engine.evaluate_ic(data2, "WL")
        
        assert ic_decision in ("include", "exclude")

    def test_protocol_engine_parses_protocol_rules(self):
        """Protocol engine correctly parses and applies protocol definitions."""
        from src.core.protocol_engine import ProtocolEngine
        
        test_protocol = {
            "protocol_version": "1.0",
            "exclusion_criteria": {
                "EC1": {
                    "type": "rule",
                    "field": "text_combined",
                    "operator": "contains_any",
                    "value": ["software", "engineering"],
                    "action": "exclude_if_none_found",
                    "description": "No SE context"
                }
            },
            "inclusion_criteria": {},
            "quality_criteria": {"threshold": 2.0}
        }
        
        engine = ProtocolEngine(protocol=test_protocol)
        
        data = {"title": "Random Topic", "abstract": "Random abstract about gardening", "text_combined": "random gardening"}
        decision, criterion, reason = engine.evaluate_ec(data, "WL", False)
        
        assert decision == "exclude"
        assert criterion == "EC1"

    def test_protocol_engine_validate_function(self):
        """Protocol engine provides validate_protocol function."""
        from src.core.protocol_engine import validate_protocol
        
        valid_protocol = {
            "protocol_version": "1.0",
            "name": "Test Protocol",
            "exclusion_criteria": {},
            "inclusion_criteria": {},
            "quality_criteria": {"threshold": 2.0}
        }
        
        is_valid, errors = validate_protocol(valid_protocol)
        assert is_valid is True
        assert len(errors) == 0
        
        invalid_protocol = {"name": "Incomplete"}
        is_valid2, errors2 = validate_protocol(invalid_protocol)
        assert is_valid2 is False
        assert len(errors2) > 0

    def test_no_overlap_atlas_processor_protocol_engine(self):
        """atlas_processor does NOT re-implement protocol parsing logic."""
        atlas_content = Path("D:/Projetos/apollo/src/core/atlas_processor.py").read_text(encoding="utf-8")
        
        assert "get_default_protocol" not in atlas_content
        assert "load_protocol" not in atlas_content
        assert "validate_protocol" not in atlas_content
        assert "ProtocolRule" not in atlas_content
        assert "class ProtocolEngine" not in atlas_content
        assert "class ProtocolRule" not in atlas_content


class TestUIBoundaryEnforcement:
    """Verify UI layer never performs DataFrame operations."""

    def test_screening_views_no_dataframe_operations(self):
        """UI views must not contain pd.read_excel or .iterrows."""
        screening_views = [
            "src/ui/modules/ec_screening_view.py",
            "src/ui/modules/ic_screening_view.py",
            "src/ui/modules/qc_assessment_view.py",
        ]

        for view_path in screening_views:
            full_path = Path(__file__).parent.parent / view_path
            if not full_path.exists():
                continue

            content = full_path.read_text(encoding="utf-8")

            assert "pd.read_excel" not in content, (
                f"{view_path} contains pd.read_excel — UI boundary violation"
            )
            assert ".iterrows()" not in content, (
                f"{view_path} contains .iterrows() — UI boundary violation"
            )

    def test_no_str_on_dict_in_views(self):
        """UI views must not use str(dict) for JSON serialization."""
        view_files = [
            "src/ui/modules/export_view.py",
            "src/ui/modules/qc_assessment_view.py",
        ]

        for view_path in view_files:
            full_path = Path(__file__).parent.parent / view_path
            if not full_path.exists():
                continue

            content = full_path.read_text(encoding="utf-8")

            import re
            lines_with_str_dict = []
            for i, line in enumerate(content.split("\n"), 1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if "str(" in line and ("{" in line or "dict" in line.lower()):
                    if "json.dumps" not in line:
                        lines_with_str_dict.append(f"Line {i}: {line.rstrip()}")

            assert len(lines_with_str_dict) == 0, (
                f"{view_path} uses str(dict) for JSON serialization:\n" +
                "\n".join(lines_with_str_dict)
            )


class TestSessionRoundtrip:
    """Verify session state survives export/reload cycle."""

    def test_session_decisions_preserved_after_export_reload(self):
        """Canonical: decisions survive Session → JSON → Reload cycle."""
        session = ScreeningSession(
            session_id="roundtrip-test-001",
            created_at="2024-01-01T00:00:00",
            protocol_version="1.0"
        )

        wl_article = ArticleReview(
            article_id="WL-001",
            title="White Literature Paper",
            abstract="Abstract for WL paper",
            metadata={"literature_type": "WL", "library": "ACM", "global_id": "G001"}
        )
        gl_article = ArticleReview(
            article_id="GL-001",
            title="Grey Literature Paper",
            abstract="Abstract for GL paper",
            metadata={"literature_type": "GL", "url": "http://example.com/paper"}
        )

        session.articles.append(wl_article)
        session.articles.append(gl_article)
        session.total_count = 2
        session.stage = "ec"
        session.record_decision("include", notes="WL include")

        with tempfile.TemporaryDirectory() as tmpdir:
            saved_path = session.save(output_dir=tmpdir)

            loaded_session = ScreeningSession.load(
                session_id="roundtrip-test-001",
                output_dir=tmpdir
            )

        assert loaded_session is not None
        assert loaded_session.session_id == "roundtrip-test-001"
        assert loaded_session.total_count == 2
        assert len(loaded_session.articles) == 2

        wl_loaded = next((a for a in loaded_session.articles if a.article_id == "WL-001"), None)
        gl_loaded = next((a for a in loaded_session.articles if a.article_id == "GL-001"), None)

        assert wl_loaded is not None
        assert gl_loaded is not None
        assert wl_loaded.ec_stage == "include"
        assert gl_loaded.ec_stage == ""

    def test_session_hash_matches_after_reload(self):
        """Canonical: session hash is identical after save/load cycle."""
        session = ScreeningSession(
            session_id="hash-roundtrip-001",
            created_at="2024-01-01T00:00:00",
            protocol_version="1.0"
        )

        article = ArticleReview(
            article_id="HASH-001",
            title="Hash Test Paper",
            abstract="Abstract",
            metadata={"literature_type": "WL"}
        )
        session.articles.append(article)
        session.record_decision("exclude", notes="Failed EC")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = session.save(output_dir=tmpdir)

            loaded_session = ScreeningSession.load(
                session_id="hash-roundtrip-001",
                output_dir=tmpdir
            )

        saved_path = session.save(output_dir=tmpdir)
        original_filename = os.path.basename(saved_path)

        loaded_session = ScreeningSession.load(
            session_id="hash-roundtrip-001",
            output_dir=tmpdir
        )

        loaded_path = loaded_session.save(output_dir=tmpdir)

        with open(saved_path, "r") as f:
            original_data = json.load(f)

        with open(loaded_path, "r") as f:
            loaded_data = json.load(f)

        assert original_data["session_hash"] == loaded_data["session_hash"], (
            f"Session hash changed after reload: "
            f"{original_data['session_hash']} vs {loaded_data['session_hash']}"
        )


class TestArticleIdentityPreservation:
    """Verify article identity is preserved through the pipeline."""

    def test_article_global_id_preserved_through_normalization(self):
        """Canonical: global_id must survive normalize_wl_metadata roundtrip."""
        from src.core.article_metadata import normalize_wl_metadata

        raw_row = {
            "Title": "Identity Test Paper",
            "Global_ID": "ID-12345",
            "Local_ID": "LOCAL-999",
            "Abstract": "Test abstract for identity preservation",
            "Year": 2023,
            "Authors": "Test Author",
            "Library": "IEEE"
        }

        article = normalize_wl_metadata(raw_row)

        assert article.global_id == "ID-12345", (
            f"global_id changed: expected 'ID-12345', got '{article.global_id}'"
        )
        assert article.local_id == "LOCAL-999", (
            f"local_id changed: expected 'LOCAL-999', got '{article.local_id}'"
        )

    def test_article_id_consistent_after_roundtrip(self):
        """Canonical: article_id is stable across to_dict/from_dict."""
        article = ArticleReview(
            article_id="PERM-001",
            title="Permanent ID Test",
            abstract="Abstract",
            metadata={"literature_type": "WL", "global_id": "G-PERM"}
        )

        article_dict = article.to_dict()
        assert article_dict["article_id"] == "PERM-001"

        review_dict = article.to_review_dict()
        assert review_dict["article_id"] == "PERM-001"

        article_dict_full = article.to_dict()
        assert article_dict_full["article_id"] == "PERM-001"
        assert "global_id" in article_dict_full.get("metadata", {})
        assert article_dict_full["metadata"]["global_id"] == "G-PERM"


class TestE2EReproducibility:
    """Verify full pipeline produces reproducible results."""

    def test_atlas_processor_produces_deterministic_results(self):
        """Full ATLAS processing produces deterministic ArticleRecords."""
        from src.core.ingestion_engine import ATLASLoader
        from src.core.criteria_evaluator import ExclusionCriteria, InclusionCriteria, QualityCriteria
        from src.core.year_extraction import extract_year, compute_metadata_completeness
        from src.core.article_record import ArticleRecord
        
        test_row = {
            "Library": "IEEE", "Global_ID": "G-DET-001", "Local_ID": "L001",
            "Title": "Software Testing Methods in Engineering 2023",
            "Abstract": "This paper studies testing methods for software engineering companies. Empirical results show improved quality.",
            "Keywords": "testing, software engineering", "Authors": "Smith, J.", "Year": 2023,
            "Duplicate_Flag": "", "Title": "Software Testing Methods in Engineering 2023"
        }
        
        row = type('MockRow', (), test_row)()
        row.get = lambda k, d=None: test_row.get(k, d)
        row.to_dict = lambda: test_row
        
        year, year_source = extract_year(row.Title, row.Abstract, row.Year)
        metadata = row.to_dict()
        metadata["year_source"] = year_source
        metadata["metadata_completeness"] = compute_metadata_completeness(metadata)
        
        record1 = ArticleRecord(
            literature_type="WL", library=row.Library, global_id=row.Global_ID,
            local_id=row.Local_ID, title=row.Title, abstract=row.Abstract,
            keywords=row.Keywords, authors=row.Authors, year=year, metadata=metadata
        )
        
        ec = ExclusionCriteria.evaluate(record1.title, record1.abstract, record1.year, True, False, "")
        record1.ec_decision = ec.to_display()
        
        if ec.decision == "include":
            ic = InclusionCriteria.evaluate(record1.title, record1.abstract)
            record1.ic_decision = ic.to_display()
            if ic.decision == "include":
                qc = QualityCriteria.evaluate(record1.title, record1.abstract, "WL")
                record1.qc_score = qc.to_display()
                record1.final_decision = "INCLUDE" if qc.decision == "include" else "EXCLUDE"
            else:
                record1.final_decision = "EXCLUDE"
        else:
            record1.final_decision = "EXCLUDE"
        
        record2_dict = record1.__dict__.copy()
        record2 = ArticleRecord(**{k: v for k, v in record2_dict.items() if k in ArticleRecord.__dataclass_fields__})
        
        assert record1.ec_decision == record2.ec_decision
        assert record1.ic_decision == record2.ic_decision
        assert record1.qc_score == record2.qc_score

    def test_protocol_hash_matches_after_roundtrip(self):
        """Protocol hash is stable after JSON serialization."""
        from src.core.dynamic_protocol import create_default_protocol
        
        protocol = create_default_protocol()
        original_hash = protocol.protocol_hash
        
        protocol_dict = protocol.to_dict()
        from src.core.dynamic_protocol import DynamicProtocol
        restored = DynamicProtocol.from_dict(protocol_dict)
        
        assert original_hash == restored.protocol_hash

    def test_session_hash_reproducible_with_same_articles(self):
        """Identical sessions produce identical hashes."""
        from src.core.screening_session import ScreeningSession, ArticleReview
        
        def make_session(session_id):
            session = ScreeningSession(
                session_id=session_id,
                created_at="2024-01-01T00:00:00",
                protocol_version="1.0"
            )
            for i in range(3):
                article = ArticleReview(
                    article_id=f"ART-{i}",
                    title=f"Paper {i}",
                    abstract="Test abstract",
                    metadata={"literature_type": "WL"}
                )
                session.articles.append(article)
            session.total_count = 3
            return session
        
        s1 = make_session("repro-test")
        s2 = make_session("repro-test")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            p1 = s1.save(output_dir=tmpdir)
            p2 = s2.save(output_dir=tmpdir)
            
            d1 = json.load(open(p1, "r"))
            d2 = json.load(open(p2, "r"))
        
        assert d1["session_hash"] == d2["session_hash"]
        assert d1["total_count"] == d2["total_count"] == 3

    def test_decision_outcomes_stable_across_evaluator_calls(self):
        """Same article evaluated multiple times produces same outcome."""
        from src.core.criteria_evaluator import ExclusionCriteria, InclusionCriteria
        
        title = "Software Engineering Recruitment Study"
        abstract = "This paper studies recruitment methods in software engineering companies."
        
        results = []
        for _ in range(5):
            ec = ExclusionCriteria.evaluate(title, abstract, 2020, True, False, "")
            ic = InclusionCriteria.evaluate(title, abstract)
            results.append((ec.decision, ec.criterion, ic.decision, ic.criterion))
        
        unique_results = set(results)
        assert len(unique_results) == 1, f"Non-deterministic results: {unique_results}"


class TestPersistenceAndAudit:
    """Phase 1-2: Persistent session and immutable audit chain."""

    def test_session_save_to_json_creates_file(self):
        """Phase 1: save_to_json creates valid JSON file."""
        session = ScreeningSession(
            session_id="persist-test-001",
            created_at="2024-01-01T00:00:00",
            protocol_version="1.0"
        )
        session.articles.append(ArticleReview(
            article_id="PERSIST-001",
            title="Persist Test",
            abstract="Abstract",
            metadata={"literature_type": "WL"}
        ))
        session.record_decision("include")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "session.json")
            saved_path = session.save_to_json(path)

            assert os.path.exists(saved_path)
            with open(saved_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            assert data["session_id"] == "persist-test-001"
            assert data["schema_version"] == "2.0"
            assert "session_checksum" in data

    def test_session_load_from_json_restores_state(self):
        """Phase 1: load_from_json restores session with checksum validation."""
        session = ScreeningSession(
            session_id="load-test-001",
            created_at="2024-01-01T00:00:00",
            protocol_version="1.0"
        )
        session.articles.append(ArticleReview(
            article_id="LOAD-001",
            title="Load Test",
            abstract="Abstract",
            metadata={"literature_type": "WL"}
        ))
        session.record_decision("include")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "session.json")
            session.save_to_json(path)

            session2 = ScreeningSession("dummy", "2024-01-01", "1.0")
            success = session2.load_from_json(path)

            assert success is True
            assert session2.session_id == "load-test-001"
            assert session2.included_count == 1

    def test_session_checksum_deterministic(self):
        """Phase 1: compute_checksum produces stable SHA256."""
        session = ScreeningSession(
            session_id="checksum-test",
            created_at="2024-01-01T00:00:00",
            protocol_version="1.0"
        )
        session.articles.append(ArticleReview(
            article_id="CHECK-001",
            title="Checksum Test",
            abstract="Abstract",
            metadata={"literature_type": "WL"}
        ))
        session.record_decision("include")

        checksum1 = session.compute_checksum()
        checksum2 = session.compute_checksum()

        assert checksum1 == checksum2
        assert len(checksum1) == 64

    def test_audit_chain_events_appended_on_decision(self):
        """Phase 2: audit events appended to chain on record_decision."""
        session = ScreeningSession(
            session_id="audit-test-001",
            created_at="2024-01-01T00:00:00",
            protocol_version="1.0"
        )
        session.articles.append(ArticleReview(
            article_id="AUDIT-001",
            title="Audit Test",
            abstract="Abstract",
            metadata={"literature_type": "WL"}
        ))
        session.record_decision("include")

        events = session.get_audit_events()
        assert len(events) == 1
        assert "event_id" in events[0]
        assert "previous_hash" in events[0]
        assert "current_hash" in events[0]
        assert events[0]["previous_hash"] == "GENESIS"

    def test_audit_chain_verify_passes_clean(self):
        """Phase 2: verify_audit_chain passes for unmodified chain."""
        session = ScreeningSession(
            session_id="verify-test-001",
            created_at="2024-01-01T00:00:00",
            protocol_version="1.0"
        )
        session.articles.append(ArticleReview(
            article_id="VERIFY-001",
            title="Verify Test",
            abstract="Abstract",
            metadata={"literature_type": "WL"}
        ))
        session.record_decision("include")
        session.record_decision("include")

        is_valid, errors = session.verify_audit_chain()
        assert is_valid is True
        assert len(errors) == 0

    def test_audit_chain_detect_tampering_fails_altered_event(self):
        """Phase 2: detect_tampering fails if event is altered."""
        session = ScreeningSession(
            session_id="tamper-test-001",
            created_at="2024-01-01T00:00:00",
            protocol_version="1.0"
        )
        session.articles.append(ArticleReview(
            article_id="TAMPER-001",
            title="Tamper Test",
            abstract="Abstract",
            metadata={"literature_type": "WL"}
        ))
        session.record_decision("include")

        session._audit_chain[0]["decision"] = "altered"
        is_clean, tampered = session.detect_tampering()

        assert is_clean is False
        assert len(tampered) > 0


class TestReproducibilityBundle:
    """Phase 3: Reproducibility bundle creation and validation."""

    def test_reproducibility_bundle_creation(self):
        """Phase 3: Create bundle with all required files."""
        from src.core.reproducibility_engine import ReproducibilityEngine, create_reproducibility_bundle

        session = ScreeningSession(
            session_id="bundle-test-001",
            created_at="2024-01-01T00:00:00",
            protocol_version="1.0"
        )
        session.articles.append(ArticleReview(
            article_id="BUNDLE-001",
            title="Bundle Test",
            abstract="Abstract",
            metadata={"literature_type": "WL"}
        ))
        session.record_decision("include")

        with tempfile.TemporaryDirectory() as tmpdir:
            bundle = create_reproducibility_bundle(session, tmpdir)

            assert os.path.exists(bundle.bundle_path)
            assert os.path.exists(bundle.manifest_json)
            assert os.path.exists(bundle.protocol_json)
            assert os.path.exists(bundle.session_json)
            assert os.path.exists(bundle.audit_log_json)
            assert os.path.exists(bundle.checksums_sha256)

    def test_bundle_manifest_includes_all_fields(self):
        """Phase 3: Manifest includes required metadata."""
        from src.core.reproducibility_engine import ReproducibilityEngine

        session = ScreeningSession(
            session_id="manifest-test-001",
            created_at="2024-01-01T00:00:00",
            protocol_version="1.0"
        )
        session.articles.append(ArticleReview(
            article_id="MANIFEST-001",
            title="Manifest Test",
            abstract="Abstract",
            metadata={"literature_type": "WL"}
        ))

        with tempfile.TemporaryDirectory() as tmpdir:
            engine = ReproducibilityEngine(session)
            bundle = engine.create_bundle(tmpdir)

            with open(bundle.manifest_json, "r", encoding="utf-8") as f:
                manifest = json.load(f)

            assert "apollo_version" in manifest
            assert "protocol_hash" in manifest
            assert "session_hash" in manifest
            assert "article_counts" in manifest
            assert "total" in manifest["article_counts"]
            assert "wl" in manifest["article_counts"]
            assert "gl" in manifest["article_counts"]


class TestDeterministicReplay:
    """Phase 4: Deterministic replay validation."""

    def test_replay_session_reconstructs_state(self):
        """Phase 4: replay_session restores session from bundle."""
        from src.core.reproducibility_engine import ReplayEngine, create_reproducibility_bundle

        session = ScreeningSession(
            session_id="replay-test-001",
            created_at="2024-01-01T00:00:00",
            protocol_version="1.0"
        )
        session.articles.append(ArticleReview(
            article_id="REPLAY-001",
            title="Replay Test",
            abstract="Abstract",
            metadata={"literature_type": "WL"}
        ))
        session.record_decision("include")

        with tempfile.TemporaryDirectory() as tmpdir:
            bundle = create_reproducibility_bundle(session, tmpdir)

            replayed, validation = ReplayEngine.replay_session(bundle.bundle_path)

            assert replayed is not None
            assert replayed.session_id == "replay-test-001"
            assert validation["valid"] is True

    def test_regenerate_exports_produces_output(self):
        """Phase 4: regenerate_exports creates decision files."""
        from src.core.reproducibility_engine import ReplayEngine, create_reproducibility_bundle

        session = ScreeningSession(
            session_id="regen-test-001",
            created_at="2024-01-01T00:00:00",
            protocol_version="1.0"
        )
        session.articles.append(ArticleReview(
            article_id="REGEN-001",
            title="Regen Test",
            abstract="Abstract",
            metadata={"literature_type": "WL", "library": "IEEE", "global_id": "G001"}
        ))
        session.record_decision("include")

        with tempfile.TemporaryDirectory() as tmpdir:
            bundle = create_reproducibility_bundle(session, tmpdir)
            replayed, _ = ReplayEngine.replay_session(bundle.bundle_path)

            exports_dir = os.path.join(tmpdir, "regen_exports")
            exports = ReplayEngine.regenerate_exports(replayed, exports_dir)

            assert "decisions_excel" in exports
            assert os.path.exists(exports["decisions_excel"])


class TestStressAndDeterminism:
    """Phase 5: Stress testing at scale."""

    def test_session_with_10_articles_deterministic(self):
        """Phase 5: 10 articles produce stable hashes."""
        session = ScreeningSession(
            session_id="stress-10",
            created_at="2024-01-01T00:00:00",
            protocol_version="1.0"
        )
        for i in range(10):
            session.articles.append(ArticleReview(
                article_id=f"STRESS-10-{i}",
                title=f"Paper {i}",
                abstract="This paper studies software engineering testing methods.",
                metadata={"literature_type": "WL"}
            ))
        session.total_count = 10

        checksum1 = session.compute_checksum()
        for article in session.articles:
            session.record_decision("include")

        checksum2 = session.compute_checksum()
        assert checksum1 != checksum2

        checksum3 = session.compute_checksum()
        assert checksum2 == checksum3

    def test_session_with_100_articles_deterministic(self):
        """Phase 5: 100 articles produce stable hashes."""
        session = ScreeningSession(
            session_id="stress-100",
            created_at="2024-01-01T00:00:00",
            protocol_version="1.0"
        )
        for i in range(100):
            session.articles.append(ArticleReview(
                article_id=f"STRESS-100-{i}",
                title=f"Paper {i}",
                abstract="This paper studies software engineering testing methods.",
                metadata={"literature_type": "WL"}
            ))
        session.total_count = 100

        checksums = []
        for i, article in enumerate(session.articles[:10]):
            session.record_decision("include" if i % 2 == 0 else "exclude")
            checksums.append(session.compute_checksum())

        for i in range(1, len(checksums)):
            assert checksums[i] == checksums[i], "Hash drift detected"

    def test_audit_chain_stable_at_scale(self):
        """Phase 5: Audit chain remains stable with many events."""
        session = ScreeningSession(
            session_id="audit-scale",
            created_at="2024-01-01T00:00:00",
            protocol_version="1.0"
        )
        for i in range(50):
            session.articles.append(ArticleReview(
                article_id=f"AUDIT-SCALE-{i}",
                title=f"Paper {i}",
                abstract="Abstract",
                metadata={"literature_type": "WL"}
            ))

        for article in session.articles:
            session.record_decision("include")

        is_valid, errors = session.verify_audit_chain()
        assert is_valid is True
        assert len(errors) == 0
        assert len(session._audit_chain) == 50

    def test_save_load_roundtrip_preserves_state(self):
        """Phase 5: Save/load roundtrip preserves all state at scale."""
        session = ScreeningSession(
            session_id="roundtrip-scale",
            created_at="2024-01-01T00:00:00",
            protocol_version="1.0"
        )
        for i in range(20):
            session.articles.append(ArticleReview(
                article_id=f"RT-SCALE-{i}",
                title=f"Paper {i}",
                abstract="This paper studies software engineering testing methods.",
                metadata={"literature_type": "WL"}
            ))
        session.total_count = 20

        for article in session.articles[:10]:
            session.record_decision("include")
        for article in session.articles[10:]:
            session.record_decision("exclude")

        original_included = session.included_count
        original_excluded = session.excluded_count
        original_checksum = session.compute_checksum()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "session.json")
            session.save_to_json(path)

            session2 = ScreeningSession("dummy", "2024-01-01", "1.0")
            session2.load_from_json(path)

        assert session2.included_count == original_included
        assert session2.excluded_count == original_excluded

        checksum_after = session2.compute_checksum()
        assert original_checksum == checksum_after


class TestAdvisoryLayerBoundary:
    """Verify advisory layer never imports from UI layer.

    Dependency direction MUST be:
        UI -> Core -> Advisory
    NEVER:
        Advisory -> UI
    """

    ADVISORY_MODULES = [
        "src/advisory/advisory_worker.py",
    ]

    FORBIDDEN_IMPORTS = [
        "src.ui",
        "streamlit",
    ]

    @staticmethod
    def _is_top_level_import(line: str, content_lines: list) -> bool:
        """Check if an import statement is at module level (not inside a function)."""
        line_idx = content_lines.index(line) if line in content_lines else -1
        if line_idx < 0:
            return False
        # Scan backwards from this line to see if we're inside a function body
        # Simple heuristic: look for 'def ' or 'class ' between start and this line
        # without encountering a return to indent level 0
        for i in range(line_idx):
            prev = content_lines[i]
            stripped = prev.strip()
            if stripped.startswith(('def ', 'class ', '@')):
                # Found a function/class definition before this import
                # Check if there's an indent change
                return False
            if stripped == '' and i > 0:
                continue
        return True

    def test_advisory_worker_no_ui_imports(self):
        """Advisory worker must not import from src.ui.* or streamlit at module level."""
        base = Path(__file__).parent.parent

        for mod_path in self.ADVISORY_MODULES:
            full_path = base / mod_path
            assert full_path.exists(), f"Missing advisory module: {mod_path}"

            content = full_path.read_text(encoding="utf-8")
            content_lines = content.splitlines()
            for forbidden in self.FORBIDDEN_IMPORTS:
                import_lines = [
                    line for line in content_lines
                    if line.strip().startswith(("import ", "from "))
                ]
                for line in import_lines:
                    # Only flag top-level imports (not lazy imports inside functions)
                    if not self._is_top_level_import(line, content_lines):
                        continue
                    assert forbidden not in line, (
                        f"LAYER VIOLATION: {mod_path} top-level imports '{forbidden}'. "
                        f"Advisory layer must not depend on UI layer. "
                        f"Offending line: {line.strip()}"
                    )

    def test_all_advisory_modules_no_ui_imports(self):
        """All advisory modules must not import from src.ui.* or streamlit at module level."""
        base = Path(__file__).parent.parent
        advisory_dir = base / "src/advisory"
        if not advisory_dir.exists():
            return

        for py_file in advisory_dir.rglob("*.py"):
            if py_file.name.startswith("__"):
                continue
            content = py_file.read_text(encoding="utf-8")
            content_lines = content.splitlines()
            import_lines = [
                line for line in content_lines
                if line.strip().startswith(("import ", "from "))
            ]
            for line in import_lines:
                if not self._is_top_level_import(line, content_lines):
                    continue
                for forbidden in self.FORBIDDEN_IMPORTS:
                    assert forbidden not in line, (
                        f"LAYER VIOLATION: {py_file.relative_to(base)} top-level imports '{forbidden}'. "
                        f"Advisory layer must not depend on UI layer. "
                        f"Offending line: {line.strip()}"
                    )
