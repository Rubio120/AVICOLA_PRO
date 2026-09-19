from __future__ import annotations

import os
import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg import errors
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from avicola_pro.modules.catalog.infrastructure.models import Product, Warehouse
from avicola_pro.modules.identity.infrastructure.models import User
from avicola_pro.modules.inventory.application.service import InventoryConflictError, inventory_service
from avicola_pro.modules.inventory.infrastructure.models import (
    InventoryBalance,
    InventoryCostVariance,
    InventoryDocument,
    InventoryDocumentLine,
)
from avicola_pro.modules.settings.infrastructure.models import UnitOfMeasure

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _database_url() -> str:
    return os.environ["AVICOLA_TEST_DATABASE_URL"]


def _reset_schema() -> None:
    environment = os.environ.copy()
    environment["AVICOLA_DATABASE_URL"] = _database_url()
    environment["AVICOLA_SESSION_HMAC_KEY"] = "jUrUWz89-ZPO0xh7ppVRm50Pt-un53S_NSfNCACPXaM"
    for command in (("downgrade", "base"), ("upgrade", "head")):
        subprocess.run([sys.executable, "-m", "alembic", *command], cwd=BACKEND_ROOT, env=environment, check=True)


@pytest.fixture(autouse=True)
def migrated_database() -> None:
    _reset_schema()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_confirmed_receipts_and_issue_reconcile_moving_average() -> None:
    assert UnitOfMeasure.__tablename__ == "units_of_measure"
    engine = create_async_engine(_database_url())
    session_factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    user_id = uuid4()
    product_id = uuid4()
    warehouse_id = uuid4()
    async with session_factory() as session, session.begin():
        session.add(
            User(
                id=user_id,
                username="inventory",
                email="inventory@example.test",
                display_name="Inventory",
                password_hash="argon2id",  # noqa: S106 - synthetic fixture value, never a credential
            )
        )
        session.add(
            Product(
                id=product_id,
                sku="INV-001",
                name="Inventory test",
                product_type="INPUT",
                base_unit_code="unit",
            )
        )
        session.add(Warehouse(id=warehouse_id, code="INV-WH", name="Inventory warehouse", is_active=True))
    async with session_factory() as session, session.begin():
        receipt_ids: list[UUID] = []
        for quantity, cost in ((Decimal("10"), Decimal("10")), (Decimal("10"), Decimal("20"))):
            document = InventoryDocument(
                id=uuid4(), document_type="RECEIPT", effective_date=date(2026, 9, 19), warehouse_id=warehouse_id
            )
            session.add(document)
            receipt_ids.append(document.id)
            await session.flush()
            session.add(
                InventoryDocumentLine(
                    id=uuid4(),
                    document_id=document.id,
                    ordinal=1,
                    product_id=product_id,
                    quantity=quantity,
                    unit_cost=cost,
                    direction="IN",
                )
            )
            await session.flush()
            await inventory_service.confirm(session, document.id, user_id)
        issue = InventoryDocument(
            id=uuid4(), document_type="ISSUE", effective_date=date(2026, 9, 19), warehouse_id=warehouse_id
        )
        session.add(issue)
        await session.flush()
        session.add(
            InventoryDocumentLine(
                id=uuid4(),
                document_id=issue.id,
                ordinal=1,
                product_id=product_id,
                quantity=Decimal("10"),
                unit_cost=Decimal("0"),
                direction="OUT",
            )
        )
        await session.flush()
        await inventory_service.confirm(session, issue.id, user_id)
        balance = await session.scalar(select(InventoryBalance).where(InventoryBalance.warehouse_id == warehouse_id))
        assert balance is not None
        assert balance.quantity == Decimal("10.0000")
        assert balance.inventory_value == Decimal("150.00")
        assert balance.average_cost == Decimal("15.000000")
        reversal = await inventory_service.reverse(session, issue.id, user_id, "Test correction")
        assert reversal.status == "CONFIRMED"
        balance = await session.scalar(select(InventoryBalance).where(InventoryBalance.warehouse_id == warehouse_id))
        assert balance is not None
        assert balance.quantity == Decimal("20.0000")
        assert balance.inventory_value == Decimal("300.00")
        with pytest.raises(InventoryConflictError, match="already reversed"):
            await inventory_service.reverse(session, issue.id, user_id, "Duplicate correction")
        await inventory_service.reverse(session, receipt_ids[0], user_id, "Historical cost correction")
        variance = await session.scalar(select(InventoryCostVariance))
        assert variance is not None
        assert variance.amount == Decimal("-50.00")
    await engine.dispose()
    with psycopg.connect(_database_url().replace("+psycopg", "")) as connection, connection.cursor() as cursor:
        cursor.execute("select id from inventory_movements limit 1")
        movement_row = cursor.fetchone()
        assert movement_row is not None
        movement_id = movement_row[0]
        with pytest.raises(errors.RaiseException, match="append-only"):
            cursor.execute("update inventory_movements set unit_cost = 999 where id = %s", (movement_id,))
