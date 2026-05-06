from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.services import ExtractionService


router = APIRouter(prefix="/api/v1", tags=["extraction"])


def validate_review_id(review_id: int = None) -> int:
    if not review_id or review_id <= 0:
        raise HTTPException(status_code=400, detail="review_id is required")
    return review_id


def validate_user(user_id: str = Header(..., alias="X-User-ID")) -> str:
    if not user_id:
        raise HTTPException(status_code=401, detail="user_id required")
    return user_id


@router.get("/extraction/fragments/{rq_code}")
def get_fragments_by_rq(
    rq_code: str,
    review_id: int,
    user_id: str = Depends(validate_user),
    db: Session = Depends(get_db)
):
    """Get fragments for research question."""
    service = ExtractionService(db)
    fragments = service.get_fragments_by_rq(review_id, rq_code.upper())
    
    return {
        "fragments": [
            {
                "id": f[0],
                "article_id": f[1],
                "rq_code": f[2],
                "fragment_text": f[3],
                "theme_category": f[4],
                "reviewer_id": f[5],
                "article_title": f[7],
                "literature_type": f[8]
            }
            for f in fragments
        ],
        "count": len(fragments)
    }


@router.get("/extraction/codes/{rq_code}")
def get_codes_by_rq(
    rq_code: str,
    review_id: int,
    user_id: str = Depends(validate_user),
    db: Session = Depends(get_db)
):
    """Get codes for research question."""
    service = ExtractionService(db)
    codes = service.get_codes_by_rq(review_id, rq_code.upper())
    
    return {
        "codes": [
            {
                "id": c[0],
                "code_label": c[1],
                "code_description": c[2],
                "rq_code": c[3]
            }
            for c in codes
        ],
        "count": len(codes)
    }


@router.get("/extraction/themes/{rq_code}")
def get_themes_by_rq(
    rq_code: str,
    review_id: int,
    user_id: str = Depends(validate_user),
    db: Session = Depends(get_db)
):
    """Get themes for research question."""
    service = ExtractionService(db)
    themes = service.get_themes_by_rq(review_id, rq_code.upper())
    
    return {
        "themes": [
            {
                "id": t[0],
                "theme_code": t[1],
                "theme_label": t[2],
                "theme_description": t[3]
            }
            for t in themes
        ],
        "count": len(themes)
    }