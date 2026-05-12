"""
APOLLO Database - ORPHANED RUNTIME MODULE
==========================================

DEPRECATED as of 2026-05-12.

This module is ORPHANED and is NOT part of the canonical APOLLO execution path.

CANONICAL PATH:
  - Session management: src.core.screening_session.ScreeningSession (JSON-based)
  - Article records: src.core.atlas_processor.ArticleRecord
  - Export: src.core.export_engine.ExportEngine

WHY ORPHANED:
  1. The canonical path uses ScreeningSession (JSON, file-persisted) for state
  2. This module uses SQLite for persistence — separate persistence layer
  3. Only used by orphaned UI modules (eligibility_view, quality_view, etc.)
  4. No canonical module imports it

REMAINING CONSUMERS (ORPHANED):
  - src/ui/modules/overview_view.py (ORPHANED)
  - src/ui/modules/eligibility_view.py (ORPHANED)
  - src/ui/modules/quality_view.py (ORPHANED)
  - src/ui/modules/planning_view.py (ORPHANED)

FUTURE USE CASE:
  This module may be useful for future multi-user features or persistent
  database requirements. For now, it is preserved but not extended.

This module will be reviewed when multi-user features are planned.

AVOID: Do not use for new features without architectural review.
"""
import sqlite3
import json
import logging
import pandas as pd
from contextlib import contextmanager
from typing import Optional


class DatabaseError(Exception):
    pass


class Database:
    def __init__(self, db_path="apollo.db", review_id=None):
        if review_id is None:
            raise DatabaseError("review_id is REQUIRED for isolation")
        
        self.db_path = db_path
        self.review_id = review_id
        self._logger = logging.getLogger("apollo.database")
        self._initialize_schema()
    
    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def _initialize_schema(self):
        with self.connect() as conn:
            cursor = conn.cursor()
            
            # Reviews table (minimal)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            cursor.execute("SELECT COUNT(*) FROM reviews")
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    INSERT INTO reviews (id, name, description, status)
                    VALUES (1, 'Default Review', 'APOLLO EC/IC/QC Review', 'active')
                """)
            
            # Articles table (simplified)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                review_id INTEGER DEFAULT 1,
                title TEXT,
                authors TEXT,
                year INTEGER,
                abstract TEXT,
                doi TEXT,
                url TEXT,
                source TEXT,
                literature_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (review_id) REFERENCES reviews(id)
            )
            """)
            
            # Eligibility Decisions (EC + IC) - with LLM rationale
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS eligibility_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER NOT NULL,
                reviewer_id TEXT NOT NULL,
                stage TEXT NOT NULL CHECK(stage IN ('EC', 'IC')),
                decision TEXT NOT NULL CHECK(decision IN ('include', 'exclude', 'pending')),
                reason TEXT,
                criteria_snapshot TEXT,
                llm_rationale TEXT,
                llm_confidence REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (article_id) REFERENCES articles(id)
            )
            """)
            
            cursor.execute("""
            CREATE INDEX idx_eligibility_article ON eligibility_decisions(article_id)
            """)
            
            cursor.execute("""
            CREATE INDEX idx_eligibility_stage ON eligibility_decisions(stage)
            """)
            
            # Quality Assessments (WL-Q1 to GL-Q4) - with LLM rationale
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS quality_assessments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER NOT NULL,
                reviewer_id TEXT NOT NULL,
                literature_type TEXT NOT NULL CHECK(literature_type IN ('WL', 'GL')),
                criteria_scores TEXT NOT NULL,
                total_score REAL NOT NULL,
                decision TEXT NOT NULL CHECK(decision IN ('include', 'exclude')),
                threshold REAL DEFAULT 2.0,
                llm_rationale TEXT,
                llm_confidence REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (article_id) REFERENCES articles(id)
            )
            """)
            
            cursor.execute("""
            CREATE INDEX idx_quality_article ON quality_assessments(article_id)
            """)
            
            # Users (minimal - audit only)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                role TEXT DEFAULT 'reviewer',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            cursor.execute("SELECT COUNT(*) FROM users")
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    INSERT INTO users (user_id, name, role)
                    VALUES ('system', 'System', 'reviewer')
                """)
            
            # Project Config (minimal - for QC threshold only)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_config (
                id INTEGER PRIMARY KEY CHECK(id = 1),
                quality_threshold REAL DEFAULT 2.0,
                wl_criteria TEXT DEFAULT '["WL-Q1", "WL-Q2", "WL-Q3", "WL-Q4"]',
                gl_criteria TEXT DEFAULT '["GL-Q1", "GL-Q2", "GL-Q3", "GL-Q4"]',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            cursor.execute("SELECT COUNT(*) FROM project_config")
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    INSERT INTO project_config (id, quality_threshold) VALUES (1, 2.0)
                """)
    
    def add_article(self, article_data: dict) -> int:
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO articles (review_id, title, authors, year, abstract, doi, url, source, literature_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                self.review_id,
                article_data.get("title"),
                article_data.get("authors"),
                article_data.get("year"),
                article_data.get("abstract"),
                article_data.get("doi"),
                article_data.get("url"),
                article_data.get("source"),
                article_data.get("literature_type", "WL")
            ))
            return cursor.lastrowid
    
    def get_articles(self, limit: int = None) -> list:
        with self.connect() as conn:
            query = "SELECT * FROM articles WHERE review_id = ?"
            if limit:
                query += f" LIMIT {limit}"
            cursor = conn.cursor()
            cursor.execute(query, (self.review_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_article_by_id(self, article_id: int) -> Optional[dict]:
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM articles WHERE id = ? AND review_id = ?", (article_id, self.review_id))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def save_eligibility_decision(self, article_id: int, reviewer_id: str, stage: str, 
                                   decision: str, reason: str = None, criteria_snapshot: str = None,
                                   llm_rationale: dict = None, llm_confidence: float = None) -> int:
        with self.connect() as conn:
            cursor = conn.cursor()
            rationale_json = json.dumps(llm_rationale) if llm_rationale else None
            cursor.execute("""
                INSERT INTO eligibility_decisions (article_id, reviewer_id, stage, decision, reason, criteria_snapshot, llm_rationale, llm_confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (article_id, reviewer_id, stage, decision, reason, criteria_snapshot, rationale_json, llm_confidence))
            return cursor.lastrowid
    
    def get_eligibility_decisions(self, article_id: int = None, stage: str = None) -> list:
        with self.connect() as conn:
            query = "SELECT * FROM eligibility_decisions WHERE 1=1"
            params = []
            if article_id:
                query += " AND article_id = ?"
                params.append(article_id)
            if stage:
                query += " AND stage = ?"
                params.append(stage)
            
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_pending_articles_for_eligibility(self, stage: str, reviewer_id: str) -> list:
        """Get articles that need eligibility evaluation at given stage."""
        with self.connect() as conn:
            cursor = conn.cursor()
            
            if stage == "EC":
                cursor.execute("""
                    SELECT a.* FROM articles a
                    WHERE a.review_id = ?
                    AND NOT EXISTS (
                        SELECT 1 FROM eligibility_decisions ed 
                        WHERE ed.article_id = a.id AND ed.stage = 'EC' AND ed.reviewer_id = ?
                    )
                """, (self.review_id, reviewer_id))
            else:
                cursor.execute("""
                    SELECT a.* FROM articles a
                    WHERE a.review_id = ?
                    AND EXISTS (
                        SELECT 1 FROM eligibility_decisions ed 
                        WHERE ed.article_id = a.id AND ed.stage = 'EC' AND ed.decision = 'include'
                    )
                    AND NOT EXISTS (
                        SELECT 1 FROM eligibility_decisions ed 
                        WHERE ed.article_id = a.id AND ed.stage = 'IC' AND ed.reviewer_id = ?
                    )
                """, (self.review_id, reviewer_id))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_ec_passed_articles(self) -> list:
        """Get articles that passed EC stage."""
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT a.* FROM articles a
                JOIN eligibility_decisions ed ON a.id = ed.article_id
                WHERE a.review_id = ? AND ed.stage = 'EC' AND ed.decision = 'include'
            """, (self.review_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_ic_passed_articles(self) -> list:
        """Get articles that passed both EC and IC stages."""
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT a.* FROM articles a
                WHERE a.review_id = ?
                AND EXISTS (
                    SELECT 1 FROM eligibility_decisions ed1 
                    WHERE ed1.article_id = a.id AND ed1.stage = 'EC' AND ed1.decision = 'include'
                )
                AND EXISTS (
                    SELECT 1 FROM eligibility_decisions ed2 
                    WHERE ed2.article_id = a.id AND ed2.stage = 'IC' AND ed2.decision = 'include'
                )
            """, (self.review_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def save_quality_assessment(self, article_id: int, reviewer_id: str, literature_type: str,
                                 criteria_scores: dict, total_score: float, decision: str,
                                 llm_rationale: dict = None, llm_confidence: float = None) -> int:
        with self.connect() as conn:
            cursor = conn.cursor()
            rationale_json = json.dumps(llm_rationale) if llm_rationale else None
            cursor.execute("""
                INSERT INTO quality_assessments 
                (article_id, reviewer_id, literature_type, criteria_scores, total_score, decision, llm_rationale, llm_confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (article_id, reviewer_id, literature_type, json.dumps(criteria_scores), total_score, decision, rationale_json, llm_confidence))
            return cursor.lastrowid
    
    def get_quality_assessment(self, article_id: int) -> Optional[dict]:
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM quality_assessments WHERE article_id = ? ORDER BY created_at DESC LIMIT 1
            """, (article_id,))
            row = cursor.fetchone()
            if row:
                result = dict(row)
                result['criteria_scores'] = json.loads(result['criteria_scores'])
                return result
            return None
    
    def get_quality_assessments_for_articles(self, article_ids: list) -> dict:
        if not article_ids:
            return {}
        with self.connect() as conn:
            placeholders = ','.join('?' * len(article_ids))
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT * FROM quality_assessments 
                WHERE article_id IN ({placeholders})
                ORDER BY article_id, created_at DESC
            """, article_ids)
            
            result = {}
            for row in cursor.fetchall():
                art_id = row['article_id']
                if art_id not in result:
                    result[art_id] = dict(row)
                    result[art_id]['criteria_scores'] = json.loads(result[art_id]['criteria_scores'])
            return result
    
    def get_stats(self) -> dict:
        with self.connect() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM articles WHERE review_id = ?", (self.review_id,))
            total_articles = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(DISTINCT article_id) FROM eligibility_decisions 
                WHERE stage = 'EC' AND decision = 'include'
            """)
            ec_passed = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(DISTINCT article_id) FROM eligibility_decisions 
                WHERE stage = 'EC' AND decision = 'exclude'
            """)
            ec_excluded = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(DISTINCT article_id) FROM eligibility_decisions 
                WHERE stage = 'IC' AND decision = 'include'
            """)
            ic_passed = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(DISTINCT article_id) FROM eligibility_decisions 
                WHERE stage = 'IC' AND decision = 'exclude'
            """)
            ic_excluded = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(*) FROM quality_assessments WHERE decision = 'include'
            """)
            qc_passed = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(*) FROM quality_assessments WHERE decision = 'exclude'
            """)
            qc_failed = cursor.fetchone()[0]
            
            return {
                "total_articles": total_articles,
                "ec_passed": ec_passed,
                "ec_excluded": ec_excluded,
                "ic_passed": ic_passed,
                "ic_excluded": ic_excluded,
                "qc_passed": qc_passed,
                "qc_failed": qc_failed
            }
    
    def get_config(self, key: str):
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT {key} FROM project_config WHERE id = 1")
            row = cursor.fetchone()
            if row:
                value = row[0]
                if key in ['wl_criteria', 'gl_criteria']:
                    return json.loads(value)
                return value
            return None
    
    def set_config(self, key: str, value):
        with self.connect() as conn:
            cursor = conn.cursor()
            if isinstance(value, (list, dict)):
                value = json.dumps(value)
            cursor.execute(f"UPDATE project_config SET {key} = ? WHERE id = 1", (value,))
    
    def export_eligibility_results(self) -> pd.DataFrame:
        with self.connect() as conn:
            query = """
                SELECT 
                    a.id, a.title, a.authors, a.year, a.literature_type,
                    ec.decision as ec_decision, ec.reason as ec_reason,
                    ic.decision as ic_decision, ic.reason as ic_reason
                FROM articles a
                LEFT JOIN eligibility_decisions ec ON a.id = ec.article_id AND ec.stage = 'EC'
                LEFT JOIN eligibility_decisions ic ON a.id = ic.article_id AND ic.stage = 'IC'
                WHERE a.review_id = ?
            """
            return pd.read_sql_query(query, conn, params=(self.review_id,))
    
    def export_quality_results(self) -> pd.DataFrame:
        with self.connect() as conn:
            query = """
                SELECT 
                    a.id, a.title, a.authors, a.year, a.literature_type,
                    qa.literature_type as assessed_type,
                    qa.criteria_scores, qa.total_score, qa.decision as qc_decision
                FROM quality_assessments qa
                JOIN articles a ON qa.article_id = a.id
                WHERE a.review_id = ?
                ORDER BY qa.article_id, qa.created_at DESC
            """
            return pd.read_sql_query(query, conn, params=(self.review_id,))
    
    def get_article_rationale(self, article_id: int) -> dict:
        """Get all LLM rationales for an article across EC, IC, QC stages."""
        with self.connect() as conn:
            result = {"article_id": article_id, "stages": {}}
            
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT stage, decision, reason, llm_rationale, llm_confidence
                FROM eligibility_decisions WHERE article_id = ? ORDER BY stage
            """, (article_id,))
            for row in cursor.fetchall():
                rationale = row["llm_rationale"]
                result["stages"][row["stage"]] = {
                    "decision": row["decision"],
                    "reason": row["reason"],
                    "rationale": json.loads(rationale) if rationale else None,
                    "confidence": row["llm_confidence"]
                }
            
            cursor.execute("""
                SELECT literature_type, criteria_scores, total_score, decision, llm_rationale, llm_confidence
                FROM quality_assessments WHERE article_id = ? ORDER BY created_at DESC LIMIT 1
            """, (article_id,))
            qa = cursor.fetchone()
            if qa:
                rationale = qa["llm_rationale"]
                result["stages"]["QC"] = {
                    "literature_type": qa["literature_type"],
                    "criteria_scores": json.loads(qa["criteria_scores"]) if qa["criteria_scores"] else {},
                    "total_score": qa["total_score"],
                    "decision": qa["decision"],
                    "rationale": json.loads(rationale) if rationale else None,
                    "confidence": qa["llm_confidence"]
                }
            
            return result