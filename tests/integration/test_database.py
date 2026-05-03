"""
Integration Tests for src/core/database.py.
These tests are NOT mocking - they hit a real SQLite database.
"""
import pytest
import sqlite3
from src.core.database import Database, DatabaseError


@pytest.fixture
def temp_db_file(tmp_path):
    """Create a temporary database file for each test."""
    return str(tmp_path / "test_aims.db")


# Test fixtures with review_id
@pytest.fixture
def db_with_review(temp_db_file):
    """Create database with review_id for testing."""
    return Database(temp_db_file, review_id=1)


class TestDatabaseSchema:
    """Test database schema initialization."""

    def test_database_creates_tables(self, temp_db_file):
        """Database should create all required tables."""
        db = Database(temp_db_file, review_id=1)
        
        with db.connect() as conn:
            result = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = {row[0] for row in result}
        
        required_tables = {"articles", "screening_decisions", "final_decisions", 
                        "quality_assessments", "fragments", "codes", "themes"}
        assert required_tables.issubset(table_names)


class TestArticleOperations:
    """Test article CRUD operations."""

    def test_add_article_returns_id_and_can_be_read_back(self, temp_db_file):
        """CRITICAL: Add article AND read it back from real database."""
        db = Database(temp_db_file, review_id=1)
        
        # Write
        article_id = db.add_article({
            "title": "Test Paper for DB Validation",
            "authors": "Smith, J.",
            "year": 2023,
            "abstract": "Test abstract",
            "doi": "10.1234/test",
            "url": "",
            "source": "test",
            "literature_type": "WL"
        })
        
        # Verify ID returned
        assert article_id is not None
        assert article_id > 0
        
        # READ BACK - This is the real assertion!
        with db.connect() as conn:
            result = conn.execute(
                "SELECT title, authors, year FROM articles WHERE id = ?",
                (article_id,)
            ).fetchone()
            
        assert result is not None
        assert result[0] == "Test Paper for DB Validation"  # title
        assert result[1] == "Smith, J."  # authors
        assert result[2] == 2023  # year

    def test_multiple_articles_persist_in_database(self, temp_db_file):
        """CRITICAL: Multiple articles should all persist."""
        db = Database(temp_db_file, review_id=1)
        
        ids = []
        for i in range(5):
            aid = db.add_article({
                "title": f"Article {i}",
                "authors": f"Author {i}",
                "year": 2020 + i,
                "abstract": "",
                "doi": "",
                "url": "",
                "source": "test",
                "literature_type": "WL"
            })
            ids.append(aid)
        
        # Verify all 5 exist
        with db.connect() as conn:
            count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        
        assert count == 5
        
        # Verify specific titles
        with db.connect() as conn:
            titles = conn.execute("SELECT title FROM articles ORDER BY id").fetchall()
        
        assert [t[0] for t in titles] == [f"Article {i}" for i in range(5)]


class TestForeignKeyConstraints:
    """Test foreign key constraint enforcement."""

    def test_fragment_fk_constraint_prevents_invalid_reference(self, temp_db_file):
        """Fragment for non-existent article should raise sqlite3.IntegrityError."""
        db = Database(temp_db_file, review_id=1)
        
        # Try to insert fragment for non-existent article
        with pytest.raises((DatabaseError, sqlite3.IntegrityError, sqlite3.OperationalError)):
            db.insert_fragment(
                article_id=999,
                rq_code="RQ1",
                fragment_text="Test",
                reviewer_id="test",
                theme_category="test"
            )

    def test_quality_fk_constraint_prevents_invalid_reference(self, temp_db_file):
        """Quality assessment for non-existent article should raise error."""
        db = Database(temp_db_file, review_id=1)
        
        with pytest.raises((DatabaseError, sqlite3.IntegrityError, sqlite3.OperationalError)):
            db.save_quality_assessment(
                article_id=9999,
                reviewer_id="Test",
                scores_dict={"Q1": 1.0},
                total_score=1.0,
                decision="include"
            )


class TestScreeningDecisions:
    """CRITICAL: Test that screening decisions persist correctly."""

    def test_save_and_retrieve_decision(self, temp_db_file):
        """CRITICAL: Decision saved must be retrievable."""
        db = Database(temp_db_file, review_id=1)
        
        # Add article
        art_id = db.add_article({
            "title": "Test",
            "authors": "A",
            "year": 2023,
            "abstract": "",
            "doi": "",
            "url": "",
            "source": "test",
            "literature_type": "WL"
        })
        
        # Save decision
        db.save_decision(
            article_id=art_id,
            reviewer_id="Reviewer_1",
            decision="include",
            exclusion_reason=None,
            criteria={"IC1": "Test"}
        )
        
        # READ BACK - This is the real test!
        with db.connect() as conn:
            result = conn.execute(
                "SELECT decision, reviewer_id FROM screening_decisions WHERE article_id = ?",
                (art_id,)
            ).fetchone()
        
        assert result[0] == "include"  # decision
        assert result[1] == "Reviewer_1"  # reviewer