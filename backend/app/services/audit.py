from sqlalchemy.orm import Session
from datetime import datetime
from app.models.models import AuditLog
from typing import Optional
import json


class AuditService:
    """Service for audit logging."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def log(
        self,
        user_id: str,
        action: str,
        entity: str,
        entity_id: Optional[int] = None,
        review_id: Optional[int] = None,
        details: Optional[dict] = None
    ):
        """Log an audit event."""
        try:
            log_entry = AuditLog(
                user_id=user_id,
                action=action,
                entity=entity,
                entity_id=entity_id,
                review_id=review_id,
                details=json.dumps(details) if details else None
            )
            self.db.add(log_entry)
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            raise e
    
    def log_decision(self, user_id: str, review_id: int, article_id: int, decision: str):
        """Log screening decision."""
        self.log(
            user_id=user_id,
            action="screening_decision",
            entity="screening_decisions",
            entity_id=article_id,
            review_id=review_id,
            details={"decision": decision}
        )
    
    def log_article_created(self, user_id: str, review_id: int, article_id: int):
        """Log article creation."""
        self.log(
            user_id=user_id,
            action="article_created",
            entity="articles",
            entity_id=article_id,
            review_id=review_id
        )
    
    def log_assignment(self, user_id: str, review_id: int, article_id: int, assigned_to: str):
        """Log article assignment."""
        self.log(
            user_id=user_id,
            action="article_assigned",
            entity="assignments",
            entity_id=article_id,
            review_id=review_id,
            details={"assigned_to": assigned_to}
        )
    
    def log_login(self, user_id: str):
        """Log user login."""
        self.log(
            user_id=user_id,
            action="login",
            entity="auth"
        )
    
    def get_recent_logs(self, review_id: Optional[int] = None, limit: int = 100):
        """Get recent audit logs."""
        query = self.db.query(AuditLog)
        if review_id:
            query = query.filter(AuditLog.review_id == review_id)
        return query.order_by(AuditLog.created_at.desc()).limit(limit).all()