from __future__ import annotations

from typing import Protocol
from uuid import UUID


class AuthorizationPort(Protocol):
    async def has_permission(self, user_id: UUID, permission: str) -> bool: ...
