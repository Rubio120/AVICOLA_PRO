from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from avicola_pro.bootstrap.app import create_app
from avicola_pro.modules.identity.application.credentials import Argon2PasswordService, PasswordPolicy
from avicola_pro.modules.identity.infrastructure.models import Role, User, UserRole
from avicola_pro.shared.infrastructure.config import Settings
from avicola_pro.shared.infrastructure.database import DatabaseResources, create_database_resources

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PASSWORD = "Correct-Horse-Avicola-47!"  # noqa: S105
SESSION_HMAC_KEY = "jUrUWz89-ZPO0xh7ppVRm50Pt-un53S_NSfNCACPXaM"


def _database_url() -> str:
    return os.environ["AVICOLA_TEST_DATABASE_URL"]


@pytest.fixture(scope="module", autouse=True)
def migrated_database() -> Iterator[None]:
    import subprocess
    import sys

    environment = os.environ.copy()
    environment["AVICOLA_DATABASE_URL"] = _database_url()
    environment["AVICOLA_SESSION_HMAC_KEY"] = SESSION_HMAC_KEY
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND_ROOT, env=environment, check=True)
    yield


@pytest.fixture(autouse=True)
def clean_database() -> Iterator[None]:
    with psycopg.connect(_database_url().replace("+psycopg", "")) as connection, connection.cursor() as cursor:
        cursor.execute(
            "truncate table security_events, audit_events, sessions, user_roles, "
            "role_permissions, users restart identity"
        )
        cursor.execute(
            "insert into role_permissions (role_id, permission_id) "
            "select r.id, p.id from roles r cross join permissions p where r.code = 'administrator'"
        )
    yield


@pytest_asyncio.fixture
async def context() -> AsyncIterator[tuple[DatabaseResources, AsyncClient]]:
    settings = Settings(_env_file=None, database_url=_database_url(), session_hmac_key=SESSION_HMAC_KEY)
    resources = create_database_resources(settings)
    app = create_app(settings, database=resources)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield resources, client
    await resources.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_administrator_can_read_catalog_and_create_audited_user(
    context: tuple[DatabaseResources, AsyncClient],
) -> None:
    resources, client = context
    password_service = Argon2PasswordService(PasswordPolicy(12, 128), time_cost=1, memory_cost_kib=8_192, parallelism=1)
    admin = User(
        id=uuid4(),
        username="admin",
        email="admin@example.test",
        display_name="Admin",
        password_hash=password_service.hash(PASSWORD),
        token_version=1,
    )
    async with resources.session_factory() as session, session.begin():
        session.add(admin)
        role = await session.scalar(select(Role).where(Role.code == "administrator"))
        assert role is not None
        session.add(UserRole(user_id=admin.id, role_id=role.id))

    login = await client.post("/api/v1/auth/login", json={"identity": "admin", "password": PASSWORD})
    assert login.status_code == 200
    csrf = login.headers["x-csrf-token"]
    permissions = await client.get("/api/v1/permissions")
    assert permissions.status_code == 200
    assert permissions.json()["total"] > 0

    created = await client.post(
        "/api/v1/users",
        json={
            "username": "operator",
            "email": "operator@example.test",
            "display_name": "Operator",
            "password": PASSWORD,
        },
        headers={"X-CSRF-Token": csrf, "X-Correlation-ID": str(UUID(int=1))},
    )
    assert created.status_code == 201
    assert created.json()["must_change_password"] is True
    audit = await client.get("/api/v1/audit-events")
    assert audit.status_code == 200
    assert any(item["action"] == "users.create" for item in audit.json()["items"])
