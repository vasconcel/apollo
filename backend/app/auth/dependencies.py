from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List
from sqlalchemy.orm import Session
from app.auth.auth import decode_token, get_user_from_token_payload, check_review_access
from app.db.session import get_db
import logging

logger = logging.getLogger(__name__)
security = HTTPBearer()


def get_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Extract token from Authorization header."""
    return credentials.credentials


def get_current_user(
    token: str = Depends(get_token),
    db: Session = Depends(get_db)
) -> User:
    """
    Extract and validate user from JWT token, then verify against database.
    CRITICAL: This ensures user still exists and is active.
    """
    payload = decode_token(token)
    
    if not payload:
        logger.warning("Invalid token decode attempt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = get_user_from_token_payload(payload, db)
    
    if not user:
        logger.warning(f"User from token not found or inactive: {payload.get('user_id')}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


def require_review_access(
    user: User,
    review_id: int,
    db: Session = Depends(get_db)
) -> int:
    """
    Validate user has access to review_id.
    CRITICAL: Enforces tenant isolation via database.
    """
    if review_id not in user.allowed_reviews:
        has_access = check_review_access(user.user_id, review_id, db)
        if not has_access:
            logger.warning(f"Access denied: user {user.user_id} tried to access review {review_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User {user.user_id} does not have access to review {review_id}"
            )
    return review_id


class User:
    """User object for auth."""
    
    def __init__(self, user_id: str, name: str, email: str, role: str, is_active: bool, allowed_reviews: List[int]):
        self.user_id = user_id
        self.name = name
        self.email = email
        self.role = role
        self.is_active = is_active
        self.allowed_reviews = allowed_reviews