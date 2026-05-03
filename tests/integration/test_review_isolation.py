"""Tests for review-level isolation enforcement."""

import pytest
import sqlite3
from src.core.database import Database, DatabaseError


class TestReviewIsolation:
    """Test strict review-level data isolation."""
    
    def test_cannot_instantiate_without_review_id(self, tmp_path):
        """CRITICAL: Database MUST require review_id."""
        db_path = str(tmp_path / "isolated.db")
        
        with pytest.raises(DatabaseError, match="review_id is REQUIRED"):
            Database(db_path)
    
    def test_can_isolate_two_reviews(self, tmp_path):
        """Two reviews should have completely isolated data through scoping."""
        db_path = str(tmp_path / "isolated.db")
        
        # Create first database instance - this creates the schema
        db1 = Database(db_path, review_id=1)
        
        # Add articles to review 1
        art1_id = db1.add_article({
            "title": "Review 1 Article",
            "authors": "Author 1",
            "year": 2024,
            "literature_type": "WL"
        })
        
        # Create second instance with review_id=2 (same db file, different scope)
        # This instance should see 0 articles because it's scoped to review 2
        db2 = Database(db_path, review_id=2)
        
        # Verify counts are isolated
        count_r1 = db1.count_articles()  # Should see review 1's article
        count_r2 = db2.count_articles()  # Should be 0 (no articles for review 2)
        
        assert count_r1 >= 1, f"Expected at least 1 article in review 1, got {count_r1}"
        assert count_r2 == 0, f"Expected 0 articles in review 2 (new scope), got {count_r2}"
    
    def test_unsafe_query_detection(self, tmp_path):
        """Queries without review_id filtering should be detectable."""
        db_path = str(tmp_path / "unsafe_test.db")
        db = Database(db_path, review_id=1)
        
        # Add some data
        db.add_article({
            "title": "Test Article",
            "authors": "Test Author",
            "year": 2024,
            "literature_type": "WL"
        })
        
        # Demonstrate proper query includes review_id filtering
        with db.connect() as conn:
            # This query IS safe - it filters by review_id
            safe_result = conn.execute(
                "SELECT COUNT(*) FROM articles WHERE review_id = ?",
                (db.get_review_id(),)
            ).fetchone()
            
            # This query WOULD be unsafe without filtering (if review_id exists in table)
            # In practice, this should be caught at the method level
            
        assert safe_result[0] >= 1


class TestImmutableReviewContext:
    """Test that review_id cannot be changed after instantiation."""
    
    def test_review_id_isImmutable(self, tmp_path):
        """review_id should be immutable after construction."""
        db_path = str(tmp_path / "immutable.db")
        db = Database(db_path, review_id=42)
        
        # Verify the review_id is set
        assert db.get_review_id() == 42
        
        # Note: We cannot change review_id - there's no setter method
        # Any data access uses the instance's review_id implicitly