from __future__ import annotations

from collections.abc import Awaitable, Callable

import pytest
from httpx import ASGITransport, AsyncClient

from avicola_pro.bootstrap.app import create_app
from avicola_pro.shared.infrastructure.config import Settings

DATABASE_URL = "postgresql+psycopg://avicola:password@127.0.0.1:5432/avicola_pro"
SESSION_HMAC_KEY = "jUrUWz89-ZPO0xh7ppVRm50Pt-un53S_NSfNCACPXaM"


class DatabaseStub:
    def __init__(self, check: Callable[[], Awaitable[None]]) -> None:
        self._check = check

    async def check_ready(self) -> None:
        await self._check()

    async def dispose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_liveness_does_not_query_database() -> None:
    async def fail_if_called() -> None:
        raise AssertionError("liveness must not query PostgreSQL")

    settings = Settings(_env_file=None, database_url=DATABASE_URL, session_hmac_key=SESSION_HMAC_KEY)
    app = create_app(settings, database=DatabaseStub(fail_if_called))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_readiness_reports_database_availability() -> None:
    async def ready() -> None:
        return None

    settings = Settings(_env_file=None, database_url=DATABASE_URL, session_hmac_key=SESSION_HMAC_KEY)
    app = create_app(settings, database=DatabaseStub(ready))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "available"}


@pytest.mark.asyncio
async def test_readiness_failure_is_safe_problem_details() -> None:
    async def unavailable() -> None:
        raise OSError("postgresql://user:secret@database/internal")

    settings = Settings(_env_file=None, database_url=DATABASE_URL, session_hmac_key=SESSION_HMAC_KEY)
    app = create_app(settings, database=DatabaseStub(unavailable))
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "database_unavailable"
    assert "secret" not in response.text
