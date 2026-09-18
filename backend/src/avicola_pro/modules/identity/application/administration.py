from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from avicola_pro.modules.identity.application.authentication import RequestContext, UserAccount


@dataclass(frozen=True, slots=True)
class UserSummary:
    id: UUID
    username: str
    email: str
    display_name: str
    status: str
    must_change_password: bool
    roles: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AuditSummary:
    id: UUID
    actor_username: str | None
    action: str
    resource_type: str
    resource_id: str | None
    outcome: str
    correlation_id: UUID
    created_at: datetime


class AdministrationPort(Protocol):
    async def list_users(self, *, offset: int, limit: int) -> tuple[list[UserSummary], int]: ...

    async def list_roles(self, *, offset: int, limit: int) -> tuple[Sequence[object], int]: ...

    async def list_permissions(self, *, offset: int, limit: int) -> tuple[Sequence[object], int]: ...

    async def list_audit_events(self, *, offset: int, limit: int) -> tuple[list[AuditSummary], int]: ...

    async def create_user(
        self,
        *,
        actor: UserAccount,
        context: RequestContext,
        username: str,
        email: str,
        display_name: str,
        password: str,
    ) -> UserSummary: ...

    async def set_user_status(
        self, *, actor: UserAccount, context: RequestContext, user_id: UUID, status: str
    ) -> None: ...

    async def replace_user_roles(
        self, *, actor: UserAccount, context: RequestContext, user_id: UUID, role_ids: list[UUID]
    ) -> None: ...
