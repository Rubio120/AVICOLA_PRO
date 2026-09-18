from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from avicola_pro.modules.audit.application.writer import AuditRecord, FunctionalAuditWriter
from avicola_pro.modules.identity.application.administration import AuditSummary, UserSummary
from avicola_pro.modules.identity.application.authentication import RequestContext, UserAccount
from avicola_pro.modules.identity.application.credentials import Argon2PasswordService
from avicola_pro.modules.identity.infrastructure.models import Permission, Role, User, UserRole
from avicola_pro.shared.api.errors import ConflictError


class SQLAlchemyAdministrationService:
    """PostgreSQL adapter for transactional identity administration."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        password_service: Argon2PasswordService,
        audit_writer: FunctionalAuditWriter,
    ) -> None:
        self._session_factory = session_factory
        self._password_service = password_service
        self._audit_writer = audit_writer

    @staticmethod
    def _snapshot(user: User) -> dict[str, object]:
        return {
            "username": user.username,
            "email": user.email,
            "display_name": user.display_name,
            "status": user.status,
            "must_change_password": user.must_change_password,
            "token_version": user.token_version,
        }

    @staticmethod
    def _audit(
        *,
        actor: UserAccount,
        context: RequestContext,
        action: str,
        resource_id: UUID | None,
        before: dict[str, object] | None,
        after: dict[str, object] | None,
    ) -> AuditRecord:
        try:
            correlation_id = UUID(context.correlation_id)
        except ValueError:
            correlation_id = UUID(int=0)
        return AuditRecord(
            actor_user_id=actor.id,
            actor_username=actor.username,
            action=action,
            resource_type="user",
            resource_id=str(resource_id) if resource_id else None,
            correlation_id=correlation_id,
            ip_address=context.ip_address,
            user_agent=context.user_agent,
            before_data=before,
            after_data=after,
        )

    async def list_users(self, *, offset: int, limit: int) -> tuple[list[UserSummary], int]:
        async with self._session_factory() as session:
            total = int(await session.scalar(select(func.count(User.id))) or 0)
            users = (await session.scalars(select(User).order_by(User.username).offset(offset).limit(limit))).all()
            result: list[UserSummary] = []
            for user in users:
                role_codes = await session.scalars(
                    select(Role.code)
                    .join(UserRole, UserRole.role_id == Role.id)
                    .where(UserRole.user_id == user.id)
                    .order_by(Role.code)
                )
                result.append(
                    UserSummary(
                        user.id,
                        user.username,
                        user.email,
                        user.display_name,
                        user.status,
                        user.must_change_password,
                        tuple(role_codes.all()),
                    )
                )
        return result, total

    async def list_roles(self, *, offset: int, limit: int) -> tuple[list[Role], int]:
        async with self._session_factory() as session:
            total = int(await session.scalar(select(func.count(Role.id))) or 0)
            return list(
                (await session.scalars(select(Role).order_by(Role.code).offset(offset).limit(limit))).all()
            ), total

    async def list_permissions(self, *, offset: int, limit: int) -> tuple[list[Permission], int]:
        async with self._session_factory() as session:
            total = int(await session.scalar(select(func.count(Permission.id))) or 0)
            return list(
                (await session.scalars(select(Permission).order_by(Permission.key).offset(offset).limit(limit))).all()
            ), total

    async def list_audit_events(self, *, offset: int, limit: int) -> tuple[list[AuditSummary], int]:
        async with self._session_factory() as session:
            total = int(await session.scalar(text("select count(id) from audit_events")) or 0)
            events = (
                await session.execute(
                    text(
                        "select id, actor_username, action, resource_type, resource_id, outcome, "
                        "correlation_id, created_at from audit_events order by created_at desc "
                        "offset :offset limit :limit"
                    ),
                    {"offset": offset, "limit": limit},
                )
            ).mappings()
            return [
                AuditSummary(
                    event["id"],
                    event["actor_username"],
                    event["action"],
                    event["resource_type"],
                    event["resource_id"],
                    event["outcome"],
                    event["correlation_id"],
                    event["created_at"],
                )
                for event in events
            ], total

    async def create_user(
        self,
        *,
        actor: UserAccount,
        context: RequestContext,
        username: str,
        email: str,
        display_name: str,
        password: str,
    ) -> UserSummary:
        user = User(
            id=uuid4(),
            username=username.strip().casefold(),
            email=email.strip().casefold(),
            display_name=display_name.strip(),
            password_hash=self._password_service.hash(password),
            must_change_password=True,
            token_version=1,
        )
        async with self._session_factory() as session, session.begin():
            existing = await session.scalar(
                select(User.id).where((User.username == user.username) | (User.email == user.email)).with_for_update()
            )
            if existing is not None:
                raise ConflictError(code="identity_already_exists", detail="Username or email already exists")
            session.add(user)
            await session.flush()
            self._audit_writer.add(
                session,
                self._audit(
                    actor=actor,
                    context=context,
                    action="users.create",
                    resource_id=user.id,
                    before=None,
                    after=self._snapshot(user),
                ),
            )
        return UserSummary(
            user.id, user.username, user.email, user.display_name, user.status, user.must_change_password, ()
        )

    async def set_user_status(self, *, actor: UserAccount, context: RequestContext, user_id: UUID, status: str) -> None:
        now = datetime.now(UTC)
        async with self._session_factory() as session, session.begin():
            user = await session.scalar(select(User).where(User.id == user_id).with_for_update())
            if user is None:
                raise ConflictError(code="user_not_found", detail="User not found")
            before = self._snapshot(user)
            if user.status == status:
                return
            if status == "INACTIVE":
                admins = await session.scalar(
                    select(func.count(User.id))
                    .join(UserRole, UserRole.user_id == User.id)
                    .join(Role, Role.id == UserRole.role_id)
                    .where(User.status == "ACTIVE", Role.code == "administrator")
                )
                is_admin = await session.scalar(
                    select(func.count(UserRole.user_id))
                    .join(Role, Role.id == UserRole.role_id)
                    .where(UserRole.user_id == user.id, Role.code == "administrator")
                )
                if is_admin and int(admins or 0) <= 1:
                    raise ConflictError(
                        code="last_administrator", detail="The last active administrator cannot be disabled"
                    )
            user.status = status
            user.updated_at = now
            self._audit_writer.add(
                session,
                self._audit(
                    actor=actor,
                    context=context,
                    action="users.status_changed",
                    resource_id=user.id,
                    before=before,
                    after=self._snapshot(user),
                ),
            )

    async def replace_user_roles(
        self, *, actor: UserAccount, context: RequestContext, user_id: UUID, role_ids: list[UUID]
    ) -> None:
        async with self._session_factory() as session, session.begin():
            user = await session.scalar(select(User).where(User.id == user_id).with_for_update())
            if user is None:
                raise ConflictError(code="user_not_found", detail="User not found")
            roles = (await session.scalars(select(Role).where(Role.id.in_(role_ids), Role.is_active.is_(True)))).all()
            if len(roles) != len(set(role_ids)):
                raise ConflictError(code="role_not_found", detail="One or more roles are unavailable")
            current_admin = await session.scalar(
                select(func.count(UserRole.user_id))
                .join(Role, Role.id == UserRole.role_id)
                .where(UserRole.user_id == user.id, Role.code == "administrator")
            )
            if current_admin and not any(role.code == "administrator" for role in roles):
                active_admins = await session.scalar(
                    select(func.count(User.id))
                    .join(UserRole, UserRole.user_id == User.id)
                    .join(Role, Role.id == UserRole.role_id)
                    .where(User.status == "ACTIVE", Role.code == "administrator")
                )
                if int(active_admins or 0) <= 1:
                    raise ConflictError(
                        code="last_administrator", detail="The last active administrator cannot be removed"
                    )
            await session.execute(delete(UserRole).where(UserRole.user_id == user.id))
            session.add_all(
                [UserRole(user_id=user.id, role_id=role.id, assigned_by_user_id=actor.id) for role in roles]
            )
            self._audit_writer.add(
                session,
                self._audit(
                    actor=actor,
                    context=context,
                    action="users.roles_replaced",
                    resource_id=user.id,
                    before=None,
                    after={"user_id": str(user.id)},
                ),
            )
