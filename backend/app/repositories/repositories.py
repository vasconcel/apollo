from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, not_, text
from app.models import models
import logging

logger = logging.getLogger(__name__)


class BaseRepository:
    """Base repository with common functionality."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def _execute_with_transaction(self, query: str, params: dict = None):
        """Execute query within a transaction."""
        with self.db.begin():
            result = self.db.execute(text(query), params or {})
            return result.fetchall()


class ScreeningRepository(BaseRepository):
    """Repository for screening operations with tenant isolation."""
    
    def get_pending_articles(self, review_id: int, user_id: str) -> list:
        """
        Get articles assigned to user that haven't been screened yet.
        CRITICAL: Enforces review_id AND user_id isolation.
        """
        result = self.db.execute(text("""
            SELECT a.id, a.title, a.abstract, a.literature_type, a.year, a.authors
            FROM articles a
            JOIN assignments ass ON a.id = ass.article_id
            WHERE ass.user_id = :user_id
            AND a.review_id = :review_id
            AND a.id NOT IN (
                SELECT article_id 
                FROM screening_decisions 
                WHERE reviewer_id = :user_id 
                AND review_id = :review_id
            )
            ORDER BY a.id
        """), {"review_id": review_id, "user_id": user_id}).fetchall()
        return result
    
    def get_article_by_id(self, article_id: int, review_id: int) -> dict:
        """Get single article with tenant isolation."""
        result = self.db.execute(text("""
            SELECT * FROM articles 
            WHERE id = :article_id AND review_id = :review_id
        """), {"article_id": article_id, "review_id": review_id}).fetchone()
        return dict(result._mapping) if result else None
    
    def save_decision(self, article_id: int, review_id: int, reviewer_id: str,
                      decision: str, exclusion_reason: str = None, 
                      criteria: dict = None) -> bool:
        """
        Save screening decision with transaction safety.
        CRITICAL: Uses DB constraint - NEVER overwrites existing decisions.
        """
        import json
        try:
            with self.db.begin():
                existing = self.db.execute(text("""
                    SELECT id FROM screening_decisions 
                    WHERE article_id = :article_id 
                    AND reviewer_id = :reviewer_id
                    AND review_id = :review_id
                """), {"article_id": article_id, "reviewer_id": reviewer_id, "review_id": review_id}).fetchone()
                
                if existing:
                    return False
                
                self.db.execute(text("""
                    INSERT INTO screening_decisions 
                    (article_id, review_id, reviewer_id, decision, exclusion_reason, criteria_snapshot)
                    VALUES (:article_id, :review_id, :reviewer_id, :decision, :exclusion_reason, :criteria)
                """), {
                    "article_id": article_id,
                    "review_id": review_id,
                    "reviewer_id": reviewer_id,
                    "decision": decision,
                    "exclusion_reason": exclusion_reason,
                    "criteria": json.dumps(criteria) if criteria else None
                })
            return True
        except Exception as e:
            logger.error(f"Failed to save decision: {e}")
            return False
    
    def get_all_screening_decisions(self, review_id: int) -> list:
        """Get all screening decisions for a review (consensus only)."""
        result = self.db.execute(text("""
            SELECT * FROM screening_decisions WHERE review_id = :review_id
        """), {"review_id": review_id}).fetchall()
        return result
    
    def get_user_decisions(self, review_id: int, user_id: str) -> list:
        """Get decisions made by a specific user."""
        result = self.db.execute(text("""
            SELECT * FROM screening_decisions 
            WHERE review_id = :review_id AND reviewer_id = :user_id
        """), {"review_id": review_id, "user_id": user_id}).fetchall()
        return result


class ArticleRepository(BaseRepository):
    """Repository for article operations."""
    
    def count_articles(self, review_id: int) -> int:
        """Count articles with tenant isolation."""
        result = self.db.execute(text(
            "SELECT COUNT(*) as count FROM articles WHERE review_id = :review_id"
        ), {"review_id": review_id}).fetchone()
        return result[0] if result else 0
    
    def add_article(self, review_id: int, article_data: dict) -> int:
        """Add new article with tenant isolation and transaction."""
        try:
            with self.db.begin():
                result = self.db.execute(text("""
                    INSERT INTO articles 
                    (review_id, title, authors, year, abstract, doi, url, source, literature_type)
                    VALUES (:review_id, :title, :authors, :year, :abstract, :doi, :url, :source, :literature_type)
                    RETURNING id
                """), {
                    "review_id": review_id,
                    "title": article_data.get("title", ""),
                    "authors": article_data.get("authors", ""),
                    "year": article_data.get("year"),
                    "abstract": article_data.get("abstract", ""),
                    "doi": article_data.get("doi", ""),
                    "url": article_data.get("url", ""),
                    "source": article_data.get("source", ""),
                    "literature_type": article_data.get("literature_type", "WL")
                })
                return result.fetchone()[0]
        except Exception as e:
            logger.error(f"Failed to add article: {e}")
            raise
    
    def get_included_articles(self, review_id: int) -> list:
        """Get articles passed screening and quality - ready for extraction."""
        result = self.db.execute(text("""
            SELECT a.id, a.title, a.abstract, a.literature_type, a.year, a.authors
            FROM articles a
            JOIN final_decisions f ON a.id = f.article_id
            WHERE f.final_decision = 'include'
            AND a.review_id = :review_id
            AND NOT EXISTS (
                SELECT 1 FROM quality_assessments q
                WHERE q.article_id = a.id AND q.decision = 'exclude'
            )
        """), {"review_id": review_id}).fetchall()
        return result
    
    def assign_article(self, article_id: int, review_id: int, user_id: str) -> bool:
        """Assign article to user with transaction."""
        try:
            with self.db.begin():
                self.db.execute(text("""
                    INSERT INTO assignments (article_id, review_id, user_id)
                    VALUES (:article_id, :review_id, :user_id)
                    ON CONFLICT DO NOTHING
                """), {"article_id": article_id, "review_id": review_id, "user_id": user_id})
            return True
        except Exception as e:
            logger.error(f"Failed to assign article: {e}")
            return False


class StatsRepository(BaseRepository):
    """Repository for statistics."""
    
    def get_stats(self, review_id: int) -> dict:
        """Get real-time statistics with tenant isolation."""
        total = self.db.execute(text(
            "SELECT COUNT(*) FROM articles WHERE review_id = :review_id"
        ), {"review_id": review_id}).fetchone()[0]
        
        screened = self.db.execute(text("""
            SELECT COUNT(DISTINCT article_id) 
            FROM screening_decisions WHERE review_id = :review_id
        """), {"review_id": review_id}).fetchone()[0]
        
        included = self.db.execute(text("""
            SELECT COUNT(DISTINCT article_id) 
            FROM screening_decisions 
            WHERE review_id = :review_id AND decision = 'include'
        """), {"review_id": review_id}).fetchone()[0]
        
        final = self.db.execute(text("""
            SELECT COUNT(*) FROM final_decisions fd
            JOIN articles a ON fd.article_id = a.id
            WHERE a.review_id = :review_id AND fd.final_decision = 'include'
        """), {"review_id": review_id}).fetchone()[0]
        
        return {
            "total_articles": total,
            "screened": screened,
            "pending": total - screened,
            "included": included,
            "final_included": final
        }
    
    def get_prisma_stats(self, review_id: int) -> dict:
        """Get PRISMA flow statistics."""
        total = self.db.execute(text(
            "SELECT COUNT(*) FROM articles WHERE review_id = :review_id"
        ), {"review_id": review_id}).fetchone()[0]
        
        screened = self.db.execute(text("""
            SELECT COUNT(DISTINCT article_id) 
            FROM screening_decisions WHERE review_id = :review_id
        """), {"review_id": review_id}).fetchone()[0]
        
        included = self.db.execute(text("""
            SELECT COUNT(DISTINCT article_id) 
            FROM screening_decisions 
            WHERE review_id = :review_id AND decision = 'include'
        """), {"review_id": review_id}).fetchone()[0]
        
        final_included = self.db.execute(text("""
            SELECT COUNT(*) FROM final_decisions fd
            JOIN articles a ON fd.article_id = a.id
            WHERE a.review_id = :review_id AND fd.final_decision = 'include'
        """), {"review_id": review_id}).fetchone()[0]
        
        return {
            "total_imported": total,
            "screened": screened,
            "pending_screening": total - screened,
            "included_screening": included,
            "excluded_screening": screened - included,
            "final_included": final_included
        }


class ExtractionRepository(BaseRepository):
    """Repository for extraction/synthesis operations."""
    
    def get_fragments_by_rq(self, review_id: int, rq_code: str) -> list:
        """Get fragments for a research question with tenant isolation."""
        result = self.db.execute(text("""
            SELECT f.*, a.title as article_title, a.literature_type
            FROM fragments f
            JOIN articles a ON f.article_id = a.id
            WHERE f.rq_code = :rq_code
            AND a.review_id = :review_id
            ORDER BY f.created_at
        """), {"review_id": review_id, "rq_code": rq_code}).fetchall()
        return result
    
    def get_codes_by_rq(self, review_id: int, rq_code: str) -> list:
        """Get codes for a research question."""
        result = self.db.execute(text("""
            SELECT DISTINCT c.* FROM codes c
            JOIN fragments f ON f.rq_code = c.rq_code
            JOIN articles a ON f.article_id = a.id
            WHERE c.rq_code = :rq_code
            AND a.review_id = :review_id
        """), {"review_id": review_id, "rq_code": rq_code}).fetchall()
        return result
    
    def get_themes_by_rq(self, review_id: int, rq_code: str) -> list:
        """Get themes for a research question."""
        result = self.db.execute(text("""
            SELECT * FROM themes WHERE rq_code = :rq_code
        """), {"rq_code": rq_code}).fetchall()
        return result