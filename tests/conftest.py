"""
Pytest Configuration and Shared Fixtures for AIMS Testing.
"""
import os
import pytest
import sqlite3
import pandas as pd
import tempfile
import shutil
from pathlib import Path

# Set test environment variable to avoid API calls
os.environ["GROQ_API_KEY"] = "test-key-not-real"


@pytest.fixture
def temp_db():
    """Create a temporary in-memory SQLite database for testing."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    yield conn
    conn.close()


@pytest.fixture
def temp_db_file():
    """Create a temporary file-based SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    
    yield db_path
    
    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def sample_articles_df():
    """Sample DataFrame for testing article ingestion."""
    return pd.DataFrame([
        {"title": "Test Paper 1", "authors": "Smith, J.", "year": 2023, "doi": "10.1234/test.1", "abstract": "Test abstract", "source": "test", "literature_type": "WL"},
        {"title": "Test Paper 2", "authors": "Doe, A.", "year": 2022, "doi": "10.1234/test.2", "abstract": "Test abstract 2", "source": "test", "literature_type": "GL"},
        {"title": "Duplicate Paper", "authors": "Jones, B.", "year": 2021, "doi": "10.1234/dup", "abstract": "Duplicate", "source": "test", "literature_type": "WL"},
    ])


@pytest.fixture
def sample_screening_decisions():
    """Sample DataFrame for testing Kappa calculation."""
    return pd.DataFrame([
        {"article_id": 1, "reviewer_id": "Reviewer_1", "decision": "include"},
        {"article_id": 1, "reviewer_id": "Reviewer_2", "decision": "include"},
        {"article_id": 2, "reviewer_id": "Reviewer_1", "decision": "include"},
        {"article_id": 2, "reviewer_id": "Reviewer_2", "decision": "exclude"},
        {"article_id": 3, "reviewer_id": "Reviewer_1", "decision": "exclude"},
        {"article_id": 3, "reviewer_id": "Reviewer_2", "decision": "exclude"},
    ])


@pytest.fixture
def perfect_agreement_decisions():
    """DataFrame where both reviewers agree 100% (edge case for Kappa)."""
    return pd.DataFrame([
        {"article_id": 1, "reviewer_id": "Reviewer_1", "decision": "include"},
        {"article_id": 1, "reviewer_id": "Reviewer_2", "decision": "include"},
        {"article_id": 2, "reviewer_id": "Reviewer_1", "decision": "exclude"},
        {"article_id": 2, "reviewer_id": "Reviewer_2", "decision": "exclude"},
    ])


@pytest.fixture
def complete_disagreement_decisions():
    """DataFrame where reviewers completely disagree (edge case for Kappa)."""
    return pd.DataFrame([
        {"article_id": 1, "reviewer_id": "Reviewer_1", "decision": "include"},
        {"article_id": 1, "reviewer_id": "Reviewer_2", "decision": "exclude"},
    ])


@pytest.fixture
def missing_reviewer_decisions():
    """DataFrame where one reviewer hasn't completed all articles."""
    return pd.DataFrame([
        {"article_id": 1, "reviewer_id": "Reviewer_1", "decision": "include"},
        {"article_id": 1, "reviewer_id": "Reviewer_2", "decision": "include"},
        {"article_id": 2, "reviewer_id": "Reviewer_1", "decision": "include"},
        # Reviewer_2 hasn't reviewed article 2 yet
    ])


@pytest.fixture
def mock_ai_response():
    """Mock AI response for testing without real API calls."""
    return {
        "decision": "include",
        "confidence": 85,
        "matched_criteria": ["IC1", "IC3"],
        "reasons": ["Matches inclusion criteria for SE recruitment"]
    }