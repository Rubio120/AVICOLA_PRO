from __future__ import annotations

import asyncio
import uuid

import pytest
import structlog.contextvars
from httpx import ASGITransport, AsyncClient

from avicola_pro.bootstrap.app import create_app
from avicola_pro.shared.infrastructure.config import Settings

DATABASE_URL = "postgresql+psycopg://avicola:password@127.0.0.1:5432/avicola_pro"
SESSION_HMAC_KEY = "jUrUWz89-ZPO0xh7ppVRm50Pt-un53S_NSfNCACPXaM"


@pytest.mark.asyncio
async def test_correlation_id_is_generated_and_returned() -> None:
    app = create_app(Settings(_env_file=None, database_url=DATABASE_URL, session_hmac_key=SESSION_HMAC_KEY))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/live")

    uuid.UUID(response.headers["X-Correlation-ID"])


@pytest.mark.asyncio
async def test_valid_correlation_id_is_propagated() -> None:
    app = create_app(Settings(_env_file=None, database_url=DATABASE_URL, session_hmac_key=SESSION_HMAC_KEY))

    @app.get("/correlation-context")
    async def correlation_context() -> dict[str, object]:
        return structlog.contextvars.get_contextvars()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/correlation-context", headers={"X-Correlation-ID": "request-123"})

    assert response.headers["X-Correlation-ID"] == "request-123"
    assert response.json()["correlation_id"] == "request-123"


@pytest.mark.asyncio
async def test_correlation_context_is_isolated_between_concurrent_requests() -> None:
    app = create_app(Settings(_env_file=None, database_url=DATABASE_URL, session_hmac_key=SESSION_HMAC_KEY))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first, second = await asyncio.gather(
            client.get("/health/live", headers={"X-Correlation-ID": "first-request"}),
            client.get("/health/live", headers={"X-Correlation-ID": "second-request"}),
        )

    assert first.headers["X-Correlation-ID"] == "first-request"
    assert second.headers["X-Correlation-ID"] == "second-request"


@pytest.mark.asyncio
async def test_oversized_correlation_id_is_replaced() -> None:
    app = create_app(Settings(_env_file=None, database_url=DATABASE_URL, session_hmac_key=SESSION_HMAC_KEY))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/live", headers={"X-Correlation-ID": "x" * 200})

    assert response.headers["X-Correlation-ID"] != "x" * 200
    uuid.UUID(response.headers["X-Correlation-ID"])
