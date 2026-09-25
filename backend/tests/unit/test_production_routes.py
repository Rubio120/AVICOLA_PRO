from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest
from fastapi.routing import APIRoute
from pydantic import ValidationError
from starlette.requests import Request

from avicola_pro.modules.production.api.routes import (
    AdjustmentPayload,
    EggClassificationReversalPayload,
    EggRecordPayload,
    FlockPayload,
    build_production_router,
)
from avicola_pro.modules.production.infrastructure.models import Flock
from avicola_pro.shared.infrastructure.database import DatabaseResources


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


def test_egg_record_payload_accepts_zero_and_rejects_fractional_counts() -> None:
    payload = EggRecordPayload(
        flock_id=uuid4(),
        house_id=uuid4(),
        occurred_on=date(2026, 9, 19),
        egg_count=0,
        idempotency_key="eggs-2026-09-19-01",
    )
    assert payload.egg_count == 0
    with pytest.raises(ValidationError):
        EggRecordPayload(
            flock_id=uuid4(),
            house_id=uuid4(),
            occurred_on=date(2026, 9, 19),
            # Fractional input should fail Pydantic validation at runtime.
            egg_count=Decimal("1.5"),  # type: ignore[arg-type]
            idempotency_key="eggs-2026-09-19-02",
        )


def test_egg_classification_reversal_payload_requires_a_nonblank_reason() -> None:
    assert EggClassificationReversalPayload(reason="Correct classification").reason == "Correct classification"
    with pytest.raises(ValidationError):
        EggClassificationReversalPayload(reason="   ")
    with pytest.raises(ValidationError):
        EggRecordPayload(
            flock_id=uuid4(),
            house_id=uuid4(),
            occurred_on=date(2026, 9, 19),
            egg_count=True,
            idempotency_key="eggs-2026-09-19-03",
        )


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
    router = build_production_router(
        object(),
        object(),
        cast(DatabaseResources, Database()),
        audit,
        "session",
        security_events=SimpleNamespace(write=lambda *_: None),
    )
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


def test_egg_production_routes_are_registered() -> None:
    router = build_production_router(
        object(),
        object(),
        cast(DatabaseResources, object()),
        SimpleNamespace(add=lambda *_: None),
        "session",
        security_events=SimpleNamespace(write=lambda *_: None),
    )
    endpoints = {
        (method, route.path)
        for route in router.routes
        if isinstance(route, APIRoute)
        for method in route.methods or set()
    }
    assert ("POST", "/api/v1/production/egg-records") in endpoints
    assert ("GET", "/api/v1/production/egg-records") in endpoints
    assert ("GET", "/api/v1/production/egg-record-options") in endpoints
    assert ("GET", "/api/v1/production/egg-records/unclassified") in endpoints
    assert ("POST", "/api/v1/production/egg-records/{production_event_id}/classifications") in endpoints
    assert ("GET", "/api/v1/production/egg-records/{production_event_id}/classifications") in endpoints
    assert (
        "POST",
        "/api/v1/production/egg-records/{production_event_id}/classifications/{classification_id}/reverse",
    ) in endpoints


@pytest.mark.asyncio
async def test_egg_classification_reversal_endpoint_audits_the_compensation(monkeypatch: pytest.MonkeyPatch) -> None:
    event_id, classification_id, receipt_id, reversal_id = (uuid4() for _ in range(4))
    actor_id = uuid4()
    service_arguments: list[tuple[object, ...]] = []
    audit_records: list[object] = []

    async def reverse(*args: object) -> SimpleNamespace:
        service_arguments.append(args)
        return SimpleNamespace(id=reversal_id, reversal_of_id=receipt_id, status="CONFIRMED")

    monkeypatch.setattr(
        "avicola_pro.modules.production.api.routes.production_service.reverse_egg_classification", reverse
    )

    class Session:
        def begin(self) -> "Session":
            return self

        async def __aenter__(self) -> "Session":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

    class Database:
        def __init__(self) -> None:
            self.session = Session()

        def session_factory(self) -> Session:
            return self.session

    database = Database()
    audit = SimpleNamespace(add=lambda _session, record: audit_records.append(record))
    router = build_production_router(
        object(),
        object(),
        cast(DatabaseResources, database),
        audit,
        "session",
        security_events=SimpleNamespace(write=lambda *_: None),
    )
    route = next(
        route
        for route in router.routes
        if isinstance(route, APIRoute)
        and route.path.endswith("/{classification_id}/reverse")
        and "POST" in (route.methods or set())
    )
    request = Request({"type": "http", "method": "POST", "path": "/", "headers": [], "query_string": b""})
    request.state.correlation_id = str(uuid4())
    user = SimpleNamespace(id=actor_id, username="egg-reviewer")

    response = await route.endpoint(
        event_id,
        classification_id,
        EggClassificationReversalPayload(reason="Correct classification"),
        request,
        user,
        object(),
    )

    assert (response.id, response.reversal_of_id, response.status) == (reversal_id, receipt_id, "CONFIRMED")
    assert service_arguments == [(database.session, event_id, classification_id, actor_id, "Correct classification")]
    assert len(audit_records) == 1
    assert cast(Any, audit_records[0]).action == "production.eggs.classification.reverse"
    assert cast(Any, audit_records[0]).resource_id == str(reversal_id)


@pytest.mark.asyncio
async def test_egg_classification_history_endpoint_returns_reversed_and_current_snapshots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event_id, old_classification_id, category_id, warehouse_id = (uuid4() for _ in range(4))
    session = object()
    async def list_history(received_session: object, received_event_id: object) -> list[dict[str, object]]:
        assert received_session is session
        assert received_event_id == event_id
        return [
            {
                "id": old_classification_id,
                "warehouse_id": warehouse_id,
                "inventory_status": "REVERSED",
                "allocations": [{"category_id": category_id, "category_code": "GRADE-A", "egg_count": 12}],
            }
        ]

    monkeypatch.setattr(
        "avicola_pro.modules.production.api.routes.production_service.list_egg_classifications", list_history
    )

    class SessionContext:
        async def __aenter__(self) -> object:
            return session

        async def __aexit__(self, *_: object) -> None:
            return None

    class Database:
        def session_factory(self) -> SessionContext:
            return SessionContext()

    router = build_production_router(
        object(),
        object(),
        cast(DatabaseResources, Database()),
        SimpleNamespace(add=lambda *_: None),
        "session",
        security_events=SimpleNamespace(write=lambda *_: None),
    )
    route = next(
        route
        for route in router.routes
        if isinstance(route, APIRoute)
        and route.path.endswith("/{production_event_id}/classifications")
        and "GET" in (route.methods or set())
    )
    response = await route.endpoint(event_id)
    assert response[0].inventory_status == "REVERSED"
    assert response[0].allocations[0].category_code == "GRADE-A"
    assert response[0].allocations[0].egg_count == 12

