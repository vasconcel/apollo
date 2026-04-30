import sqlite3
import json
from contextlib import contextmanager
from typing import Optional


class DatabaseError(Exception):
    """Custom exception for database validation errors."""
    pass


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
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # =============================
    # VALIDATION LAYER
    # =============================
    def _validate_rq_code(self, rq_code: str) -> None:
        valid_rq_codes = {'RQ1', 'RQ2', 'RQ3', 'RQ4', 'RQ5'}
        if not rq_code or rq_code.upper() not in valid_rq_codes:
            raise DatabaseError(f"Invalid rq_code '{rq_code}'. Must be one of {valid_rq_codes}")

    def _validate_not_empty(self, value: str, field_name: str) -> None:
        if not value or not value.strip():
            raise DatabaseError(f"{field_name} cannot be empty")

    def _validate_article_exists(self, conn, article_id: int) -> None:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM articles WHERE id = ?", (article_id,))
        if not cursor.fetchone():
            raise DatabaseError(f"Article with id {article_id} does not exist")

    def _validate_fragment_exists(self, conn, fragment_id: int) -> None:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM fragments WHERE id = ?", (fragment_id,))
        if not cursor.fetchone():
            raise DatabaseError(f"Fragment with id {fragment_id} does not exist")

    def _validate_code_exists(self, conn, code_id: int) -> None:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM codes WHERE id = ?", (code_id,))
        if not cursor.fetchone():
            raise DatabaseError(f"Code with id {code_id} does not exist")

    def _validate_theme_exists(self, conn, theme_id: int) -> None:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM themes WHERE id = ?", (theme_id,))
        if not cursor.fetchone():
            raise DatabaseError(f"Theme with id {theme_id} does not exist")

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
            # FRAGMENT-LEVEL EXTRACTION (Section 3.2.1)
            # =============================
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS fragments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER NOT NULL,
                rq_code TEXT NOT NULL,
                fragment_text TEXT NOT NULL,
                theme_category TEXT,
                reviewer_id TEXT NOT NULL,
                page_or_section TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (article_id) REFERENCES articles(id)
            )
            """)

            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_fragments_rq ON fragments(rq_code)
            """)
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_fragments_article ON fragments(article_id)
            """)
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_fragments_rq_article ON fragments(rq_code, article_id)
            """)

            # =============================
            # THEMATIC CODING LAYER (Section 3.3)
            # =============================
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code_label TEXT NOT NULL,
                code_description TEXT,
                rq_code TEXT NOT NULL,
                reviewer_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(code_label, rq_code)
            )
            """)
            
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_codes_rq ON codes(rq_code)
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS fragment_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fragment_id INTEGER NOT NULL,
                code_id INTEGER NOT NULL,
                reviewer_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (fragment_id) REFERENCES fragments(id),
                FOREIGN KEY (code_id) REFERENCES codes(id),
                UNIQUE(fragment_id, code_id)
            )
            """)

            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_fragment_codes_fragment ON fragment_codes(fragment_id)
            """)
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_fragment_codes_code ON fragment_codes(code_id)
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS themes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                theme_code TEXT NOT NULL,
                theme_label TEXT NOT NULL,
                theme_description TEXT,
                rq_code TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(theme_code)
            )
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS code_themes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code_id INTEGER NOT NULL,
                theme_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (code_id) REFERENCES codes(id),
                FOREIGN KEY (theme_id) REFERENCES themes(id),
                UNIQUE(code_id, theme_id)
            )
            """)

            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_code_themes_code ON code_themes(code_id)
            """)
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_code_themes_theme ON code_themes(theme_id)
            """)

            # =============================
            # AUDIT TRAIL - CODING EVENTS
            # =============================
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS coding_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL CHECK(event_type IN ('code_added', 'code_removed', 'fragment_linked', 'fragment_unlinked', 'theme_linked', 'theme_unlinked')),
                fragment_id INTEGER,
                code_id INTEGER,
                theme_id INTEGER,
                reviewer_id TEXT NOT NULL,
                event_metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_coding_events_fragment ON coding_events(fragment_id)
            """)
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_coding_events_code ON coding_events(code_id)
            """)
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_coding_events_theme ON coding_events(theme_id)
            """)

    # =============================
    # BACKWARD COMPATIBILITY - EXISTING METHODS
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

    def count_articles(self):
        with self.connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    
    def add_article(self, article_data: dict) -> int:
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO articles (title, authors, year, abstract, doi, url, source, literature_type, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'imported')
            """, (
                article_data.get("title", ""),
                article_data.get("authors", ""),
                article_data.get("year"),
                article_data.get("abstract", ""),
                article_data.get("doi", ""),
                article_data.get("url", ""),
                article_data.get("source", ""),
                article_data.get("literature_type", "WL")
            ))
            conn.commit()
            return cursor.lastrowid
    
    def get_articles_included(self, limit: int = 100):
        with self.connect() as conn:
            return pd.read_sql_query(f"""
            SELECT id, title, authors, doi, year 
            FROM articles a
            INNER JOIN final_decisions fd ON a.id = fd.article_id
            WHERE fd.final_decision = 'include'
            ORDER BY a.year DESC
            LIMIT {limit}
            """, conn)
    
    def get_article_by_id(self, article_id: int):
        with self.connect() as conn:
            return pd.read_sql_query("""
            SELECT * FROM articles WHERE id = ?
            """, conn, params=(article_id,)).iloc[0].to_dict() if article_id else None

    def count_screened(self):
        with self.connect() as conn:
            return conn.execute("""
            SELECT COUNT(DISTINCT article_id) FROM screening_decisions
            """).fetchone()[0]

    # =============================
    # FRAGMENT EXTRACTION (Section 3.2.1)
    # =============================

    def insert_fragment(self, article_id: int, rq_code: str, fragment_text: str,
                        reviewer_id: str, theme_category: str = None, page_or_section: str = None) -> int:
        self._validate_not_empty(rq_code, "rq_code")
        self._validate_not_empty(fragment_text, "fragment_text")
        self._validate_not_empty(reviewer_id, "reviewer_id")
        
        rq_code = rq_code.upper()
        self._validate_rq_code(rq_code)

        with self.connect() as conn:
            self._validate_article_exists(conn, article_id)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO fragments (article_id, rq_code, fragment_text, theme_category, reviewer_id, page_or_section)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (article_id, rq_code, fragment_text, theme_category, reviewer_id, page_or_section))
            return cursor.lastrowid

    def get_fragments_by_rq(self, rq_code: str):
        rq_code = rq_code.upper()
        self._validate_rq_code(rq_code)
        with self.connect() as conn:
            return conn.execute("""
                SELECT f.*, a.title as article_title, a.literature_type
                FROM fragments f
                JOIN articles a ON f.article_id = a.id
                WHERE f.rq_code = ?
                ORDER BY f.created_at
            """, (rq_code,)).fetchall()

    def get_fragments_by_article(self, article_id: int):
        with self.connect() as conn:
            return conn.execute("""
                SELECT * FROM fragments
                WHERE article_id = ?
                ORDER BY rq_code
            """, (article_id,)).fetchall()

    def get_all_fragments_with_sources(self):
        with self.connect() as conn:
            return conn.execute("""
                SELECT f.id, f.fragment_text, f.rq_code, f.theme_category,
                       a.id as source_id, a.title as source_title, a.literature_type
                FROM fragments f
                JOIN articles a ON f.article_id = a.id
                ORDER BY f.rq_code, a.id
            """).fetchall()

    # =============================
    # THEMATIC CODING - CODES
    # =============================

    def create_code(self, code_label: str, rq_code: str, reviewer_id: str, code_description: str = None) -> int:
        self._validate_not_empty(code_label, "code_label")
        self._validate_not_empty(rq_code, "rq_code")
        self._validate_not_empty(reviewer_id, "reviewer_id")
        
        rq_code = rq_code.upper()
        self._validate_rq_code(rq_code)

        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO codes (code_label, rq_code, reviewer_id, code_description)
                VALUES (?, ?, ?, ?)
            """, (code_label, rq_code, reviewer_id, code_description))
            if cursor.lastrowid == 0:
                cursor.execute("SELECT id FROM codes WHERE code_label = ? AND rq_code = ?", (code_label, rq_code))
                return cursor.fetchone()[0]
            return cursor.lastrowid

    def get_codes_by_rq(self, rq_code: str):
        rq_code = rq_code.upper()
        self._validate_rq_code(rq_code)
        with self.connect() as conn:
            return conn.execute("""
                SELECT * FROM codes WHERE rq_code = ?
            """, (rq_code,)).fetchall()

    def link_fragment_code(self, fragment_id: int, code_id: int, reviewer_id: str = "system"):
        with self.connect() as conn:
            self._validate_fragment_exists(conn, fragment_id)
            self._validate_code_exists(conn, code_id)
            conn.execute("""
                INSERT OR IGNORE INTO fragment_codes (fragment_id, code_id, reviewer_id)
                VALUES (?, ?, ?)
            """, (fragment_id, code_id, reviewer_id))
            
            # Log audit event
            conn.execute("""
                INSERT INTO coding_events (event_type, fragment_id, code_id, reviewer_id)
                VALUES ('fragment_linked', ?, ?, ?)
            """, (fragment_id, code_id, reviewer_id))

    def get_codes_for_fragment(self, fragment_id: int):
        with self.connect() as conn:
            return conn.execute("""
                SELECT c.* FROM codes c
                JOIN fragment_codes fc ON c.id = fc.code_id
                WHERE fc.fragment_id = ?
            """, (fragment_id,)).fetchall()

    def get_fragments_for_code(self, code_id: int):
        with self.connect() as conn:
            return conn.execute("""
                SELECT f.*, a.title as article_title, a.literature_type
                FROM fragments f
                JOIN fragment_codes fc ON f.id = fc.fragment_id
                JOIN articles a ON f.article_id = a.id
                WHERE fc.code_id = ?
            """, (code_id,)).fetchall()

    # =============================
    # THEMATIC CODING - THEMES
    # =============================

    def create_theme(self, theme_code: str, theme_label: str, rq_code: str, theme_description: str = None) -> int:
        self._validate_not_empty(theme_code, "theme_code")
        self._validate_not_empty(theme_label, "theme_label")
        self._validate_not_empty(rq_code, "rq_code")
        
        rq_code = rq_code.upper()
        self._validate_rq_code(rq_code)

        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO themes (theme_code, theme_label, rq_code, theme_description)
                VALUES (?, ?, ?, ?)
            """, (theme_code, theme_label, rq_code, theme_description))
            if cursor.lastrowid == 0:
                cursor.execute("SELECT id FROM themes WHERE theme_code = ?", (theme_code,))
                return cursor.fetchone()[0]
            return cursor.lastrowid

    def get_themes_by_rq(self, rq_code: str):
        rq_code = rq_code.upper()
        self._validate_rq_code(rq_code)
        with self.connect() as conn:
            return conn.execute("""
                SELECT * FROM themes WHERE rq_code = ?
            """, (rq_code,)).fetchall()

    def link_code_theme(self, code_id: int, theme_id: int, reviewer_id: str = "system"):
        with self.connect() as conn:
            self._validate_code_exists(conn, code_id)
            self._validate_theme_exists(conn, theme_id)
            conn.execute("""
                INSERT OR IGNORE INTO code_themes (code_id, theme_id)
                VALUES (?, ?)
            """, (code_id, theme_id))
            
            # Log audit event
            conn.execute("""
                INSERT INTO coding_events (event_type, code_id, theme_id, reviewer_id)
                VALUES ('theme_linked', ?, ?, ?)
            """, (code_id, theme_id, reviewer_id))

    def get_themes_for_code(self, code_id: int):
        with self.connect() as conn:
            return conn.execute("""
                SELECT t.* FROM themes t
                JOIN code_themes ct ON t.id = ct.theme_id
                WHERE ct.code_id = ?
            """, (code_id,)).fetchall()

    def get_codes_for_theme(self, theme_id: int):
        with self.connect() as conn:
            return conn.execute("""
                SELECT c.* FROM codes c
                JOIN code_themes ct ON c.id = ct.code_id
                WHERE ct.theme_id = ?
            """, (theme_id,)).fetchall()

    # =============================
    # TRACEABILITY QUERIES
    # =============================

    def get_theme_fragments_with_sources(self, theme_id: int):
        with self.connect() as conn:
            self._validate_theme_exists(conn, theme_id)
            return conn.execute("""
                SELECT f.fragment_text, f.rq_code, a.id as source_id, a.title as source_title,
                       a.literature_type, t.theme_code, t.theme_label
                FROM fragments f
                JOIN fragment_codes fc ON f.id = fc.fragment_id
                JOIN codes c ON fc.code_id = c.id
                JOIN code_themes ct ON c.id = ct.code_id
                JOIN themes t ON ct.theme_id = t.id
                JOIN articles a ON f.article_id = a.id
                WHERE t.id = ?
                ORDER BY a.literature_type, a.id
            """, (theme_id,)).fetchall()

    def compare_theme_by_literature_type(self, theme_id: int):
        with self.connect() as conn:
            self._validate_theme_exists(conn, theme_id)
            return conn.execute("""
                SELECT a.literature_type, COUNT(DISTINCT f.id) as fragment_count,
                       COUNT(DISTINCT a.id) as source_count
                FROM fragments f
                JOIN fragment_codes fc ON f.id = fc.fragment_id
                JOIN codes c ON fc.code_id = c.id
                JOIN code_themes ct ON c.id = ct.code_id
                JOIN articles a ON f.article_id = a.id
                WHERE ct.theme_id = ?
                GROUP BY a.literature_type
            """, (theme_id,)).fetchall()

    # =============================
    # INTEGRATION HOOK FOR PIPELINE
    # =============================

    def get_included_articles_for_extraction(self):
        """Returns articles that have passed screening and QC - ready for extraction."""
        with self.connect() as conn:
            return conn.execute("""
                SELECT a.id, a.title, a.abstract, a.literature_type
                FROM articles a
                JOIN final_decisions f ON a.id = f.article_id
                WHERE f.final_decision = 'include'
                AND NOT EXISTS (
                    SELECT 1 FROM quality_assessments q
                    WHERE q.article_id = a.id AND q.decision = 'exclude'
                )
            """).fetchall()

    def get_articles_ready_for_extraction(self):
        """Alias for backward compatibility."""
        return self.get_included_articles_for_extraction()

    # =============================
    # TRACEABILITY INVARIANT VALIDATION
    # =============================

    def validate_traceability_integrity(self) -> dict:
        """
        Diagnostic tool to check traceability integrity.
        Returns a structured report of potential issues.
        
        Does NOT enforce constraints - only identifies potential problems.
        
        Returns:
            dict with keys:
                - fragments_without_codes: list of fragment IDs
                - codes_without_fragments: list of code IDs  
                - themes_without_codes: list of theme IDs
        """
        report = {
            "fragments_without_codes": [],
            "codes_without_fragments": [],
            "themes_without_codes": []
        }
        
        with self.connect() as conn:
            # 1. Find fragments without any codes linked
            cursor = conn.execute("""
                SELECT f.id, f.fragment_text, f.rq_code, a.title as article_title
                FROM fragments f
                JOIN articles a ON f.article_id = a.id
                WHERE f.id NOT IN (
                    SELECT DISTINCT fragment_id FROM fragment_codes
                )
            """)
            report["fragments_without_codes"] = [
                {
                    "fragment_id": row[0],
                    "fragment_text": row[1][:100] + "..." if len(row[1]) > 100 else row[1],
                    "rq_code": row[2],
                    "article_title": row[3]
                }
                for row in cursor.fetchall()
            ]
            
            # 2. Find codes not linked to any fragment
            cursor = conn.execute("""
                SELECT c.id, c.code_label, c.rq_code
                FROM codes c
                WHERE c.id NOT IN (
                    SELECT DISTINCT code_id FROM fragment_codes
                )
            """)
            report["codes_without_fragments"] = [
                {
                    "code_id": row[0],
                    "code_label": row[1],
                    "rq_code": row[2]
                }
                for row in cursor.fetchall()
            ]
            
            # 3. Find themes not linked to any code
            cursor = conn.execute("""
                SELECT t.id, t.theme_code, t.theme_label, t.rq_code
                FROM themes t
                WHERE t.id NOT IN (
                    SELECT DISTINCT theme_id FROM code_themes
                )
            """)
            report["themes_without_codes"] = [
                {
                    "theme_id": row[0],
                    "theme_code": row[1],
                    "theme_label": row[2],
                    "rq_code": row[3]
                }
                for row in cursor.fetchall()
            ]
        
        return report

    def print_traceability_report(self) -> None:
        """
        Print a formatted traceability report to stdout.
        Useful for CLI debugging and quick diagnostics.
        """
        print("\n" + "="*60)
        print("  TRACEABILITY INTEGRITY REPORT")
        print("="*60)
        
        report = self.validate_traceability_integrity()
        
        # Fragments without codes
        print("\n[1] Fragments without codes:")
        if report["fragments_without_codes"]:
            for item in report["fragments_without_codes"]:
                print(f"  - Fragment ID {item['fragment_id']} | RQ: {item['rq_code']}")
                print(f"    Article: {item['article_title'][:50]}...")
                print(f"    Text: {item['fragment_text'][:80]}...")
        else:
            print("  [OK] All fragments have at least one code")
        
        # Codes without fragments
        print("\n[2] Codes without fragments:")
        if report["codes_without_fragments"]:
            for item in report["codes_without_fragments"]:
                print(f"  - Code ID {item['code_id']} | Label: {item['code_label']} | RQ: {item['rq_code']}")
        else:
            print("  [OK] All codes are linked to at least one fragment")
        
        # Themes without codes
        print("\n[3] Themes without codes:")
        if report["themes_without_codes"]:
            for item in report["themes_without_codes"]:
                print(f"  - Theme ID {item['theme_id']} | Code: {item['theme_code']} | Label: {item['theme_label']} | RQ: {item['rq_code']}")
        else:
            print("  [OK] All themes have at least one code")
        
        # Summary
        total_issues = (
            len(report["fragments_without_codes"]) +
            len(report["codes_without_fragments"]) +
            len(report["themes_without_codes"])
        )
        
        print("\n" + "-"*60)
        if total_issues == 0:
            print("  RESULT: All traceability invariants satisfied")
        else:
            print(f"  RESULT: {total_issues} traceability issue(s) found")
        print("="*60 + "\n")

    # =============================
    # RESEARCH EXPORTS
    # =============================

    def export_traceability_matrix(self, path: str) -> int:
        """
        Export the full traceability matrix as CSV.
        
        Joins: fragments -> fragment_codes -> codes -> code_themes -> themes -> articles
        Only includes fully linked data (fragments connected through the full chain).
        
        Args:
            path: Output CSV file path
            
        Returns:
            Number of rows exported
        """
        import pandas as pd
        
        with self.connect() as conn:
            df = pd.read_sql_query("""
                SELECT 
                    f.rq_code,
                    t.theme_code,
                    t.theme_label,
                    c.code_label,
                    f.id as fragment_id,
                    f.fragment_text,
                    a.id as source_id,
                    a.title as source_title,
                    a.literature_type
                FROM fragments f
                JOIN fragment_codes fc ON f.id = fc.fragment_id
                JOIN codes c ON fc.code_id = c.id
                JOIN code_themes ct ON c.id = ct.code_id
                JOIN themes t ON ct.theme_id = t.id
                JOIN articles a ON f.article_id = a.id
                ORDER BY f.rq_code, t.theme_code, a.id
            """, conn)
        
        df.to_csv(path, index=False, encoding='utf-8-sig')
        return len(df)

    def export_fragments_with_sources(self, path: str) -> int:
        """
        Export all fragments with source article information.
        
        Args:
            path: Output CSV file path
            
        Returns:
            Number of rows exported
        """
        import pandas as pd
        
        with self.connect() as conn:
            df = pd.read_sql_query("""
                SELECT 
                    f.id as fragment_id,
                    f.rq_code,
                    f.fragment_text,
                    f.theme_category,
                    f.page_or_section,
                    a.id as source_id,
                    a.title as source_title,
                    a.literature_type,
                    f.reviewer_id as extracted_by,
                    f.created_at as extracted_at
                FROM fragments f
                JOIN articles a ON f.article_id = a.id
                ORDER BY f.rq_code, a.id
            """, conn)
        
        df.to_csv(path, index=False, encoding='utf-8-sig')
        return len(df)

    def export_codes(self, path: str) -> int:
        """
        Export all codes with their RQ associations.
        
        Args:
            path: Output CSV file path
            
        Returns:
            Number of rows exported
        """
        import pandas as pd
        
        with self.connect() as conn:
            df = pd.read_sql_query("""
                SELECT 
                    c.id as code_id,
                    c.code_label,
                    c.code_description,
                    c.rq_code,
                    c.reviewer_id as created_by,
                    c.created_at
                FROM codes c
                ORDER BY c.rq_code, c.code_label
            """, conn)
        
        df.to_csv(path, index=False, encoding='utf-8-sig')
        return len(df)

    def export_themes(self, path: str) -> int:
        """
        Export all themes with their RQ associations.
        
        Args:
            path: Output CSV file path
            
        Returns:
            Number of rows exported
        """
        import pandas as pd
        
        with self.connect() as conn:
            df = pd.read_sql_query("""
                SELECT 
                    t.id as theme_id,
                    t.theme_code,
                    t.theme_label,
                    t.theme_description,
                    t.rq_code,
                    t.created_at
                FROM themes t
                ORDER BY t.rq_code, t.theme_code
            """, conn)
        
        df.to_csv(path, index=False, encoding='utf-8-sig')
        return len(df)

    def export_all_research_artifacts(self, base_path: str) -> dict:
        """
        Export all research artifacts to CSV files.
        
        Generates:
            - traceability_matrix.csv (full chain)
            - fragments_with_sources.csv (all fragments)
            - codes.csv (all codes)
            - themes.csv (all themes)
        
        Args:
            base_path: Directory path for output files
            
        Returns:
            dict with export counts for each file
        """
        import os
        
        # Ensure directory exists
        os.makedirs(base_path, exist_ok=True)
        
        counts = {}
        
        # Export each artifact
        counts['traceability_matrix'] = self.export_traceability_matrix(
            os.path.join(base_path, 'traceability_matrix.csv')
        )
        counts['fragments_with_sources'] = self.export_fragments_with_sources(
            os.path.join(base_path, 'fragments_with_sources.csv')
        )
        counts['codes'] = self.export_codes(
            os.path.join(base_path, 'codes.csv')
        )
        counts['themes'] = self.export_themes(
            os.path.join(base_path, 'themes.csv')
        )
        
        return counts