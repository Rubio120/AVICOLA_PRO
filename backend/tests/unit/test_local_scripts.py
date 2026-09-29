from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_local_quality_gate_uses_a_dedicated_migration_database() -> None:
    check_script = (PROJECT_ROOT / "scripts" / "check.ps1").read_text(encoding="utf-8")
    database_script = (PROJECT_ROOT / "scripts" / "db-up.ps1").read_text(encoding="utf-8")

    assert "55432/avicola_pro_test" in check_script
    assert "createdb.exe" in database_script
    assert "avicola_pro_test" in database_script


@pytest.mark.skipif(sys.platform != "win32", reason="PowerShell gate behavior is Windows-specific")
def test_local_quality_gate_rejects_shared_application_and_migration_database() -> None:
    powershell = shutil.which("powershell.exe")
    assert powershell is not None
    database_url = "postgresql+psycopg://avicola:test@127.0.0.1:55432/shared"
    environment = os.environ.copy()
    environment["AVICOLA_DATABASE_URL"] = database_url
    environment["AVICOLA_TEST_DATABASE_URL"] = database_url

    result = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(PROJECT_ROOT / "scripts" / "check.ps1"),
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "must use a dedicated database" in result.stderr
