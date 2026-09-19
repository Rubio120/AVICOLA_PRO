"""Add auditable poultry production and feed tracking."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_production"
down_revision = "0004_inventory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    u = postgresql.UUID(as_uuid=True)
    op.create_table(
        "flocks",
        sa.Column("id", u, primary_key=True),
        sa.Column("code", sa.String(64), nullable=False, unique=True),
        sa.Column("purpose", sa.String(120), nullable=False),
        sa.Column("breed", sa.String(120)),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("planned_initial_quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="DRAFT"),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint("planned_initial_quantity > 0", name="flock_initial_positive"),
    )
    op.create_table(
        "flock_house_assignments",
        sa.Column("id", u, primary_key=True),
        sa.Column("flock_id", u, sa.ForeignKey("flocks.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("house_id", u, sa.ForeignKey("houses.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_until", sa.Date()),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.CheckConstraint("quantity > 0", name="assignment_quantity_positive"),
    )
    op.create_table(
        "flock_balances",
        sa.Column("flock_id", u, sa.ForeignKey("flocks.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("live_birds", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint("live_birds >= 0", name="flock_balance_nonnegative"),
    )
    op.create_table(
        "bird_movement_events",
        sa.Column("id", u, primary_key=True),
        sa.Column("flock_id", u, sa.ForeignKey("flocks.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("house_id", u, sa.ForeignKey("houses.id", ondelete="RESTRICT")),
        sa.Column("movement_type", sa.String(16), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="CONFIRMED"),
        sa.Column("idempotency_key", sa.String(128), unique=True),
        sa.Column("reversal_of_id", u, sa.ForeignKey("bird_movement_events.id", ondelete="RESTRICT")),
        sa.CheckConstraint("quantity > 0", name="movement_quantity_positive"),
        sa.CheckConstraint(
            "movement_type in ('INITIAL','TRANSFER_IN','TRANSFER_OUT','SALE','SLAUGHTER','OTHER')",
            name="movement_type_valid",
        ),
    )
    op.create_table(
        "mortality_events",
        sa.Column("id", u, primary_key=True),
        sa.Column("flock_id", u, sa.ForeignKey("flocks.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("house_id", u, sa.ForeignKey("houses.id", ondelete="RESTRICT")),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("cause", sa.String(300), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="CONFIRMED"),
        sa.Column("idempotency_key", sa.String(128), unique=True),
        sa.Column("reversal_of_id", u, sa.ForeignKey("mortality_events.id", ondelete="RESTRICT")),
        sa.CheckConstraint("quantity > 0", name="mortality_quantity_positive"),
    )
    op.create_table(
        "bird_adjustment_events",
        sa.Column("id", u, primary_key=True),
        sa.Column("flock_id", u, sa.ForeignKey("flocks.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("adjustment_type", sa.String(20), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("idempotency_key", sa.String(128), unique=True),
        sa.CheckConstraint("quantity > 0", name="adjustment_quantity_positive"),
        sa.CheckConstraint("adjustment_type in ('CORRECTION_IN','CORRECTION_OUT')", name="adjustment_type_valid"),
    )
    op.create_table(
        "flock_daily_records",
        sa.Column("id", u, primary_key=True),
        sa.Column("flock_id", u, sa.ForeignKey("flocks.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("record_date", sa.Date(), nullable=False),
        sa.Column("observed_birds", sa.Numeric(18, 4), nullable=False),
        sa.Column("average_weight", sa.Numeric(18, 6)),
        sa.Column("notes", sa.String(500)),
        sa.UniqueConstraint("flock_id", "record_date", name="uq_flock_daily_date"),
    )
    op.create_table(
        "feed_consumption",
        sa.Column("id", u, primary_key=True),
        sa.Column("flock_id", u, sa.ForeignKey("flocks.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("house_id", u, sa.ForeignKey("houses.id", ondelete="RESTRICT")),
        sa.Column("product_id", u, sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("warehouse_id", u, sa.ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("inventory_movement_id", u, sa.ForeignKey("inventory_movements.id", ondelete="RESTRICT")),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="feed_quantity_positive"),
    )
    op.create_index("ix_flock_status_entry", "flocks", ["status", "entry_date"])
    op.create_index("ix_production_events_flock_date", "bird_movement_events", ["flock_id", "occurred_on"])
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
                "id": "10000000-0000-7000-8000-000000000030",
                "key": "production.flocks.manage",
                "description": "Permite production.flocks.manage",
            },
            {
                "id": "10000000-0000-7000-8000-000000000031",
                "key": "production.adjustments.approve",
                "description": "Permite production.adjustments.approve",
            },
        ],
    )


def downgrade() -> None:
    for table in (
        "feed_consumption",
        "flock_daily_records",
        "bird_adjustment_events",
        "mortality_events",
        "bird_movement_events",
        "flock_balances",
        "flock_house_assignments",
        "flocks",
    ):
        op.drop_table(table)
