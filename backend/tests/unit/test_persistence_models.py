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
        "flocks",
        "flock_house_assignments",
        "flock_balances",
        "bird_movement_events",
        "mortality_events",
        "bird_adjustment_events",
        "flock_daily_records",
        "feed_consumption",
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
