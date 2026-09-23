from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import select, update

from avicola_pro.bootstrap.app import create_app
from avicola_pro.modules.audit.infrastructure.models import SecurityEvent
from avicola_pro.modules.identity.application.credentials import Argon2PasswordService, PasswordPolicy
from avicola_pro.modules.identity.infrastructure.models import Session, User
from avicola_pro.shared.infrastructure.config import Settings
from avicola_pro.shared.infrastructure.database import DatabaseResources, create_database_resources

BACKEND_ROOT = Path(__file__).resolve().parents[2]
SESSION_HMAC_KEY = "jUrUWz89-ZPO0xh7ppVRm50Pt-un53S_NSfNCACPXaM"
PASSWORD = "Correct-Horse-Avicola-47!"  # noqa: S105 - fictitious integration credential
NEW_PASSWORD = "Replaced-Horse-Avicola-92!"  # noqa: S105 - fictitious integration credential
WRONG_PASSWORD_ONE = "Wrong-Password-Avicola-11!"  # noqa: S105 - fictitious integration credential
WRONG_PASSWORD_TWO = "Wrong-Password-Avicola-22!"  # noqa: S105 - fictitious integration credential


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
def empty_authentication_state() -> Iterator[None]:
    with psycopg.connect(_database_url().replace("+psycopg", "")) as connection, connection.cursor() as cursor:
        cursor.execute("truncate table security_events, sessions, user_roles, users restart identity cascade")
    yield


@pytest_asyncio.fixture
async def auth_context() -> AsyncIterator[tuple[DatabaseResources, AsyncClient]]:
    settings = Settings(
        _env_file=None,
        database_url=_database_url(),
        session_hmac_key=SESSION_HMAC_KEY,
        session_cookie_path="/api/v1",
        session_idle_timeout_seconds=300,
        session_absolute_timeout_seconds=1_800,
        session_rotation_interval_seconds=60,
        login_max_failed_attempts=2,
        login_lockout_seconds=60,
        login_rate_limit_attempts=20,
    )
    resources = create_database_resources(settings)
    app = create_app(settings, database=resources)
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        yield resources, client
    await resources.dispose()


async def _create_user(
    resources: DatabaseResources,
    *,
    username: str = "operator",
    status: str = "ACTIVE",
    must_change_password: bool = False,
) -> User:
    password_service = Argon2PasswordService(
        PasswordPolicy(min_length=12, max_length=128),
        time_cost=1,
        memory_cost_kib=8_192,
        parallelism=1,
    )
    user = User(
        id=uuid4(),
        username=username,
        email=f"{username}@example.test",
        display_name="Test Operator",
        password_hash=password_service.hash(PASSWORD),
        status=status,
        must_change_password=must_change_password,
        failed_login_attempts=0,
        token_version=1,
    )
    async with resources.session_factory() as session, session.begin():
        session.add(user)
    return user


async def _login(client: AsyncClient, *, username: str = "operator", password: str = PASSWORD) -> Response:
    return await client.post(
        "/api/v1/auth/login",
        json={"identity": username, "password": password},
        headers={"User-Agent": "integration-agent", "X-Correlation-ID": "login-correlation"},
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_issues_secure_opaque_cookie_and_persists_only_hashes(
    auth_context: tuple[DatabaseResources, AsyncClient],
) -> None:
    resources, client = auth_context
    user = await _create_user(resources)

    response = await _login(client)

    assert response.status_code == 200
    assert response.json() == {
        "id": str(user.id),
        "username": "operator",
        "email": "operator@example.test",
        "display_name": "Test Operator",
        "must_change_password": False,
    }
    session_token = client.cookies.get("avicola_session")
    csrf_token = response.headers["x-csrf-token"]
    set_cookie = response.headers["set-cookie"].lower()
    assert session_token
    assert csrf_token
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie
    assert "path=/api/v1" in set_cookie
    assert "secure" not in set_cookie
    assert session_token not in response.text
    assert PASSWORD not in response.text

    async with resources.session_factory() as session:
        stored = (await session.scalars(select(Session))).one()
        event = (await session.scalars(select(SecurityEvent))).one()
    assert stored.token_hash != session_token.encode()
    assert stored.csrf_hash != csrf_token.encode()
    assert str(stored.ip_address) == "127.0.0.1"
    assert stored.user_agent == "integration-agent"
    assert event.event_type == "auth.login"
    assert event.outcome == "SUCCESS"
    assert session_token not in str(event.metadata_)
    assert csrf_token not in str(event.metadata_)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_operational_permission_denial_is_persisted_without_changing_403(
    auth_context: tuple[DatabaseResources, AsyncClient],
) -> None:
    resources, client = auth_context
    user = await _create_user(resources)
    assert (await _login(client)).status_code == 200
    correlation_id = UUID("1cb538a7-0e37-4b7c-9e59-101010101010")

    denied = await client.get(
        "/api/v1/inventory/balances",
        headers={"X-Correlation-ID": str(correlation_id), "User-Agent": "permission-audit-test"},
    )

    assert denied.status_code == 403
    assert denied.json()["code"] == "permission_denied"
    async with resources.session_factory() as session:
        event = (
            await session.scalars(
                select(SecurityEvent).where(
                    SecurityEvent.event_type == "authorization.denied",
                    SecurityEvent.correlation_id == correlation_id,
                )
            )
        ).one()
    assert event.actor_user_id == user.id
    assert event.actor_username == user.username
    assert event.outcome == "DENIED"
    assert event.user_agent == "permission-audit-test"
    assert event.metadata_ == {
        "permission": "inventory.products.read",
        "resource_type": "inventory",
        "resource_id": "/api/v1/inventory/balances",
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_failures_are_generic_and_progressively_lock_the_user(
    auth_context: tuple[DatabaseResources, AsyncClient],
) -> None:
    resources, client = auth_context
    user = await _create_user(resources)

    missing = await _login(client, username="missing")
    inactive_user = await _create_user(resources, username="inactive", status="INACTIVE")
    inactive = await _login(client, username=inactive_user.username)
    first = await _login(client, password=WRONG_PASSWORD_ONE)
    second = await _login(client, password=WRONG_PASSWORD_TWO)
    locked = await _login(client)

    for response in (missing, inactive, first, second, locked):
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid credentials"
        assert response.json()["code"] == "invalid_credentials"
    assert missing.text == inactive.text
    async with resources.session_factory() as session:
        persisted = await session.get(User, user.id)
        events = (await session.scalars(select(SecurityEvent).order_by(SecurityEvent.created_at))).all()
    assert persisted is not None
    assert persisted.failed_login_attempts == 2
    assert persisted.locked_until is not None
    assert any(event.event_type == "auth.locked" and event.outcome == "DENIED" for event in events)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_me_rejects_expired_session_and_logout_requires_csrf(
    auth_context: tuple[DatabaseResources, AsyncClient],
) -> None:
    resources, client = auth_context
    await _create_user(resources)
    login = await _login(client)
    csrf_token = login.headers["x-csrf-token"]

    missing_csrf = await client.post("/api/v1/auth/logout")
    assert missing_csrf.status_code == 403
    assert missing_csrf.json()["code"] == "csrf_validation_failed"
    async with resources.session_factory() as session:
        csrf_denials = (
            await session.scalars(select(SecurityEvent).where(SecurityEvent.event_type == "auth.csrf_denied"))
        ).all()
    assert len(csrf_denials) == 1
    assert csrf_denials[0].outcome == "DENIED"

    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200

    logout = await client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf_token})
    assert logout.status_code == 204
    assert "max-age=0" in logout.headers["set-cookie"].lower()
    assert (await client.get("/api/v1/auth/me")).status_code == 401

    relogin = await _login(client)
    assert relogin.status_code == 200
    async with resources.session_factory() as session, session.begin():
        stored = (await session.scalars(select(Session).where(Session.revoked_at.is_(None)))).one()
        await session.execute(
            update(Session)
            .where(Session.id == stored.id)
            .values(
                created_at=datetime.now(UTC) - timedelta(seconds=301),
                last_used_at=datetime.now(UTC) - timedelta(seconds=301),
                idle_expires_at=datetime.now(UTC) - timedelta(seconds=1),
            )
        )
    expired = await client.get("/api/v1/auth/me")
    assert expired.status_code == 401
    assert expired.json()["code"] == "invalid_session"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_refresh_rotates_when_due_and_reuse_revokes_the_entire_family(
    auth_context: tuple[DatabaseResources, AsyncClient],
) -> None:
    resources, client = auth_context
    await _create_user(resources)
    login = await _login(client)
    old_token = client.cookies.get("avicola_session")
    assert old_token is not None
    old_csrf = login.headers["x-csrf-token"]
    async with resources.session_factory() as session, session.begin():
        await session.execute(
            update(Session).values(
                created_at=datetime.now(UTC) - timedelta(seconds=61),
                last_used_at=datetime.now(UTC) - timedelta(seconds=61),
            )
        )
    assert (await client.get("/api/v1/auth/me")).status_code == 200

    refreshed = await client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": old_csrf})

    assert refreshed.status_code == 204
    new_token = client.cookies.get("avicola_session")
    assert new_token and new_token != old_token
    new_csrf = refreshed.headers["x-csrf-token"]
    assert new_csrf != old_csrf

    attacker = AsyncClient(transport=client._transport, base_url="http://test")  # noqa: SLF001
    try:
        attacker.cookies.set("avicola_session", old_token, path="/api/v1")
        reused = await attacker.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": old_csrf})
    finally:
        await attacker.aclose()

    assert reused.status_code == 401
    assert reused.json()["code"] == "session_reused"
    assert (await client.get("/api/v1/auth/me")).status_code == 401
    async with resources.session_factory() as session:
        family = (await session.scalars(select(Session))).all()
        events = (await session.scalars(select(SecurityEvent))).all()
    assert len(family) == 2
    assert all(item.revoked_at is not None for item in family)
    assert any(event.event_type == "auth.session_reuse" for event in events)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_forced_password_change_restricts_refresh_revokes_other_sessions_and_reissues(
    auth_context: tuple[DatabaseResources, AsyncClient],
) -> None:
    resources, client = auth_context
    user = await _create_user(resources, must_change_password=True)
    first_login = await _login(client)
    first_csrf = first_login.headers["x-csrf-token"]
    other = AsyncClient(transport=client._transport, base_url="http://test")  # noqa: SLF001
    try:
        other_login = await _login(other)
        assert other_login.status_code == 200

        assert (await client.get("/api/v1/auth/me")).status_code == 200
        refresh = await client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": first_csrf})
        assert refresh.status_code == 403
        assert refresh.json()["code"] == "password_change_required"

        invalid_extra = await client.post(
            "/api/v1/auth/change-password",
            json={"current_password": PASSWORD, "new_password": NEW_PASSWORD, "unexpected": True},
            headers={"X-CSRF-Token": first_csrf},
        )
        assert invalid_extra.status_code == 422

        changed = await client.post(
            "/api/v1/auth/change-password",
            json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
            headers={"X-CSRF-Token": first_csrf},
        )
        assert changed.status_code == 200
        assert changed.json()["must_change_password"] is False
        assert changed.headers["x-csrf-token"] != first_csrf
        assert (await client.get("/api/v1/auth/me")).status_code == 200
        assert (await other.get("/api/v1/auth/me")).status_code == 401
    finally:
        await other.aclose()

    async with resources.session_factory() as session:
        persisted = await session.get(User, user.id)
        sessions = (await session.scalars(select(Session).where(Session.user_id == user.id))).all()
    assert persisted is not None
    assert persisted.must_change_password is False
    assert persisted.token_version == 2
    assert Argon2PasswordService(PasswordPolicy(12, 128)).verify(NEW_PASSWORD, persisted.password_hash).is_valid
    assert sum(item.revoked_at is None for item in sessions) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_secure_cookie_setting_and_cors_allow_the_csrf_header() -> None:
    settings = Settings(
        _env_file=None,
        database_url=_database_url(),
        session_hmac_key=SESSION_HMAC_KEY,
        session_cookie_secure=True,
        cors_origins=["https://allowed.example"],
    )
    resources = create_database_resources(settings)
    await _create_user(resources)
    app = create_app(settings, database=resources)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
        login = await _login(client)
        preflight = await client.options(
            "/api/v1/auth/logout",
            headers={
                "Origin": "https://allowed.example",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "X-CSRF-Token",
            },
        )
    await resources.dispose()

    assert login.status_code == 200
    assert "secure" in login.headers["set-cookie"].lower()
    assert "x-csrf-token" in preflight.headers["access-control-allow-headers"].lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_forced_password_change_is_enforced_for_future_api_routes() -> None:
    settings = Settings(_env_file=None, database_url=_database_url(), session_hmac_key=SESSION_HMAC_KEY)
    resources = create_database_resources(settings)
    await _create_user(resources, must_change_password=True)
    app = create_app(settings, database=resources)

    @app.get("/api/v1/protected")
    async def protected() -> dict[str, bool]:
        return {"ok": True}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await _login(client)).status_code == 200
        denied = await client.get("/api/v1/protected")
        allowed = await client.get("/api/v1/auth/me")
    await resources.dispose()

    assert denied.status_code == 403
    assert denied.json()["code"] == "password_change_required"
    assert allowed.status_code == 200
