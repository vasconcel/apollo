# src/core/database.py
import sqlite3
import pandas as pd
import re
import os
from typing import Dict, Any

class DatabaseManager:
    def __init__(self, db_path: str = "data/aims_project.db"):
        self.db_path = db_path
        self._ensure_db_directory()
        self._initialize_schema()

    def _ensure_db_directory(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    def _initialize_schema(self):
        """Creates table and handles seamless schema migration if strict constraints are found."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='articles'")
            row = cursor.fetchone()
            
            create_sql = """
                CREATE TABLE IF NOT EXISTS articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    original_title TEXT,
                    authors TEXT,
                    year INTEGER,
                    abstract TEXT,
                    doi TEXT,
                    url TEXT,
                    source TEXT,
                    literature_type TEXT CHECK(literature_type IN ('WL', 'GL', 'PENDING')),
                    status TEXT CHECK(status IN ('imported', 'deduplicated', 'excluded', 'included_screening', 'included_final')) DEFAULT 'imported',
                    exclusion_reason TEXT,
                    ic_results TEXT,
                    quality_score REAL,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            
            needs_migration = False
            if row:
                current_sql = row[0].upper()
                # Check for old CHECK constraints or restrictive UNIQUE constraints
                if "('WL', 'GL')" in current_sql and "PENDING" not in current_sql:
                    needs_migration = True
                if "UNIQUE" in current_sql:
                    needs_migration = True
                    
            if needs_migration:
                conn.execute("PRAGMA foreign_keys=off")
                try:
                    conn.execute("BEGIN TRANSACTION")
                    conn.execute("ALTER TABLE articles RENAME TO articles_old")
                    conn.execute(create_sql)
                    
                    # Safely map columns in case of version differences
                    old_cols = [c[1] for c in conn.execute("PRAGMA table_info(articles_old)").fetchall()]
                    new_cols = [c[1] for c in conn.execute("PRAGMA table_info(articles)").fetchall()]
                    common_cols = ", ".join([c for c in old_cols if c in new_cols])
                    
                    if common_cols:
                        conn.execute(f"INSERT INTO articles ({common_cols}) SELECT {common_cols} FROM articles_old")
                        
                    conn.execute("DROP TABLE articles_old")
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    print(f"Migration failed: {e}")
                finally:
                    conn.execute("PRAGMA foreign_keys=on")
            else:
                conn.execute(create_sql)
                conn.commit()

    def _normalize_title(self, title: str) -> str:
        if not title: return ""
        title_str = str(title).lower().strip()
        title_str = re.sub(r'[^\w\s]', '', title_str)
        title_str = re.sub(r'\s+', ' ', title_str)
        return title_str

    def upsert_article(self, article_data: Dict[str, Any]) -> int:
        """Generic Upsert: Handles missing DOIs seamlessly without integrity violations."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            doi = str(article_data.get('doi', '')).strip()
            
            title = article_data.get('title', '')
            norm_title = self._normalize_title(title)
            year = article_data.get('year')

            existing = None
            if doi and len(doi) > 3:
                cursor = conn.execute("SELECT id FROM articles WHERE doi = ?", (doi,))
                existing = cursor.fetchone()

            if not existing and norm_title:
                if year:
                    cursor = conn.execute("SELECT id FROM articles WHERE title = ? AND year = ?", (norm_title, year))
                else:
                    cursor = conn.execute("SELECT id FROM articles WHERE title = ? AND year IS NULL", (norm_title,))
                existing = cursor.fetchone()

            if existing:
                article_id = existing['id']
                updates = []
                params = []
                for key in ['title', 'authors', 'year', 'abstract', 'doi', 'url', 'source', 'literature_type']:
                    if key in article_data and article_data[key] is not None:
                        updates.append(f"{key} = ?")
                        params.append(article_data[key])
                if updates:
                    params.append(article_id)
                    conn.execute(f"UPDATE articles SET {', '.join(updates)} WHERE id = ?", params)
                return article_id
            else:
                lit_type = article_data.get('literature_type') or 'PENDING'
                cursor = conn.execute("""
                    INSERT INTO articles (title, original_title, authors, year, abstract, doi, url, source, literature_type, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'imported')
                """, (
                    norm_title, article_data.get('original_title', title),
                    article_data.get('authors', ''), year, article_data.get('abstract', ''),
                    doi, article_data.get('url', ''), article_data.get('source', ''), lit_type
                ))
                conn.commit()
                return cursor.lastrowid

    def upsert_mesh(self, articles_list: list):
        for article in articles_list:
            self.upsert_article(article)

    def get_stats(self):
        with sqlite3.connect(self.db_path) as conn:
            stats = {}
            stats['total'] = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
            stats['wl_count'] = conn.execute("SELECT COUNT(*) FROM articles WHERE literature_type = 'WL'").fetchone()[0]
            stats['gl_count'] = conn.execute("SELECT COUNT(*) FROM articles WHERE literature_type = 'GL'").fetchone()[0]
            cursor = conn.execute("SELECT status, COUNT(*) FROM articles GROUP BY status")
            stats['status_breakdown'] = {row[0]: row[1] for row in cursor.fetchall()}
            return stats

    def get_articles_by_status(self, status: str):
        with sqlite3.connect(self.db_path) as conn:
            return pd.read_sql_query("SELECT * FROM articles WHERE status = ?", conn, params=(status,))

    def update_article_status(self, article_id: int, new_status: str, exclusion_reason: str = None):
        with sqlite3.connect(self.db_path) as conn:
            if exclusion_reason:
                conn.execute("UPDATE articles SET status = ?, exclusion_reason = ? WHERE id = ?", (new_status, exclusion_reason, article_id))
            else:
                conn.execute("UPDATE articles SET status = ? WHERE id = ?", (new_status, article_id))
            conn.commit()