import json
import sqlite3
from pathlib import Path
from typing import Optional

from src.domain.enums import ScreeningStatus
from src.domain.interfaces import ScreeningDecisionRepository
from src.domain.models import ScreeningDecision

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS screening_decisions (
    paper_id            TEXT PRIMARY KEY,
    status              TEXT    NOT NULL,
    confidence_score    REAL    NOT NULL,
    rationale           TEXT    NOT NULL,
    applied_criteria_codes TEXT NOT NULL
)
"""

_INSERT_OR_REPLACE = """
INSERT OR REPLACE INTO screening_decisions
    (paper_id, status, confidence_score, rationale, applied_criteria_codes)
VALUES
    (?, ?, ?, ?, ?)
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


def _row_to_decision(row: tuple) -> ScreeningDecision:
    paper_id, status_str, confidence, rationale, codes_json = row
    return ScreeningDecision(
        paper_id=paper_id,
        status=ScreeningStatus(status_str),
        confidence_score=float(confidence),
        rationale=rationale,
        applied_criteria_codes=list(json.loads(codes_json)),
    )


class SQLiteScreeningDecisionRepository(ScreeningDecisionRepository):
    def __init__(self, db_path: str = "screening.db") -> None:
        self._db_path = str(db_path)
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(_CREATE_TABLE)
        self._conn.commit()

    def save_decision(self, decision: ScreeningDecision) -> None:
        codes_json = json.dumps(decision.applied_criteria_codes, ensure_ascii=False)
        self._conn.execute(
            _INSERT_OR_REPLACE,
            (
                decision.paper_id,
                decision.status.value,
                decision.confidence_score,
                decision.rationale,
                codes_json,
            ),
        )
        self._conn.commit()

    def get_decision(self, paper_id: str) -> Optional[ScreeningDecision]:
        cursor = self._conn.execute(_SELECT_BY_ID, (paper_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return _row_to_decision(row)

    def get_all_decisions(self) -> list[ScreeningDecision]:
        cursor = self._conn.execute(_SELECT_ALL)
        return [_row_to_decision(row) for row in cursor.fetchall()]
