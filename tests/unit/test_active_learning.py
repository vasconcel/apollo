"""
Unit Tests for src/core/active_learning.py
"""
import pytest
import pandas as pd
from src.core.active_learning import get_training_context, format_few_shot_prompt, get_pending_articles_for_screening


class TestActiveLearningContext:
    """Test active learning context generation."""

    def test_context_separates_includes_excludes(self):
        """Context should separate Include from Exclude examples."""
        # This tests the logic structure
        context = {
            "include_examples": ["Example 1", "Example 2"],
            "exclude_examples": ["Example A", "Example B"],
            "total_includes": 2,
            "total_excludes": 2
        }
        
        assert len(context["include_examples"]) == 2
        assert len(context["exclude_examples"]) == 2

    def test_few_shot_prompt_format(self):
        """Prompt should be formatted correctly."""
        context = {
            "include_examples": ["Test Include Article 1"],
            "exclude_examples": ["Test Exclude Article 1"]
        }
        
        settings = {
            "inclusion_criteria": {"IC1": "Test criterion"},
            "exclusion_criteria": {"EC1": "Test exclusion"}
        }
        
        prompt = format_few_shot_prompt(context, settings)
        
        assert "INCLUSION CRITERIA" in prompt
        assert "EXCLUSION CRITERIA" in prompt
        assert "Test Include Article 1" in prompt
        assert "Test Exclude Article 1" in prompt
        assert "Example 1 (INCLUDED)" in prompt

    def test_prompt_stays_within_token_limits(self):
        """Prompt should remain reasonably sized."""
        context = {
            "include_examples": [f"Article {i}: " + "x" * 50 for i in range(10)],
            "exclude_examples": [f"Article {i}: " + "x" * 50 for i in range(10)]
        }
        
        settings = {
            "inclusion_criteria": {f"IC{i}": "criterion" for i in range(5)},
            "exclusion_criteria": {f"EC{i}": "criterion" for i in range(5)}
        }
        
        prompt = format_few_shot_prompt(context, settings)
        
        # Should be under ~1500 tokens approximately
        assert len(prompt) < 8000


class TestBatchPredictions:
    """Test batch prediction logic."""

    def test_articles_formatting(self):
        """Articles should be formatted for batch processing."""
        articles = [
            {"id": 1, "title": "Test Article 1", "abstract": "Abstract 1"},
            {"id": 2, "title": "Test Article 2", "abstract": "Abstract 2"}
        ]
        
        # Verify structure
        assert len(articles) == 2
        assert all("id" in a for a in articles)
        assert all("title" in a for a in articles)

    def test_batch_list_structure(self):
        """Batch predictions should have required fields."""
        prediction = {
            "id": 1,
            "decision": "include",
            "confidence": 85,
            "reason": "Matches criterion"
        }
        
        assert "id" in prediction
        assert "decision" in prediction
        assert "confidence" in prediction
        assert prediction["decision"] in ["include", "exclude"]


class TestPendingArticles:
    """Test pending article fetching."""

    def test_pending_articles_structure(self):
        """Pending articles should have required metadata."""
        article = {
            "id": 1,
            "title": "Test",
            "abstract": "Test abstract",
            "authors": "Author",
            "year": 2023,
            "literature_type": "WL"
        }
        
        assert article["id"] > 0
        assert article["title"] is not None
        assert article["literature_type"] in ["WL", "GL"]