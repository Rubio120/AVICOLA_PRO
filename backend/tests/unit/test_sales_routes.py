from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
from fastapi.routing import APIRoute
from pydantic import ValidationError
from starlette.requests import Request

from avicola_pro.modules.sales.api.routes import DocumentPayload, OrderPayload, build_sales_router
from avicola_pro.shared.infrastructure.database import DatabaseResources


def test_sales_order_payload_rejects_unknown_server_fields() -> None:
    with pytest.raises(ValidationError):
        OrderPayload(customer_id=uuid4(), order_date=date.today(), lines=[], approved=True)  # type: ignore[call-arg]


def test_sales_order_payload_requires_a_supported_channel() -> None:
    from pydantic import ValidationError

    from avicola_pro.modules.sales.api.routes import OrderPayload

    common = {
        "customer_id": uuid4(),
        "order_date": date.today(),
        "lines": [{"product_id": uuid4(), "quantity": "1", "unit_price": "2"}],
    }
    with pytest.raises(ValidationError):
        OrderPayload(**common)
    with pytest.raises(ValidationError):
        OrderPayload(**common, channel="DIRECT")
    assert OrderPayload(**common, channel="WHOLESALE").channel == "WHOLESALE"
    assert OrderPayload(**common, channel="RETAIL").channel == "RETAIL"


def test_invoice_channel_is_required_and_credit_note_channel_can_be_inherited() -> None:
    common = {
        "customer_id": uuid4(),
        "series": "A",
        "document_date": date.today(),
        "lines": [{"description": "Producto", "quantity": "1", "unit_price": "2", "tax_rate": "0"}],
    }
    with pytest.raises(ValidationError):
        DocumentPayload(**common, document_type="INVOICE")
    invoice = DocumentPayload(**common, document_type="INVOICE", channel="RETAIL")
    credit_note = DocumentPayload(**common, document_type="CREDIT_NOTE", original_document_id=uuid4())
    assert invoice.channel == "RETAIL"
    assert credit_note.channel is None


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

    database = cast(DatabaseResources, SimpleNamespace(session_factory=Factory()))
    router = build_sales_router(
        object(),
        object(),
        database,
        SimpleNamespace(add=lambda *_: None),
        "session",
        security_events=SimpleNamespace(write=lambda *_: None),
    )
    sales_routes = [route for route in router.routes if isinstance(route, APIRoute)]
    route = next(
        route for route in sales_routes if route.path == "/api/v1/sales/orders" and "POST" in (route.methods or set())
    )
    request = Request({"type": "http", "method": "POST", "path": "/", "headers": [], "query_string": b""})
    request.state.correlation_id = str(uuid4())
    payload = OrderPayload(
        customer_id=uuid4(),
        order_date=date.today(),
        channel="WHOLESALE",
        lines=[{"product_id": uuid4(), "quantity": Decimal("2"), "unit_price": Decimal("10")}],
    )
    result = await route.endpoint(payload, request, SimpleNamespace(id=uuid4(), username="seller"), object())
    assert result.status == "DRAFT"
