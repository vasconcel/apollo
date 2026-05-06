#!/usr/bin/env python3
"""
Database initialization script.
Creates all tables from SQLAlchemy models.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import engine, Base
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_tables():
    """Create all tables defined in models."""
    logger.info("Creating database tables...")
    
    tables_created = []
    tables_skipped = []
    
    for table_name in Base.metadata.tables.keys():
        try:
            table = Base.metadata.tables[table_name]
            table.create(bind=engine, checkfirst=True)
            tables_created.append(table_name)
            logger.info(f"  [OK] {table_name}")
        except Exception as e:
            tables_skipped.append((table_name, str(e)))
            logger.warning(f"  [WARN] {table_name}: {e}")
    
    return tables_created, tables_skipped


def list_tables():
    """List all tables in the database."""
    from sqlalchemy import inspect
    
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    return tables


if __name__ == "__main__":
    print("\n" + "="*60)
    print("DATABASE TABLE CREATION")
    print("="*60)
    
    created, skipped = create_tables()
    
    print(f"\n[RESULT] Created: {len(created)} tables")
    print(f"[RESULT] Skipped: {len(skipped)} tables")
    
    if skipped:
        print("\nSkipped tables (may already exist):")
        for name, error in skipped:
            print(f"  - {name}: {error}")
    
    print("\n" + "="*60)
    print("COMPLETE")
    print("="*60)