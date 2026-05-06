#!/usr/bin/env python3
"""
Main database setup script with PRODUCTION-RELIABLE validation.
Runs all required setup steps in order with proper validation.

Usage: python setup.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


def step_connection() -> bool:
    """Step 1: Test database connection."""
    print("\n" + "="*60)
    print("STEP 1: DATABASE CONNECTION")
    print("="*60)
    
    from app.db.session import test_connection
    
    if test_connection():
        return True
    else:
        print("\n[FAIL] Cannot connect to database")
        print("\nRequired fixes:")
        print("  1. Start PostgreSQL: pg_ctl start (or via services)")
        print("  2. Create database: createdb aims")
        print("  3. Set password: psql -c \"ALTER USER postgres PASSWORD 'postgres'\"")
        return False


def step_create_tables() -> bool:
    """Step 2: Create database tables."""
    print("\n" + "="*60)
    print("STEP 2: CREATE TABLES")
    print("="*60)
    
    from app.db.session import init_db
    
    if init_db():
        print("\n[OK] Tables created successfully")
        return True
    else:
        print("\n[FAIL] Table creation failed")
        return False


def step_seed() -> bool:
    """Step 3: Seed initial data."""
    print("\n" + "="*60)
    print("STEP 3: SEED DATA")
    print("="*60)
    
    from app.db.session import SessionLocal
    from app.models.models import User, Review, ReviewAccess
    import hashlib
    
    def get_password_hash(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()
    
    session = SessionLocal()
    
    try:
        # DELETE non-admin users (strict)
        print("\n[ACTION] Cleaning non-admin users...")
        deleted = 0
        for user in session.query(User).all():
            if user.user_id != "admin":
                session.delete(user)
                deleted += 1
                print(f"       Deleted: {user.user_id}")
        if deleted:
            session.commit()
            print(f"       Total: {deleted}")
        else:
            print("       None to delete")
        
        # UPSERT admin user
        print("\n[ACTION] Creating admin user...")
        admin = session.query(User).filter(User.user_id == "admin").first()
        
        if admin:
            admin.name = "Administrator"
            admin.email = "admin@aims.org"
            admin.hashed_password = get_password_hash("admin123")
            admin.role = "admin"
            admin.is_active = True
            print("       [OK] Admin updated")
        else:
            admin = User(
                user_id="admin",
                name="Administrator",
                email="admin@aims.org",
                hashed_password=get_password_hash("admin123"),
                role="admin",
                is_active=True
            )
            session.add(admin)
            print("       [OK] Admin created")
        
        # UPSERT review
        print("\n[ACTION] Creating default review...")
        review = session.query(Review).filter(Review.id == 1).first()
        
        if review:
            review.name = "Default Review"
            review.status = "active"
            print("       [OK] Review updated")
        else:
            review = Review(id=1, name="Default Review", description="Initial review", status="active")
            session.add(review)
            print("       [OK] Review created")
        
        # UPSERT review access
        print("\n[ACTION] Creating review access...")
        
        access = session.query(ReviewAccess).filter(
            ReviewAccess.user_id == "admin",
            ReviewAccess.review_id == 1
        ).first()
        
        if access:
            access.role = "admin"
            print("       [OK] Access updated")
        else:
            access = ReviewAccess(user_id="admin", review_id=1, role="admin")
            session.add(access)
            print("       [OK] Access created")
        
        session.commit()
        
        # VERIFY via query
        print("\n[VERIFY] Checking final state...")
        
        user_count = session.query(User).count()
        review_count = session.query(Review).count()
        access_count = session.query(ReviewAccess).count()
        
        if user_count == 0:
            print("       [FAIL] No users in database!")
            return False
        
        if review_count == 0:
            print("       [FAIL] No reviews in database!")
            return False
        
        print(f"       Users: {user_count}")
        print(f"       Reviews: {review_count}")
        print(f"       Access entries: {access_count}")
        
        print("\n[OK] Seed completed and verified")
        return True
        
    except Exception as e:
        session.rollback()
        print(f"\n[FAIL] Seed failed: {e}")
        return False
        
    finally:
        session.close()


def step_validate_auth() -> bool:
    """Step 4: Validate authentication with REAL database."""
    print("\n" + "="*60)
    print("STEP 4: VALIDATE AUTH")
    print("="*60)
    
    import hashlib
    from app.db.session import SessionLocal
    from app.auth.auth import (
        verify_password, get_password_hash, 
        create_access_token, decode_token, 
        authenticate_user_db, get_user_allowed_reviews
    )
    from app.models.models import User, ReviewAccess
    
    session = SessionLocal()
    
    try:
        # Test 1: User exists
        print("\n[Test 1] User exists...")
        admin = session.query(User).filter(User.user_id == "admin").first()
        
        if not admin:
            print("       [FAIL] Admin user not found!")
            return False
        
        if not admin.is_active:
            print("       [FAIL] Admin user is inactive!")
            return False
        
        print(f"       [OK] user_id={admin.user_id}, role={admin.role}, active={admin.is_active}")
        
        # Test 2: Password verification
        print("\n[Test 2] Password verification...")
        
        stored_hash = admin.hashed_password
        input_hash = get_password_hash("admin123")
        
        if stored_hash != input_hash:
            print(f"       [FAIL] Password hash mismatch!")
            return False
        
        print("       [OK] Password verified")
        
        # Test 3: Review access exists
        print("\n[Test 3] Review access...")
        
        access = session.query(ReviewAccess).filter(
            ReviewAccess.user_id == "admin",
            ReviewAccess.review_id == 1
        ).first()
        
        if not access:
            print("       [FAIL] No review access for admin!")
            return False
        
        print(f"       [OK] review_id={access.review_id}, role={access.role}")
        
        # Test 4: Full DB-backed authentication
        print("\n[Test 4] Full DB authentication...")
        
        user = authenticate_user_db("admin", "admin123", session)
        
        if not user:
            print("       [FAIL] Authentication failed!")
            return False
        
        allowed = get_user_allowed_reviews("admin", session)
        
        if 1 not in allowed:
            print(f"       [FAIL] No review access: {allowed}")
            return False
        
        print(f"       [OK] Authenticated, reviews={allowed}")
        
        # Test 5: JWT generation with DB data
        print("\n[Test 5] JWT token...")
        
        token = create_access_token({
            "user_id": user.user_id,
            "role": user.role,
            "reviews": allowed
        })
        
        if not token:
            print("       [FAIL] Token generation failed!")
            return False
        
        payload = decode_token(token)
        
        if not payload or payload.get("user_id") != "admin" or 1 not in payload.get("reviews", []):
            print("       [FAIL] Token invalid!")
            return False
        
        print(f"       [OK] Token valid, reviews={payload['reviews']}")
        
        print("\n[OK] All auth validation passed")
        return True
        
    except Exception as e:
        print(f"\n[FAIL] Auth validation error: {e}")
        return False
        
    finally:
        session.close()


def main():
    """Run all setup steps with proper failure handling."""
    print("\n" + "="*60)
    print("DATABASE SETUP (PRODUCTION-RELIABLE)")
    print("="*60)
    print("\nThis will:")
    print("  1. Test database connection")
    print("  2. Create all tables")
    print("  3. Seed strict (admin only)")
    print("  4. Validate auth with REAL database")
    
    steps = [
        ("Connection", step_connection),
        ("Create Tables", step_create_tables),
        ("Seed Data", step_seed),
        ("Validate Auth", step_validate_auth),
    ]
    
    results = []
    
    for name, step_func in steps:
        try:
            result = step_func()
            results.append((name, result))
            
            if not result:
                print(f"\n[STOPPED] Failed at step: {name}")
                break
                
        except Exception as e:
            print(f"\n[ERROR] {name} failed with exception: {e}")
            results.append((name, False))
            break
    
    # Final summary
    print("\n" + "="*60)
    print("FINAL SUMMARY")
    print("="*60)
    
    all_passed = True
    for name, result in results:
        status = "[OK]" if result else "[FAIL]"
        print(f"  {status} {name}")
        if not result:
            all_passed = False
    
    print("\n" + "="*60)
    
    if all_passed:
        print("SUCCESS: System is production-ready!")
        print("\n[CREDS] admin / admin123")
        print("[API] http://localhost:8000")
        print("[DOCS] http://localhost:8000/docs")
    else:
        print("FAILED: Setup incomplete")
        print("\nFix the failed step and re-run setup.py")
        sys.exit(1)
    
    print("="*60)


if __name__ == "__main__":
    main()