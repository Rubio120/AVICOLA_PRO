from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from sqlalchemy import select
from typer.testing import CliRunner

from avicola_pro.bootstrap.initial_admin import InitialAdministratorBootstrapper
from avicola_pro.cli import app
from avicola_pro.modules.audit.infrastructure.models import AuditEvent
from avicola_pro.modules.identity.application.bootstrap import (
    BootstrapAlreadyCompletedError,
    BootstrapIdentity,
)
from avicola_pro.modules.identity.application.credentials import Argon2PasswordService, PasswordPolicy
from avicola_pro.modules.identity.infrastructure.models import Role, User, UserRole
from avicola_pro.shared.infrastructure.config import Settings, get_settings
from avicola_pro.shared.infrastructure.database import DatabaseResources, create_database_resources

BACKEND_ROOT = Path(__file__).resolve().parents[2]
SESSION_HMAC_KEY = "jUrUWz89-ZPO0xh7ppVRm50Pt-un53S_NSfNCACPXaM"


def _database_url() -> str:
    try:
        return os.environ["AVICOLA_TEST_DATABASE_URL"]
    except KeyError as exc:
        pytest.fail("AVICOLA_TEST_DATABASE_URL must reference a real PostgreSQL database")
        raise AssertionError from exc


def _run_alembic(*args: str) -> None:
    environment = os.environ.copy()
    environment["AVICOLA_DATABASE_URL"] = _database_url()
    environment["AVICOLA_SESSION_HMAC_KEY"] = SESSION_HMAC_KEY
    subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture(scope="module", autouse=True)
def migrated_database() -> Iterator[None]:
    _run_alembic("upgrade", "head")
    yield


@pytest.fixture(autouse=True)
def empty_identity_state() -> Iterator[None]:
    with psycopg.connect(_database_url().replace("+psycopg", "")) as connection, connection.cursor() as cursor:
        cursor.execute(
            "truncate table audit_events, security_events, sessions, user_roles, users restart identity cascade"
        )
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _settings() -> Settings:
    return Settings(database_url=_database_url(), session_hmac_key=SESSION_HMAC_KEY)


def _identity(suffix: str = "") -> BootstrapIdentity:
    return BootstrapIdentity.from_input(
        username=f"initial.admin{suffix}",
        email=f"initial.admin{suffix}@example.test",
        display_name="Initial Administrator",
    )


def _bootstrapper(settings: Settings) -> tuple[InitialAdministratorBootstrapper, DatabaseResources]:
    resources = create_database_resources(settings)
    policy = PasswordPolicy(settings.password_min_length, settings.password_max_length)
    service = InitialAdministratorBootstrapper(
        session_factory=resources.session_factory,
        password_service=Argon2PasswordService(policy, time_cost=1, memory_cost_kib=8_192, parallelism=1),
        password_policy=policy,
    )
    return service, resources


@pytest.mark.integration
@pytest.mark.asyncio
async def test_bootstrap_persists_only_argon2id_role_and_allowlisted_audit(caplog: pytest.LogCaptureFixture) -> None:
    settings = _settings()
    bootstrapper, resources = _bootstrapper(settings)
    caplog.set_level(logging.DEBUG)

    result = await bootstrapper.create(_identity())

    async with resources.session_factory() as session:
        user = (await session.scalars(select(User))).one()
        assigned_role = (
            await session.scalars(
                select(Role).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user.id)
            )
        ).one()
        audit = (await session.scalars(select(AuditEvent))).one()
    await resources.dispose()

    assert result.temporary_password not in user.password_hash
    assert user.password_hash.startswith("$argon2id$")
    assert user.status == "ACTIVE"
    assert user.must_change_password is True
    assert assigned_role.code == "administrator"
    assert audit.action == "users.bootstrap"
    assert audit.after_data == {
        "username": "initial.admin",
        "email": "initial.admin@example.test",
        "display_name": "Initial Administrator",
        "status": "ACTIVE",
        "must_change_password": True,
        "role_id": str(assigned_role.id),
    }
    assert result.temporary_password not in str(audit.after_data)
    assert result.temporary_password not in caplog.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_repeated_bootstrap_is_non_destructive_and_does_not_generate_another_secret() -> None:
    settings = _settings()
    bootstrapper, resources = _bootstrapper(settings)
    first = await bootstrapper.create(_identity())

    with pytest.raises(BootstrapAlreadyCompletedError):
        await bootstrapper.create(_identity("2"))

    async with resources.session_factory() as session:
        users = (await session.scalars(select(User))).all()
        assignments = (await session.scalars(select(UserRole))).all()
        audits = (await session.scalars(select(AuditEvent))).all()
    await resources.dispose()

    assert len(users) == len(assignments) == len(audits) == 1
    assert users[0].username == "initial.admin"
    assert first.temporary_password not in str(audits[0].after_data)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_bootstraps_create_exactly_one_administrator() -> None:
    settings = _settings()
    first_bootstrapper, first_resources = _bootstrapper(settings)
    second_bootstrapper, second_resources = _bootstrapper(settings)

    outcomes = await asyncio.gather(
        first_bootstrapper.create(_identity("1")),
        second_bootstrapper.create(_identity("2")),
        return_exceptions=True,
    )

    successes = [outcome for outcome in outcomes if not isinstance(outcome, BaseException)]
    failures = [outcome for outcome in outcomes if isinstance(outcome, BootstrapAlreadyCompletedError)]
    async with first_resources.session_factory() as session:
        user_count = len((await session.scalars(select(User))).all())
        assignment_count = len((await session.scalars(select(UserRole))).all())
        audit_count = len((await session.scalars(select(AuditEvent))).all())
    await first_resources.dispose()
    await second_resources.dispose()

    assert len(successes) == 1
    assert len(failures) == 1
    assert user_count == assignment_count == audit_count == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_audit_failure_rolls_back_user_and_role_assignment() -> None:
    with psycopg.connect(_database_url().replace("+psycopg", "")) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            create function reject_bootstrap_audit() returns trigger language plpgsql as $$
            begin
                raise exception 'forced audit failure';
            end;
            $$
            """
        )
        cursor.execute(
            """
            create trigger reject_bootstrap_audit_before_insert
            before insert on audit_events
            for each row execute function reject_bootstrap_audit()
            """
        )

    settings = _settings()
    bootstrapper, resources = _bootstrapper(settings)
    try:
        with pytest.raises(Exception, match="forced audit failure"):  # noqa: B017
            await bootstrapper.create(_identity())
        async with resources.session_factory() as session:
            assert (await session.scalars(select(User))).all() == []
            assert (await session.scalars(select(UserRole))).all() == []
            assert (await session.scalars(select(AuditEvent))).all() == []
    finally:
        await resources.dispose()
        with psycopg.connect(_database_url().replace("+psycopg", "")) as connection, connection.cursor() as cursor:
            cursor.execute("drop trigger if exists reject_bootstrap_audit_before_insert on audit_events")
            cursor.execute("drop function if exists reject_bootstrap_audit()")


@pytest.mark.integration
def test_cli_prints_temporary_password_only_for_first_success() -> None:
    runner = CliRunner()
    environment = {
        "AVICOLA_DATABASE_URL": _database_url(),
        "AVICOLA_SESSION_HMAC_KEY": SESSION_HMAC_KEY,
    }
    arguments = [
        "bootstrap-admin",
        "--username",
        "initial.admin",
        "--email",
        "initial.admin@example.test",
        "--name",
        "Initial Administrator",
    ]

    first = runner.invoke(app, arguments, env=environment)
    assert first.exit_code == 0, first.output
    password_lines = [line for line in first.output.splitlines() if line.startswith("Contraseña temporal: ")]
    assert len(password_lines) == 1
    temporary_password = password_lines[0].partition(": ")[2]

    second = runner.invoke(app, arguments, env=environment)

    assert second.exit_code != 0
    assert "ya fue realizado" in second.output
    assert "Contraseña temporal:" not in second.output
    assert temporary_password not in second.output


@pytest.mark.integration
def test_cli_does_not_echo_invalid_sensitive_configuration() -> None:
    sensitive_invalid_value = "sensitive-invalid-hmac-value"
    result = CliRunner().invoke(
        app,
        [
            "bootstrap-admin",
            "--username",
            "initial.admin",
            "--email",
            "initial.admin@example.test",
            "--name",
            "Initial Administrator",
        ],
        env={
            "AVICOLA_DATABASE_URL": _database_url(),
            "AVICOLA_SESSION_HMAC_KEY": sensitive_invalid_value,
        },
    )

    assert result.exit_code != 0
    assert sensitive_invalid_value not in result.output
    assert "Contraseña temporal:" not in result.output
