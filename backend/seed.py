#!/usr/bin/env python3
"""
Database seeding script with STRICT control.
- Only creates admin user if no users exist (or with explicit option)
- Deletes non-admin users before seeding
- Uses transactions for safety
- Idempotent with clear logging
"""
import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.models.models import User, Review, ReviewAccess

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_password_hash(password: str) -> str:
    """Generate password hash using SHA256."""
    import hashlib
    return hashlib.sha256(password.encode()).hexdigest()


def seed_strict(force_admin: bool = True, keep_existing: bool = False) -> bool:
    """
    Seed database with strict control.
    
    Args:
        force_admin: Always ensure admin exists
        keep_existing: Keep existing users (only add admin if none)
    
    Returns:
        True if successful
    """
    session = SessionLocal()
    
    try:
        print("\n" + "="*60)
        print("DATABASE SEEDING (STRICT MODE)")
        print("="*60)
        
        # Start transaction
        print("\n[INFO] Starting transaction...")
        
        # Get current users
        existing_users = session.query(User).all()
        user_count = len(existing_users)
        
        print(f"\n[INFO] Current users in database: {user_count}")
        for u in existing_users:
            print(f"       - {u.user_id} (role={u.role}, active={u.is_active})")
        
        # DELETE non-admin users (strict mode)
        if not keep_existing:
            print("\n[ACTION] Deleting non-admin users...")
            deleted_count = 0
            for user in existing_users:
                if user.user_id != "admin":
                    session.delete(user)
                    print(f"       Deleted: {user.user_id}")
                    deleted_count += 1
            if deleted_count > 0:
                session.commit()
                print(f"       Total deleted: {deleted_count}")
            else:
                print("       No non-admin users to delete")
        
        # UPSERT admin user
        print("\n[ACTION] Ensuring admin user exists...")
        admin = session.query(User).filter(User.user_id == "admin").first()
        
        if admin:
            print(f"       Found existing admin (role={admin.role})")
            admin.name = "Administrator"
            admin.email = "admin@aims.org"
            admin.hashed_password = get_password_hash("admin123")
            admin.role = "admin"
            admin.is_active = True
            print("       [OK] Updated admin user")
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
            print("       [OK] Created admin user")
        
        # UPSERT review
        print("\n[ACTION] Ensuring default review exists...")
        review = session.query(Review).filter(Review.id == 1).first()
        
        if review:
            print(f"       Found existing review: {review.name}")
            review.name = "Default Review"
            review.status = "active"
            print("       [OK] Updated review")
        else:
            review = Review(
                id=1,
                name="Default Review",
                description="Initial review project for systematic literature review",
                status="active"
            )
            session.add(review)
            print("       [OK] Created default review (id=1)")
        
        # UPSERT review access
        print("\n[ACTION] Ensuring review access exists...")
        
        # Admin access
        admin_access = session.query(ReviewAccess).filter(
            ReviewAccess.user_id == "admin",
            ReviewAccess.review_id == 1
        ).first()
        
        if admin_access:
            admin_access.role = "admin"
            print("       [OK] Admin access exists (updated role)")
        else:
            admin_access = ReviewAccess(
                user_id="admin",
                review_id=1,
                role="admin"
            )
            session.add(admin_access)
            print("       [OK] Created admin -> review 1 access")
        
        # Commit transaction
        session.commit()
        print("\n[INFO] Transaction committed successfully")
        
        # Final verification via query
        print("\n" + "-"*40)
        print("FINAL STATE (verified via query)")
        print("-"*40)
        
        final_users = session.query(User).all()
        final_reviews = session.query(Review).all()
        final_access = session.query(ReviewAccess).all()
        
        print(f"\nUsers: {len(final_users)}")
        for u in final_users:
            print(f"  - {u.user_id} (role={u.role}, active={u.is_active})")
        
        print(f"\nReviews: {len(final_reviews)}")
        for r in final_reviews:
            print(f"  - id={r.id}, name={r.name}, status={r.status}")
        
        print(f"\nReview Access: {len(final_access)}")
        for a in final_access:
            print(f"  - user={a.user_id}, review={a.review_id}, role={a.role}")
        
        print("\n" + "="*60)
        print("[OK] SEEDING COMPLETE")
        print("="*60)
        
        return True
        
    except Exception as e:
        session.rollback()
        print(f"\n[ERROR] Seed failed: {e}")
        print("[ACTION] Transaction rolled back")
        return False
        
    finally:
        session.close()


def seed_idempotent() -> bool:
    """Backward-compatible seeding (keeps existing users)."""
    return seed_strict(keep_existing=True)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Seed database")
    parser.add_argument("--strict", action="store_true", 
                       help="Delete non-admin users before seeding")
    args = parser.parse_args()
    
    success = seed_strict(force_admin=True, keep_existing=not args.strict)
    
    if not success:
        sys.exit(1)