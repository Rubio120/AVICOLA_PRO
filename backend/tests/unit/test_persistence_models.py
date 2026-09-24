from __future__ import annotations

import importlib
import importlib.util

from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import JSONB, UUID


def test_identity_and_audit_models_share_central_metadata() -> None:
    assert importlib.util.find_spec("avicola_pro.shared.infrastructure.models") is not None

    persistence = importlib.import_module("avicola_pro.shared.infrastructure.models")
    persistence.load_persistence_models()
    importlib.import_module("avicola_pro.modules.identity.infrastructure.models")
    importlib.import_module("avicola_pro.modules.audit.infrastructure.models")

    assert set(persistence.metadata.tables) == {
        "audit_events",
        "permissions",
        "role_permissions",
        "roles",
        "security_events",
        "sessions",
        "user_roles",
        "users",
        "company_profile",
        "currencies",
        "units_of_measure",
        "tax_rates",
        "stamps",
        "document_sequences",
        "payment_methods",
        "customers",
        "suppliers",
        "product_categories",
        "products",
        "farms",
        "houses",
        "warehouses",
        "inventory_lots",
        "inventory_documents",
        "inventory_document_lines",
        "inventory_movements",
        "inventory_balances",
        "inventory_cost_variances",
        "egg_categories",
        "egg_presentation_conversions",
        "egg_production_classifications",
        "egg_production_allocations",
        "flocks",
        "flock_house_assignments",
        "flock_balances",
        "bird_movement_events",
        "mortality_events",
        "bird_adjustment_events",
        "flock_daily_records",
        "feed_consumption",
        "egg_production_events",
        "purchase_orders",
        "purchase_order_lines",
        "purchase_receipts",
        "purchase_receipt_lines",
        "supplier_documents",
        "supplier_document_lines",
        "supplier_document_receipts",
        "accounts_payable",
        "supplier_payments",
        "supplier_payment_allocations",
        "sales_orders",
        "sales_order_lines",
        "sales_deliveries",
        "sales_delivery_lines",
        "commercial_documents",
        "commercial_document_lines",
        "commercial_document_relations",
        "accounts_receivable",
        "customer_payments",
        "customer_payment_allocations",
        "cash_accounts",
        "cash_sessions",
        "cash_movements",
        "cash_transfers",
        "cost_centers",
        "cost_events",
        "cost_allocations",
        "cost_runs",
        "cost_run_snapshots",
        "profitability_snapshots",
    }


def test_persistence_models_use_postgresql_uuid_timestamptz_and_jsonb() -> None:
    assert importlib.util.find_spec("avicola_pro.shared.infrastructure.models") is not None

    persistence = importlib.import_module("avicola_pro.shared.infrastructure.models")
    persistence.load_persistence_models()
    importlib.import_module("avicola_pro.modules.identity.infrastructure.models")
    importlib.import_module("avicola_pro.modules.audit.infrastructure.models")
    tables = persistence.metadata.tables

    assert isinstance(tables["users"].c.id.type, UUID)
    assert tables["users"].c.id.type.as_uuid is True
    assert isinstance(tables["users"].c.created_at.type, DateTime)
    assert tables["users"].c.created_at.type.timezone is True
    assert isinstance(tables["audit_events"].c.before_data.type, JSONB)
    assert isinstance(tables["audit_events"].c.after_data.type, JSONB)
    assert isinstance(tables["security_events"].c.metadata.type, JSONB)


def test_egg_inventory_models_require_explicit_configuration_and_classification() -> None:
    persistence = importlib.import_module("avicola_pro.shared.infrastructure.models")
    persistence.load_persistence_models()
    tables = persistence.metadata.tables

    categories = tables["egg_categories"]
    assert categories.c.product_id.nullable is False
    assert categories.c.is_saleable.nullable is False
    assert categories.c.is_saleable.server_default is None
    assert any(
        {"product_id"} == {column.name for column in constraint.columns} for constraint in categories.constraints
    )

    conversions = tables["egg_presentation_conversions"]
    assert {"category_id", "unit_code", "version"} <= set(conversions.c.keys())
    assert any(constraint.name.endswith("egg_conversion_factor_positive") for constraint in conversions.constraints)
    assert any(constraint.name.endswith("egg_conversion_version_positive") for constraint in conversions.constraints)

    classifications = tables["egg_production_classifications"]
    assert classifications.c.warehouse_id.nullable is False
    assert classifications.c.production_event_id.unique is True
    assert classifications.c.inventory_document_id.nullable is True

    allocations = tables["egg_production_allocations"]
    assert any(constraint.name.endswith("egg_allocation_count_nonnegative") for constraint in allocations.constraints)


def test_sales_channels_allow_unclassified_history_but_constrain_new_values() -> None:
    persistence = importlib.import_module("avicola_pro.shared.infrastructure.models")
    persistence.load_persistence_models()
    tables = persistence.metadata.tables

    for table_name in ("sales_orders", "commercial_documents"):
        channel = tables[table_name].c.channel
        assert channel.nullable is True
        checks = [
            constraint.sqltext.text
            for constraint in tables[table_name].constraints
            if constraint.__class__.__name__ == "CheckConstraint"
        ]
        assert any("WHOLESALE" in check and "RETAIL" in check for check in checks)
