import sqlite3
from datetime import UTC, datetime, timedelta

from app.storage import AnalysisJobRepository, CaseRepository


def test_retention_purges_expired_case_review_and_job_data(tmp_path) -> None:
    database_path = tmp_path / "cases.sqlite3"
    cases = CaseRepository(database_path)
    jobs = AnalysisJobRepository(database_path)
    cases.list_cases(limit=1)
    old_time = (datetime.now(UTC) - timedelta(days=40)).isoformat()
    recent_time = datetime.now(UTC).isoformat()

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO cases (case_id, stored_at, decision, review_status, case_json)
            VALUES ('expired', ?, 'manual_review', 'completed', '{}'),
                   ('recent', ?, 'accept', 'pending', '{}')
            """,
            (old_time, recent_time),
        )
        connection.execute(
            """
            INSERT INTO review_events (
                case_id, reviewer_name, final_decision, comment, reviewed_at
            ) VALUES ('expired', 'reviewer', 'accept', 'done', ?)
            """,
            (old_time,),
        )

    jobs.create_job("old-job", "expired")
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE analysis_jobs SET updated_at = ? WHERE job_id = 'old-job'",
            (old_time,),
        )

    removed = cases.purge_expired_cases(
        retention_days=30,
        now=datetime.now(UTC),
    )

    assert removed == 1
    assert cases.get_case("expired") is None
    assert [case["case_id"] for case in cases.list_cases()] == ["recent"]
    assert jobs.get_job("old-job") is None
