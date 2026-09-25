from __future__ import annotations

from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from avicola_pro.modules.audit.infrastructure.models import SecurityEvent
from avicola_pro.modules.identity.application.authentication import SecurityEventData, SecurityEventWriter


class SQLAlchemySecurityEventWriter(SecurityEventWriter):
    """Persist and query security evidence in transactions independent of auth state."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    @staticmethod
    def _correlation_uuid(value: str) -> UUID:
        try:
            return UUID(value)
        except ValueError:
            return uuid5(NAMESPACE_URL, value)

    async def write(self, event: SecurityEventData) -> None:
        async with self._session_factory() as session, session.begin():
            session.add(
                SecurityEvent(
                    id=uuid4(),
                    actor_user_id=event.actor_user_id,
                    actor_username=event.actor_username,
                    event_type=event.event_type,
                    outcome=event.outcome,
                    correlation_id=self._correlation_uuid(event.context.correlation_id),
                    ip_address=event.context.ip_address,
                    user_agent=event.context.user_agent,
                    metadata_=event.metadata,
                )
            )

    async def count_recent_login_denials(self, identity: str, ip_address: str | None, since: datetime) -> int:
        ip_filter = SecurityEvent.ip_address.is_(None) if ip_address is None else SecurityEvent.ip_address == ip_address
        async with self._session_factory() as session:
            count = await session.scalar(
                select(func.count(SecurityEvent.id)).where(
                    SecurityEvent.created_at >= since,
                    SecurityEvent.outcome.in_(("FAILURE", "DENIED")),
                    SecurityEvent.event_type.in_(("auth.login", "auth.locked", "auth.rate_limited")),
                    SecurityEvent.metadata_["username"].as_string() == identity,
                    ip_filter,
                )
            )
        return int(count or 0)
