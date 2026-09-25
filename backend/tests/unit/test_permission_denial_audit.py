from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import pytest
from starlette.requests import Request

from avicola_pro.modules.identity.api.auth import build_permission_dependency
from avicola_pro.modules.identity.application.authentication import RequestContext, SecurityEventData, UserAccount
from avicola_pro.shared.api.errors import ForbiddenError

_TEST_PASSWORD_HASH = "synthetic-test-hash"  # noqa: S105 - synthetic value; never used for authentication.


class _Authorization:
    def __init__(self, allowed: bool) -> None:
        self.allowed = allowed

    async def has_permission(self, user_id: UUID, permission: str) -> bool:
        del user_id, permission
        return self.allowed


class _SecurityEventSink:
    def __init__(self) -> None:
        self.events: list[SecurityEventData] = []

    async def write(self, event: SecurityEventData) -> None:
        self.events.append(event)

    async def count_recent_login_denials(self, identity: str, ip_address: str | None, since: datetime) -> int:
        del identity, ip_address, since
        return 0


def _request() -> Request:
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/inventory/balances",
            "headers": [(b"user-agent", b"audit-test")],
            "query_string": b"secret=not-recorded",
            "client": ("192.0.2.10", 5000),
        }
    )
    request.state.correlation_id = "9c837db0-4656-4420-9191-0c0c390ebd14"
    return request


@pytest.mark.asyncio
async def test_denied_permission_persists_actor_scope_and_correlation_without_changing_403() -> None:
    actor_id = uuid4()
    actor = UserAccount(
        id=actor_id,
        username="operator",
        email="operator@example.invalid",
        display_name="Operator",
        password_hash=_TEST_PASSWORD_HASH,
        status="ACTIVE",
        must_change_password=False,
        failed_login_attempts=0,
        locked_until=None,
        token_version=1,
    )
    sink = _SecurityEventSink()

    async def current_user() -> UserAccount:
        return actor

    require = build_permission_dependency(
        current_user=current_user,
        authorization=_Authorization(allowed=False),
        security_events=sink,
        resource_type="inventory",
    )
    dependency = require("inventory.balances.read")
    request = _request()

    with pytest.raises(ForbiddenError) as error:
        await dependency(request, actor)

    assert error.value.status_code == 403
    assert len(sink.events) == 1
    event = sink.events[0]
    assert event.actor_user_id == actor_id
    assert event.actor_username == "operator"
    assert event.event_type == "authorization.denied"
    assert event.outcome == "DENIED"
    assert event.context == RequestContext(
        correlation_id="9c837db0-4656-4420-9191-0c0c390ebd14",
        ip_address="192.0.2.10",
        user_agent="audit-test",
    )
    assert event.metadata == {
        "permission": "inventory.balances.read",
        "resource_type": "inventory",
        "resource_id": "/api/v1/inventory/balances",
    }


@pytest.mark.asyncio
async def test_allowed_permission_does_not_write_a_denial_event() -> None:
    actor = UserAccount(
        id=uuid4(),
        username="operator",
        email="operator@example.invalid",
        display_name="Operator",
        password_hash=_TEST_PASSWORD_HASH,
        status="ACTIVE",
        must_change_password=False,
        failed_login_attempts=0,
        locked_until=None,
        token_version=1,
    )
    sink = _SecurityEventSink()

    async def current_user() -> UserAccount:
        return actor

    require = build_permission_dependency(
        current_user=current_user,
        authorization=_Authorization(allowed=True),
        security_events=sink,
        resource_type="inventory",
    )
    dependency = require("inventory.balances.read")

    assert await dependency(_request(), actor) is actor
    assert sink.events == []
