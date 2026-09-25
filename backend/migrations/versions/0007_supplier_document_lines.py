"""Ensure supplier document lines exist after the purchasing baseline."""

from alembic import op

revision = "0007_supplier_document_lines"
down_revision = "0006_purchasing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table if not exists supplier_document_lines (
            id uuid primary key,
            supplier_document_id uuid not null references supplier_documents(id) on delete restrict,
            ordinal integer not null,
            product_id uuid references products(id) on delete restrict,
            description varchar(300) not null,
            quantity numeric(18,4) not null,
            unit_price numeric(18,6) not null,
            tax_rate numeric(9,6) not null default 0,
            tax_amount numeric(18,2) not null default 0,
            total numeric(18,2) not null,
            constraint supplier_document_line_values check (quantity > 0 and unit_price >= 0)
        )
        """
    )


def downgrade() -> None:
    op.execute("drop table if exists supplier_document_lines")
