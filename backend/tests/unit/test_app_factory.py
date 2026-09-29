import pytest
from httpx import ASGITransport, AsyncClient

from avicola_pro.bootstrap.app import create_app
from avicola_pro.shared.infrastructure.config import Settings

VALID_DATABASE_URL = "postgresql+psycopg://avicola:local-password@127.0.0.1:5432/avicola_pro"
VALID_SESSION_HMAC_KEY = "jUrUWz89-ZPO0xh7ppVRm50Pt-un53S_NSfNCACPXaM"


def test_app_factory_creates_isolated_application_instances() -> None:
    settings = Settings(
        _env_file=None,
        database_url=VALID_DATABASE_URL,
        session_hmac_key=VALID_SESSION_HMAC_KEY,
    )

    first = create_app(settings)
    second = create_app(settings)
    first.state.marker = "first"

    assert first is not second
    assert not hasattr(second.state, "marker")
    assert first.title == "AVÍCOLA PRO API"


@pytest.mark.asyncio
async def test_app_factory_applies_exact_cors_allowlist() -> None:
    settings = Settings(
        _env_file=None,
        database_url=VALID_DATABASE_URL,
        session_hmac_key=VALID_SESSION_HMAC_KEY,
        cors_origins=["https://allowed.example"],
    )

    async with AsyncClient(transport=ASGITransport(app=create_app(settings)), base_url="http://test") as client:
        allowed = await client.options(
            "/health/live",
            headers={
                "Origin": "https://allowed.example",
                "Access-Control-Request-Method": "GET",
            },
        )
        denied = await client.options(
            "/health/live",
            headers={
                "Origin": "https://denied.example",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert allowed.headers["access-control-allow-origin"] == "https://allowed.example"
    assert "access-control-allow-origin" not in denied.headers
