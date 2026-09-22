from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from avicola_pro.modules.catalog.infrastructure.models import Product, Warehouse
from avicola_pro.modules.identity.infrastructure.models import User
from avicola_pro.modules.parties.infrastructure.models import Supplier
from avicola_pro.modules.purchasing.application.service import purchasing_service
from avicola_pro.modules.purchasing.domain.rules import PurchaseConflictError
from avicola_pro.modules.purchasing.infrastructure.models import (
    AccountsPayable,
    PurchaseOrderLine,
    PurchaseReceipt,
    PurchaseReceiptLine,
    SupplierDocument,
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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_supplier_payment_idempotency_reuses_identical_request_and_rejects_changed_request() -> None:
    engine = create_async_engine(_database_url())
    sessions = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    supplier_id, payable_ids, actor_id = uuid4(), [uuid4(), uuid4()], uuid4()
    async with sessions() as session, session.begin():
        session.add(Supplier(id=supplier_id, code="IDEM-SUP", document_number="80000002-2", name="Idempotent"))
        session.add(
            User(
                id=actor_id,
                username="idempotent-buyer",
                email="idempotent-buyer@example.test",
                display_name="Idempotent Buyer",
                password_hash="argon2id",  # noqa: S106
            )
        )
        for ordinal, payable_id in enumerate(payable_ids, start=1):
            document = SupplierDocument(
                id=uuid4(),
                supplier_id=supplier_id,
                external_number=f"IDEM-{ordinal}",
                document_date=date(2026, 9, 22),
                total=Decimal("100"),
            )
            session.add(document)
            await session.flush()
            session.add(
                AccountsPayable(
                    id=payable_id,
                    supplier_document_id=document.id,
                    supplier_id=supplier_id,
                    original_amount=Decimal("100"),
                    balance=Decimal("100"),
                    due_date=date(2026, 10, 22),
                )
            )

    first_key = "delivery6-payment-001"
    first_allocations = [
        {"accounts_payable_id": payable_ids[0], "amount": Decimal("40")},
        {"accounts_payable_id": payable_ids[1], "amount": Decimal("60")},
    ]

    async def create() -> UUID:
        async with sessions() as session, session.begin():
            payment, _ = await purchasing_service.create_payment(
                session,
                supplier_id,
                Decimal("100"),
                date(2026, 9, 22),
                "cash",
                first_key,
                first_allocations,
            )
            return cast(UUID, payment.id)

    first_id, retry_id = await asyncio.gather(create(), create())
    assert first_id == retry_id

    async with sessions() as session:
        payments = list((await session.scalars(select(SupplierPayment))).all())
        allocations = list((await session.scalars(select(SupplierPaymentAllocation))).all())
    assert len(payments) == 1
    assert len(allocations) == 2
    assert {row.amount for row in allocations} == {Decimal("40"), Decimal("60")}

    second_allocations = [
        {"accounts_payable_id": payable_ids[0], "amount": Decimal("60")},
        {"accounts_payable_id": payable_ids[1], "amount": Decimal("40")},
    ]
    async with sessions() as session, session.begin():
        second_payment, replayed = await purchasing_service.create_payment(
            session,
            supplier_id,
            Decimal("100"),
            date(2026, 9, 22),
            "cash",
            "delivery6-payment-002",
            second_allocations,
        )
        assert not replayed
        await purchasing_service.confirm_payment(session, first_id, actor_id)
        await purchasing_service.confirm_payment(session, second_payment.id, actor_id)
        balances = list(
            (
                await session.scalars(
                    select(AccountsPayable).where(AccountsPayable.id.in_(payable_ids)).order_by(AccountsPayable.id)
                )
            ).all()
        )
    assert [account.balance for account in balances] == [Decimal("0"), Decimal("0")]
    async with sessions() as session, session.begin():
        unkeyed_payment, replayed = await purchasing_service.create_payment(
            session,
            supplier_id,
            Decimal("10"),
            date(2026, 9, 22),
            "cash",
            None,
            [{"accounts_payable_id": payable_ids[0], "amount": Decimal("10")}],
        )
        assert not replayed
        assert unkeyed_payment.idempotency_key is None
    async with sessions() as session:
        payments = list((await session.scalars(select(SupplierPayment))).all())
        allocations = list((await session.scalars(select(SupplierPaymentAllocation))).all())
    assert len(payments) == 3
    assert len(allocations) == 5

    with pytest.raises(PurchaseConflictError, match="idempotency key reused"):
        async with sessions() as session, session.begin():
            await purchasing_service.create_payment(
                session,
                supplier_id,
                Decimal("101"),
                date(2026, 9, 22),
                "cash",
                first_key,
                first_allocations,
            )

    await engine.dispose()
