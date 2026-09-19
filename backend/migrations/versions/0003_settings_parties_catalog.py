"""Add company settings, parties and master catalog."""

from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_settings_parties_catalog"
down_revision = "0002_identity_rbac_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "company_profile",
        sa.Column("singleton_key", sa.SmallInteger(), primary_key=True, server_default="1"),
        sa.Column("legal_name", sa.String(200), nullable=False),
        sa.Column("tax_id", sa.String(32), nullable=False),
        sa.Column("trade_name", sa.String(200)),
        sa.Column("address", sa.String(500)),
        sa.Column("base_currency", sa.String(3), nullable=False, server_default="PYG"),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="America/Asuncion"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("singleton_key = 1", name="singleton_key_one"),
        sa.CheckConstraint("base_currency = 'PYG'", name="base_currency_pyg"),
    )
    op.create_table(
        "currencies",
        sa.Column("code", sa.String(3), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("decimals", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.CheckConstraint("decimals between 0 and 6", name="currency_decimals_range"),
    )
    op.create_table(
        "units_of_measure",
        sa.Column("code", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("precision", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.CheckConstraint("precision between 0 and 9", name="unit_precision_range"),
    )
    op.create_table(
        "tax_rates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("rate", sa.Numeric(9, 6), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.CheckConstraint("rate >= 0 and rate <= 1", name="rate_range"),
        sa.CheckConstraint("valid_to is null or valid_to >= valid_from", name="validity_order"),
        sa.UniqueConstraint("code", "valid_from", name="uq_tax_rates_code_valid_from"),
    )
    op.create_table(
        "stamps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("establishment", sa.String(10), nullable=False),
        sa.Column("number", sa.String(32), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("establishment", "number", name="uq_stamps_establishment_number"),
    )
    op.create_table(
        "document_sequences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_type", sa.String(64), nullable=False),
        sa.Column("series", sa.String(16), nullable=False),
        sa.Column("prefix", sa.String(16), nullable=False, server_default=""),
        sa.Column("current_number", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("padding", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("stamp_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stamps.id", ondelete="RESTRICT")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.CheckConstraint("current_number >= 0", name="current_number_nonnegative"),
        sa.CheckConstraint("padding between 1 and 18", name="padding_range"),
        sa.UniqueConstraint("document_type", "series", name="uq_document_sequences_type_series"),
    )
    op.create_table(
        "payment_methods",
        sa.Column("code", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column("document_type", sa.String(16), nullable=False),
        sa.Column("document_number", sa.String(32), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("contacts", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("credit_limit", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("payment_term_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("credit_limit >= 0", name="credit_limit_nonnegative"),
        sa.CheckConstraint("payment_term_days >= 0", name="customer_payment_term_nonnegative"),
    )
    op.create_table(
        "suppliers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column("document_type", sa.String(16), nullable=False, server_default="RUC"),
        sa.Column("document_number", sa.String(32), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("contacts", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("payment_term_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("payment_term_days >= 0", name="supplier_payment_term_nonnegative"),
    )
    op.create_table(
        "product_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("sku", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("product_type", sa.String(16), nullable=False),
        sa.Column(
            "category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("product_categories.id", ondelete="RESTRICT")
        ),
        sa.Column(
            "base_unit_code", sa.String(32), sa.ForeignKey("units_of_measure.code", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("tracks_lot", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("tracks_expiration", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("product_type in ('PRODUCT','INPUT','SERVICE')", name="product_type_valid"),
    )
    op.create_table(
        "farms",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("location", sa.String(300)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "houses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "farm_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("farms.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.CheckConstraint("capacity > 0", name="capacity_positive"),
        sa.UniqueConstraint("farm_id", "code", name="uq_houses_farm_code"),
    )
    op.create_table(
        "warehouses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("location", sa.String(300)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_customers_name", "customers", ["name"])
    op.create_index("ix_suppliers_name", "suppliers", ["name"])
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "insert into currencies(code,name,decimals) values ('PYG','Guaraní paraguayo',0) on conflict do nothing"
        )
    )
    bind.execute(
        sa.text(
            "insert into units_of_measure(code,name,precision) values "
            "('unit','Unidad',0),('kg','Kilogramo',4),('l','Litro',4) on conflict do nothing"
        )
    )
    bind.execute(
        sa.text(
            "insert into payment_methods(code,name) values "
            "('cash','Efectivo'),('bank_transfer','Transferencia bancaria') on conflict do nothing"
        )
    )
    permission_rows = [
        ("parties.manage", "Gestionar terceros"),
        ("catalog.manage", "Gestionar catálogo"),
        ("catalog.read", "Leer catálogo"),
    ]
    for index, (key, description) in enumerate(permission_rows, start=27):
        bind.execute(
            sa.text(
                "insert into permissions(id,key,description) "
                "select :id,cast(:key as varchar),cast(:description as text) where not exists "
                "(select 1 from permissions where key=cast(:key as varchar))"
            ),
            {
                "id": UUID(f"10000000-0000-7000-8000-{index:012d}"),
                "key": key,
                "description": description,
            },
        )
        bind.execute(
            sa.text(
                "insert into role_permissions(role_id,permission_id) "
                "select r.id,p.id from roles r,permissions p "
                "where r.code='administrator' and p.key=:key on conflict do nothing"
            ),
            {"key": key},
        )


def downgrade() -> None:
    for table in (
        "warehouses",
        "houses",
        "farms",
        "products",
        "product_categories",
        "suppliers",
        "customers",
        "payment_methods",
        "document_sequences",
        "stamps",
        "tax_rates",
        "units_of_measure",
        "currencies",
        "company_profile",
    ):
        op.drop_table(table)
