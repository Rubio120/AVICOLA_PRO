from __future__ import annotations

from unittest.mock import Mock

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from avicola_pro.bootstrap.app import create_app
from avicola_pro.shared.api import error_handlers
from avicola_pro.shared.api.errors import ConflictError
from avicola_pro.shared.infrastructure.config import Settings

DATABASE_URL = "postgresql+psycopg://avicola:password@127.0.0.1:5432/avicola_pro"
SESSION_HMAC_KEY = "jUrUWz89-ZPO0xh7ppVRm50Pt-un53S_NSfNCACPXaM"


class SamplePayload(BaseModel):
    quantity: int


def build_test_app() -> FastAPI:
    app = create_app(Settings(_env_file=None, database_url=DATABASE_URL, session_hmac_key=SESSION_HMAC_KEY))

    @app.get("/conflict")
    async def conflict() -> None:
        raise ConflictError(code="duplicate_resource", detail="Resource already exists")

    @app.get("/missing")
    async def missing() -> None:
        raise HTTPException(status_code=404, detail="Not found")

    @app.post("/validated")
    async def validated(_: SamplePayload) -> dict[str, bool]:
        return {"ok": True}

    @app.get("/crash")
    async def crash() -> None:
        raise ValueError("secret-value")

    return app


@pytest.mark.asyncio
async def test_application_error_uses_problem_details_contract() -> None:
    async with AsyncClient(transport=ASGITransport(app=build_test_app()), base_url="http://test") as client:
        response = await client.get("/conflict", headers={"X-Correlation-ID": "problem-request"})

    assert response.status_code == 409
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json() == {
        "type": "about:blank",
        "title": "Conflict",
        "status": 409,
        "detail": "Resource already exists",
        "instance": "/conflict",
        "code": "duplicate_resource",
        "correlation_id": "problem-request",
    }


@pytest.mark.asyncio
async def test_validation_error_has_safe_field_errors() -> None:
    async with AsyncClient(transport=ASGITransport(app=build_test_app()), base_url="http://test") as client:
        response = await client.post("/validated", json={"quantity": "not-an-int"})

    body = response.json()
    assert response.status_code == 422
    assert body["code"] == "validation_error"
    assert body["field_errors"][0]["field"] == "quantity"
    assert "input" not in body["field_errors"][0]


@pytest.mark.asyncio
async def test_unhandled_error_does_not_leak_details_or_traceback() -> None:
    transport = ASGITransport(app=build_test_app(), raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/crash")

    rendered = response.text.lower()
    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["detail"] == "An unexpected error occurred"
    assert "secret-value" not in rendered
    assert "traceback" not in rendered


@pytest.mark.asyncio
async def test_unhandled_error_is_logged_without_exception_message(monkeypatch: pytest.MonkeyPatch) -> None:
    logger = Mock()
    monkeypatch.setattr(error_handlers, "logger", logger)
    transport = ASGITransport(app=build_test_app(), raise_app_exceptions=False)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/crash", headers={"X-Correlation-ID": "error-request"})

    logger.error.assert_called_once_with(
        "unhandled_request_error",
        correlation_id="error-request",
        exception_type="ValueError",
        path="/crash",
    )
    assert "secret-value" not in repr(logger.error.call_args)


@pytest.mark.asyncio
async def test_http_error_is_normalized() -> None:
    async with AsyncClient(transport=ASGITransport(app=build_test_app()), base_url="http://test") as client:
        response = await client.get("/missing")

    assert response.status_code == 404
    assert response.json()["code"] == "http_error"
