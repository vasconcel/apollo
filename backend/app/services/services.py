from sqlalchemy.orm import Session
from app.repositories.repositories import (
    ScreeningRepository,
    ArticleRepository,
    StatsRepository,
    ExtractionRepository
)


class ScreeningService:
    """Service layer for screening operations."""
    
    def __init__(self, db: Session):
        self.repo = ScreeningRepository(db)
    
    def get_pending_articles(self, review_id: int, user_id: str) -> list:
        """
        Get pending articles for a user.
        ENFORCES: review_id + user_id isolation
        """
        if not review_id:
            raise ValueError("review_id is required")
        if not user_id:
            raise ValueError("user_id is required")
        
        return self.repo.get_pending_articles(review_id, user_id)
    
    def get_article(self, article_id: int, review_id: int) -> dict:
        """Get article details with tenant isolation."""
        return self.repo.get_article_by_id(article_id, review_id)
    
    def submit_decision(self, article_id: int, review_id: int, reviewer_id: str,
                        decision: str, exclusion_reason: str = None,
                        criteria: dict = None) -> dict:
        """
        Submit a screening decision.
        Returns dict with success status.
        """
        if not review_id:
            return {"success": False, "reason": "review_id required"}
        if not reviewer_id:
            return {"success": False, "reason": "reviewer_id required"}
        
        saved = self.repo.save_decision(
            article_id, review_id, reviewer_id, 
            decision, exclusion_reason, criteria
        )
        
        return {
            "success": saved,
            "reason": "Decision already exists" if not saved else None
        }
    
    def get_user_progress(self, review_id: int, user_id: str) -> dict:
        """Get screening progress for a user."""
        decisions = self.repo.get_user_decisions(review_id, user_id)
        total_assigned = self.repo.get_pending_articles(review_id, user_id)
        
        included = sum(1 for d in decisions if d.decision == "include")
        excluded = sum(1 for d in decisions if d.decision == "exclude")
        
        return {
            "total_assigned": len(total_assigned) + len(decisions),
            "screened": len(decisions),
            "included": included,
            "excluded": excluded,
            "pending": len(total_assigned)
        }
    
    def get_all_decisions(self, review_id: int) -> list:
        """Get all decisions for consensus (review_id required)."""
        if not review_id:
            raise ValueError("review_id is required")
        return self.repo.get_all_screening_decisions(review_id)


class ArticleService:
    """Service layer for article operations."""
    
    def __init__(self, db: Session):
        self.repo = ArticleRepository(db)
    
    def count_articles(self, review_id: int) -> int:
        """Count articles with tenant isolation."""
        if not review_id:
            raise ValueError("review_id is required")
        return self.repo.count_articles(review_id)
    
    def add_article(self, review_id: int, article_data: dict) -> int:
        """Add article with tenant isolation."""
        if not review_id:
            raise ValueError("review_id is required")
        return self.repo.add_article(review_id, article_data)
    
    def get_included_articles(self, review_id: int) -> list:
        """Get articles ready for extraction."""
        if not review_id:
            raise ValueError("review_id is required")
        return self.repo.get_included_articles(review_id)
    
    def assign_article(self, article_id: int, review_id: int, user_id: str) -> bool:
        """Assign article to user."""
        return self.repo.assign_article(article_id, review_id, user_id)


class StatsService:
    """Service layer for statistics."""
    
    def __init__(self, db: Session):
        self.repo = StatsRepository(db)
    
    def get_stats(self, review_id: int) -> dict:
        """Get dashboard statistics."""
        if not review_id:
            raise ValueError("review_id is required")
        return self.repo.get_stats(review_id)
    
    def get_prisma_stats(self, review_id: int) -> dict:
        """Get PRISMA statistics."""
        if not review_id:
            raise ValueError("review_id is required")
        return self.repo.get_prisma_stats(review_id)


class ExtractionService:
    """Service layer for extraction/synthesis."""
    
    def __init__(self, db: Session):
        self.repo = ExtractionRepository(db)
    
    def get_fragments_by_rq(self, review_id: int, rq_code: str) -> list:
        """Get fragments for research question."""
        if not review_id:
            raise ValueError("review_id is required")
        return self.repo.get_fragments_by_rq(review_id, rq_code)
    
    def get_codes_by_rq(self, review_id: int, rq_code: str) -> list:
        """Get codes for research question."""
        if not review_id:
            raise ValueError("review_id is required")
        return self.repo.get_codes_by_rq(review_id, rq_code)
    
    def get_themes_by_rq(self, review_id: int, rq_code: str) -> list:
        """Get themes for research question."""
        if not review_id:
            raise ValueError("review_id is required")
        return self.repo.get_themes_by_rq(review_id, rq_code)