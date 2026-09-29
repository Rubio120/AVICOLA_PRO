from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AuditRecord:
    actor_user_id: UUID
    actor_username: str
    action: str
    resource_type: str
    resource_id: str | None
    correlation_id: UUID
    ip_address: str | None
    user_agent: str | None
    before_data: dict[str, object] | None
    after_data: dict[str, object] | None


class SessionLike(Protocol):
    def add(self, instance: object) -> None: ...


class FunctionalAuditWriter(Protocol):
    def add(self, session: SessionLike, record: AuditRecord) -> None: ...
