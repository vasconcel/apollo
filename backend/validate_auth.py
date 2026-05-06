#!/usr/bin/env python3
"""
Auth flow validation script with REAL database validation.
Tests: user exists, password matches, review_access exists, JWT works.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.auth.auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_token,
    authenticate_user_db,
    get_user_allowed_reviews
)
from app.models.models import User, ReviewAccess
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_user_exists(session) -> bool:
    """Verify admin user exists in database."""
    logger.info("Testing user exists in database...")
    
    user = session.query(User).filter(User.user_id == "admin").first()
    
    if not user:
        logger.error("  [FAIL] Admin user not found in database")
        return False
    
    if not user.is_active:
        logger.error("  [FAIL] Admin user is inactive")
        return False
    
    logger.info(f"  [OK] User found: {user.user_id}, role={user.role}, active={user.is_active}")
    return True


def test_password_verification(session) -> bool:
    """Verify password matches stored hash."""
    logger.info("Testing password verification...")
    
    user = session.query(User).filter(User.user_id == "admin").first()
    
    if not user or not user.hashed_password:
        logger.error("  [FAIL] No password hash stored")
        return False
    
    # Verify stored hash matches "admin123"
    stored_hash = user.hashed_password
    input_hash = get_password_hash("admin123")
    
    if stored_hash != input_hash:
        logger.error(f"  [FAIL] Password mismatch")
        logger.error(f"       stored: {stored_hash[:20]}...")
        logger.error(f"       input:  {input_hash[:20]}...")
        return False
    
    logger.info("  [OK] Password verified successfully")
    return True


def test_review_access_exists(session) -> bool:
    """Verify review_access entry exists for admin."""
    logger.info("Testing review access...")
    
    access = session.query(ReviewAccess).filter(
        ReviewAccess.user_id == "admin",
        ReviewAccess.review_id == 1
    ).first()
    
    if not access:
        logger.error("  [FAIL] No review_access for admin -> review 1")
        return False
    
    logger.info(f"  [OK] Access exists: user={access.user_id}, review={access.review_id}, role={access.role}")
    return True


def test_jwt_generation() -> bool:
    """Test JWT token generation."""
    logger.info("Testing JWT generation...")
    
    user_data = {
        "user_id": "admin",
        "name": "Administrator",
        "email": "admin@aims.org",
        "role": "admin",
        "reviews": [1]
    }
    
    token = create_access_token(user_data)
    
    if not token:
        logger.error("  [FAIL] Token generation failed")
        return False
    
    logger.info(f"  [OK] Token generated: {token[:30]}...")
    
    payload = decode_token(token)
    
    if not payload:
        logger.error("  [FAIL] Token decode failed")
        return False
    
    if payload.get("user_id") != "admin":
        logger.error(f"  [FAIL] Token has wrong user_id: {payload.get('user_id')}")
        return False
    
    if 1 not in payload.get("reviews", []):
        logger.error(f"  [FAIL] Token missing review 1: {payload.get('reviews')}")
        return False
    
    logger.info(f"  [OK] Token valid: user_id={payload['user_id']}, reviews={payload['reviews']}")
    return True


def test_full_auth_flow() -> bool:
    """Test complete authentication using database."""
    logger.info("Testing full auth flow (DB-backed)...")
    
    session = SessionLocal()
    try:
        # Step 1: Authenticate against DB
        user = authenticate_user_db("admin", "admin123", session)
        
        if not user:
            logger.error("  [FAIL] Authentication failed - user not found or inactive")
            return False
        
        logger.info(f"  [OK] DB Authentication: user={user.user_id}, role={user.role}")
        
        # Step 2: Verify allowed_reviews from DB
        allowed = get_user_allowed_reviews("admin", session)
        
        if 1 not in allowed:
            logger.error(f"  [FAIL] No review access in DB: {allowed}")
            return False
        
        logger.info(f"  [OK] Review access from DB: {allowed}")
        
        # Step 3: Generate JWT with DB-derived data
        token_data = {
            "user_id": user.user_id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "reviews": allowed
        }
        
        token = create_access_token(token_data)
        
        if not token:
            logger.error("  [FAIL] JWT generation failed")
            return False
        
        # Step 4: Verify token
        payload = decode_token(token)
        
        if not payload:
            logger.error("  [FAIL] Token decode failed")
            return False
        
        if payload.get("user_id") != "admin" or 1 not in payload.get("reviews", []):
            logger.error("  [FAIL] Token payload invalid")
            return False
        
        logger.info("  [OK] Full auth flow verified:")
        logger.info(f"       - User authenticated via DB")
        logger.info(f"       - Review access verified via DB")
        logger.info(f"       - JWT contains DB-derived review_ids")
        
        return True
        
    finally:
        session.close()


def validate_auth() -> bool:
    """Run all auth validation tests with REAL DB."""
    print("\n" + "="*60)
    print("AUTH VALIDATION (REAL DATABASE)")
    print("="*60)
    
    session = SessionLocal()
    
    tests = []
    
    # Test 1: User exists
    print("\n--- Test 1: User Exists ---")
    tests.append(("User exists", test_user_exists(session)))
    
    # Test 2: Password verification
    print("\n--- Test 2: Password Verification ---")
    tests.append(("Password matches", test_password_verification(session)))
    
    # Test 3: Review access
    print("\n--- Test 3: Review Access ---")
    tests.append(("Review access", test_review_access_exists(session)))
    
    # Test 4: JWT
    print("\n--- Test 4: JWT Generation ---")
    tests.append(("JWT token", test_jwt_generation()))
    
    # Test 5: Full flow
    print("\n--- Test 5: Full Auth Flow (DB-backed) ---")
    tests.append(("Full auth", test_full_auth_flow()))
    
    session.close()
    
    # Summary
    print("\n" + "="*60)
    print("AUTH VALIDATION RESULTS")
    print("="*60)
    
    all_passed = True
    for name, result in tests:
        status = "[OK]" if result else "[FAIL]"
        print(f"  {status} {name}")
        if not result:
            all_passed = False
    
    if all_passed:
        print("\n" + "="*60)
        print("[OK] AUTH VALIDATION PASSED")
        print("="*60)
        return True
    else:
        print("\n" + "="*60)
        print("[FAIL] AUTH VALIDATION FAILED")
        print("="*60)
        return False


if __name__ == "__main__":
    success = validate_auth()
    sys.exit(0 if success else 1)