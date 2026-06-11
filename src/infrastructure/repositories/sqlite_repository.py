import json
import os
import random
import sqlite3
from typing import Any, Optional

from src.domain.enums import CriterionType, ScreeningStatus
from src.domain.interfaces import ScreeningDecisionRepository
from src.domain.models import Criterion, Paper, ScreeningDecision

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS screening_decisions (
    paper_id            TEXT PRIMARY KEY,
    status              TEXT    NOT NULL,
    confidence_score    REAL    NOT NULL,
    rationale           TEXT    NOT NULL,
    applied_criteria_codes TEXT NOT NULL,
    is_calibration      INTEGER DEFAULT 0,
    gl_q1               REAL,
    gl_q2               REAL,
    gl_q3               REAL,
    gl_q4               REAL,
    wl_q1               REAL,
    wl_q2               REAL,
    wl_q3               REAL,
    wl_q4               REAL,
    quality_score       REAL,
    wl_quality_score    REAL,
    full_text           TEXT,
    pdf_url             TEXT
)
"""

_INSERT_OR_REPLACE = """
INSERT OR REPLACE INTO screening_decisions
    (paper_id, status, confidence_score, rationale, applied_criteria_codes, is_calibration,
     gl_q1, gl_q2, gl_q3, gl_q4, quality_score,
     wl_q1, wl_q2, wl_q3, wl_q4, wl_quality_score,
     full_text, pdf_url)
VALUES
    (?, ?, ?, ?, ?,
     COALESCE((SELECT is_calibration FROM screening_decisions WHERE paper_id = ?), 0),
     COALESCE((SELECT gl_q1 FROM screening_decisions WHERE paper_id = ?), NULL),
     COALESCE((SELECT gl_q2 FROM screening_decisions WHERE paper_id = ?), NULL),
     COALESCE((SELECT gl_q3 FROM screening_decisions WHERE paper_id = ?), NULL),
     COALESCE((SELECT gl_q4 FROM screening_decisions WHERE paper_id = ?), NULL),
     COALESCE((SELECT quality_score FROM screening_decisions WHERE paper_id = ?), NULL),
     COALESCE((SELECT wl_q1 FROM screening_decisions WHERE paper_id = ?), NULL),
     COALESCE((SELECT wl_q2 FROM screening_decisions WHERE paper_id = ?), NULL),
     COALESCE((SELECT wl_q3 FROM screening_decisions WHERE paper_id = ?), NULL),
     COALESCE((SELECT wl_q4 FROM screening_decisions WHERE paper_id = ?), NULL),
     COALESCE((SELECT wl_quality_score FROM screening_decisions WHERE paper_id = ?), NULL),
     COALESCE((SELECT full_text FROM screening_decisions WHERE paper_id = ?), NULL),
     COALESCE((SELECT pdf_url FROM screening_decisions WHERE paper_id = ?), NULL))
"""

_SELECT_BY_ID = """
SELECT paper_id, status, confidence_score, rationale, applied_criteria_codes
FROM screening_decisions
WHERE paper_id = ?
"""

_SELECT_ALL = """
SELECT paper_id, status, confidence_score, rationale, applied_criteria_codes
FROM screening_decisions
ORDER BY paper_id
"""

_UPDATE_AUDIT = """
UPDATE screening_decisions
SET human_decision = ?, is_audited = 1
WHERE paper_id = ?
"""

_UPDATE_GL_QA = """
UPDATE screening_decisions
SET gl_q1 = ?, gl_q2 = ?, gl_q3 = ?, gl_q4 = ?, quality_score = ?
WHERE paper_id = ?
"""

_UPDATE_WL_QA = """
UPDATE screening_decisions
SET wl_q1 = ?, wl_q2 = ?, wl_q3 = ?, wl_q4 = ?, wl_quality_score = ?
WHERE paper_id = ?
"""

_SELECT_AUDITED = """
SELECT paper_id, status, human_decision, rationale, applied_criteria_codes
FROM screening_decisions
WHERE is_audited = 1
"""

_SELECT_AUDITED_CALIBRATION = """
SELECT paper_id, status, human_decision, rationale, applied_criteria_codes
FROM screening_decisions
WHERE is_audited = 1 AND is_calibration = 1
"""

_CREATE_CRITERIA_TABLE = """
CREATE TABLE IF NOT EXISTS criteria (
    id              VARCHAR(10) PRIMARY KEY,
    title           VARCHAR(255) NOT NULL,
    description     TEXT        NOT NULL,
    type            VARCHAR(10) NOT NULL,
    is_heuristic    INTEGER     DEFAULT 0
)
"""

_CREATE_SETTINGS_TABLE = """
CREATE TABLE IF NOT EXISTS system_settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
)
"""

_SELECT_ALL_CRITERIA = """
SELECT id, title, description, type, is_heuristic
FROM criteria
ORDER BY id
"""

_UPDATE_CRITERION = """
UPDATE criteria SET title = ?, description = ? WHERE id = ?
"""

_SEED_CRITERIA: list[dict[str, Any]] = [
    {"id": "EC1", "title": "Language Check", "type": "EXCLUSION", "is_heuristic": 1, "description": "The paper is not written in English."},
    {"id": "EC2", "title": "Availability", "type": "EXCLUSION", "is_heuristic": 0, "description": "The full text of the publication is not available."},
    {"id": "EC3", "title": "Length Check", "type": "EXCLUSION", "is_heuristic": 1, "description": "The paper is a short publication (under 3 pages), editorial, tutorial, or keynote abstract."},
    {"id": "EC4", "title": "Year of Publication", "type": "EXCLUSION", "is_heuristic": 1, "description": "The paper was published before the year 2015."},
    {"id": "EC5", "title": "Relevance to SE R&S", "type": "EXCLUSION", "is_heuristic": 0, "description": "The paper does not explicitly discuss Recruitment & Selection processes, pipelines, challenges, or practices for Software Engineering roles. Remember: Technical tool evaluations like Code Reviews, Pull Request concurrent edits, UI Usability reviews, Peer Programming reviews, or Software Project Management tools must be EXCLUDED under EC5 unless they explicitly evaluate or target the hiring/recruitment of candidates."},
    {"id": "EC6", "title": "Deduplication", "type": "EXCLUSION", "is_heuristic": 1, "description": "The paper is an exact or near-duplicate of an already screened study."},
    {"id": "IC1", "title": "R&S Pipeline Phases", "type": "INCLUSION", "is_heuristic": 0, "description": "The paper addresses recruitment and selection stages such as sourcing, screening, technical evaluation, interviewing, onboarding, or final hiring decisions."},
    {"id": "IC2", "title": "R&S Procedures", "type": "INCLUSION", "is_heuristic": 0, "description": "The paper describes specific practices, mechanisms, workflows, or platforms used by organizations during hiring."},
    {"id": "IC3", "title": "R&S Challenges", "type": "INCLUSION", "is_heuristic": 0, "description": "The paper discusses key pain points, bottlenecks, biases, diversity hurdles, or evaluation difficulties in technical hiring."},
    {"id": "IC4", "title": "Empirical Evidence", "type": "INCLUSION", "is_heuristic": 0, "description": "The study provides empirical findings, metrics, statistical data, or case studies on technical hiring outcomes."},
    {"id": "IC5", "title": "Experience Report", "type": "INCLUSION", "is_heuristic": 0, "description": "The study reports practitioner experiences, recruiter surveys, candidate perceptions, or organizational retrospectives on SE hiring."},
]


def _seed_criteria_if_empty(conn: sqlite3.Connection) -> None:
    cursor = conn.execute("SELECT COUNT(*) AS cnt FROM criteria")
    row = cursor.fetchone()
    if row["cnt"] > 0:
        return
    for c in _SEED_CRITERIA:
        conn.execute(
            "INSERT INTO criteria (id, title, description, type, is_heuristic) "
            "VALUES (?, ?, ?, ?, ?)",
            (c["id"], c["title"], c["description"], c["type"], c["is_heuristic"]),
        )
    conn.commit()


def _seed_settings_if_empty(conn: sqlite3.Connection) -> None:
    cursor = conn.execute("SELECT COUNT(*) AS cnt FROM system_settings")
    row = cursor.fetchone()
    if row["cnt"] > 0:
        return
    defaults: list[tuple[str, str]] = [
        ("llm_provider", "ollama"),
        ("llm_base_url", os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")),
        ("llm_model", os.getenv("OLLAMA_MODEL", "qwen2.5:3b-instruct")),
        ("llm_api_key", ""),
        ("llm_delay", "0.0"),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO system_settings (key, value) VALUES (?, ?)",
        defaults,
    )
    conn.commit()


def _row_to_decision(row: tuple) -> ScreeningDecision:
    paper_id, status_str, confidence, rationale, codes_json = row
    return ScreeningDecision(
        paper_id=paper_id,
        status=ScreeningStatus(status_str),
        confidence_score=float(confidence),
        rationale=rationale,
        applied_criteria_codes=list(json.loads(codes_json)),
    )


def _migrate_audit_columns(conn: sqlite3.Connection) -> None:
    for col in ("human_decision", "is_audited"):
        try:
            conn.execute(
                f"ALTER TABLE screening_decisions ADD COLUMN {col} "
                f"{'INTEGER DEFAULT 0' if col == 'is_audited' else 'TEXT DEFAULT NULL'}"
            )
        except sqlite3.OperationalError:
            pass
    conn.commit()


def _migrate_calibration_column(conn: sqlite3.Connection) -> None:
    try:
        conn.execute(
            "ALTER TABLE screening_decisions ADD COLUMN is_calibration INTEGER DEFAULT 0"
        )
    except sqlite3.OperationalError:
        pass
    conn.commit()


def _migrate_qa_columns(conn: sqlite3.Connection) -> None:
    for col in ("gl_q1", "gl_q2", "gl_q3", "gl_q4", "quality_score"):
        try:
            conn.execute(f"ALTER TABLE screening_decisions ADD COLUMN {col} REAL")
        except sqlite3.OperationalError:
            pass
    conn.commit()


def _migrate_wl_qa_columns(conn: sqlite3.Connection) -> None:
    for col in ("wl_q1", "wl_q2", "wl_q3", "wl_q4", "wl_quality_score"):
        try:
            conn.execute(f"ALTER TABLE screening_decisions ADD COLUMN {col} REAL")
        except sqlite3.OperationalError:
            pass
    conn.commit()


def _migrate_pdf_columns(conn: sqlite3.Connection) -> None:
    for col in ("full_text", "pdf_url"):
        try:
            conn.execute(f"ALTER TABLE screening_decisions ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass
    conn.commit()


def _migrate_title_abstract_columns(conn: sqlite3.Connection) -> None:
    for col in ("title", "abstract"):
        try:
            conn.execute(f"ALTER TABLE screening_decisions ADD COLUMN {col} TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass
    conn.commit()


class SQLiteScreeningDecisionRepository(ScreeningDecisionRepository):
    def __init__(self, db_path: str = "screening.db") -> None:
        self._db_path = str(db_path)
        self._conn = sqlite3.connect(self._db_path)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA busy_timeout=5000;")
        self._in_batch = False
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(_CREATE_TABLE)
        self._conn.execute(_CREATE_CRITERIA_TABLE)
        self._conn.execute(_CREATE_SETTINGS_TABLE)
        _seed_criteria_if_empty(self._conn)
        _seed_settings_if_empty(self._conn)
        _migrate_audit_columns(self._conn)
        _migrate_calibration_column(self._conn)
        _migrate_qa_columns(self._conn)
        _migrate_wl_qa_columns(self._conn)
        _migrate_pdf_columns(self._conn)
        _migrate_title_abstract_columns(self._conn)

    def save_decision(self, decision: ScreeningDecision, title: str = "", abstract: str = "") -> None:
        codes_json = json.dumps(decision.applied_criteria_codes, ensure_ascii=False)
        self._conn.execute(
            _INSERT_OR_REPLACE,
            (
                decision.paper_id,
                decision.status.value,
                decision.confidence_score,
                decision.rationale,
                codes_json,
                decision.paper_id,  # is_calibration COALESCE
                decision.paper_id,  # gl_q1 COALESCE
                decision.paper_id,  # gl_q2 COALESCE
                decision.paper_id,  # gl_q3 COALESCE
                decision.paper_id,  # gl_q4 COALESCE
                decision.paper_id,  # quality_score COALESCE
                decision.paper_id,  # wl_q1 COALESCE
                decision.paper_id,  # wl_q2 COALESCE
                decision.paper_id,  # wl_q3 COALESCE
                decision.paper_id,  # wl_q4 COALESCE
                decision.paper_id,  # wl_quality_score COALESCE
                decision.paper_id,  # full_text COALESCE
                decision.paper_id,  # pdf_url COALESCE
            ),
        )
        if title or abstract:
            self._conn.execute(
                "UPDATE screening_decisions SET title = ?, abstract = ? WHERE paper_id = ?",
                (title, abstract, decision.paper_id),
            )
        if not self._in_batch:
            self._conn.commit()

    def flush_pending_commits(self) -> None:
        self._conn.commit()

    def begin_batch(self) -> None:
        """
        Start a batch transaction. Idempotent: no-op if a transaction is
        already active (prevents 'cannot start a transaction within a
        transaction' errors on rapid start/stop cycles).
        """
        self._in_batch = True
        self._conn.isolation_level = None
        if not self._conn.in_transaction:
            self._conn.execute("BEGIN;")

    def end_batch(self) -> None:
        """
        Commit the current batch. Safe to call even when no transaction is
        active (e.g. after a CancelledError interrupts mid-batch, or when
        save_decision's own commit() already closed the transaction).
        """
        if self._in_batch:
            self._in_batch = False
            try:
                in_transaction = self._conn.in_transaction
            except AttributeError:
                in_transaction = True

            if in_transaction:
                try:
                    self._conn.execute("COMMIT;")
                except Exception as exc:
                    import logging

                    logging.getLogger(__name__).warning(
                        "end_batch(): COMMIT suppressed (%s)", exc
                    )

    def get_decision(self, paper_id: str) -> Optional[ScreeningDecision]:
        cursor = self._conn.execute(_SELECT_BY_ID, (paper_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return _row_to_decision(row)

    def get_all_decisions(self) -> list[ScreeningDecision]:
        cursor = self._conn.execute(_SELECT_ALL)
        return [_row_to_decision(row) for row in cursor.fetchall()]

    # ── System Settings ──────────────────────────────────────────────────────

    def get_setting(self, key: str, default: str = "") -> str:
        cursor = self._conn.execute(
            "SELECT value FROM system_settings WHERE key = ?", (key,)
        )
        row = cursor.fetchone()
        if row is None:
            return default
        return row["value"]

    def save_setting(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO system_settings (key, value) VALUES (?, ?)",
            (key, value),
        )
        self._conn.commit()

    # ── Calibration ──────────────────────────────────────────────────────────

    def mark_calibration_sample(
        self, papers: list[Paper], size: int = 100
    ) -> list[str]:
        self._conn.execute("UPDATE screening_decisions SET is_calibration = 0")
        self._conn.commit()

        def _normalize(title: str) -> str:
            return "".join(c for c in title.lower() if c.isalnum())

        seen = set()
        unique_papers: list[Paper] = []
        for p in papers:
            key = _normalize(p.title)
            if key not in seen:
                seen.add(key)
                unique_papers.append(p)

        def _get_source_type(p: Paper) -> str:
            v = p.source_type
            return v.value if hasattr(v, "value") else str(v)

        wl = [p for p in unique_papers if _get_source_type(p) == "WL"]
        gl = [p for p in unique_papers if _get_source_type(p) == "GL"]

        selected: list[str] = []
        total = len(wl) + len(gl)

        if total == 0:
            return selected

        def _sample(group: list[Paper], target: int) -> list[str]:
            if not group:
                return []
            return [p.id for p in random.sample(group, min(target, len(group)))]

        wl_target = max(1, round(size * len(wl) / total)) if wl else 0
        gl_target = size - wl_target if gl else size

        selected.extend(_sample(wl, wl_target))
        selected.extend(_sample(gl, gl_target))

        if len(selected) > size:
            selected = random.sample(selected, size)

        paper_map = {p.id: p for p in papers}
        for pid in selected:
            p = paper_map.get(pid)
            self._conn.execute(
                "INSERT OR REPLACE INTO screening_decisions "
                "(paper_id, status, confidence_score, rationale, "
                "applied_criteria_codes, is_calibration, title, abstract) "
                "VALUES (?, 'NEEDS_REVIEW', 0.0, '[calibration sample]', '[]', 1, ?, ?)",
                (pid, p.title if p else "", (p.abstract or "") if p else ""),
            )
        self._conn.commit()
        return selected

    def clear_calibration_flags(self) -> None:
        self._conn.execute("UPDATE screening_decisions SET is_calibration = 0")
        self._conn.commit()

    def seed_calibration_from_audits(self) -> int:
        self._conn.execute("UPDATE screening_decisions SET is_calibration = 0")
        self._conn.commit()
        self._conn.execute("UPDATE screening_decisions SET is_calibration = 1 WHERE is_audited = 1")
        self._conn.commit()
        cursor = self._conn.execute(
            "SELECT COUNT(*) AS cnt FROM screening_decisions WHERE is_calibration = 1"
        )
        return cursor.fetchone()["cnt"]

    def get_calibration_papers(self) -> list[str]:
        cursor = self._conn.execute(
            "SELECT paper_id FROM screening_decisions WHERE is_calibration = 1"
        )
        return [row["paper_id"] for row in cursor.fetchall()]

    def seed_human_decision(self, paper_id: str, human_decision: str) -> None:
        self._conn.execute(
            "INSERT INTO screening_decisions "
            "(paper_id, status, confidence_score, rationale, "
            "applied_criteria_codes, is_calibration, is_audited, human_decision) "
            "VALUES (?, 'NEEDS_REVIEW', 0.0, '[calibration sample]', '[]', 1, 1, ?) "
            "ON CONFLICT(paper_id) DO UPDATE SET "
            "human_decision = excluded.human_decision, "
            "is_audited = 1, "
            "is_calibration = 1",
            (paper_id, human_decision),
        )
        self._conn.commit()

    def get_screened_calibration_count(self) -> int:
        cursor = self._conn.execute(
            "SELECT COUNT(*) AS cnt FROM screening_decisions "
            "WHERE is_calibration = 1 AND status != 'NEEDS_REVIEW'"
        )
        return cursor.fetchone()["cnt"]

    def get_human_decision_map(self) -> dict[str, str]:
        cursor = self._conn.execute(
            "SELECT paper_id, human_decision FROM screening_decisions "
            "WHERE human_decision IS NOT NULL"
        )
        return {row["paper_id"]: row["human_decision"] for row in cursor.fetchall()}

    def get_few_shot_examples(self, limit: int = 3) -> list[dict]:
        cursor = self._conn.execute(
            "SELECT title, abstract, human_decision FROM screening_decisions "
            "WHERE is_audited = 1 AND human_decision IS NOT NULL "
            "ORDER BY RANDOM() LIMIT ?",
            (limit,),
        )
        return [
            {
                "title": row["title"] or "",
                "abstract": row["abstract"] or "",
                "human_decision": row["human_decision"],
            }
            for row in cursor.fetchall()
        ]

    # ── Criteria ─────────────────────────────────────────────────────────────

    def get_all_criteria(self) -> list[dict[str, Any]]:
        cursor = self._conn.execute(_SELECT_ALL_CRITERIA)
        rows = cursor.fetchall()
        return [
            {
                "id": row["id"],
                "title": row["title"],
                "description": row["description"],
                "type": row["type"],
                "is_heuristic": bool(row["is_heuristic"]),
            }
            for row in rows
        ]

    def update_criterion(self, criterion_id: str, title: str, description: str) -> None:
        self._conn.execute(_UPDATE_CRITERION, (title, description, criterion_id))
        self._conn.commit()

    def get_criteria_for_pipeline(self) -> list[Criterion]:
        rows = self.get_all_criteria()
        return [
            Criterion(
                id=row["id"],
                type=CriterionType.EXCLUSION if row["type"] == "EXCLUSION" else CriterionType.INCLUSION,
                code=row["id"],
                description=row["description"],
            )
            for row in rows
        ]

    # ── Audit helpers ───────────────────────────────────────────────────────

    def clear_all(self) -> None:
        self._conn.execute("DELETE FROM screening_decisions")
        self._conn.commit()

    def delete_decisions(self, paper_ids: list[str]) -> None:
        placeholders = ",".join("?" for _ in paper_ids)
        self._conn.execute(
            f"DELETE FROM screening_decisions WHERE paper_id IN ({placeholders})",
            paper_ids,
        )
        self._conn.commit()

    def save_audit(self, paper_id: str, human_decision: str) -> None:
        self._conn.execute(_UPDATE_AUDIT, (human_decision, paper_id))
        self._conn.commit()

    def save_bulk_audit(self, paper_ids: list[str], human_decision: str) -> None:
        params = [(human_decision, pid) for pid in paper_ids]
        self._conn.executemany(_UPDATE_AUDIT, params)
        self._conn.commit()

    def save_quality_assessment(self, paper_id: str, q1: float, q2: float, q3: float, q4: float, source_type: str = "GL") -> float:
        score = q1 + q2 + q3 + q4
        if source_type == "WL":
            self._conn.execute(_UPDATE_WL_QA, (q1, q2, q3, q4, score, paper_id))
        else:
            self._conn.execute(_UPDATE_GL_QA, (q1, q2, q3, q4, score, paper_id))
        if score < 2.0:
            self._conn.execute(
                "UPDATE screening_decisions SET status = 'EXCLUDED', "
                "applied_criteria_codes = ?, rationale = ? WHERE paper_id = ?",
                (json.dumps(["QC_FAIL"]), f"Excluded: Failed Quality Assessment (Score: {score}/4.0)", paper_id),
            )
        else:
            cursor = self._conn.execute(
                "SELECT status, applied_criteria_codes FROM screening_decisions WHERE paper_id = ?",
                (paper_id,),
            )
            row = cursor.fetchone()
            if row:
                current_codes = json.loads(row["applied_criteria_codes"]) if row["applied_criteria_codes"] else []
                if row["status"] == "EXCLUDED" and "QC_FAIL" in current_codes:
                    self._conn.execute(
                        "UPDATE screening_decisions SET status = 'INCLUDED', "
                        "applied_criteria_codes = ?, rationale = ? WHERE paper_id = ?",
                        (json.dumps([]), f"Restored: Met Quality threshold (Score: {score}/4.0)", paper_id),
                    )
        self._conn.commit()
        return score

    def save_pdf_metadata(self, paper_id: str, full_text: str, pdf_url: str) -> None:
        self._conn.execute(
            "UPDATE screening_decisions SET full_text = ?, pdf_url = ? WHERE paper_id = ?",
            (full_text, pdf_url, paper_id),
        )
        self._conn.commit()

    def get_included_papers_data(self) -> list[dict]:
        cursor = self._conn.execute(
            "SELECT paper_id, full_text FROM screening_decisions WHERE status = ?",
            (ScreeningStatus.INCLUDED.value,),
        )
        return [
            {"paper_id": row["paper_id"], "full_text": row["full_text"]}
            for row in cursor.fetchall()
        ]

    def get_pdf_metadata(self, paper_id: str) -> Optional[dict]:
        cursor = self._conn.execute(
            "SELECT full_text, pdf_url FROM screening_decisions WHERE paper_id = ?",
            (paper_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return {"full_text": row["full_text"], "pdf_url": row["pdf_url"]}

    def get_quality_map(self) -> dict[str, dict]:
        cursor = self._conn.execute(
            "SELECT paper_id, gl_q1, gl_q2, gl_q3, gl_q4, quality_score, "
            "wl_q1, wl_q2, wl_q3, wl_q4, wl_quality_score, pdf_url, full_text "
            "FROM screening_decisions WHERE gl_q1 IS NOT NULL OR wl_q1 IS NOT NULL "
            "OR pdf_url IS NOT NULL OR full_text IS NOT NULL"
        )
        result: dict[str, dict] = {}
        for row in cursor.fetchall():
            result[row["paper_id"]] = {
                "gl_q1": row["gl_q1"],
                "gl_q2": row["gl_q2"],
                "gl_q3": row["gl_q3"],
                "gl_q4": row["gl_q4"],
                "quality_score": row["quality_score"],
                "wl_q1": row["wl_q1"],
                "wl_q2": row["wl_q2"],
                "wl_q3": row["wl_q3"],
                "wl_q4": row["wl_q4"],
                "wl_quality_score": row["wl_quality_score"],
                "pdf_url": row["pdf_url"],
                "full_text": row["full_text"],
            }
        return result

    def get_all_audited(self, calibration_only: bool = False) -> list[dict]:
        query = _SELECT_AUDITED_CALIBRATION if calibration_only else _SELECT_AUDITED
        cursor = self._conn.execute(query)
        rows = cursor.fetchall()
        result = []
        for row in rows:
            result.append({
                "paper_id": row["paper_id"],
                "status": ScreeningStatus(row["status"]),
                "human_decision": row["human_decision"],
                "rationale": row["rationale"],
                "applied_criteria_codes": json.loads(row["applied_criteria_codes"]),
            })
        return result
