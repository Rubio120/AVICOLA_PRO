from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
from fastapi.routing import APIRoute
from pydantic import ValidationError
from starlette.requests import Request

from avicola_pro.modules.inventory.api.routes import (
    EggCategoryPayload,
    EggConversionPayload,
    build_inventory_router,
)
from avicola_pro.shared.api.errors import ForbiddenError
from avicola_pro.shared.infrastructure.database import DatabaseResources


def test_egg_category_payload_requires_explicit_business_configuration() -> None:
    payload = EggCategoryPayload(
        code="SYNTHETIC",
        name="Synthetic test category",
        product_id=uuid4(),
        is_saleable=False,
        is_active=True,
    )
    assert payload.is_saleable is False
    with pytest.raises(ValidationError):
        EggCategoryPayload(
            code="MISSING-RULE",
            name="Missing rule",
            product_id=uuid4(),
            is_active=True,
        )  # type: ignore[call-arg]


def test_egg_conversion_payload_rejects_zero_or_noninteger_factor() -> None:
    with pytest.raises(ValidationError):
        EggConversionPayload(unit_code="synthetic-unit", units_per_package=0)
    with pytest.raises(ValidationError):
        EggConversionPayload(unit_code="synthetic-unit", units_per_package=1.5)  # type: ignore[arg-type]


def test_egg_category_management_and_balance_routes_are_registered() -> None:
    router = build_inventory_router(
        object(),
        object(),
        cast(DatabaseResources, object()),
        SimpleNamespace(add=lambda *_: None),
        security_events=SimpleNamespace(write=lambda *_: None),
    )
    endpoints = {
        (method, route.path)
        for route in router.routes
        if isinstance(route, APIRoute)
        for method in route.methods or set()
    }
    assert ("GET", "/api/v1/inventory/egg-categories") in endpoints
    assert ("POST", "/api/v1/inventory/egg-categories") in endpoints
    assert ("PATCH", "/api/v1/inventory/egg-categories/{category_id}") in endpoints
    assert ("POST", "/api/v1/inventory/egg-categories/{category_id}/conversions") in endpoints
    assert ("GET", "/api/v1/inventory/egg-categories/{category_id}/conversions") in endpoints
    assert ("GET", "/api/v1/inventory/egg-balances") in endpoints
    assert ("GET", "/api/v1/inventory/egg-configuration-options") in endpoints


@pytest.mark.asyncio
@pytest.mark.parametrize(("base_unit_code", "is_allowed"), [("kg", False), ("unit", True)])
async def test_create_egg_category_only_accepts_individual_unit_products(base_unit_code: str, is_allowed: bool) -> None:
    product_id = uuid4()
    product = SimpleNamespace(id=product_id, sku="TEST-EGG", base_unit_code=base_unit_code)

    class Session:
        def __init__(self) -> None:
            self.scalar_results = [product, None, None]
            self.scalar_calls = 0
            self.added: list[object] = []

        def begin(self) -> Session:
            return self

        async def __aenter__(self) -> Session:
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def scalar(self, _: object) -> object | None:
            self.scalar_calls += 1
            return self.scalar_results.pop(0)

        def add(self, item: object) -> None:
            self.added.append(item)

        async def flush(self) -> None:
            return None

    session = Session()

    class Factory:
        def __call__(self) -> Session:
            return session

    audit_records: list[tuple[object, ...]] = []
    router = build_inventory_router(
        object(),
        object(),
        cast(DatabaseResources, SimpleNamespace(session_factory=Factory())),
        SimpleNamespace(add=lambda *args: audit_records.append(args)),
        security_events=SimpleNamespace(write=lambda *_: None),
    )
    route = next(
        route
        for route in router.routes
        if isinstance(route, APIRoute)
        and route.path == "/api/v1/inventory/egg-categories"
        and "POST" in (route.methods or set())
    )
    request = Request({"type": "http", "method": "POST", "path": "/", "headers": [], "query_string": b""})
    request.state.correlation_id = str(uuid4())
    payload = EggCategoryPayload(
        code="TEST-EGG",
        name="Synthetic test egg",
        product_id=product_id,
        is_saleable=False,
        is_active=True,
    )
    user = SimpleNamespace(id=uuid4(), username="tester")

    if not is_allowed:
        with pytest.raises(ForbiddenError, match="individual egg unit"):
            await route.endpoint(payload, request, user, object())
        assert session.scalar_calls == 1
        assert session.added == []
        assert audit_records == []
        return

    result = await route.endpoint(payload, request, user, object())
    assert result.base_unit_code == "unit"
    assert result.product_id == product_id
    assert len(session.added) == 1
    assert len(audit_records) == 1
