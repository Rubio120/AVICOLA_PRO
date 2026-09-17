from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from avicola_pro.modules.audit.infrastructure.models import AuditEvent
from avicola_pro.modules.identity.application.bootstrap import (
    BootstrapAlreadyCompletedError,
    BootstrapConfigurationError,
    BootstrapIdentity,
    BootstrapResult,
)
from avicola_pro.modules.identity.application.credentials import (
    Argon2PasswordService,
    PasswordPolicy,
    generate_temporary_password,
)
from avicola_pro.modules.identity.infrastructure.models import Role, User, UserRole

_BOOTSTRAP_ADVISORY_LOCK_KEY = 0x415649434F4C4102


class InitialAdministratorBootstrapper:
    """Create the sole initial administrator atomically under a PostgreSQL advisory lock."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        password_service: Argon2PasswordService,
        password_policy: PasswordPolicy,
        temporary_password_generator: Callable[[PasswordPolicy], str] = generate_temporary_password,
    ) -> None:
        self._session_factory = session_factory
        self._password_service = password_service
        self._password_policy = password_policy
        self._temporary_password_generator = temporary_password_generator

    async def create(self, identity: BootstrapIdentity) -> BootstrapResult:
        """Persist a first administrator and return its generated credential exactly once."""
        async with self._session_factory() as session, session.begin():
            await session.execute(
                text("select pg_advisory_xact_lock(:lock_key)"),
                {"lock_key": _BOOTSTRAP_ADVISORY_LOCK_KEY},
            )
            administrator_role = await session.scalar(
                select(Role).where(Role.code == "administrator", Role.is_system.is_(True), Role.is_active.is_(True))
            )
            if administrator_role is None:
                raise BootstrapConfigurationError("administrator role is unavailable")

            existing_assignment = await session.scalar(
                select(UserRole.user_id).where(UserRole.role_id == administrator_role.id).limit(1)
            )
            conflicting_identity = await session.scalar(
                select(User.id).where(or_(User.username == identity.username, User.email == identity.email)).limit(1)
            )
            if existing_assignment is not None or conflicting_identity is not None:
                raise BootstrapAlreadyCompletedError("initial administrator bootstrap is unavailable")

            temporary_password = self._temporary_password_generator(self._password_policy)
            user = User(
                id=uuid4(),
                username=identity.username,
                email=identity.email,
                display_name=identity.display_name,
                password_hash=self._password_service.hash(temporary_password),
                status="ACTIVE",
                must_change_password=True,
            )
            session.add(user)
            await session.flush()
            session.add(UserRole(user_id=user.id, role_id=administrator_role.id, assigned_by_user_id=None))
            session.add(
                AuditEvent(
                    id=uuid4(),
                    actor_user_id=None,
                    actor_username="system:bootstrap",
                    action="users.bootstrap",
                    resource_type="user",
                    resource_id=str(user.id),
                    outcome="SUCCESS",
                    reason=None,
                    correlation_id=uuid4(),
                    ip_address=None,
                    user_agent=None,
                    before_data=None,
                    after_data={
                        "username": user.username,
                        "email": user.email,
                        "display_name": user.display_name,
                        "status": user.status,
                        "must_change_password": user.must_change_password,
                        "role_id": str(administrator_role.id),
                    },
                )
            )

        return BootstrapResult(user_id=user.id, temporary_password=temporary_password)
