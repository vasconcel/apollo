from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.services import StatsService, ArticleService
from app.auth.dependencies import get_current_user, require_review_access
from app.auth.auth import User


router = APIRouter(prefix="/api/v1", tags=["stats"])


@router.get("/stats/dashboard")
def get_dashboard_stats(
    review_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get dashboard statistics with access control."""
    require_review_access(current_user, review_id)
    
    service = StatsService(db)
    return service.get_stats(review_id)


@router.get("/stats/prisma")
def get_prisma_stats(
    review_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get PRISMA flow statistics."""
    require_review_access(current_user, review_id)
    
    service = StatsService(db)
    return service.get_prisma_stats(review_id)


@router.get("/stats/user/{user_id}")
def get_user_stats(
    user_id: str,
    review_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user-specific statistics (admin only or own stats)."""
    require_review_access(current_user, review_id)
    
    if current_user.role != "admin" and current_user.user_id != user_id:
        raise HTTPException(status_code=403, detail="Cannot view other user's stats")
    
    from app.services.services import ScreeningService
    screening = ScreeningService(db)
    return screening.get_user_progress(review_id, user_id)