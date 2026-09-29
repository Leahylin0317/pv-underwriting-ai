import pytest


@pytest.fixture(autouse=True)
def isolate_case_database(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep persisted API test cases isolated from each other and from local runs."""

    monkeypatch.setenv(
        "PV_CASE_DB_PATH",
        str(tmp_path / "cases.sqlite3"),
    )
