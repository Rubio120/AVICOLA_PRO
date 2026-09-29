from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from avicola_pro.shared.infrastructure.models import Base

_NULLABLE_STRING = ("string", "null")
_NULLABLE_NUMBER = ("number", "null")
_NULLABLE_BOOLEAN = ("boolean", "null")
_AUDIT_SNAPSHOT_SHAPE = {
    "username": _NULLABLE_STRING,
    "email": _NULLABLE_STRING,
    "display_name": _NULLABLE_STRING,
    "status": _NULLABLE_STRING,
    "must_change_password": _NULLABLE_BOOLEAN,
    "locked_until": _NULLABLE_STRING,
    "token_version": _NULLABLE_NUMBER,
    "code": _NULLABLE_STRING,
    "name": _NULLABLE_STRING,
    "description": _NULLABLE_STRING,
    "is_system": _NULLABLE_BOOLEAN,
    "is_active": _NULLABLE_BOOLEAN,
    "user_id": _NULLABLE_STRING,
    "role_id": _NULLABLE_STRING,
    "permission_id": _NULLABLE_STRING,
    "permission_key": _NULLABLE_STRING,
}
_SECURITY_METADATA_SHAPE = {
    "username": _NULLABLE_STRING,
    "user_id": _NULLABLE_STRING,
    "session_id": _NULLABLE_STRING,
    "session_family_id": _NULLABLE_STRING,
    "reason": _NULLABLE_STRING,
    "permission": _NULLABLE_STRING,
    "resource_type": _NULLABLE_STRING,
    "resource_id": _NULLABLE_STRING,
    "failed_attempts": _NULLABLE_NUMBER,
    "locked_until": _NULLABLE_STRING,
    "token_version": _NULLABLE_NUMBER,
}


def _jsonb_key_array_sql(shape: Mapping[str, tuple[str, ...]]) -> str:
    quoted_keys = ", ".join(f"'{key}'" for key in shape)
    return f"array[{quoted_keys}]::text[]"


def _jsonb_scalar_shape_sql(column: str, shape: Mapping[str, tuple[str, ...]]) -> str:
    clauses = []
    for key, allowed_types in shape.items():
        quoted_types = ", ".join(f"'{value_type}'" for value_type in allowed_types)
        clauses.append(f"({column} -> '{key}' is null or jsonb_typeof({column} -> '{key}') in ({quoted_types}))")
    return " and ".join(clauses)


class AuditEvent(Base):
    """Append-only functional audit record."""

    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint("outcome in ('SUCCESS', 'FAILURE')", name="outcome_valid"),
        CheckConstraint("before_data is null or jsonb_typeof(before_data) = 'object'", name="before_data_object"),
        CheckConstraint("after_data is null or jsonb_typeof(after_data) = 'object'", name="after_data_object"),
        CheckConstraint(
            f"before_data is null or before_data - {_jsonb_key_array_sql(_AUDIT_SNAPSHOT_SHAPE)} = '{{}}'::jsonb",
            name="before_data_allowlist",
        ),
        CheckConstraint(
            f"after_data is null or after_data - {_jsonb_key_array_sql(_AUDIT_SNAPSHOT_SHAPE)} = '{{}}'::jsonb",
            name="after_data_allowlist",
        ),
        CheckConstraint(
            f"before_data is null or ({_jsonb_scalar_shape_sql('before_data', _AUDIT_SNAPSHOT_SHAPE)})",
            name="before_data_scalar_shape",
        ),
        CheckConstraint(
            f"after_data is null or ({_jsonb_scalar_shape_sql('after_data', _AUDIT_SNAPSHOT_SHAPE)})",
            name="after_data_scalar_shape",
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
    before_data: Mapped[dict[str, object] | None] = mapped_column(JSONB(none_as_null=True))
    after_data: Mapped[dict[str, object] | None] = mapped_column(JSONB(none_as_null=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class SecurityEvent(Base):
    """Append-only authentication and authorization security record."""

    __tablename__ = "security_events"
    __table_args__ = (
        CheckConstraint("outcome in ('SUCCESS', 'FAILURE', 'DENIED')", name="outcome_valid"),
        CheckConstraint("jsonb_typeof(metadata) = 'object'", name="metadata_object"),
        CheckConstraint(
            f"metadata - {_jsonb_key_array_sql(_SECURITY_METADATA_SHAPE)} = '{{}}'::jsonb",
            name="metadata_allowlist",
        ),
        CheckConstraint(
            _jsonb_scalar_shape_sql("metadata", _SECURITY_METADATA_SHAPE),
            name="metadata_scalar_shape",
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
