"""Local SQLite storage for analysis results and human-review history."""

import json
import os
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.contracts import MapImageryReview, ProcessingTrace, UnderwritingCase


class CaseRepositoryConflict(Exception):
    """Raised when an analysis reuses an existing case identifier."""


class CaseRepository:
    """Persist structured case results without retaining uploaded source files."""

    def __init__(self, database_path: str | Path | None = None) -> None:
        configured_path = database_path or os.getenv(
            "PV_CASE_DB_PATH", "outputs/pv-underwriting.sqlite3"
        )
        self.database_path = Path(configured_path).expanduser()

    def save_case(self, case: UnderwritingCase) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        stored_at = datetime.now(UTC).isoformat()
        payload = case.model_dump_json()

        with closing(sqlite3.connect(self.database_path, timeout=10)) as connection:
            self._initialize(connection)
            try:
                with connection:
                    connection.execute(
                        """
                        INSERT INTO cases (
                            case_id, stored_at, decision, review_status, case_json
                        ) VALUES (?, ?, ?, 'pending', ?)
                        """,
                        (
                            case.case_id,
                            stored_at,
                            case.decision.decision.value if case.decision else None,
                            payload,
                        ),
                    )
            except sqlite3.IntegrityError as exc:
                raise CaseRepositoryConflict(case.case_id) from exc

    def list_cases(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        decision: str | None = None,
        review_status: str | None = None,
    ) -> list[dict[str, Any]]:
        with closing(sqlite3.connect(self.database_path, timeout=10)) as connection:
            self._initialize(connection)
            connection.row_factory = sqlite3.Row
            conditions: list[str] = []
            parameters: list[object] = []
            if decision:
                conditions.append("decision = ?")
                parameters.append(decision)
            if review_status:
                conditions.append("review_status = ?")
                parameters.append(review_status)
            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            rows = connection.execute(
                f"""
                SELECT case_id, stored_at, decision, review_status,
                       reviewer_name, final_decision, reviewed_at
                FROM cases
                {where_clause}
                ORDER BY stored_at DESC, case_id
                LIMIT ? OFFSET ?
                """,
                [*parameters, limit, offset],
            ).fetchall()
            return [dict(row) for row in rows]

    def get_case(self, case_id: str) -> dict[str, Any] | None:
        with closing(sqlite3.connect(self.database_path, timeout=10)) as connection:
            self._initialize(connection)
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT case_id, stored_at, decision, review_status,
                       reviewer_name, final_decision, review_comment, reviewed_at,
                       case_json
                FROM cases WHERE case_id = ?
                """,
                (case_id,),
            ).fetchone()
            if row is None:
                return None
            result = dict(row)
            result["case"] = json.loads(result.pop("case_json"))
            result["review_history"] = self._review_history(connection, case_id)
            return result

    def submit_review(
        self,
        *,
        case_id: str,
        reviewer_name: str,
        final_decision: str,
        comment: str,
    ) -> dict[str, Any] | None:
        reviewed_at = datetime.now(UTC).isoformat()
        with closing(sqlite3.connect(self.database_path, timeout=10)) as connection:
            self._initialize(connection)
            with connection:
                cursor = connection.execute(
                    """
                    UPDATE cases SET review_status = 'completed',
                        reviewer_name = ?, final_decision = ?,
                        review_comment = ?, reviewed_at = ?
                    WHERE case_id = ?
                    """,
                    (reviewer_name, final_decision, comment, reviewed_at, case_id),
                )
                if cursor.rowcount == 0:
                    return None
                connection.execute(
                    """
                    INSERT INTO review_events (
                        case_id, reviewer_name, final_decision, comment, reviewed_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (case_id, reviewer_name, final_decision, comment, reviewed_at),
                )
            return self.get_case(case_id)

    def append_map_review(
        self,
        *,
        case_id: str,
        review: MapImageryReview,
        trace: ProcessingTrace,
    ) -> dict[str, Any] | None:
        """Append an external map observation without changing the decision."""

        with closing(sqlite3.connect(self.database_path, timeout=10)) as connection:
            self._initialize(connection)
            with connection:
                row = connection.execute(
                    "SELECT case_json FROM cases WHERE case_id = ?",
                    (case_id,),
                ).fetchone()
                if row is None:
                    return None

                case = UnderwritingCase.model_validate(json.loads(row[0]))
                if any(item.review_id == review.review_id for item in case.map_reviews):
                    raise ValueError("map review ID already exists")
                updated_case = case.model_copy(
                    update={
                        "map_reviews": [*case.map_reviews, review],
                        "processing_trace": [*case.processing_trace, trace],
                    }
                )
                connection.execute(
                    "UPDATE cases SET case_json = ? WHERE case_id = ?",
                    (updated_case.model_dump_json(), case_id),
                )

        return self.get_case(case_id)

    def purge_expired_cases(
        self,
        *,
        retention_days: int,
        now: datetime | None = None,
    ) -> int:
        """Delete expired result records, their review events and cached job results."""

        if retention_days < 1:
            return 0
        cutoff = (
            (datetime.now(UTC) if now is None else now.astimezone(UTC))
            - timedelta(days=retention_days)
        ).isoformat()
        with closing(sqlite3.connect(self.database_path, timeout=10)) as connection:
            self._initialize(connection)
            connection.execute("PRAGMA secure_delete = ON")
            with connection:
                connection.execute(
                    """
                    DELETE FROM review_events
                    WHERE case_id IN (SELECT case_id FROM cases WHERE stored_at < ?)
                    """,
                    (cutoff,),
                )
                connection.execute(
                    """
                    DELETE FROM analysis_jobs
                    WHERE case_id IN (SELECT case_id FROM cases WHERE stored_at < ?)
                       OR updated_at < ?
                    """,
                    (cutoff, cutoff),
                )
                cursor = connection.execute(
                    "DELETE FROM cases WHERE stored_at < ?",
                    (cutoff,),
                )
                return cursor.rowcount

    @staticmethod
    def _initialize(connection: sqlite3.Connection) -> None:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS cases (
                case_id TEXT PRIMARY KEY,
                stored_at TEXT NOT NULL,
                decision TEXT,
                review_status TEXT NOT NULL,
                reviewer_name TEXT,
                final_decision TEXT,
                review_comment TEXT,
                reviewed_at TEXT,
                case_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_cases_stored_at
                ON cases(stored_at DESC);
            CREATE INDEX IF NOT EXISTS idx_cases_decision
                ON cases(decision);
            CREATE INDEX IF NOT EXISTS idx_cases_review_status
                ON cases(review_status);
            CREATE TABLE IF NOT EXISTS review_events (
                review_id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id TEXT NOT NULL REFERENCES cases(case_id),
                reviewer_name TEXT NOT NULL,
                final_decision TEXT NOT NULL,
                comment TEXT NOT NULL,
                reviewed_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS analysis_jobs (
                job_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                status TEXT NOT NULL,
                progress_percent INTEGER NOT NULL,
                current_step TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                error_code TEXT,
                result_json TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_analysis_jobs_updated_at
                ON analysis_jobs(updated_at DESC);
            """
        )

    @staticmethod
    def _review_history(
        connection: sqlite3.Connection,
        case_id: str,
    ) -> list[dict[str, Any]]:
        rows = connection.execute(
            """
            SELECT reviewer_name, final_decision, comment, reviewed_at
            FROM review_events WHERE case_id = ? ORDER BY review_id
            """,
            (case_id,),
        ).fetchall()
        return [dict(row) for row in rows]


class AnalysisJobRepository:
    """Persist the status and progress of an in-process analysis job."""

    def __init__(self, database_path: str | Path | None = None) -> None:
        self._cases = CaseRepository(database_path)

    def create_job(self, job_id: str, case_id: str) -> None:
        self._cases.database_path.parent.mkdir(parents=True, exist_ok=True)
        now = datetime.now(UTC).isoformat()
        with closing(sqlite3.connect(self._cases.database_path, timeout=10)) as connection:
            self._cases._initialize(connection)
            with connection:
                connection.execute(
                    """
                    INSERT INTO analysis_jobs (
                        job_id, case_id, status, progress_percent, current_step,
                        created_at, updated_at
                    ) VALUES (?, ?, 'queued', 0, '等待处理', ?, ?)
                    """,
                    (job_id, case_id, now, now),
                )

    def fail_incomplete_jobs(self) -> None:
        """Mark in-process jobs from a previous server run as interrupted."""

        now = datetime.now(UTC).isoformat()
        self._cases.database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self._cases.database_path, timeout=10)) as connection:
            self._cases._initialize(connection)
            with connection:
                connection.execute(
                    """
                    UPDATE analysis_jobs SET status = 'failed',
                        current_step = '服务重启导致任务中断',
                        error_code = 'SERVER_RESTARTED', updated_at = ?
                    WHERE status IN ('queued', 'running')
                    """,
                    (now,),
                )

    def update_job(
        self,
        job_id: str,
        *,
        status: str,
        progress_percent: int,
        current_step: str,
        error_code: str | None = None,
        result: UnderwritingCase | None = None,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        result_json = result.model_dump_json() if result is not None else None
        with closing(sqlite3.connect(self._cases.database_path, timeout=10)) as connection:
            self._cases._initialize(connection)
            with connection:
                connection.execute(
                    """
                    UPDATE analysis_jobs SET status = ?, progress_percent = ?,
                        current_step = ?, updated_at = ?, error_code = ?, result_json = ?
                    WHERE job_id = ?
                    """,
                    (
                        status,
                        progress_percent,
                        current_step,
                        now,
                        error_code,
                        result_json,
                        job_id,
                    ),
                )

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with closing(sqlite3.connect(self._cases.database_path, timeout=10)) as connection:
            self._cases._initialize(connection)
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT job_id, case_id, status, progress_percent, current_step,
                       created_at, updated_at, error_code, result_json
                FROM analysis_jobs WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()
            if row is None:
                return None
            result = dict(row)
            if result["result_json"] is not None:
                result["result"] = json.loads(result.pop("result_json"))
            else:
                result.pop("result_json")
            return result
