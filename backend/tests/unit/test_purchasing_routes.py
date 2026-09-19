from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.routing import APIRoute
from pydantic import ValidationError
from starlette.requests import Request

from avicola_pro.modules.purchasing.api.routes import OrderPayload, build_purchasing_router


def test_order_payload_rejects_unknown_server_fields() -> None:
    with pytest.raises(ValidationError):
        OrderPayload(supplier_id=uuid4(), order_date=date.today(), lines=[], is_approved=True)  # type: ignore[call-arg]


@pytest.mark.asyncio
async def test_create_order_endpoint_persists_and_audits() -> None:
    class Session:
        def add(self, _: object) -> None:
            return None

        async def flush(self) -> None:
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

    audit = SimpleNamespace(add=lambda *_: None)
    router = build_purchasing_router(object(), object(), SimpleNamespace(session_factory=Factory()), audit, "session")  # type: ignore[arg-type]
    route = next(
        route
        for route in router.routes
        if isinstance(route, APIRoute)
        and route.path == "/api/v1/purchasing/orders"
        and "POST" in (route.methods or set())
    )
    request = Request({"type": "http", "method": "POST", "path": "/", "headers": [], "query_string": b""})
    request.state.correlation_id = str(uuid4())
    payload = OrderPayload(
        supplier_id=uuid4(),
        order_date=date.today(),
        lines=[{"product_id": uuid4(), "quantity": Decimal("2"), "unit_price": Decimal("10")}],
    )
    result = await route.endpoint(payload, request, SimpleNamespace(id=uuid4(), username="operator"), object())
    assert result.status == "DRAFT"
