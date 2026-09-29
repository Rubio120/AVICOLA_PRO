from __future__ import annotations

from uuid import uuid4

from avicola_pro.modules.audit.application.writer import AuditRecord, FunctionalAuditWriter, SessionLike
from avicola_pro.modules.audit.infrastructure.models import AuditEvent


class SQLAlchemyFunctionalAuditWriter(FunctionalAuditWriter):
    """Adds functional audit events to the caller's transaction."""

    def add(self, session: SessionLike, record: AuditRecord) -> None:
        session.add(
            AuditEvent(
                id=uuid4(),
                actor_user_id=record.actor_user_id,
                actor_username=record.actor_username,
                action=record.action,
                resource_type=record.resource_type,
                resource_id=record.resource_id,
                outcome="SUCCESS",
                correlation_id=record.correlation_id,
                ip_address=record.ip_address,
                user_agent=record.user_agent,
                before_data=record.before_data,
                after_data=record.after_data,
            )
        )
