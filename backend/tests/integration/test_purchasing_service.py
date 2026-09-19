from __future__ import annotations

import os
import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from avicola_pro.modules.catalog.infrastructure.models import Product, Warehouse
from avicola_pro.modules.identity.infrastructure.models import User
from avicola_pro.modules.parties.infrastructure.models import Supplier
from avicola_pro.modules.purchasing.application.service import purchasing_service
from avicola_pro.modules.purchasing.infrastructure.models import (
    AccountsPayable,
    PurchaseOrderLine,
    PurchaseReceipt,
    PurchaseReceiptLine,
    SupplierPayment,
    SupplierPaymentAllocation,
)
from avicola_pro.modules.settings.infrastructure.models import UnitOfMeasure

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _database_url() -> str:
    return os.environ["AVICOLA_TEST_DATABASE_URL"]


@pytest.fixture(autouse=True)
def migrated_database() -> None:
    environment = os.environ.copy()
    environment["AVICOLA_DATABASE_URL"] = _database_url()
    environment["AVICOLA_SESSION_HMAC_KEY"] = "jUrUWz89-ZPO0xh7ppVRm50Pt-un53S_NSfNCACPXaM"
    for command in (("downgrade", "base"), ("upgrade", "head")):
        subprocess.run([sys.executable, "-m", "alembic", *command], cwd=BACKEND_ROOT, env=environment, check=True)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_purchase_order_receipt_ap_payment_and_reversal_are_atomic() -> None:
    assert UnitOfMeasure.__tablename__ == "units_of_measure"
    engine = create_async_engine(_database_url())
    sessions = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    user_id, supplier_id, product_id, warehouse_id = (uuid4() for _ in range(4))
    async with sessions() as session, session.begin():
        session.add(
            User(
                id=user_id,
                username="buyer",
                email="buyer@example.test",
                display_name="Buyer",
                password_hash="argon2id",  # noqa: S106
            )
        )
        session.add(Supplier(id=supplier_id, code="SUP-001", document_number="80000001-1", name="Supplier"))
        session.add(Product(id=product_id, sku="BUY-001", name="Feed", product_type="INPUT", base_unit_code="unit"))
        session.add(Warehouse(id=warehouse_id, code="BUY-WH", name="Buy warehouse", is_active=True))

    async with sessions() as session, session.begin():
        order = await purchasing_service.create_order(
            session,
            supplier_id,
            date(2026, 9, 19),
            [{"product_id": product_id, "quantity": Decimal("5"), "unit_price": Decimal("100")}],
        )
        await purchasing_service.approve_order(session, order.id, user_id)
        line = await session.scalar(select(PurchaseOrderLine).where(PurchaseOrderLine.purchase_order_id == order.id))
        assert line is not None
        receipt = PurchaseReceipt(
            id=uuid4(), purchase_order_id=order.id, warehouse_id=warehouse_id, receipt_date=date(2026, 9, 19)
        )
        session.add(receipt)
        await session.flush()
        session.add(
            PurchaseReceiptLine(
                id=uuid4(),
                receipt_id=receipt.id,
                purchase_order_line_id=line.id,
                product_id=product_id,
                lot_code="LOT-1",
                quantity=Decimal("5"),
                unit_cost=Decimal("100"),
            )
        )
        await session.flush()
        await purchasing_service.confirm_receipt(session, receipt.id, user_id)
        assert receipt.status == "CONFIRMED"
        document = await purchasing_service.create_supplier_document(
            session,
            {
                "supplier_id": supplier_id,
                "document_type": "INVOICE",
                "external_number": "INV-1",
                "document_date": date(2026, 9, 19),
                "total": Decimal("500"),
                "subtotal": Decimal("500"),
                "tax_total": Decimal("0"),
            },
        )
        account = await session.scalar(
            select(AccountsPayable).where(AccountsPayable.supplier_document_id == document.id)
        )
        assert account is not None
        payment = SupplierPayment(
            id=uuid4(),
            supplier_id=supplier_id,
            amount=Decimal("500"),
            payment_date=date(2026, 9, 19),
            payment_method_code="cash",
        )
        session.add(payment)
        await session.flush()
        session.add(
            SupplierPaymentAllocation(
                id=uuid4(), payment_id=payment.id, accounts_payable_id=account.id, amount=Decimal("500")
            )
        )
        await session.flush()
        await purchasing_service.confirm_payment(session, payment.id, user_id)
        assert account.status == "PAID"
        reversal = await purchasing_service.reverse_payment(session, payment.id, user_id, "Correction")
        assert reversal.reversal_of_id == payment.id
        assert account.status == "OPEN"
    await engine.dispose()
