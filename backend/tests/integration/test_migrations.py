from __future__ import annotations

import os
import subprocess
from pathlib import Path

import psycopg
import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _database_url() -> str:
    try:
        return os.environ["AVICOLA_TEST_DATABASE_URL"]
    except KeyError as exc:
        pytest.fail("AVICOLA_TEST_DATABASE_URL must reference a real empty PostgreSQL database")
        raise AssertionError from exc


def _run_alembic(*args: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["AVICOLA_DATABASE_URL"] = _database_url()
    return subprocess.run(
        [str(BACKEND_ROOT / ".venv" / "Scripts" / "alembic.exe"), *args],
        cwd=BACKEND_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.mark.integration
def test_baseline_migration_round_trip_on_real_postgresql() -> None:
    _run_alembic("downgrade", "base")
    _run_alembic("upgrade", "head")
    current = _run_alembic("current")

    assert "0001_baseline" in current.stdout

    with psycopg.connect(_database_url().replace("+psycopg", "")) as connection, connection.cursor() as cursor:
        cursor.execute("select version()")
        version = cursor.fetchone()
        cursor.execute("select count(*) from information_schema.tables where table_schema = 'public'")
        table_count = cursor.fetchone()

    assert version is not None and version[0].startswith("PostgreSQL 16")
    assert table_count == (1,)  # Alembic version table only; no business schema in Delivery 1.
