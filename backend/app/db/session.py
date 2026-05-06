import os
import logging

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/aims"
)

try:
    from sqlalchemy import create_engine
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=10)
except Exception as e:
    logger.warning(f"Failed to create engine with default URL: {e}")
    engine = None

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

if engine:
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
else:
    SessionLocal = None


def get_db():
    """Dependency for FastAPI routes."""
    if not SessionLocal:
        raise RuntimeError("Database not initialized. Run setup.py first.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_connection() -> bool:
    """
    Test database connection with multiple checks.
    
    Returns:
        True if all checks pass, False otherwise.
    """
    print("\n" + "="*60)
    print("DATABASE CONNECTION TEST")
    print("="*60)
    
    connection_ok = False
    
    # Test 1: Basic connection
    print("\n[Test 1] Basic connection (SELECT 1)")
    try:
        from sqlalchemy import create_engine, text
        test_engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        with test_engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.close()
        print("  [OK] Database responds to SELECT 1")
        connection_ok = True
    except Exception as e:
        print(f"  [FAIL] Cannot connect: {str(e)[:80]}")
        connection_ok = False
    
    if not connection_ok:
        print("\n[ERROR] Database connection failed")
        return False
    
    # Test 2: Check PostgreSQL version
    print("\n[Test 2] PostgreSQL version")
    try:
        from sqlalchemy import create_engine, text
        test_engine = create_engine(DATABASE_URL)
        with test_engine.connect() as conn:
            result = conn.execute(text("SELECT version()")).fetchone()
            version = result[0] if result else "unknown"
            print(f"  [OK] {version[:60]}...")
    except Exception as e:
        print(f"  [WARN] Could not get version: {e}")
    
    # Test 3: Check tables (if any exist)
    print("\n[Test 3] Check existing tables")
    try:
        from sqlalchemy import create_engine, text, inspect
        test_engine = create_engine(DATABASE_URL)
        inspector = inspect(test_engine)
        tables = inspector.get_table_names()
        print(f"  [OK] Found {len(tables)} tables: {tables[:5]}{'...' if len(tables) > 5 else ''}")
    except Exception as e:
        print(f"  [WARN] Could not list tables: {e}")
    
    # Test 4: Verify we can query
    print("\n[Test 4] Query capability")
    try:
        from sqlalchemy import create_engine, text
        test_engine = create_engine(DATABASE_URL)
        with test_engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM pg_tables")).fetchone()
            table_count = result[0] if result else 0
            print(f"  [OK] Database accessible, {table_count} system tables")
    except Exception as e:
        print(f"  [FAIL] Cannot query database: {e}")
        return False
    
    print("\n" + "="*60)
    print("[OK] CONNECTION TEST PASSED")
    print("="*60)
    
    return True


def init_db() -> bool:
    """
    Initialize database tables with validation.
    
    Returns:
        True if successful
    """
    print("\n" + "="*60)
    print("DATABASE TABLE CREATION")
    print("="*60)
    
    if not engine:
        print("[ERROR] Engine not initialized")
        return False
    
    try:
        # Import models to register them with Base
        from app.models import models
        
        print(f"\n[INFO] Creating tables...")
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        
        print("  [OK] Tables created")
        
        # Verify tables exist
        print("\n[INFO] Verifying table creation...")
        from sqlalchemy import inspect
        inspector = inspect(engine)
        created_tables = inspector.get_table_names()
        
        expected_tables = [
            'users', 'reviews', 'review_access', 
            'articles', 'screening_decisions', 'screening_conflicts',
            'final_decisions', 'quality_assessments', 'fragments',
            'codes', 'themes', 'assignments', 'review_state', 'audit_logs'
        ]
        
        print(f"\n[INFO] Found {len(created_tables)} tables:")
        for t in sorted(created_tables):
            print(f"       - {t}")
        
        # Check for missing tables
        missing = [t for t in expected_tables if t not in created_tables]
        
        if missing:
            print(f"\n[WARN] Missing expected tables: {missing}")
        else:
            print(f"\n[OK] All {len(expected_tables)} expected tables created")
        
        return True
        
    except Exception as e:
        print(f"\n[ERROR] Failed to create tables: {e}")
        return False