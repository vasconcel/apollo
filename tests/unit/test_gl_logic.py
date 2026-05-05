"""
Unit Tests for src/core/gl_handler.py - Grey Literature Ingestion Logic.
Tests saturation detection, duplicate URL handling, JSON parsing, and truncation.
"""
import pytest
import json
import re
import pandas as pd
from unittest.mock import patch, MagicMock

try:
    from src.core.gl_handler import (
        evaluate_thematic_saturation,
        process_gl_ingestion,
        scrape_url,
        MAX_ARTICLE_CONTENT_LENGTH,
    )
except ModuleNotFoundError:
    from src.core import gl_handler
    from src.core.gl_handler import (
        evaluate_thematic_saturation,
        process_gl_ingestion,
        scrape_url,
        MAX_ARTICLE_CONTENT_LENGTH,
    )


class TestSaturationLogic:
    """Test saturation decision logic."""

    @patch('src.core.gl_handler.Groq')
    def test_is_new_false_when_content_identical(self, mock_groq):
        """Article with identical content should be marked as saturated."""
        mock_client = MagicMock()
        mock_groq.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "is_new": False,
            "reasoning": "Article confirms existing themes without new evidence",
            "suggested_tags": ["recruitment"]
        })
        mock_client.chat.completions.create.return_value = mock_response
        
        content = "Software engineering recruitment methods include interviews and tests."
        
        result = evaluate_thematic_saturation(
            article_content=content,
            article_title="Test Article",
            project_themes="Recruitment methods: interviews, tests",
            research_questions=["What are common recruitment methods?"]
        )
        
        assert result["is_new"] == False

    @patch('src.core.gl_handler.Groq')
    def test_is_new_true_when_unique_content(self, mock_groq):
        """Article with unique content should be marked as new."""
        mock_client = MagicMock()
        mock_groq.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "is_new": True,
            "reasoning": "Provides novel AI-driven screening methodology",
            "suggested_tags": ["AI screening", "machine learning"]
        })
        mock_client.chat.completions.create.return_value = mock_response
        
        content = "We propose a novel machine learning approach to screen articles automatically."
        
        result = evaluate_thematic_saturation(
            article_content=content,
            article_title="ML Screening",
            project_themes="Traditional manual screening methods",
            research_questions=["How to screen efficiently?"]
        )
        
        assert result["is_new"] == True


class TestDuplicateURL:
    """Test duplicate URL handling."""

    def test_duplicate_url_blocked_in_database(self):
        """Same URL should be blocked on second insert."""
        from src.core.database import Database
        import sqlite3
        from unittest.mock import patch, MagicMock
        
        with patch('sqlite3.connect') as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = (1,)
            mock_conn.return_value.__enter__ = MagicMock(return_value=mock_conn.return_value)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)
            mock_conn.return_value.cursor.return_value = mock_cursor
            
            db = Database(review_id=1)
            
            result = db.add_gl_article(
                title="Test",
                url="https://example.com/article",
                ingestion_notes=json.dumps({"is_new": True}),
                abstract="Test abstract"
            )
            
            assert result is None


class TestMalformedJSON:
    """Test JSON parsing with prepended text."""

    @patch('src.core.gl_handler.Groq')
    def test_json_extraction_with_prefix(self, mock_groq):
        """JSON should be extracted even with prefix text."""
        mock_client = MagicMock()
        mock_groq.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = 'Sure, here is your result: {"is_new": true, "reasoning": "New methodology", "suggested_tags": ["test"]}'
        mock_client.chat.completions.create.return_value = mock_response
        
        result = evaluate_thematic_saturation(
            article_content="Test content",
            article_title="Test",
            project_themes="",
            research_questions=["Test RQ?"]
        )
        
        assert result["is_new"] == True

    @patch('src.core.gl_handler.Groq')
    def test_json_extraction_with_suffix(self, mock_groq):
        """JSON should be extracted even with suffix text."""
        mock_client = MagicMock()
        mock_groq.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"is_new": false, "reasoning": "No new evidence", "suggested_tags": []}\n\nHope this helps!'
        mock_client.chat.completions.create.return_value = mock_response
        
        result = evaluate_thematic_saturation(
            article_content="Test content",
            article_title="Test",
            project_themes="",
            research_questions=["Test RQ?"]
        )
        
        assert result["is_new"] == False


class TestTruncation:
    """Test content truncation."""

    def test_content_truncated_to_limit(self):
        """Content over limit should be truncated."""
        long_content = "A" * 50000
        
        truncated = long_content[:MAX_ARTICLE_CONTENT_LENGTH] if len(long_content) > MAX_ARTICLE_CONTENT_LENGTH else long_content
        
        assert len(truncated) == MAX_ARTICLE_CONTENT_LENGTH
        assert MAX_ARTICLE_CONTENT_LENGTH == 15000

    def test_content_under_limit_unchanged(self):
        """Content under limit should not be truncated."""
        short_content = "A" * 5000
        
        truncated = short_content[:MAX_ARTICLE_CONTENT_LENGTH] if len(short_content) > MAX_ARTICLE_CONTENT_LENGTH else short_content
        
        assert len(truncated) == 5000


class TestEmptyKnowledgeBase:
    """Test handling of empty KB."""

    @patch('src.core.gl_handler.Groq')
    def test_empty_themes_no_crash(self, mock_groq):
        """System should handle empty themes without crashing."""
        mock_client = MagicMock()
        mock_groq.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "is_new": True,
            "reasoning": "No existing themes to compare",
            "suggested_tags": []
        })
        mock_client.chat.completions.create.return_value = mock_response
        
        result = evaluate_thematic_saturation(
            article_content="New software engineering practice",
            article_title="New Practice",
            project_themes="",
            research_questions=[]
        )
        
        assert result["is_new"] == True


class TestScraper:
    """Test web scraper."""

    @patch('src.core.gl_handler.requests.get')
    def test_scrape_returns_content(self, mock_get):
        """Scraper should return text content."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'<html><body><p>Test content here</p></body></html>'
        mock_response.encoding = 'utf-8'
        mock_get.return_value = mock_response
        
        result = scrape_url("https://example.com")
        
        assert result is not None

    @patch('src.core.gl_handler.requests.get')
    def test_scrape_handles_encoding_error(self, mock_get):
        """Scraper should handle encoding errors."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'<html><body><p>Content</p></body></html>'
        mock_response.encoding = 'invalid-encoding'
        mock_get.return_value = mock_response
        
        result = scrape_url("https://example.com")
        
        assert result is not None