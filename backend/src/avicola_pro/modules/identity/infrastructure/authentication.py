from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from avicola_pro.modules.identity.application.authentication import (
    AuthenticationRepository,
    NewSession,
    SessionAccount,
    UserAccount,
)
from avicola_pro.modules.identity.infrastructure.models import Session, User


def _user_account(user: User) -> UserAccount:
    return UserAccount(
        id=user.id,
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        password_hash=user.password_hash,
        status=user.status,
        must_change_password=user.must_change_password,
        failed_login_attempts=user.failed_login_attempts,
        locked_until=user.locked_until,
        token_version=user.token_version,
    )


def _session_model(value: NewSession) -> Session:
    return Session(
        id=value.id,
        user_id=value.user_id,
        family_id=value.family_id,
        token_hash=value.token_hash,
        csrf_hash=value.csrf_hash,
        created_at=value.created_at,
        last_used_at=value.last_used_at,
        idle_expires_at=value.idle_expires_at,
        absolute_expires_at=value.absolute_expires_at,
        ip_address=value.ip_address,
        user_agent=value.user_agent,
    )


class SQLAlchemyAuthenticationRepository(AuthenticationRepository):
    """PostgreSQL-backed identity and opaque-session persistence."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def find_user(self, identity: str) -> UserAccount | None:
        async with self._session_factory() as session:
            user = await session.scalar(
                select(User).where(or_(User.username == identity, User.email == identity)).limit(1)
            )
        return _user_account(user) if user else None

    async def record_login_failure(
        self, user_id: UUID, now: datetime, max_attempts: int, lockout_seconds: int
    ) -> tuple[int, datetime | None]:
        async with self._session_factory() as session, session.begin():
            user = await session.scalar(select(User).where(User.id == user_id).with_for_update())
            if user is None:
                return 0, None
            failed_attempts = user.failed_login_attempts + 1
            locked_until = now + timedelta(seconds=lockout_seconds) if failed_attempts >= max_attempts else None
            user.failed_login_attempts = failed_attempts
            user.locked_until = locked_until
            user.updated_at = now
        return failed_attempts, locked_until

    async def complete_login(self, user_id: UUID, updated_hash: str | None, new_session: NewSession) -> None:
        async with self._session_factory() as session, session.begin():
            user = await session.scalar(select(User).where(User.id == user_id).with_for_update())
            if user is None:
                raise RuntimeError("authenticated user disappeared")
            user.failed_login_attempts = 0
            user.locked_until = None
            user.updated_at = new_session.created_at
            if updated_hash is not None:
                user.password_hash = updated_hash
            session.add(_session_model(new_session))

    async def find_session(self, token_hash: bytes) -> SessionAccount | None:
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    select(Session, User).join(User, User.id == Session.user_id).where(Session.token_hash == token_hash)
                )
            ).one_or_none()
        if row is None:
            return None
        stored, user = row
        return SessionAccount(
            session_id=stored.id,
            family_id=stored.family_id,
            user=_user_account(user),
            csrf_hash=stored.csrf_hash,
            created_at=stored.created_at,
            last_used_at=stored.last_used_at,
            idle_expires_at=stored.idle_expires_at,
            absolute_expires_at=stored.absolute_expires_at,
            rotated_at=stored.rotated_at,
            replaced_by_session_id=stored.replaced_by_session_id,
            revoked_at=stored.revoked_at,
        )

    async def touch_session(self, session_id: UUID, last_used_at: datetime, idle_expires_at: datetime) -> None:
        async with self._session_factory() as session, session.begin():
            await session.execute(
                update(Session)
                .where(Session.id == session_id, Session.revoked_at.is_(None))
                .values(last_used_at=last_used_at, idle_expires_at=idle_expires_at)
            )

    async def rotate_session(self, old_session_id: UUID, now: datetime, replacement: NewSession) -> bool:
        async with self._session_factory() as session, session.begin():
            old = await session.scalar(select(Session).where(Session.id == old_session_id).with_for_update())
            if old is None or old.revoked_at is not None or old.replaced_by_session_id is not None:
                return False
            session.add(_session_model(replacement))
            await session.flush()
            old.rotated_at = now
            old.replaced_by_session_id = replacement.id
            old.revoked_at = now
            old.revocation_reason = "rotated"
        return True

    async def revoke_session(self, session_id: UUID, now: datetime, reason: str) -> None:
        async with self._session_factory() as session, session.begin():
            await session.execute(
                update(Session)
                .where(Session.id == session_id, Session.revoked_at.is_(None))
                .values(revoked_at=now, revocation_reason=reason)
            )

    async def revoke_family(self, family_id: UUID, now: datetime, reason: str) -> None:
        async with self._session_factory() as session, session.begin():
            await session.execute(
                update(Session)
                .where(Session.family_id == family_id)
                .values(revoked_at=func.coalesce(Session.revoked_at, now), revocation_reason=reason)
            )

    async def change_password(self, user_id: UUID, password_hash: str, now: datetime, replacement: NewSession) -> None:
        async with self._session_factory() as session, session.begin():
            user = await session.scalar(select(User).where(User.id == user_id).with_for_update())
            if user is None:
                raise RuntimeError("authenticated user disappeared")
            user.password_hash = password_hash
            user.must_change_password = False
            user.failed_login_attempts = 0
            user.locked_until = None
            user.token_version += 1
            user.updated_at = now
            await session.execute(
                update(Session)
                .where(Session.user_id == user_id, Session.revoked_at.is_(None))
                .values(revoked_at=now, revocation_reason="password_changed")
            )
            session.add(_session_model(replacement))
