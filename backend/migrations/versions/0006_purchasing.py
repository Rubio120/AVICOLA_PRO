"""Add purchasing and accounts payable."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006_purchasing"
down_revision = "0005_production"
branch_labels = None
depends_on = None


def upgrade() -> None:
    u = postgresql.UUID(as_uuid=True)
    op.create_table(
        "purchase_orders",
        sa.Column("id", u, primary_key=True),
        sa.Column("supplier_id", u, sa.ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("currency_code", sa.String(3), nullable=False, server_default="PYG"),
        sa.Column("status", sa.String(24), nullable=False, server_default="DRAFT"),
        sa.Column("subtotal", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("tax_total", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("approved_by", u, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint(
            "status in ('DRAFT','APPROVED','PARTIALLY_RECEIVED','RECEIVED','CANCELLED')",
            name="purchase_order_status_valid",
        ),
        sa.CheckConstraint("total >= 0", name="purchase_order_total_nonnegative"),
    )
    op.create_index("ix_purchase_orders_supplier_status", "purchase_orders", ["supplier_id", "status"])
    op.create_table(
        "purchase_order_lines",
        sa.Column("id", u, primary_key=True),
        sa.Column("purchase_order_id", u, sa.ForeignKey("purchase_orders.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("product_id", u, sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("received_quantity", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("unit_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("discount_rate", sa.Numeric(9, 6), nullable=False, server_default="0"),
        sa.Column("tax_rate", sa.Numeric(9, 6), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.UniqueConstraint("purchase_order_id", "ordinal", name="uq_purchase_order_line_ordinal"),
        sa.CheckConstraint(
            "quantity > 0 and received_quantity >= 0 and received_quantity <= quantity",
            name="purchase_order_line_quantities",
        ),
        sa.CheckConstraint(
            "unit_price >= 0 and discount_rate between 0 and 1 and tax_rate between 0 and 1",
            name="purchase_order_line_rates",
        ),
    )
    op.create_table(
        "purchase_receipts",
        sa.Column("id", u, primary_key=True),
        sa.Column("purchase_order_id", u, sa.ForeignKey("purchase_orders.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("warehouse_id", u, sa.ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("receipt_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="DRAFT"),
        sa.Column("inventory_document_id", u, sa.ForeignKey("inventory_documents.id", ondelete="RESTRICT")),
        sa.Column("idempotency_key", sa.String(128)),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("confirmed_by", u, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("reversed_at", sa.DateTime(timezone=True)),
        sa.Column("reversed_by", u, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("reversal_reason", sa.String(500)),
        sa.CheckConstraint("status in ('DRAFT','CONFIRMED','REVERSED')", name="purchase_receipt_status_valid"),
        sa.UniqueConstraint("idempotency_key", name="uq_purchase_receipt_idempotency"),
    )
    op.create_table(
        "purchase_receipt_lines",
        sa.Column("id", u, primary_key=True),
        sa.Column("receipt_id", u, sa.ForeignKey("purchase_receipts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column(
            "purchase_order_line_id", u, sa.ForeignKey("purchase_order_lines.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("product_id", u, sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("inventory_lot_id", u, sa.ForeignKey("inventory_lots.id", ondelete="RESTRICT")),
        sa.Column("lot_code", sa.String(80)),
        sa.Column("expiration_date", sa.Date()),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 6), nullable=False),
        sa.CheckConstraint("quantity > 0 and unit_cost >= 0", name="purchase_receipt_line_values"),
    )
    op.create_table(
        "supplier_documents",
        sa.Column("id", u, primary_key=True),
        sa.Column("supplier_id", u, sa.ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("document_type", sa.String(24), nullable=False, server_default="INVOICE"),
        sa.Column("external_number", sa.String(64), nullable=False),
        sa.Column("document_date", sa.Date(), nullable=False),
        sa.Column("currency_code", sa.String(3), nullable=False, server_default="PYG"),
        sa.Column("subtotal", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("tax_total", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(18, 2), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="CONFIRMED"),
        sa.UniqueConstraint("supplier_id", "document_type", "external_number", name="uq_supplier_document_number"),
        sa.CheckConstraint("total >= 0", name="supplier_document_total_nonnegative"),
    )
    op.create_table(
        "supplier_document_lines",
        sa.Column("id", u, primary_key=True),
        sa.Column(
            "supplier_document_id", u, sa.ForeignKey("supplier_documents.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("product_id", u, sa.ForeignKey("products.id", ondelete="RESTRICT")),
        sa.Column("description", sa.String(300), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("tax_rate", sa.Numeric(9, 6), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(18, 2), nullable=False),
        sa.CheckConstraint("quantity > 0 and unit_price >= 0", name="supplier_document_line_values"),
    )
    op.create_table(
        "supplier_document_receipts",
        sa.Column(
            "supplier_document_id", u, sa.ForeignKey("supplier_documents.id", ondelete="RESTRICT"), primary_key=True
        ),
        sa.Column("receipt_id", u, sa.ForeignKey("purchase_receipts.id", ondelete="RESTRICT"), primary_key=True),
        sa.UniqueConstraint("supplier_document_id", "receipt_id", name="uq_supplier_document_receipt"),
    )
    op.create_table(
        "accounts_payable",
        sa.Column("id", u, primary_key=True),
        sa.Column(
            "supplier_document_id",
            u,
            sa.ForeignKey("supplier_documents.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column("supplier_id", u, sa.ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("original_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("applied_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("balance", sa.Numeric(18, 2), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="OPEN"),
        sa.CheckConstraint(
            "original_amount >= 0 and applied_amount >= 0 and balance >= 0", name="ap_balance_nonnegative"
        ),
    )
    op.create_table(
        "supplier_payments",
        sa.Column("id", u, primary_key=True),
        sa.Column("supplier_id", u, sa.ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column(
            "payment_method_code",
            sa.String(32),
            sa.ForeignKey("payment_methods.code", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="DRAFT"),
        sa.Column("idempotency_key", sa.String(128)),
        sa.Column("cash_movement_id", u),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("confirmed_by", u, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("reversal_of_id", u, sa.ForeignKey("supplier_payments.id", ondelete="RESTRICT")),
        sa.Column("reversal_reason", sa.String(500)),
        sa.CheckConstraint("amount > 0", name="supplier_payment_positive"),
        sa.CheckConstraint("status in ('DRAFT','CONFIRMED','REVERSED')", name="supplier_payment_status_valid"),
        sa.UniqueConstraint("idempotency_key", name="uq_supplier_payment_idempotency"),
    )
    op.create_index("ix_supplier_payments_supplier_status", "supplier_payments", ["supplier_id", "status"])
    op.create_table(
        "supplier_payment_allocations",
        sa.Column("id", u, primary_key=True),
        sa.Column("payment_id", u, sa.ForeignKey("supplier_payments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("accounts_payable_id", u, sa.ForeignKey("accounts_payable.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.CheckConstraint("amount > 0", name="supplier_allocation_positive"),
    )


def downgrade() -> None:
    op.execute("drop table if exists supplier_document_lines")
    for table in (
        "supplier_payment_allocations",
        "supplier_payments",
        "accounts_payable",
        "supplier_document_receipts",
        "supplier_documents",
        "purchase_receipt_lines",
        "purchase_receipts",
        "purchase_order_lines",
        "purchase_orders",
    ):
        op.drop_table(table)
