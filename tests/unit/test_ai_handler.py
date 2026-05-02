"""
Unit Tests for src/core/ai_handler.py - Testing with Mocks.
"""
import pytest
import os
from unittest.mock import patch, MagicMock
from src.core.ai_handler import get_ai_suggestion, generate_theme_synthesis


class TestAISuggestion:
    """Test AI suggestion with mocked API."""

    @patch('src.core.ai_handler.Groq')
    def test_get_ai_suggestion_success(self, mock_groq):
        """Should return parsed AI response on success."""
        mock_client = MagicMock()
        mock_groq.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"decision": "include", "confidence": 85, "matched_criteria": ["IC1"], "reasons": ["Test"]}'
        mock_client.chat.completions.create.return_value = mock_response
        
        os.environ["GROQ_API_KEY"] = "test-key"
        
        settings = {
            "research_questions": ["RQ1: Test"],
            "inclusion_criteria": {"IC1": "Test criteria"},
            "exclusion_criteria": {"EC1": "Test exclusion"}
        }
        
        result = get_ai_suggestion("Test Title", "Test Abstract", settings)
        
        assert result["decision"] == "include"
        assert result["confidence"] == 85

    def test_no_api_key_returns_error(self):
        """Should return error if no API key."""
        if "GROQ_API_KEY" in os.environ:
            old_key = os.environ.pop("GROQ_API_KEY")
        else:
            old_key = None
        
        try:
            settings = {
                "research_questions": [],
                "inclusion_criteria": {},
                "exclusion_criteria": {}
            }
            
            result = get_ai_suggestion("Test", "Abstract", settings)
            
            assert result["decision"] == "error"
        finally:
            if old_key:
                os.environ["GROQ_API_KEY"] = old_key


class TestThemeSynthesis:
    """Test theme synthesis with mocks."""

    @patch('src.core.ai_handler.Groq')
    def test_generate_theme_synthesis_success(self, mock_groq):
        """Should generate synthesis on success."""
        mock_client = MagicMock()
        mock_groq.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "## Core Findings\nTest synthesis."
        mock_client.chat.completions.create.return_value = mock_response
        
        os.environ["GROQ_API_KEY"] = "test-key"
        
        wl_fragments = ["[Author, 2023]: Test fragment"]
        gl_fragments = ["[Author, 2022]: Test GL fragment"]
        
        result = generate_theme_synthesis("Test Theme", wl_fragments, gl_fragments)
        
        assert result["synthesis"] is not None

    @patch('src.core.ai_handler.Groq')
    def test_context_window_truncation(self, mock_groq):
        """Should truncate fragments to prevent context overflow."""
        mock_client = MagicMock()
        mock_groq.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Synthesis"
        mock_client.chat.completions.create.return_value = mock_response
        
        os.environ["GROQ_API_KEY"] = "test-key"
        
        # Create more than 30 fragments
        wl_fragments = [f"[Author, 202{i}]: Fragment {i}" for i in range(35)]
        gl_fragments = [f"[Author, 202{i}]: GL Fragment {i}" for i in range(35)]
        
        result = generate_theme_synthesis("Test Theme", wl_fragments, gl_fragments, max_fragments_per_side=30)
        
        # Should include truncation warning
        assert result.get("truncation_warning") is not None

    def test_no_api_key_returns_error(self):
        """Should return error if no API key."""
        if "GROQ_API_KEY" in os.environ:
            old_key = os.environ.pop("GROQ_API_KEY")
        else:
            old_key = None
        
        try:
            result = generate_theme_synthesis("Test", [], [])
            
            assert result["synthesis"] is None
            assert result.get("error") is not None
        finally:
            if old_key:
                os.environ["GROQ_API_KEY"] = old_key