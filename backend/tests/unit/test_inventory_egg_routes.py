from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
from fastapi.routing import APIRoute
from pydantic import ValidationError

from avicola_pro.modules.inventory.api.routes import (
    EggCategoryPayload,
    EggConversionPayload,
    build_inventory_router,
)
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
