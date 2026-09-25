"""Create identity, RBAC, session, and append-only audit persistence.

Revision ID: 0002_identity_rbac_audit
Revises: 0001_baseline
Create Date: 2026-09-17
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_identity_rbac_audit"
down_revision: str | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PERMISSION_KEYS = (
    "users.manage",
    "roles.manage",
    "settings.manage",
    "audit.read",
    "audit.export",
    "session.self",
    "inventory.products.read",
    "inventory.movements.create",
    "inventory.adjustments.approve",
    "inventory.transfers.confirm",
    "purchases.orders.create",
    "purchases.orders.approve",
    "purchases.receipts.confirm",
    "sales.orders.create",
    "sales.documents.issue",
    "sales.documents.cancel",
    "sales.credit_notes.issue",
    "cash.movements.create",
    "cash.movements.reverse",
    "cash.closings.execute",
    "production.mortality.record",
    "production.feed.record",
    "costs.recalculate",
    "reports.profitability.read",
    "reports.export",
    "backups.execute",
)
_ROLES = (
    ("administrator", "Administrador"),
    ("management", "Gerencia"),
    ("production", "Producción"),
    ("inventory", "Inventario"),
    ("purchasing", "Compras"),
    ("sales", "Ventas"),
    ("cash", "Caja"),
    ("finance", "Finanzas"),
    ("auditor", "Auditor"),
)
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


def _create_identity_tables() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'ACTIVE'"), nullable=False),
        sa.Column("must_change_password", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("failed_login_attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("token_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("email = lower(btrim(email))", name="email_normalized"),
        sa.CheckConstraint("failed_login_attempts >= 0", name="failed_login_attempts_nonnegative"),
        sa.CheckConstraint("status in ('ACTIVE', 'INACTIVE')", name="status_valid"),
        sa.CheckConstraint("token_version >= 1", name="token_version_positive"),
        sa.CheckConstraint("username = lower(btrim(username))", name="username_normalized"),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
    )
    op.create_index("ix_users_status", "users", ["status"])
    op.create_index("uq_users_email_ci", "users", [sa.text("lower(email)")], unique=True)
    op.create_index("uq_users_username_ci", "users", [sa.text("lower(username)")], unique=True)

    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_system", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("code = lower(btrim(code))", name="code_normalized"),
        sa.PrimaryKeyConstraint("id", name="pk_roles"),
    )
    op.create_index("ix_roles_active", "roles", ["is_active"])
    op.create_index("uq_roles_code_ci", "roles", [sa.text("lower(code)")], unique=True)

    op.create_table(
        "permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("key ~ '^[a-z][a-z0-9_]*(\\.[a-z][a-z0-9_]*)+$'", name="key_format"),
        sa.CheckConstraint("key = lower(btrim(key))", name="key_normalized"),
        sa.PrimaryKeyConstraint("id", name="pk_permissions"),
    )
    op.create_index("uq_permissions_key_ci", "permissions", [sa.text("lower(key)")], unique=True)

    op.create_table(
        "user_roles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("assigned_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["assigned_by_user_id"], ["users.id"], name="fk_user_roles_assigned_by_user_id_users", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], name="fk_user_roles_role_id_roles", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_user_roles_user_id_users", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("user_id", "role_id", name="pk_user_roles"),
    )
    op.create_index("ix_user_roles_role_id", "user_roles", ["role_id"])

    op.create_table(
        "role_permissions",
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("permission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("assigned_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["assigned_by_user_id"],
            ["users.id"],
            name="fk_role_permissions_assigned_by_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["permission_id"],
            ["permissions.id"],
            name="fk_role_permissions_permission_id_permissions",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"], ["roles.id"], name="fk_role_permissions_role_id_roles", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("role_id", "permission_id", name="pk_role_permissions"),
    )
    op.create_index("ix_role_permissions_permission_id", "role_permissions", ["permission_id"])

    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.LargeBinary(length=32), nullable=False),
        sa.Column("csrf_hash", sa.LargeBinary(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("idle_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.String(length=120), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.CheckConstraint("absolute_expires_at > created_at", name="absolute_expiry_after_creation"),
        sa.CheckConstraint("octet_length(csrf_hash) = 32", name="csrf_hash_length"),
        sa.CheckConstraint("idle_expires_at > created_at", name="idle_expiry_after_creation"),
        sa.CheckConstraint("idle_expires_at <= absolute_expires_at", name="idle_before_absolute_expiry"),
        sa.CheckConstraint("octet_length(token_hash) = 32", name="token_hash_length"),
        sa.ForeignKeyConstraint(
            ["replaced_by_session_id"],
            ["sessions.id"],
            name="fk_sessions_replaced_by_session_id_sessions",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_sessions_user_id_users", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_sessions"),
        sa.UniqueConstraint("replaced_by_session_id", name="uq_sessions_replaced_by_session_id"),
        sa.UniqueConstraint("token_hash", name="uq_sessions_token_hash"),
    )
    op.create_index("ix_sessions_absolute_expires_at", "sessions", ["absolute_expires_at"])
    op.create_index(
        "ix_sessions_family_active", "sessions", ["family_id"], postgresql_where=sa.text("revoked_at is null")
    )
    op.create_index("ix_sessions_idle_expires_at", "sessions", ["idle_expires_at"])
    op.create_index("ix_sessions_user_active", "sessions", ["user_id"], postgresql_where=sa.text("revoked_at is null"))


def _create_event_tables() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_username", sa.String(length=64), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("resource_type", sa.String(length=100), nullable=False),
        sa.Column("resource_id", sa.String(length=100), nullable=True),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("before_data", postgresql.JSONB(), nullable=True),
        sa.Column("after_data", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            f"after_data is null or after_data - {_jsonb_key_array_sql(_AUDIT_SNAPSHOT_SHAPE)} = '{{}}'::jsonb",
            name="after_data_allowlist",
        ),
        sa.CheckConstraint("after_data is null or jsonb_typeof(after_data) = 'object'", name="after_data_object"),
        sa.CheckConstraint(
            f"before_data is null or before_data - {_jsonb_key_array_sql(_AUDIT_SNAPSHOT_SHAPE)} = '{{}}'::jsonb",
            name="before_data_allowlist",
        ),
        sa.CheckConstraint("before_data is null or jsonb_typeof(before_data) = 'object'", name="before_data_object"),
        sa.CheckConstraint(
            f"before_data is null or ({_jsonb_scalar_shape_sql('before_data', _AUDIT_SNAPSHOT_SHAPE)})",
            name="before_data_scalar_shape",
        ),
        sa.CheckConstraint(
            f"after_data is null or ({_jsonb_scalar_shape_sql('after_data', _AUDIT_SNAPSHOT_SHAPE)})",
            name="after_data_scalar_shape",
        ),
        sa.CheckConstraint("outcome in ('SUCCESS', 'FAILURE')", name="outcome_valid"),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["users.id"], name="fk_audit_events_actor_user_id_users", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_events"),
    )
    op.create_index("ix_audit_events_actor_created_at", "audit_events", ["actor_user_id", sa.text("created_at desc")])
    op.create_index("ix_audit_events_correlation_id", "audit_events", ["correlation_id"])
    op.create_index(
        "ix_audit_events_resource_created_at",
        "audit_events",
        ["resource_type", "resource_id", sa.text("created_at desc")],
    )

    op.create_table(
        "security_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_username", sa.String(length=64), nullable=True),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            f"metadata - {_jsonb_key_array_sql(_SECURITY_METADATA_SHAPE)} = '{{}}'::jsonb",
            name="metadata_allowlist",
        ),
        sa.CheckConstraint("jsonb_typeof(metadata) = 'object'", name="metadata_object"),
        sa.CheckConstraint(
            _jsonb_scalar_shape_sql("metadata", _SECURITY_METADATA_SHAPE),
            name="metadata_scalar_shape",
        ),
        sa.CheckConstraint("outcome in ('SUCCESS', 'FAILURE', 'DENIED')", name="outcome_valid"),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["users.id"], name="fk_security_events_actor_user_id_users", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_security_events"),
    )
    op.create_index(
        "ix_security_events_actor_created_at", "security_events", ["actor_user_id", sa.text("created_at desc")]
    )
    op.create_index("ix_security_events_correlation_id", "security_events", ["correlation_id"])
    op.create_index("ix_security_events_type_created_at", "security_events", ["event_type", sa.text("created_at desc")])


def _seed_base_catalog() -> None:
    permissions = sa.table(
        "permissions",
        sa.column("id", postgresql.UUID()),
        sa.column("key", sa.String()),
        sa.column("description", sa.Text()),
    )
    roles = sa.table(
        "roles",
        sa.column("id", postgresql.UUID()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("is_system", sa.Boolean()),
    )
    grants = sa.table(
        "role_permissions", sa.column("role_id", postgresql.UUID()), sa.column("permission_id", postgresql.UUID())
    )
    permission_ids = {
        key: UUID(f"10000000-0000-7000-8000-{index:012d}") for index, key in enumerate(_PERMISSION_KEYS, 1)
    }
    role_ids = {code: UUID(f"20000000-0000-7000-8000-{index:012d}") for index, (code, _) in enumerate(_ROLES, 1)}
    bind = op.get_bind()
    bind.execute(
        postgresql.insert(permissions)
        .values([{"id": permission_ids[key], "key": key, "description": f"Permite {key}"} for key in _PERMISSION_KEYS])
        .on_conflict_do_nothing()
    )
    bind.execute(
        postgresql.insert(roles)
        .values(
            [
                {
                    "id": role_ids[code],
                    "code": code,
                    "name": name,
                    "description": f"Rol oficial {name}",
                    "is_system": True,
                }
                for code, name in _ROLES
            ]
        )
        .on_conflict_do_nothing()
    )
    bind.execute(
        postgresql.insert(grants)
        .values(
            [{"role_id": role_ids["administrator"], "permission_id": permission_ids[key]} for key in _PERMISSION_KEYS]
        )
        .on_conflict_do_nothing()
    )


def upgrade() -> None:
    """Create the Delivery 2 persistence schema and base authorization catalog."""
    _create_identity_tables()
    _create_event_tables()
    op.execute("""create function reject_append_only_mutation() returns trigger language plpgsql as $$
        begin raise exception '% is append-only', tg_table_name using errcode = 'P0001'; end; $$""")
    for table_name in ("audit_events", "security_events"):
        op.execute(
            f"""create trigger trg_{table_name}_append_only
            before update or delete on {table_name}
            for each row execute function reject_append_only_mutation()"""
        )
    _seed_base_catalog()


def downgrade() -> None:
    """Remove the Delivery 2 persistence schema."""
    for table_name in ("audit_events", "security_events"):
        op.execute(f"drop trigger if exists trg_{table_name}_append_only on {table_name}")
    op.execute("drop function if exists reject_append_only_mutation()")
    for table_name in (
        "security_events",
        "audit_events",
        "sessions",
        "role_permissions",
        "user_roles",
        "permissions",
        "roles",
        "users",
    ):
        op.drop_table(table_name)
