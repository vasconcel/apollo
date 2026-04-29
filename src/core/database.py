import sqlite3
import json
from contextlib import contextmanager

class Database:
    def __init__(self, db_path="aims.db"):
        self.db_path = db_path
        self._initialize_schema()

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _initialize_schema(self):
        with self.connect() as conn:
            cursor = conn.cursor()

            # ARTICLES
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                abstract TEXT,
                source_id TEXT,
                literature_type TEXT,
                status TEXT DEFAULT 'imported'
            )
            """)

            # SCREENING DECISIONS (Multi-reviewer)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS screening_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER NOT NULL,
                reviewer_id TEXT NOT NULL,
                decision TEXT CHECK(decision IN ('include','exclude','uncertain')),
                exclusion_reason TEXT,
                criteria_snapshot TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(article_id, reviewer_id)
            )
            """)

            # FINAL DECISIONS (consenso)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS final_decisions (
                article_id INTEGER PRIMARY KEY,
                final_decision TEXT,
                resolved_by TEXT,
                resolution_notes TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """)

    # ----------------------------
    # Screening Decisions
    # ----------------------------

    def save_decision(self, article_id, reviewer_id, decision, exclusion_reason=None, criteria=None):
        with self.connect() as conn:
            conn.execute("""
            INSERT OR REPLACE INTO screening_decisions
            (article_id, reviewer_id, decision, exclusion_reason, criteria_snapshot)
            VALUES (?, ?, ?, ?, ?)
            """, (
                article_id,
                reviewer_id,
                decision,
                exclusion_reason,
                json.dumps(criteria) if criteria else None
            ))

    def get_pending_articles(self, reviewer_id):
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT * FROM articles
            WHERE id NOT IN (
                SELECT article_id FROM screening_decisions WHERE reviewer_id = ?
            )
            """, (reviewer_id,))
            return cursor.fetchall()

    def get_all_decisions(self):
        with self.connect() as conn:
            return conn.execute("""
            SELECT * FROM screening_decisions
            """).fetchall()

    # ----------------------------
    # Export / Import
    # ----------------------------

    def export_decisions_csv(self, path, reviewer_id):
        import pandas as pd
        with self.connect() as conn:
            df = pd.read_sql_query("""
                SELECT * FROM screening_decisions
                WHERE reviewer_id = ?
            """, conn, params=(reviewer_id,))
            df.to_csv(path, index=False)

    def import_decisions_csv(self, path):
        import pandas as pd
        df = pd.read_csv(path)

        with self.connect() as conn:
            for _, row in df.iterrows():
                conn.execute("""
                INSERT OR IGNORE INTO screening_decisions
                (article_id, reviewer_id, decision, exclusion_reason, criteria_snapshot, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    row["article_id"],
                    row["reviewer_id"],
                    row["decision"],
                    row.get("exclusion_reason"),
                    row.get("criteria_snapshot"),
                    row.get("created_at")
                ))