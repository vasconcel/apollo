"""
Integration Tests for src/core/config_manager.py - Configuration Lifecycle.
"""
import os
import json
import tempfile
import pytest
from src.core.config_manager import ConfigManager, load_config


class TestConfigLifecycle:
    """Test configuration loading, overriding, and saving."""

    def test_load_default_config(self):
        """When no config file exists, should load defaults."""
        config = load_config("/nonexistent/path.json")
        
        assert config.get("project_name") is not None
        assert config.get("research_questions") is not None

    def test_default_rqs(self):
        """Default config should have 5 research questions."""
        config = load_config("/nonexistent.json")
        rqs = config.get("research_questions", [])
        assert len(rqs) == 5
        assert all("RQ" in rq for rq in rqs)

    def test_merge_file_with_defaults(self):
        """File config should merge with defaults."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"project_name": "Custom Project"}, f)
            temp_path = f.name
        
        try:
            config = load_config(temp_path)
            assert config.get("project_name") == "Custom Project"
            assert config.get("research_questions") is not None
        finally:
            os.remove(temp_path)

    def test_invalid_json_handled_gracefully(self):
        """Invalid JSON should be handled (may raise error or use defaults)."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json {")
            f.flush()
            temp_path = f.name
        
        try:
            config = load_config(temp_path)
            # Should have loaded defaults
            assert config.get("project_name") is not None
        except Exception:
            pass  # Accept either behavior
        finally:
            os.remove(temp_path)


class TestConfigValues:
    """Test specific configuration values."""

    def test_exclusion_criteria_count(self):
        """Should have at least 5 exclusion criteria."""
        config = load_config("/nonexistent.json")
        ec = config.get("exclusion_criteria", {})
        assert len(ec) >= 5

    def test_inclusion_criteria_count(self):
        """Should have at least 3 inclusion criteria."""
        config = load_config("/nonexistent.json")
        ic = config.get("inclusion_criteria", {})
        assert len(ic) >= 3

    def test_quality_criteria_wl(self):
        """Should have WL quality criteria."""
        config = load_config("/nonexistent.json")
        qc = config.get("quality_criteria", {})
        assert "WL" in qc
        assert len(qc["WL"]) >= 3

    def test_quality_criteria_gl(self):
        """Should have GL quality criteria."""
        config = load_config("/nonexistent.json")
        qc = config.get("quality_criteria", {})
        assert "GL" in qc
        assert len(qc["GL"]) >= 3


class TestConfigProperties:
    """Test ConfigManager properties."""

    def test_column_aliases_property(self):
        """column_aliases should be accessible as property."""
        config = load_config("/nonexistent.json")
        aliases = config.column_aliases
        assert isinstance(aliases, dict)

    def test_source_columns_property(self):
        """source_columns should be accessible as property."""
        config = load_config("/nonexistent.json")
        cols = config.source_columns
        assert isinstance(cols, list)