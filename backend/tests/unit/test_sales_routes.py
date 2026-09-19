from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.routing import APIRoute
from pydantic import ValidationError
from starlette.requests import Request

from avicola_pro.modules.sales.api.routes import OrderPayload, build_sales_router


def test_sales_order_payload_rejects_unknown_server_fields() -> None:
    with pytest.raises(ValidationError):
        OrderPayload(customer_id=uuid4(), order_date=date.today(), lines=[], approved=True)  # type: ignore[call-arg]


@pytest.mark.asyncio
async def test_create_sales_order_endpoint_persists_and_audits() -> None:
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

    router = build_sales_router(
        object(), object(), SimpleNamespace(session_factory=Factory()), SimpleNamespace(add=lambda *_: None), "session"
    )  # type: ignore[arg-type]
    route = next(
        route
        for route in router.routes
        if isinstance(route, APIRoute) and route.path == "/api/v1/sales/orders" and "POST" in (route.methods or set())
    )
    request = Request({"type": "http", "method": "POST", "path": "/", "headers": [], "query_string": b""})
    request.state.correlation_id = str(uuid4())
    payload = OrderPayload(
        customer_id=uuid4(),
        order_date=date.today(),
        lines=[{"product_id": uuid4(), "quantity": Decimal("2"), "unit_price": Decimal("10")}],
    )
    result = await route.endpoint(payload, request, SimpleNamespace(id=uuid4(), username="seller"), object())
    assert result.status == "DRAFT"
