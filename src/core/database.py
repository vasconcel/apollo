import sqlite3
import json
from contextlib import contextmanager


class Database:
    def __init__(self, db_path="aims.db"):
        self.db_path = db_path
        self._initialize_schema()

    # =============================
    # CONNECTION
    # =============================
    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # =============================
    # SCHEMA
    # =============================
    def _initialize_schema(self):
        with self.connect() as conn:
            cursor = conn.cursor()

            # -------------------------
            # ARTICLES
            # -------------------------
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

            # -------------------------
            # SCREENING (MULTI-REVIEWER)
            # -------------------------
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

            # -------------------------
            # FINAL CONSENSUS
            # -------------------------
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS final_decisions (
                article_id INTEGER PRIMARY KEY,
                final_decision TEXT CHECK(final_decision IN ('include','exclude')),
                resolved_by TEXT,
                resolution_notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)

            # -------------------------
            # QUALITY ASSESSMENT
            # -------------------------
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS quality_assessments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER,
                reviewer_id TEXT,
                criteria_scores TEXT,
                total_score REAL,
                decision TEXT CHECK(decision IN ('include','exclude')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)

    # =============================
    # SCREENING METHODS
    # =============================

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

    def get_all_screening_decisions(self):
        with self.connect() as conn:
            return conn.execute("""
            SELECT * FROM screening_decisions
            """).fetchall()

    # =============================
    # CONSENSUS METHODS
    # =============================

    def save_final_decision(self, article_id, decision, reviewer_id, notes):
        with self.connect() as conn:
            conn.execute("""
            INSERT OR REPLACE INTO final_decisions
            (article_id, final_decision, resolved_by, resolution_notes)
            VALUES (?, ?, ?, ?)
            """, (article_id, decision, reviewer_id, notes))

    def get_final_decisions(self):
        with self.connect() as conn:
            return conn.execute("""
            SELECT * FROM final_decisions
            """).fetchall()

    # =============================
    # QUALITY METHODS
    # =============================

    def save_quality_assessment(self, article_id, reviewer_id, scores_dict, total_score, decision):
        with self.connect() as conn:
            conn.execute("""
            INSERT INTO quality_assessments
            (article_id, reviewer_id, criteria_scores, total_score, decision)
            VALUES (?, ?, ?, ?, ?)
            """, (
                article_id,
                reviewer_id,
                json.dumps(scores_dict),
                total_score,
                decision
            ))

    def get_quality_by_article(self, article_id):
        with self.connect() as conn:
            return conn.execute("""
            SELECT * FROM quality_assessments
            WHERE article_id = ?
            """, (article_id,)).fetchall()

    # =============================
    # EXPORT / IMPORT (REPLICA + MERGE)
    # =============================

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

    # =============================
    # OPTIONAL (DEBUG / STATS)
    # =============================

    def count_articles(self):
        with self.connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]

    def count_screened(self):
        with self.connect() as conn:
            return conn.execute("""
            SELECT COUNT(DISTINCT article_id) FROM screening_decisions
            """).fetchone()[0]