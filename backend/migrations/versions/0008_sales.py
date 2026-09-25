"""Add internal sales, deliveries and accounts receivable."""

# ruff: noqa: E501

from alembic import op

revision = "0008_sales"
down_revision = "0007_supplier_document_lines"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    create table sales_orders (
      id uuid primary key, customer_id uuid not null references customers(id) on delete restrict,
      order_date date not null, status varchar(24) not null default 'DRAFT', currency_code varchar(3) not null default 'PYG',
      total numeric(18,2) not null default 0, version integer not null default 1,
      constraint sales_order_status_valid check (status in ('DRAFT','CONFIRMED','PARTIALLY_FULFILLED','FULFILLED','CANCELLED'))
    );
    create table sales_order_lines (
      id uuid primary key, sales_order_id uuid not null references sales_orders(id) on delete restrict, ordinal integer not null,
      product_id uuid not null references products(id) on delete restrict, quantity numeric(18,4) not null,
      delivered_quantity numeric(18,4) not null default 0, unit_price numeric(18,6) not null,
      discount_rate numeric(9,6) not null default 0, tax_rate numeric(9,6) not null default 0,
      unique(sales_order_id, ordinal), check (quantity > 0 and delivered_quantity >= 0 and delivered_quantity <= quantity), check (unit_price >= 0)
    );
    create table sales_deliveries (
      id uuid primary key, sales_order_id uuid not null references sales_orders(id) on delete restrict,
      customer_id uuid not null references customers(id) on delete restrict, warehouse_id uuid not null references warehouses(id) on delete restrict,
      delivery_date date not null, status varchar(16) not null default 'DRAFT', inventory_document_id uuid references inventory_documents(id) on delete restrict,
      idempotency_key varchar(128) unique, confirmed_at timestamptz, confirmed_by uuid references users(id) on delete restrict,
      check (status in ('DRAFT','CONFIRMED','REVERSED'))
    );
    create table sales_delivery_lines (
      id uuid primary key, delivery_id uuid not null references sales_deliveries(id) on delete restrict,
      sales_order_line_id uuid not null references sales_order_lines(id) on delete restrict, product_id uuid not null references products(id) on delete restrict,
      inventory_lot_id uuid references inventory_lots(id) on delete restrict, quantity numeric(18,4) not null check(quantity > 0)
    );
    create table commercial_documents (
      id uuid primary key, document_type varchar(24) not null default 'INVOICE', series varchar(16) not null, number varchar(32) not null,
      customer_id uuid not null references customers(id) on delete restrict, customer_name_snapshot varchar(200) not null,
      customer_document_snapshot varchar(64) not null, document_date date not null, currency_code varchar(3) not null default 'PYG',
      status varchar(24) not null default 'ISSUED', exempt_subtotal numeric(18,2) not null default 0, vat_5_base numeric(18,2) not null default 0,
      vat_5_amount numeric(18,2) not null default 0, vat_10_base numeric(18,2) not null default 0, vat_10_amount numeric(18,2) not null default 0,
      discount_total numeric(18,2) not null default 0, subtotal numeric(18,2) not null default 0, tax_total numeric(18,2) not null default 0,
      total numeric(18,2) not null, original_document_id uuid references commercial_documents(id) on delete restrict, confirmed_at timestamptz not null default now(),
      unique(document_type, series, number), check(total >= 0)
    );
    create index ix_commercial_documents_customer_status on commercial_documents(customer_id, status);
    create table commercial_document_lines (
      id uuid primary key, commercial_document_id uuid not null references commercial_documents(id) on delete restrict, ordinal integer not null,
      product_id uuid references products(id) on delete restrict, description varchar(300) not null, quantity numeric(18,4) not null,
      unit_price numeric(18,6) not null, discount_rate numeric(9,6) not null default 0, tax_rate numeric(9,6) not null,
      base_amount numeric(18,2) not null, tax_amount numeric(18,2) not null, total numeric(18,2) not null,
      unique(commercial_document_id, ordinal), check(quantity > 0 and unit_price >= 0)
    );
    create table commercial_document_relations (
      source_document_id uuid not null references commercial_documents(id) on delete restrict, target_type varchar(24) not null,
      target_id uuid not null, primary key(source_document_id, target_type, target_id)
    );
    create table accounts_receivable (
      id uuid primary key, commercial_document_id uuid not null unique references commercial_documents(id) on delete restrict,
      customer_id uuid not null references customers(id) on delete restrict, original_amount numeric(18,2) not null,
      applied_amount numeric(18,2) not null default 0, balance numeric(18,2) not null, due_date date not null, status varchar(16) not null default 'OPEN',
      check(original_amount >= 0 and applied_amount >= 0 and balance >= 0)
    );
    create table customer_payments (
      id uuid primary key, customer_id uuid not null references customers(id) on delete restrict, amount numeric(18,2) not null,
      payment_date date not null, payment_method_code varchar(32) not null references payment_methods(code) on delete restrict,
      status varchar(16) not null default 'DRAFT', idempotency_key varchar(128) unique, cash_movement_id uuid,
      confirmed_at timestamptz, confirmed_by uuid references users(id) on delete restrict, check(amount > 0)
    );
    create table customer_payment_allocations (
      id uuid primary key, payment_id uuid not null references customer_payments(id) on delete restrict,
      accounts_receivable_id uuid not null references accounts_receivable(id) on delete restrict, amount numeric(18,2) not null check(amount > 0)
    );
    """)


def downgrade() -> None:
    for table in (
        "customer_payment_allocations",
        "customer_payments",
        "accounts_receivable",
        "commercial_document_relations",
        "commercial_document_lines",
        "commercial_documents",
        "sales_delivery_lines",
        "sales_deliveries",
        "sales_order_lines",
        "sales_orders",
    ):
        op.execute(f"drop table if exists {table}")
