from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.db.session import get_db
from app.services.services import ArticleService
from app.auth.dependencies import get_current_user, require_review_access
from app.auth.auth import User


router = APIRouter(prefix="/api/v1", tags=["articles"])


class ArticleInput(BaseModel):
    review_id: int
    title: str
    authors: Optional[str] = ""
    year: Optional[int] = None
    abstract: Optional[str] = ""
    doi: Optional[str] = ""
    url: Optional[str] = ""
    source: Optional[str] = ""
    literature_type: str = "WL"


@router.get("/articles/count")
def get_article_count(
    review_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get total article count."""
    require_review_access(current_user, review_id)
    
    service = ArticleService(db)
    return {"count": service.count_articles(review_id)}


@router.post("/articles")
def add_article(
    payload: ArticleInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add new article with access control."""
    require_review_access(current_user, payload.review_id)
    
    service = ArticleService(db)
    article_id = service.add_article(payload.review_id, payload.dict())
    return {"article_id": article_id, "status": "created"}


@router.get("/articles/included")
def get_included_articles(
    review_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get articles ready for extraction."""
    require_review_access(current_user, review_id)
    
    service = ArticleService(db)
    articles = service.get_included_articles(review_id)
    
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


@router.post("/articles/{article_id}/assign")
def assign_article(
    article_id: int,
    review_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Assign article to user (admin only)."""
    require_review_access(current_user, review_id)
    
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    service = ArticleService(db)
    success = service.assign_article(article_id, review_id, current_user.user_id)
    return {"assigned": success}