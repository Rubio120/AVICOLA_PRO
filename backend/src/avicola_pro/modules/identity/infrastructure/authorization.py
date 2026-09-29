from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from avicola_pro.modules.identity.infrastructure.models import Permission, Role, RolePermission, UserRole


class SQLAlchemyAuthorizationService:
    """Loads effective permissions from active roles and denies by default."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def has_permission(self, user_id: UUID, permission: str) -> bool:
        async with self._session_factory() as session:
            result = await session.scalar(
                select(func.count(Permission.id))
                .join(RolePermission, RolePermission.permission_id == Permission.id)
                .join(UserRole, UserRole.role_id == RolePermission.role_id)
                .join(Role, Role.id == UserRole.role_id)
                .where(UserRole.user_id == user_id, Permission.key == permission, Role.is_active.is_(True))
            )
        return bool(result)
