"""Add immutable daily egg production facts."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0011_egg_production"
down_revision = "0010_costing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    u = postgresql.UUID(as_uuid=True)
    op.create_table(
        "egg_production_events",
        sa.Column("id", u, primary_key=True),
        sa.Column("flock_id", u, sa.ForeignKey("flocks.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("house_id", u, sa.ForeignKey("houses.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("egg_count", sa.BigInteger(), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False, unique=True),
        sa.Column("actor_user_id", u, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reversal_of_id", u, sa.ForeignKey("egg_production_events.id", ondelete="RESTRICT"), unique=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="CONFIRMED"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("egg_count >= 0", name="egg_count_nonnegative"),
        sa.CheckConstraint("status = 'CONFIRMED'", name="egg_production_status_valid"),
    )
    op.create_index("ix_egg_production_flock_date", "egg_production_events", ["flock_id", "occurred_on"])
    op.execute("""
        create trigger trg_egg_production_events_append_only
        before update or delete on egg_production_events
        for each row execute function reject_append_only_mutation()
    """)
    permissions = sa.table(
        "permissions",
        sa.column("id", u),
        sa.column("key", sa.String()),
        sa.column("description", sa.String()),
    )
    op.bulk_insert(
        permissions,
        [
            {
                "id": "10000000-0000-7000-8000-000000000035",
                "key": "production.eggs.read",
                "description": "Permite production.eggs.read",
            },
            {
                "id": "10000000-0000-7000-8000-000000000036",
                "key": "production.eggs.record",
                "description": "Permite production.eggs.record",
            },
        ],
    )


def downgrade() -> None:
    op.execute("drop trigger if exists trg_egg_production_events_append_only on egg_production_events")
    op.drop_index("ix_egg_production_flock_date", table_name="egg_production_events")
    op.drop_table("egg_production_events")
    op.execute(
        "delete from role_permissions where permission_id in "
        "('10000000-0000-7000-8000-000000000035', '10000000-0000-7000-8000-000000000036')"
    )
    op.execute(
        "delete from permissions where id in "
        "('10000000-0000-7000-8000-000000000035', '10000000-0000-7000-8000-000000000036')"
    )
