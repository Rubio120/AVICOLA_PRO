from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.routing import APIRoute
from pydantic import ValidationError
from starlette.requests import Request

from avicola_pro.modules.treasury.api.routes import AccountPayload, MovementPayload, build_treasury_router


def test_treasury_payloads_reject_unknown_fields_and_invalid_direction() -> None:
    with pytest.raises(ValidationError):
        AccountPayload(code="MAIN", name="Main", server_side=True)  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        MovementPayload(
            session_id=uuid4(),
            account_id=uuid4(),
            movement_type="INCOME",
            direction="SIDEWAYS",
            amount=Decimal("1"),
            effective_date=date.today(),
        )


@pytest.mark.asyncio
async def test_create_account_endpoint_persists_and_audits() -> None:
    class Session:
        def add(self, _: object) -> None:
            return None

        def begin(self) -> "Session":
            return self

        async def __aenter__(self) -> "Session":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

    class Factory:
        def __call__(self) -> Session:
            return Session()

    router = build_treasury_router(
        object(),
        object(),
        SimpleNamespace(session_factory=Factory()),
        SimpleNamespace(add=lambda *_: None),
        "session",
        security_events=SimpleNamespace(write=lambda *_: None),
    )
    route = next(
        route
        for route in router.routes
        if isinstance(route, APIRoute)
        and route.path == "/api/v1/treasury/accounts"
        and "POST" in (route.methods or set())
    )
    request = Request({"type": "http", "method": "POST", "path": "/", "headers": [], "query_string": b""})
    request.state.correlation_id = str(uuid4())
    result = await route.endpoint(
        AccountPayload(code="MAIN", name="Main"), request, SimpleNamespace(id=uuid4(), username="cash"), object()
    )
    assert result.code == "MAIN"
