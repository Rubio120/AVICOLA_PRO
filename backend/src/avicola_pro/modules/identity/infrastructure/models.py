from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, LargeBinary, String, Text, text
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from avicola_pro.shared.infrastructure.models import Base


class User(Base):
    """Persisted application identity."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("username = lower(btrim(username))", name="username_normalized"),
        CheckConstraint("email = lower(btrim(email))", name="email_normalized"),
        CheckConstraint("status in ('ACTIVE', 'INACTIVE')", name="status_valid"),
        CheckConstraint("failed_login_attempts >= 0", name="failed_login_attempts_nonnegative"),
        CheckConstraint("token_version >= 1", name="token_version_positive"),
        Index("uq_users_username_ci", text("lower(username)"), unique=True),
        Index("uq_users_email_ci", text("lower(email)"), unique=True),
        Index("ix_users_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'ACTIVE'"))
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    failed_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class Role(Base):
    """Named collection of permissions."""

    __tablename__ = "roles"
    __table_args__ = (
        CheckConstraint("code = lower(btrim(code))", name="code_normalized"),
        Index("uq_roles_code_ci", text("lower(code)"), unique=True),
        Index("ix_roles_active", "is_active"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class Permission(Base):
    """Stable authorization capability."""

    __tablename__ = "permissions"
    __table_args__ = (
        CheckConstraint("key = lower(btrim(key))", name="key_normalized"),
        CheckConstraint("key ~ '^[a-z][a-z0-9_]*(\\.[a-z][a-z0-9_]*)+$'", name="key_format"),
        Index("uq_permissions_key_ci", text("lower(key)"), unique=True),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class UserRole(Base):
    """Assignment of a role to a user."""

    __tablename__ = "user_roles"
    __table_args__ = (Index("ix_user_roles_role_id", "role_id"),)

    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True
    )
    role_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("roles.id", ondelete="RESTRICT"), primary_key=True
    )
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    assigned_by_user_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )


class RolePermission(Base):
    """Assignment of a permission to a role."""

    __tablename__ = "role_permissions"
    __table_args__ = (Index("ix_role_permissions_permission_id", "permission_id"),)

    role_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("roles.id", ondelete="RESTRICT"), primary_key=True
    )
    permission_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("permissions.id", ondelete="RESTRICT"), primary_key=True
    )
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    assigned_by_user_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )


class Session(Base):
    """Opaque, server-side session containing only keyed hashes."""

    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint("octet_length(token_hash) = 32", name="token_hash_length"),
        CheckConstraint("octet_length(csrf_hash) = 32", name="csrf_hash_length"),
        CheckConstraint("idle_expires_at > created_at", name="idle_expiry_after_creation"),
        CheckConstraint("absolute_expires_at > created_at", name="absolute_expiry_after_creation"),
        CheckConstraint("idle_expires_at <= absolute_expires_at", name="idle_before_absolute_expiry"),
        Index("ix_sessions_user_active", "user_id", postgresql_where=text("revoked_at is null")),
        Index("ix_sessions_family_active", "family_id", postgresql_where=text("revoked_at is null")),
        Index("ix_sessions_idle_expires_at", "idle_expires_at"),
        Index("ix_sessions_absolute_expires_at", "absolute_expires_at"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    family_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False, unique=True)
    csrf_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    idle_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    absolute_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_by_session_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("sessions.id", ondelete="RESTRICT"), unique=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revocation_reason: Mapped[str | None] = mapped_column(String(120))
    ip_address: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(String(512))
