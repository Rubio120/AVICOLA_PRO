from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection

from avicola_pro.modules.identity.infrastructure.models import Permission, Role, RolePermission

BASE_PERMISSION_KEYS = (
    "users.manage",
    "roles.manage",
    "settings.manage",
    "audit.read",
    "audit.export",
    "session.self",
    "inventory.products.read",
    "inventory.movements.create",
    "inventory.adjustments.approve",
    "inventory.transfers.confirm",
    "purchases.orders.create",
    "purchases.orders.approve",
    "purchases.receipts.confirm",
    "sales.orders.create",
    "sales.documents.issue",
    "sales.documents.cancel",
    "sales.credit_notes.issue",
    "cash.movements.create",
    "cash.movements.reverse",
    "cash.closings.execute",
    "production.mortality.record",
    "production.feed.record",
    "production.flocks.manage",
    "production.adjustments.approve",
    "costs.recalculate",
    "reports.profitability.read",
    "reports.export",
    "backups.execute",
    "parties.manage",
    "catalog.manage",
    "catalog.read",
    "purchases.documents.create",
    "purchases.payments.create",
    "purchases.payments.reverse",
    "production.eggs.read",
    "production.eggs.record",
    "inventory.egg_categories.manage",
    "production.eggs.classify",
)

BASE_ROLE_CODES = (
    "administrator",
    "management",
    "production",
    "inventory",
    "purchasing",
    "sales",
    "cash",
    "finance",
    "auditor",
)

_PERMISSION_IDS = {
    key: UUID(f"10000000-0000-7000-8000-{index:012d}") for index, key in enumerate(BASE_PERMISSION_KEYS, start=1)
}
_ROLE_IDS = {code: UUID(f"20000000-0000-7000-8000-{index:012d}") for index, code in enumerate(BASE_ROLE_CODES, start=1)}
_ROLE_NAMES = {
    "administrator": "Administrador",
    "management": "Gerencia",
    "production": "Producción",
    "inventory": "Inventario",
    "purchasing": "Compras",
    "sales": "Ventas",
    "cash": "Caja",
    "finance": "Finanzas",
    "auditor": "Auditor",
}


def seed_base_catalog(connection: Connection) -> None:
    """Idempotently install the versioned base role and permission catalog."""

    permission_rows = [
        {
            "id": _PERMISSION_IDS[key],
            "key": key,
            "description": f"Permite {key}",
        }
        for key in BASE_PERMISSION_KEYS
    ]
    role_rows = [
        {
            "id": _ROLE_IDS[code],
            "code": code,
            "name": _ROLE_NAMES[code],
            "description": f"Rol oficial {_ROLE_NAMES[code]}",
            "is_system": True,
        }
        for code in BASE_ROLE_CODES
    ]
    connection.execute(insert(Permission).values(permission_rows).on_conflict_do_nothing())
    connection.execute(insert(Role).values(role_rows).on_conflict_do_nothing())
    persisted_permission_ids: dict[str, UUID] = {
        row.key: row.id for row in connection.execute(select(Permission.key, Permission.id)).all()
    }
    persisted_role_ids: dict[str, UUID] = {
        row.code: row.id for row in connection.execute(select(Role.code, Role.id)).all()
    }
    administrator_grants = [
        {
            "role_id": persisted_role_ids["administrator"],
            "permission_id": persisted_permission_ids[key],
        }
        for key in BASE_PERMISSION_KEYS
    ]
    connection.execute(insert(RolePermission).values(administrator_grants).on_conflict_do_nothing())
