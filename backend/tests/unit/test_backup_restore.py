from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from deploy.backup.backup import _restic_environment  # noqa: E402
from deploy.backup.db_connection import (  # noqa: E402
    DatabaseUrlError,
    service_section,
)
from deploy.backup.restore import _restic_environment as _restore_restic_environment  # noqa: E402
from deploy.backup.restore import validate_restore_target  # noqa: E402
from deploy.backup.verify_restore import (  # noqa: E402
    CHECKS,
    RestoreVerificationError,
    verify_database,
)


class _QueryResults:
    def __init__(self, counts: list[int]) -> None:
        self.counts = iter(counts)

    def __call__(self, _query: str) -> int:
        return next(self.counts)


def test_restore_verifier_accepts_clean_results_for_all_business_invariants() -> None:
    completed = verify_database(_QueryResults([0] * len(CHECKS)))

    assert completed == [name for name, _ in CHECKS]


def test_restore_verifier_rejects_any_business_invariant_drift() -> None:
    with_error = [0] * len(CHECKS)
    with_error[3] = 1

    try:
        verify_database(_QueryResults(with_error))
    except RestoreVerificationError as error:
        assert "closed cash session expected balances" in str(error)
    else:
        raise AssertionError("reconciliation drift must fail restore verification")


def test_every_restore_reconciliation_rejects_its_own_drift() -> None:
    for index, (name, _) in enumerate(CHECKS):
        drift = [0] * len(CHECKS)
        drift[index] = 1
        try:
            verify_database(_QueryResults(drift))
        except RestoreVerificationError as error:
            assert name in str(error)
        else:
            raise AssertionError(f"reconciliation {name} must reject controlled drift")


def test_database_service_file_uses_raw_ini_values_for_libpq() -> None:
    section = service_section(
        "avicola",
        "postgresql+psycopg://backup%40user:p%3A%5Cword@db:5432/avicola_pro?sslmode=verify-full",
    )

    assert "host=db" in section
    assert "user=backup@user" in section
    assert "password=p:\\word" in section
    assert "sslmode=verify-full" in section
    assert "[avicola]" in section


def test_database_service_file_leaves_integer_connection_options_unquoted() -> None:
    section = service_section(
        "avicola",
        "postgresql+psycopg://backup:secret@127.0.0.1:55432/avicola_pro?connect_timeout=7",
    )

    assert "port=55432" in section
    assert "connect_timeout=7" in section
    assert 'port="55432"' not in section
    assert 'connect_timeout="7"' not in section


def test_database_service_file_rejects_non_integer_timeout() -> None:
    try:
        service_section("avicola", "postgresql+psycopg://backup:secret@db/avicola_pro?connect_timeout=fast")
    except DatabaseUrlError as error:
        assert "connect_timeout" in str(error)
    else:
        raise AssertionError("libpq integer service settings must be validated before writing")


def test_database_service_file_rejects_line_break_in_encoded_credentials() -> None:
    try:
        service_section("avicola", "postgresql+psycopg://user:secret%0Ainjected@db/avicola_pro")
    except DatabaseUrlError:
        pass
    else:
        raise AssertionError("connection settings must not inject service-file lines")


def test_database_service_file_rejects_trailing_whitespace_libpq_would_strip() -> None:
    try:
        service_section("avicola", "postgresql+psycopg://user:secret%20@db/avicola_pro")
    except DatabaseUrlError as error:
        assert "whitespace" in str(error)
    else:
        raise AssertionError("service-file trailing whitespace would change the credential")


def test_restic_environment_does_not_pass_repository_value_and_file_together(tmp_path: Path) -> None:
    repository_file = tmp_path / "repository-path"
    password_file = tmp_path / "restic-password"
    repository_file.write_text("local:/backup", encoding="utf-8")
    password_file.write_text("test-only", encoding="utf-8")

    environment = _restic_environment(
        {
            "RESTIC_REPOSITORY_FILE": str(repository_file),
            "RESTIC_PASSWORD_FILE": str(password_file),
        }
    )

    assert environment["RESTIC_REPOSITORY"] == "local:/backup"
    assert "RESTIC_REPOSITORY_FILE" not in environment


def test_restore_environment_does_not_pass_repository_value_and_file_together(tmp_path: Path) -> None:
    repository_file = tmp_path / "repository-path"
    password_file = tmp_path / "restic-password"
    repository_file.write_text("local:/backup", encoding="utf-8")
    password_file.write_text("test-only", encoding="utf-8")

    environment = _restore_restic_environment(
        {
            "RESTIC_REPOSITORY_FILE": str(repository_file),
            "RESTIC_PASSWORD_FILE": str(password_file),
        }
    )

    assert environment["RESTIC_REPOSITORY"] == "local:/backup"
    assert "RESTIC_REPOSITORY_FILE" not in environment


def test_restore_target_requires_another_explicitly_disposable_database_and_full_snapshot_id() -> None:
    source = "postgresql+psycopg://app:secret@db:5432/avicola_pro"
    valid_target = "postgresql+psycopg://restore:secret@restore-db:5432/avicola_restore_drill"
    snapshot_id = "a" * 64

    validate_restore_target(source, valid_target, "avicola_restore_drill", snapshot_id)

    for target, name, snapshot in (
        (source, "avicola_pro", snapshot_id),
        (valid_target, "avicola_restore_drill", "latest"),
        (valid_target, "avicola_pro", snapshot_id),
    ):
        try:
            validate_restore_target(source, target, name, snapshot)
        except ValueError:
            continue
        raise AssertionError("unsafe or ambiguous restore targets must be rejected")
