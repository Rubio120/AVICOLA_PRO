from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .db_connection import read_secret_file, write_service_file

SNAPSHOT_PATTERN = re.compile(r"[a-f0-9]{64}\Z")
TARGET_PATTERN = re.compile(r"avicola_restore_[a-z0-9_]{1,48}\Z")
ARCHIVE_NAME = "avicola-pro.pgdump"
VERIFIER = Path(__file__).with_name("verify_restore.py")
RESTIC = "/usr/local/bin/restic"
PSQL = "/usr/lib/postgresql/16/bin/psql"
PG_RESTORE = "/usr/lib/postgresql/16/bin/pg_restore"
PYTHON = "/usr/bin/python3"


def _restic_environment(environ: dict[str, str] | None = None) -> dict[str, str]:
    environment = os.environ.copy() if environ is None else environ.copy()
    read_secret_file("RESTIC_REPOSITORY_FILE", "RESTIC_REPOSITORY", environment)
    environment.pop("RESTIC_REPOSITORY_FILE", None)
    password_file = environment.get("RESTIC_PASSWORD_FILE")
    if not password_file or not Path(password_file).is_file() or Path(password_file).stat().st_size == 0:
        raise ValueError("Required Restic password file is missing or empty")
    return environment


def _database_identity(database_url: str) -> tuple[str, int, str]:
    parsed = urlsplit(database_url)
    if parsed.scheme != "postgresql+psycopg" or parsed.hostname is None:
        raise ValueError("Database URL is invalid")
    try:
        port = parsed.port or 5432
    except ValueError:
        raise ValueError("Database URL port is invalid") from None
    return parsed.hostname.lower(), port, unquote(parsed.path.lstrip("/"))


def validate_restore_target(source_url: str, target_url: str, target_name: str, snapshot_id: str) -> None:
    if not TARGET_PATTERN.fullmatch(target_name) or _database_identity(target_url)[2] != target_name:
        raise ValueError("An explicitly named disposable restore database is required")
    if _database_identity(source_url) == _database_identity(target_url):
        raise ValueError("Restore target must be different from the source database")
    if not SNAPSHOT_PATTERN.fullmatch(snapshot_id):
        raise ValueError("A full Restic snapshot ID is required")


def _target_is_empty(environment: dict[str, str], timeout: int) -> bool:
    result = subprocess.run(  # noqa: S603 - executable and SQL are fixed by this image.
        [
            PSQL,
            "--no-psqlrc",
            "--tuples-only",
            "--no-align",
            "--set=ON_ERROR_STOP=1",
            "--dbname=service=restore",
            "--command",
            "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname <> 'information_schema' "
            "AND c.relkind IN ('r','p','v','m','S','f')",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError("Restore target preflight failed")
    try:
        return int(result.stdout.strip()) == 0
    except ValueError:
        raise RuntimeError("Restore target preflight returned an invalid result") from None


def main() -> int:
    try:
        environment = _restic_environment()
        source_url = read_secret_file("AVICOLA_DATABASE_URL_FILE", "AVICOLA_DATABASE_URL", environment)
        target_url = read_secret_file("RESTORE_TARGET_DATABASE_URL_FILE", "RESTORE_TARGET_DATABASE_URL", environment)
        target_name = environment.get("RESTORE_TARGET_DATABASE_NAME", "")
        snapshot_id = environment.get("RESTORE_SNAPSHOT_ID", "")
        validate_restore_target(source_url, target_url, target_name, snapshot_id)
        timeout = int(environment.get("RESTORE_TIMEOUT_SECONDS", "7200"))
        if not 60 <= timeout <= 86_400:
            raise ValueError("Restore timeout is outside the allowed range")

        check = subprocess.run(  # noqa: S603 - executable and arguments are fixed by this image.
            [RESTIC, "check", "--read-data"],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
            timeout=timeout,
        )
        if check.returncode != 0:
            raise RuntimeError("Restic repository integrity check failed")

        with tempfile.TemporaryDirectory(prefix="avicola-restore-") as temporary_directory:
            temp_path = Path(temporary_directory)
            result = subprocess.run(  # noqa: S603 - executable and arguments are fixed by this image.
                [
                    RESTIC,
                    "restore",
                    snapshot_id,
                    "--target",
                    str(temp_path),
                    "--include",
                    f"/{ARCHIVE_NAME}",
                ],
                check=False,
                capture_output=True,
                text=True,
                env=environment,
                timeout=timeout,
            )
            if result.returncode != 0:
                raise RuntimeError("Restic snapshot extraction failed")
            archive = temp_path / ARCHIVE_NAME
            if not archive.is_file() or archive.stat().st_size == 0:
                raise RuntimeError("Restored database archive is missing")
            archive_hash = hashlib.sha256()
            with archive.open("rb") as archive_stream:
                for chunk in iter(lambda: archive_stream.read(1024 * 1024), b""):
                    archive_hash.update(chunk)
            archive_check = subprocess.run(  # noqa: S603 - executable is fixed; archive is in a private temp directory.
                [PG_RESTORE, "--list", str(archive)],
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if archive_check.returncode != 0:
                raise RuntimeError("Restored database archive is invalid")

            service_file = temp_path / "pg_service.conf"
            write_service_file(service_file, {"source": source_url, "restore": target_url})
            environment["PGSERVICEFILE"] = str(service_file)
            if not _target_is_empty(environment, timeout):
                raise RuntimeError("Restore target is not empty")
            restore = subprocess.run(  # noqa: S603 - executable and options are fixed; target is a validated service alias.
                [
                    PG_RESTORE,
                    "--exit-on-error",
                    "--no-owner",
                    "--no-privileges",
                    "--dbname=service=restore",
                    str(archive),
                ],
                check=False,
                capture_output=True,
                text=True,
                env=environment,
                timeout=timeout,
            )
            if restore.returncode != 0:
                raise RuntimeError("Database restore failed")
            verification = subprocess.run(  # noqa: S603 - executable is fixed by the base image.
                [PYTHON, str(VERIFIER)],
                check=False,
                capture_output=True,
                text=True,
                env=environment,
                timeout=timeout,
            )
            if verification.returncode != 0:
                raise RuntimeError("Restored database failed reconciliation")

        print(
            f"restore_status=verified snapshot_id={snapshot_id} archive_sha256={archive_hash.hexdigest()} "
            f"target={target_name}"
        )
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
        print("Restore failed; target was checked before restore and details are withheld", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
