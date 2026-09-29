"""Add configurable egg categories, conversion versions and production allocation records."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0012_egg_inventory"
down_revision = "0011_egg_production"
branch_labels = None
depends_on = None


def upgrade() -> None:
    u = postgresql.UUID(as_uuid=True)
    op.create_table(
        "egg_categories",
        sa.Column("id", u, primary_key=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("product_id", u, sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("is_saleable", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("code <> '' and name <> ''", name="egg_category_text_nonempty"),
    )
    op.create_table(
        "egg_presentation_conversions",
        sa.Column("id", u, primary_key=True),
        sa.Column("category_id", u, sa.ForeignKey("egg_categories.id", ondelete="RESTRICT"), nullable=False),
        sa.Column(
            "unit_code",
            sa.String(32),
            sa.ForeignKey("units_of_measure.code", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("units_per_package", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("units_per_package > 0", name="egg_conversion_factor_positive"),
        sa.CheckConstraint("version > 0", name="egg_conversion_version_positive"),
        sa.UniqueConstraint("category_id", "unit_code", "version", name="egg_conversion_version_unique"),
    )
    op.create_table(
        "egg_production_classifications",
        sa.Column("id", u, primary_key=True),
        sa.Column(
            "production_event_id",
            u,
            sa.ForeignKey("egg_production_events.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column("warehouse_id", u, sa.ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False),
        sa.Column(
            "inventory_document_id",
            u,
            sa.ForeignKey("inventory_documents.id", ondelete="RESTRICT"),
            nullable=True,
            unique=True,
        ),
        sa.Column("idempotency_key", sa.String(128), nullable=False, unique=True),
        sa.Column("actor_user_id", u, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "egg_production_allocations",
        sa.Column("id", u, primary_key=True),
        sa.Column(
            "classification_id",
            u,
            sa.ForeignKey("egg_production_classifications.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("category_id", u, sa.ForeignKey("egg_categories.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("egg_count", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("egg_count >= 0", name="egg_allocation_count_nonnegative"),
        sa.UniqueConstraint("classification_id", "category_id", name="egg_allocation_category_unique"),
    )
    op.execute(
        "create trigger trg_egg_presentation_conversions_append_only "
        "before update or delete on egg_presentation_conversions "
        "for each row execute function reject_append_only_mutation()"
    )
    op.execute(
        "create trigger trg_egg_production_classifications_append_only "
        "before update or delete on egg_production_classifications "
        "for each row execute function reject_append_only_mutation()"
    )
    op.execute(
        "create trigger trg_egg_production_allocations_append_only "
        "before update or delete on egg_production_allocations "
        "for each row execute function reject_append_only_mutation()"
    )
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
                "id": "10000000-0000-7000-8000-000000000037",
                "key": "inventory.egg_categories.manage",
                "description": "Permite inventory.egg_categories.manage",
            },
            {
                "id": "10000000-0000-7000-8000-000000000038",
                "key": "production.eggs.classify",
                "description": "Permite production.eggs.classify",
            },
        ],
    )


def downgrade() -> None:
    op.execute("drop trigger if exists trg_egg_production_allocations_append_only on egg_production_allocations")
    op.execute(
        "drop trigger if exists trg_egg_production_classifications_append_only on egg_production_classifications"
    )
    op.execute("drop trigger if exists trg_egg_presentation_conversions_append_only on egg_presentation_conversions")
    op.drop_table("egg_production_allocations")
    op.drop_table("egg_production_classifications")
    op.drop_table("egg_presentation_conversions")
    op.drop_table("egg_categories")
    op.execute(
        "delete from role_permissions where permission_id in "
        "('10000000-0000-7000-8000-000000000037', '10000000-0000-7000-8000-000000000038')"
    )
    op.execute(
        "delete from permissions where id in "
        "('10000000-0000-7000-8000-000000000037', '10000000-0000-7000-8000-000000000038')"
    )
