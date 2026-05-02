"""Unit tests for the synthesis aggregator module."""

import pytest
from src.core.synthesis_aggregator import aggregate_theme_summaries


def test_aggregate_theme_summaries_with_content():
    """Test aggregation of multiple theme summaries."""
    themes = [
        (1, "Theme A", "Key finding from A", "RQ1"),
        (2, "Theme B", "Key finding from B", "RQ1"),
        (3, "Theme C", "Key finding from C", "RQ2"),
    ]
    
    result = aggregate_theme_summaries(themes)
    
    assert "Theme A" in result
    assert "Theme B" in result
    assert "Key finding from A" in result
    assert len(result) > 0


def test_aggregate_theme_summaries_empty():
    """Test aggregation with empty themes list."""
    themes = []
    
    result = aggregate_theme_summaries(themes)
    
    assert result == ""


def test_aggregate_theme_summaries_none_values():
    """Test aggregation handles None synthesis values."""
    themes = [
        (1, "Theme A", None, "RQ1"),
        (2, "Theme B", "Valid synthesis", "RQ1"),
    ]
    
    result = aggregate_theme_summaries(themes)
    
    assert "Theme B" in result
    assert "Valid synthesis" in result
    assert "Theme A" not in result


def test_aggregate_format_consistency():
    """Test that aggregation maintains consistent markdown formatting."""
    themes = [
        (1, "First Theme", "Finding one", "RQ1"),
        (2, "Second Theme", "Finding two", "RQ1"),
    ]
    
    result = aggregate_theme_summaries(themes)
    lines = result.split("\n")
    
    assert lines[0].startswith("- **")
    assert "**: " in result


def test_aggregate_whitespace_handling():
    """Test that aggregation handles whitespace properly."""
    themes = [
        (1, "Theme", "  Some finding with whitespace  ", "RQ1"),
    ]
    
    result = aggregate_theme_summaries(themes)
    
    assert "Some finding with whitespace" in result


def test_aggregate_long_themes():
    """Test aggregation with long theme descriptions."""
    long_text = "A" * 500
    
    themes = [
        (1, "Long Theme", long_text, "RQ1"),
    ]
    
    result = aggregate_theme_summaries(themes)
    
    assert len(result) >= 500