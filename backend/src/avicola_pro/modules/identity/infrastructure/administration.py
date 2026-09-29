from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from avicola_pro.modules.audit.application.writer import AuditRecord, FunctionalAuditWriter
from avicola_pro.modules.identity.application.administration import AuditSummary, UserSummary
from avicola_pro.modules.identity.application.authentication import RequestContext, UserAccount
from avicola_pro.modules.identity.application.credentials import Argon2PasswordService
from avicola_pro.modules.identity.infrastructure.models import (
    Permission,
    Role,
    RolePermission,
    Session,
    User,
    UserRole,
)
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
    def _role_snapshot(role: Role) -> dict[str, object]:
        return {
            "code": role.code,
            "name": role.name,
            "description": role.description,
            "is_system": role.is_system,
            "is_active": role.is_active,
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
        resource_type: str = "user",
    ) -> AuditRecord:
        try:
            correlation_id = UUID(context.correlation_id)
        except ValueError:
            correlation_id = UUID(int=0)
        return AuditRecord(
            actor_user_id=actor.id,
            actor_username=actor.username,
            action=action,
            resource_type=resource_type,
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

    async def create_role(
        self, *, actor: UserAccount, context: RequestContext, code: str, name: str, description: str | None
    ) -> Role:
        role = Role(id=uuid4(), code=code.strip().casefold(), name=name.strip(), description=description)
        async with self._session_factory() as session, session.begin():
            if await session.scalar(select(Role.id).where(Role.code == role.code)) is not None:
                raise ConflictError(code="role_already_exists", detail="Role code already exists")
            session.add(role)
            await session.flush()
            self._audit_writer.add(
                session,
                self._audit(
                    actor=actor,
                    context=context,
                    action="roles.create",
                    resource_type="role",
                    resource_id=role.id,
                    before=None,
                    after=self._role_snapshot(role),
                ),
            )
        return role

    async def set_role_status(
        self, *, actor: UserAccount, context: RequestContext, role_id: UUID, is_active: bool
    ) -> None:
        async with self._session_factory() as session, session.begin():
            role = await session.scalar(select(Role).where(Role.id == role_id).with_for_update())
            if role is None:
                raise ConflictError(code="role_not_found", detail="Role not found")
            if role.is_system and not is_active:
                raise ConflictError(code="system_role", detail="System roles cannot be deactivated")
            before = self._role_snapshot(role)
            role.is_active = is_active
            role.updated_at = datetime.now(UTC)
            self._audit_writer.add(
                session,
                self._audit(
                    actor=actor,
                    context=context,
                    action="roles.status_changed",
                    resource_type="role",
                    resource_id=role.id,
                    before=before,
                    after=self._role_snapshot(role),
                ),
            )

    async def replace_role_permissions(
        self, *, actor: UserAccount, context: RequestContext, role_id: UUID, permission_ids: list[UUID]
    ) -> None:
        async with self._session_factory() as session, session.begin():
            role = await session.scalar(select(Role).where(Role.id == role_id).with_for_update())
            if role is None:
                raise ConflictError(code="role_not_found", detail="Role not found")
            if role.is_system:
                raise ConflictError(code="system_role", detail="System role permissions are immutable")
            permissions = (await session.scalars(select(Permission).where(Permission.id.in_(permission_ids)))).all()
            if len(permissions) != len(set(permission_ids)):
                raise ConflictError(code="permission_not_found", detail="One or more permissions are unavailable")
            current = (
                await session.scalars(
                    select(Permission.key)
                    .join(RolePermission, RolePermission.permission_id == Permission.id)
                    .where(RolePermission.role_id == role.id)
                )
            ).all()
            await session.execute(delete(RolePermission).where(RolePermission.role_id == role.id))
            session.add_all(
                [
                    RolePermission(role_id=role.id, permission_id=permission.id, assigned_by_user_id=actor.id)
                    for permission in permissions
                ]
            )
            self._audit_writer.add(
                session,
                self._audit(
                    actor=actor,
                    context=context,
                    action="roles.permissions_replaced",
                    resource_type="role",
                    resource_id=role.id,
                    before={"permission_key": ",".join(sorted(current))},
                    after={"permission_key": ",".join(sorted(permission.key for permission in permissions))},
                ),
            )

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

    async def record_audit_read(self, *, actor: UserAccount, context: RequestContext) -> None:
        async with self._session_factory() as session, session.begin():
            self._audit_writer.add(
                session,
                self._audit(
                    actor=actor,
                    context=context,
                    action="audit.read",
                    resource_type="audit_event",
                    resource_id=None,
                    before=None,
                    after=None,
                ),
            )

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
            if status == "INACTIVE":
                await session.execute(
                    update(Session)
                    .where(Session.user_id == user.id, Session.revoked_at.is_(None))
                    .values(revoked_at=now, revocation_reason="user_deactivated")
                )
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
            current_roles = (
                await session.scalars(
                    select(Role.code).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user.id)
                )
            ).all()
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
                    before={"user_id": str(user.id), "roles": ",".join(sorted(current_roles))},
                    after={"user_id": str(user.id), "roles": ",".join(sorted(role.code for role in roles))},
                ),
            )
