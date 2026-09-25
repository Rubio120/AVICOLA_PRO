from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from .db_connection import read_secret_file, write_service_file

RESTIC = "/usr/local/bin/restic"
PG_DUMP = "/usr/lib/postgresql/16/bin/pg_dump"

TAG_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}\Z")


def _restic_environment(environ: dict[str, str] | None = None) -> dict[str, str]:
    environment = os.environ.copy() if environ is None else environ.copy()
    read_secret_file("RESTIC_REPOSITORY_FILE", "RESTIC_REPOSITORY", environment)
    environment.pop("RESTIC_REPOSITORY_FILE", None)
    password_file = environment.get("RESTIC_PASSWORD_FILE")
    if not password_file or not Path(password_file).is_file() or Path(password_file).stat().st_size == 0:
        raise ValueError("Required Restic password file is missing or empty")
    return environment


def _snapshot_info(output: str) -> tuple[str, str, str]:
    for line in reversed(output.splitlines()):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("message_type") == "summary" and re.fullmatch(r"[a-f0-9]{64}", event.get("snapshot_id", "")):
            backup_start = event.get("backup_start")
            backup_end = event.get("backup_end")
            if isinstance(backup_start, str) and isinstance(backup_end, str):
                return event["snapshot_id"], backup_start, backup_end
    raise ValueError("Restic backup did not report snapshot identity and timestamps")


def main() -> int:
    try:
        environment = _restic_environment()
        tag = environment.get("BACKUP_TAG", "avicola-pro")
        if not TAG_PATTERN.fullmatch(tag):
            raise ValueError("Backup tag is invalid")
        database_url = read_secret_file("AVICOLA_DATABASE_URL_FILE", "AVICOLA_DATABASE_URL", environment)
        timeout = int(environment.get("BACKUP_TIMEOUT_SECONDS", "3600"))
        if not 60 <= timeout <= 86_400:
            raise ValueError("Backup timeout is outside the allowed range")

        with tempfile.TemporaryDirectory(prefix="avicola-backup-") as temporary_directory:
            service_file = Path(temporary_directory) / "pg_service.conf"
            write_service_file(service_file, {"avicola": database_url})
            environment["PGSERVICEFILE"] = str(service_file)
            result = subprocess.run(  # noqa: S603 - executable and argument vector are fixed by this image.
                [
                    RESTIC,
                    "--json",
                    "backup",
                    "--stdin-filename",
                    "avicola-pro.pgdump",
                    "--stdin-from-command",
                    "--tag",
                    tag,
                    "--",
                    PG_DUMP,
                    "--format=custom",
                    "--no-owner",
                    "--no-privileges",
                    "--dbname=service=avicola",
                ],
                check=False,
                capture_output=True,
                text=True,
                env=environment,
                timeout=timeout,
            )
            if result.returncode != 0:
                raise RuntimeError("Restic backup failed")
            snapshot_id, backup_start, backup_end = _snapshot_info(result.stdout)
            check = subprocess.run(  # noqa: S603 - executable and argument vector are fixed by this image.
                [RESTIC, "check"],
                check=False,
                capture_output=True,
                text=True,
                env=environment,
                timeout=timeout,
            )
            if check.returncode != 0:
                raise RuntimeError("Restic repository verification failed")
        print(
            f"snapshot_id={snapshot_id} backup_start={backup_start} backup_end={backup_end} status=repository-verified"
        )
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
        print("Backup failed; details withheld to protect credentials", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
