"""Add explicit wholesale/retail channel snapshots to sales."""

import sqlalchemy as sa
from alembic import op

revision = "0013_sales_channel"
down_revision = "0012_egg_inventory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sales_orders", sa.Column("channel", sa.String(16), nullable=True))
    op.add_column("commercial_documents", sa.Column("channel", sa.String(16), nullable=True))
    op.create_check_constraint(
        "sales_order_channel_valid", "sales_orders", "channel is null or channel in ('WHOLESALE','RETAIL')"
    )
    op.create_check_constraint(
        "commercial_document_channel_valid",
        "commercial_documents",
        "channel is null or channel in ('WHOLESALE','RETAIL')",
    )


def downgrade() -> None:
    op.drop_constraint("commercial_document_channel_valid", "commercial_documents", type_="check")
    op.drop_constraint("sales_order_channel_valid", "sales_orders", type_="check")
    op.drop_column("commercial_documents", "channel")
    op.drop_column("sales_orders", "channel")
