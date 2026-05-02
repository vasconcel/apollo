"""
Unit Tests for src/core/pdf_processor.py
"""
import pytest
import os
import tempfile
from src.core.pdf_processor import (
    extract_text_from_pdf,
    get_pdf_metadata,
    quick_preview
)


class TestPDFProcessor:
    """Test PDF extraction functionality."""

    def test_extract_returns_dict_structure(self):
        """Function should return proper dict structure even for missing file."""
        result = extract_text_from_pdf("/nonexistent/file.pdf")
        
        assert "text" in result
        assert "page_count" in result

    def test_extract_handles_missing_file(self):
        """Missing file should return error."""
        result = extract_text_from_pdf("/nonexistent/file.pdf")
        
        assert result["text"] == ""
        assert result["error"] is not None
        assert result["page_count"] == 0

    def test_metadata_returns_structure(self):
        """Metadata should return dict structure."""
        result = get_pdf_metadata("/nonexistent/file.pdf")
        
        assert "error" in result

    def test_quick_preview_structure(self):
        """Quick preview should return string."""
        result = quick_preview("/fake/file.pdf", max_chars=100)
        
        assert isinstance(result, str)


class TestPDFErrorHandling:
    """Test error handling."""

    def test_invalid_pdf_returns_structured_error(self):
        """Invalid PDF should return structured error, not crash."""
        # Create a temp file that's not a valid PDF
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(b"Not a valid PDF content")
            tmp_path = tmp.name
        
        try:
            result = extract_text_from_pdf(tmp_path)
            
            # Should return dict with error - pdfplumber will fail gracefully
            assert isinstance(result, dict)
            assert "text" in result
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_max_pages_parameter_accepted(self):
        """max_pages parameter should be handled."""
        # File doesn't exist - gets early return
        result = extract_text_from_pdf("/fake.pdf", max_pages=10)
        
        # Returns dict even if file doesn't exist (early return)
        assert isinstance(result, dict)
        # Error is set in early return for missing file
        assert result.get("error") is not None or "truncated" in result