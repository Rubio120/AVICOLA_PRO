from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from avicola_pro.shared.infrastructure.models import Base

_AUDIT_SNAPSHOT_KEYS_SQL = """
array[
    'username', 'email', 'display_name', 'status', 'must_change_password',
    'locked_until', 'token_version', 'code', 'name', 'description',
    'is_system', 'is_active', 'user_id', 'role_id', 'permission_id', 'permission_key'
]::text[]
"""
_SECURITY_METADATA_KEYS_SQL = """
array[
    'username', 'user_id', 'session_id', 'session_family_id', 'reason',
    'permission', 'resource_type', 'resource_id', 'failed_attempts',
    'locked_until', 'token_version'
]::text[]
"""


class AuditEvent(Base):
    """Append-only functional audit record."""

    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint("outcome in ('SUCCESS', 'FAILURE')", name="outcome_valid"),
        CheckConstraint("before_data is null or jsonb_typeof(before_data) = 'object'", name="before_data_object"),
        CheckConstraint("after_data is null or jsonb_typeof(after_data) = 'object'", name="after_data_object"),
        CheckConstraint(
            f"before_data is null or before_data - {_AUDIT_SNAPSHOT_KEYS_SQL} = '{{}}'::jsonb",
            name="before_data_allowlist",
        ),
        CheckConstraint(
            f"after_data is null or after_data - {_AUDIT_SNAPSHOT_KEYS_SQL} = '{{}}'::jsonb",
            name="after_data_allowlist",
        ),
        Index("ix_audit_events_actor_created_at", "actor_user_id", text("created_at desc")),
        Index("ix_audit_events_resource_created_at", "resource_type", "resource_id", text("created_at desc")),
        Index("ix_audit_events_correlation_id", "correlation_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    actor_user_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    actor_username: Mapped[str | None] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(100))
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255))
    correlation_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(String(512))
    before_data: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    after_data: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class SecurityEvent(Base):
    """Append-only authentication and authorization security record."""

    __tablename__ = "security_events"
    __table_args__ = (
        CheckConstraint("outcome in ('SUCCESS', 'FAILURE', 'DENIED')", name="outcome_valid"),
        CheckConstraint("jsonb_typeof(metadata) = 'object'", name="metadata_object"),
        CheckConstraint(
            f"metadata - {_SECURITY_METADATA_KEYS_SQL} = '{{}}'::jsonb",
            name="metadata_allowlist",
        ),
        Index("ix_security_events_actor_created_at", "actor_user_id", text("created_at desc")),
        Index("ix_security_events_type_created_at", "event_type", text("created_at desc")),
        Index("ix_security_events_correlation_id", "correlation_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    actor_user_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    actor_username: Mapped[str | None] = mapped_column(String(64))
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(String(512))
    metadata_: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
