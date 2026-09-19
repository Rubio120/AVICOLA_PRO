from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.routing import APIRoute
from pydantic import ValidationError
from starlette.requests import Request

from avicola_pro.modules.production.api.routes import AdjustmentPayload, FlockPayload, build_production_router
from avicola_pro.modules.production.infrastructure.models import Flock


def test_flock_payload_accepts_decimal_quantity() -> None:
    payload = FlockPayload(
        code="F-1", purpose="Broilers", entry_date=date(2026, 9, 19), planned_initial_quantity=Decimal("10")
    )
    assert payload.planned_initial_quantity == Decimal("10")


def test_flock_payload_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        FlockPayload(
            code="F-1", purpose="Broilers", entry_date=date(2026, 9, 19), planned_initial_quantity=10, admin=True
        )  # type: ignore[call-arg]


def test_adjustment_payload_rejects_operational_type() -> None:
    with pytest.raises(ValidationError):
        AdjustmentPayload(adjustment_type="MORTALITY", occurred_on=date(2026, 9, 19), quantity=1, reason="x")


@pytest.mark.asyncio
async def test_production_list_and_create_endpoints_use_audit_adapter() -> None:
    class Result:
        def all(self) -> list[Flock]:
            return []

    class Session:
        def add(self, _: object) -> None:
            return None

        async def flush(self) -> None:
            return None

        async def scalars(self, _: object) -> Result:
            return Result()

        def begin(self) -> "Session":
            return self

        async def __aenter__(self) -> "Session":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

    class SessionContext:
        async def __aenter__(self) -> Session:
            return Session()

        async def __aexit__(self, *_: object) -> None:
            return None

    class Database:
        def session_factory(self) -> SessionContext:
            return SessionContext()

    audit = SimpleNamespace(add=lambda *_: None)
    router = build_production_router(object(), object(), Database(), audit, "session")  # type: ignore[arg-type]
    list_route = next(
        route
        for route in router.routes
        if isinstance(route, APIRoute)
        and route.path == "/api/v1/production/flocks"
        and "GET" in (route.methods or set())
    )
    list_endpoint = list_route.endpoint
    assert await list_endpoint(object()) == []
    request = Request({"type": "http", "method": "POST", "path": "/", "headers": [], "query_string": b""})
    request.state.correlation_id = str(uuid4())
    create_route = next(
        route
        for route in router.routes
        if isinstance(route, APIRoute)
        and route.path == "/api/v1/production/flocks"
        and "POST" in (route.methods or set())
    )
    create_endpoint = create_route.endpoint
    payload = FlockPayload(
        code="F-1", purpose="Broilers", entry_date=date(2026, 9, 19), planned_initial_quantity=Decimal("10")
    )
    user = SimpleNamespace(id=uuid4(), username="test-user")
    result = await create_endpoint(payload, request, user, object())
    assert result.code == "F-1"
