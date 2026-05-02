"""
Unit Tests for src/core/ingestion.py - Data Ingestion and Normalization Logic.
"""
import pytest
import pandas as pd
from src.core.ingestion import normalize_doi, normalize_year, clean_title, normalize_columns


class TestDOINormalization:
    """Test DOI normalization with edge cases."""

    def test_doi_with_https_prefix(self):
        """DOI with https://doi.org/ prefix should be stripped."""
        result = normalize_doi("https://doi.org/10.1234/test")
        assert result == "10.1234/test"

    def test_doi_with_http_prefix(self):
        """DOI with http://doi.org/ prefix should be stripped."""
        result = normalize_doi("http://doi.org/10.1234/test")
        assert result == "10.1234/test"

    def test_doi_with_doi_org_prefix(self):
        """DOI with doi.org/ prefix should be stripped."""
        result = normalize_doi("doi.org/10.1234/test")
        assert result == "10.1234/test"

    def test_doi_with_doi_colon_prefix(self):
        """DOI with doi: prefix should be stripped."""
        result = normalize_doi("doi:10.1234/test")
        assert result == "10.1234/test"

    def test_doi_uppercase_converted_to_lowercase(self):
        """DOI should be converted to lowercase."""
        result = normalize_doi("HTTPS://DOI.ORG/10.1234/TEST")
        assert result == "10.1234/test"

    def test_doi_strips_whitespace(self):
        """DOI should have whitespace stripped."""
        result = normalize_doi("  10.1234/test  ")
        assert result == "10.1234/test"

    def test_doi_none_returns_none(self):
        """None DOI should return None."""
        assert normalize_doi(None) is None

    def test_doi_empty_string_returns_none(self):
        """Empty string DOI should return None."""
        assert normalize_doi("") is None

    def test_doi_whitespace_only_returns_none(self):
        """Whitespace-only DOI should return None."""
        assert normalize_doi("   ") is None


class TestYearNormalization:
    """Test Year normalization with edge cases."""

    def test_valid_year(self):
        """Valid integer year should return the year."""
        assert normalize_year(2023) == 2023

    def test_year_from_string(self):
        """Year from string should be extracted."""
        assert normalize_year("2023") == 2023

    def test_year_from_date_range(self):
        """Year from date range string (e.g., '2022-2023') should return first year."""
        assert normalize_year("2022-2023") == 2022

    def test_year_from_date_string(self):
        """Year from full date string should return the year."""
        assert normalize_year("2023-10-15") == 2023

    def test_year_invalid_returns_none(self):
        """Invalid year format should return None."""
        assert normalize_year("invalid") is None

    def test_year_none_returns_none(self):
        """None year should return None."""
        assert normalize_year(None) is None

    def test_year_empty_string_returns_none(self):
        """Empty string year should return None."""
        assert normalize_year("") is None


class TestTitleCleaning:
    """Test title cleaning for deduplication."""

    def test_clean_title_lowercase(self):
        """Title should be converted to lowercase."""
        assert clean_title("Test Paper") == "test paper"

    def test_clean_title_strips_punctuation(self):
        """Title should have punctuation removed."""
        assert clean_title("Test, Paper: 2023!") == "test paper 2023"

    def test_clean_title_multiple_spaces(self):
        """Title should have multiple spaces collapsed."""
        assert clean_title("Test    Paper") == "test paper"

    def test_clean_title_empty(self):
        """Empty title should return empty string."""
        assert clean_title("") == ""

    def test_clean_title_none(self):
        """None title should return empty string."""
        assert clean_title(None) == ""


class TestColumnNormalization:
    """Test column name normalization."""

    def test_normalize_columns(self):
        """Columns should be normalized to lowercase and mapped."""
        df = pd.DataFrame({"TITLE": ["Test"], "YEAR": [2023]})
        column_aliases = {"title": "title", "year": "year"}
        result = normalize_columns(df, column_aliases)
        assert "title" in result.columns
        assert "year" in result.columns
        assert "TITLE" not in result.columns

    def test_normalize_columns_case_insensitive(self):
        """Column mapping should be case-insensitive."""
        df = pd.DataFrame({"TITLE": ["Test"]})
        column_aliases = {"TITLE": "title"}  # uppercase in config
        result = normalize_columns(df, column_aliases)
        assert "title" in result.columns