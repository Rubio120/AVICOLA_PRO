"""Add auditable inventory ledger and balance projection."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_inventory"
down_revision = "0003_settings_parties_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid_type = postgresql.UUID(as_uuid=True)
    op.create_table(
        "inventory_lots",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("product_id", uuid_type, sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("lot_code", sa.String(80), nullable=False),
        sa.Column("manufacture_date", sa.Date()),
        sa.Column("expiration_date", sa.Date()),
        sa.Column("supplier_id", uuid_type, sa.ForeignKey("suppliers.id", ondelete="RESTRICT")),
        sa.CheckConstraint("lot_code <> ''", name="inventory_lot_code_nonempty"),
        sa.CheckConstraint(
            "expiration_date is null or manufacture_date is null or expiration_date >= manufacture_date",
            name="inventory_lot_dates_order",
        ),
        sa.UniqueConstraint("product_id", "lot_code", name="uq_inventory_lots_product_code"),
    )
    op.create_table(
        "inventory_documents",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("document_type", sa.String(16), nullable=False),
        sa.Column("series", sa.String(16), nullable=False, server_default=""),
        sa.Column("number", sa.String(32), nullable=False, server_default=""),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="DRAFT"),
        sa.Column("source_type", sa.String(64)),
        sa.Column("source_id", uuid_type),
        sa.Column("warehouse_id", uuid_type, sa.ForeignKey("warehouses.id", ondelete="RESTRICT")),
        sa.Column("destination_warehouse_id", uuid_type, sa.ForeignKey("warehouses.id", ondelete="RESTRICT")),
        sa.Column("reason", sa.String(500)),
        sa.Column("idempotency_key", sa.String(128)),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("confirmed_by", uuid_type, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("reversed_at", sa.DateTime(timezone=True)),
        sa.Column("reversed_by", uuid_type, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("reversal_of_id", uuid_type, sa.ForeignKey("inventory_documents.id", ondelete="RESTRICT")),
        sa.Column("reversal_reason", sa.String(500)),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint(
            "document_type in ('RECEIPT','ISSUE','TRANSFER','ADJUSTMENT')", name="inventory_document_type_valid"
        ),
        sa.CheckConstraint("status in ('DRAFT','CONFIRMED','REVERSED')", name="inventory_document_status_valid"),
        sa.CheckConstraint("reversed_at is null or status = 'REVERSED'", name="inventory_document_reversed_state"),
    )
    op.create_table(
        "inventory_document_lines",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column(
            "document_id", uuid_type, sa.ForeignKey("inventory_documents.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("product_id", uuid_type, sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("inventory_lot_id", uuid_type, sa.ForeignKey("inventory_lots.id", ondelete="RESTRICT")),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("direction", sa.String(3), nullable=False, server_default="IN"),
        sa.CheckConstraint("quantity > 0", name="inventory_line_quantity_positive"),
        sa.CheckConstraint("unit_cost >= 0", name="inventory_line_cost_nonnegative"),
        sa.CheckConstraint("direction in ('IN','OUT')", name="inventory_line_direction_valid"),
        sa.UniqueConstraint("document_id", "ordinal", name="uq_inventory_lines_document_ordinal"),
    )
    op.create_table(
        "inventory_movements",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column(
            "document_id", uuid_type, sa.ForeignKey("inventory_documents.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "line_id", uuid_type, sa.ForeignKey("inventory_document_lines.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("product_id", uuid_type, sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("inventory_lot_id", uuid_type, sa.ForeignKey("inventory_lots.id", ondelete="RESTRICT")),
        sa.Column("warehouse_id", uuid_type, sa.ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("movement_type", sa.String(16), nullable=False),
        sa.Column("quantity_delta", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 6), nullable=False),
        sa.Column("value_delta", sa.Numeric(18, 2), nullable=False),
        sa.Column("original_unit_cost", sa.Numeric(18, 6)),
        sa.Column("original_value_delta", sa.Numeric(18, 2)),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("actor_user_id", uuid_type, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reversal_of_id", uuid_type, sa.ForeignKey("inventory_movements.id", ondelete="RESTRICT")),
        sa.CheckConstraint(
            "movement_type in ('RECEIPT','ISSUE','TRANSFER_IN','TRANSFER_OUT','ADJUSTMENT','REVERSAL')",
            name="inventory_movement_type_valid",
        ),
        sa.CheckConstraint("quantity_delta <> 0", name="inventory_movement_delta_nonzero"),
        sa.CheckConstraint("value_delta is not null", name="inventory_movement_value_required"),
    )
    op.create_table(
        "inventory_balances",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("warehouse_id", uuid_type, sa.ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("product_id", uuid_type, sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("inventory_lot_id", uuid_type, sa.ForeignKey("inventory_lots.id", ondelete="RESTRICT")),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("inventory_value", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("average_cost", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint("quantity >= 0", name="inventory_balance_quantity_nonnegative"),
        sa.CheckConstraint("inventory_value >= 0", name="inventory_balance_value_nonnegative"),
    )
    op.create_table(
        "inventory_cost_variances",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column(
            "original_movement_id",
            uuid_type,
            sa.ForeignKey("inventory_movements.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "reversal_movement_id",
            uuid_type,
            sa.ForeignKey("inventory_movements.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_inventory_movements_bucket_occurred",
        "inventory_movements",
        ["product_id", "warehouse_id", "inventory_lot_id", "occurred_at"],
    )
    op.create_index("ix_inventory_movements_source", "inventory_movements", ["document_id", "line_id"])
    op.create_index("ix_inventory_documents_status_date", "inventory_documents", ["status", "effective_date"])
    op.create_index("ix_inventory_lots_product_code", "inventory_lots", ["product_id", "lot_code"])
    op.execute(
        "create unique index uq_inventory_balances_bucket on inventory_balances "
        "(warehouse_id, product_id, inventory_lot_id) nulls not distinct"
    )
    op.execute(
        "create unique index uq_inventory_movements_reversal on inventory_movements "
        "(reversal_of_id) where reversal_of_id is not null"
    )
    op.execute(
        "create unique index uq_inventory_documents_idempotency on inventory_documents "
        "(idempotency_key) where idempotency_key is not null"
    )
    op.execute(
        """
        create or replace function reject_inventory_movement_mutation() returns trigger language plpgsql as $$
        begin
            raise exception 'inventory movements are append-only';
        end $$;
        create trigger trg_inventory_movements_append_only
        before update or delete on inventory_movements
        for each row execute function reject_inventory_movement_mutation();
        """
    )


def downgrade() -> None:
    op.execute("drop trigger if exists trg_inventory_movements_append_only on inventory_movements")
    op.execute("drop function if exists reject_inventory_movement_mutation()")
    for index_name in (
        "uq_inventory_documents_idempotency",
        "uq_inventory_movements_reversal",
        "uq_inventory_balances_bucket",
    ):
        op.execute(f"drop index if exists {index_name}")
    for table in (
        "inventory_cost_variances",
        "inventory_balances",
        "inventory_movements",
        "inventory_document_lines",
        "inventory_documents",
        "inventory_lots",
    ):
        op.drop_table(table)
