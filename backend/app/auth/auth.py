from datetime import datetime, timedelta
from typing import Optional, List
import os

from jose import JWTError, jwt
from sqlalchemy.orm import Session
import hashlib

from app.db.session import SessionLocal
from app.models.models import User as DBUser, ReviewAccess


SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production-very-long-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against SHA256 hash."""
    if not hashed_password:
        return False
    hashed = hashlib.sha256(plain_password.encode()).hexdigest()
    return hashed == hashed_password


def get_password_hash(password: str) -> str:
    """Generate password hash using SHA256."""
    return hashlib.sha256(password.encode()).hexdigest()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """Decode and validate JWT token."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


class User:
    """User object for auth."""
    
    def __init__(self, user_id: str, name: str, email: str, role: str, is_active: bool, allowed_reviews: List[int]):
        self.user_id = user_id
        self.name = name
        self.email = email
        self.role = role
        self.is_active = is_active
        self.allowed_reviews = allowed_reviews
    
    @classmethod
    def from_db_user(cls, db_user: DBUser, allowed_reviews: List[int]) -> "User":
        return cls(
            user_id=db_user.user_id,
            name=db_user.name,
            email=db_user.email or "",
            role=db_user.role or "reviewer",
            is_active=db_user.is_active if db_user.is_active is not None else True,
            allowed_reviews=allowed_reviews
        )


def get_user_by_id(user_id: str, db: Session) -> Optional[DBUser]:
    """Get user from database."""
    return db.query(DBUser).filter(DBUser.user_id == user_id).first()


def get_user_allowed_reviews(user_id: str, db: Session) -> List[int]:
    """Get list of review_ids the user has access to."""
    access_entries = db.query(ReviewAccess).filter(ReviewAccess.user_id == user_id).all()
    return [a.review_id for a in access_entries]


def authenticate_user_db(user_id: str, password: str, db: Session) -> Optional[User]:
    """Authenticate user against database with real password verification."""
    db_user = get_user_by_id(user_id, db)
    
    if not db_user:
        return None
    
    if not db_user.is_active:
        return None
    
    if not db_user.hashed_password:
        return None
    
    if not verify_password(password, db_user.hashed_password):
        return None
    
    allowed_reviews = get_user_allowed_reviews(user_id, db)
    if not allowed_reviews:
        allowed_reviews = [1]
    
    return User.from_db_user(db_user, allowed_reviews)


def get_user_from_token_payload(payload: dict, db: Session) -> Optional[User]:
    """Get user from token payload, validating against DB."""
    user_id = payload.get("user_id")
    if not user_id:
        return None
    
    db_user = get_user_by_id(user_id, db)
    if not db_user:
        return None
    
    if not db_user.is_active:
        return None
    
    allowed_reviews = get_user_allowed_reviews(user_id, db)
    if not allowed_reviews:
        allowed_reviews = [1]
    
    return User.from_db_user(db_user, allowed_reviews)


def check_review_access(user_id: str, review_id: int, db: Session) -> bool:
    """Check if user has access to specific review."""
    access = db.query(ReviewAccess).filter(
        ReviewAccess.user_id == user_id,
        ReviewAccess.review_id == review_id
    ).first()
    return access is not None