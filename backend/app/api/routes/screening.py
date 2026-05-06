from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.db.session import get_db
from app.services.services import ScreeningService
from app.auth.dependencies import get_current_user, require_review_access
from app.auth.auth import User

router = APIRouter(prefix="/api/v1", tags=["screening"])


class DecisionInput(BaseModel):
    article_id: int
    review_id: int
    decision: str
    exclusion_reason: Optional[str] = None
    criteria: Optional[dict] = None


@router.get("/screening/pending")
def get_pending_articles(
    review_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get pending articles for current user.
    ENFORCES: 
    - JWT authentication required
    - User has access to review_id
    - review_id + user_id isolation
    """
    require_review_access(current_user, review_id)
    
    service = ScreeningService(db)
    articles = service.get_pending_articles(review_id, current_user.user_id)
    
    return {
        "articles": [
            {
                "id": a[0],
                "title": a[1],
                "abstract": a[2],
                "literature_type": a[3],
                "year": a[4],
                "authors": a[5]
            }
            for a in articles
        ],
        "count": len(articles)
    }


@router.get("/screening/article/{article_id}")
def get_article(
    article_id: int,
    review_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get article details with access control."""
    require_review_access(current_user, review_id)
    
    service = ScreeningService(db)
    article = service.get_article(article_id, review_id)
    
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    return article


@router.post("/screening/decision")
def submit_decision(
    payload: DecisionInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit screening decision.
    CRITICAL:
    - User CANNOT submit for another user
    - NEVER overwrites existing decisions (DB constraint)
    """
    require_review_access(current_user, payload.review_id)
    
    service = ScreeningService(db)
    result = service.submit_decision(
        payload.article_id,
        payload.review_id,
        current_user.user_id,  # Use token user_id, NOT payload
        payload.decision,
        payload.exclusion_reason,
        payload.criteria
    )
    
    if not result["success"]:
        raise HTTPException(status_code=409, detail=result["reason"])
    
    return {"status": "saved", "article_id": payload.article_id}


@router.get("/screening/progress")
def get_progress(
    review_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's screening progress."""
    require_review_access(current_user, review_id)
    
    service = ScreeningService(db)
    return service.get_user_progress(review_id, current_user.user_id)


@router.get("/screening/decisions")
def get_all_decisions(
    review_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all screening decisions for consensus.
    Admin only - reviewers see only their own.
    """
    require_review_access(current_user, review_id)
    
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    service = ScreeningService(db)
    decisions = service.get_all_decisions(review_id)
    
    return {
        "decisions": [
            {
                "article_id": d[1],
                "reviewer_id": d[2],
                "decision": d[3],
                "exclusion_reason": d[4]
            }
            for d in decisions
        ],
        "count": len(decisions)
    }