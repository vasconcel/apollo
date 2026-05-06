from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.auth.auth import authenticate_user_db, create_access_token, get_password_hash, User as AuthUser
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


class LoginRequest(BaseModel):
    user_id: str
    password: str = ""


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user_id: str
    role: str


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate user and return JWT token.
    
    Usage:
        POST /api/v1/auth/login
        Body: {"user_id": "admin", "password": ""}
    
    Returns:
        {"access_token": "eyJ...", "token_type": "bearer", "user_id": "...", "role": "..."}
    """
    user = authenticate_user_db(request.user_id, request.password, db)
    
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )
    
    token_data = {
        "user_id": user.user_id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "reviews": user.allowed_reviews
    }
    
    access_token = create_access_token(token_data)
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user.user_id,
        role=user.role
    )


@router.post("/register")
def register(user_id: str, name: str, email: str, password: str = "", db: Session = Depends(get_db)):
    """Register a new user."""
    from app.models.models import User as DBUser
    
    existing = db.query(DBUser).filter(DBUser.user_id == user_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")
    
    hashed = get_password_hash(password) if password else None
    
    new_user = DBUser(
        user_id=user_id,
        name=name,
        email=email,
        role="reviewer"
    )
    db.add(new_user)
    db.commit()
    
    return {"status": "created", "user_id": user_id}


@router.get("/verify")
def verify_token(current_user: AuthUser = Depends(get_current_user)):
    """Verify token is valid."""
    return {"valid": True, "user_id": current_user.user_id}