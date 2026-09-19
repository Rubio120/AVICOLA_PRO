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
from avicola_pro.modules.parties.infrastructure.models import Customer
from avicola_pro.modules.sales.application.service import sales_service
from avicola_pro.modules.sales.infrastructure.models import (
    AccountsReceivable,
    CustomerPayment,
    CustomerPaymentAllocation,
)
from avicola_pro.modules.settings.infrastructure.models import DocumentSequence

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _database_url() -> str:
    return os.environ["AVICOLA_TEST_DATABASE_URL"]


@pytest.fixture(autouse=True)
def migrated_database() -> None:
    environment = os.environ.copy()
    environment["AVICOLA_DATABASE_URL"] = _database_url()
    environment["AVICOLA_SESSION_HMAC_KEY"] = "jUrUWz89-ZPO0xh7ppVRm50Pt-un53S_NSfNCACPXaM"
    subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "base"], cwd=BACKEND_ROOT, env=environment, check=True
    )
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND_ROOT, env=environment, check=True)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_issue_internal_document_creates_ar_and_payment_closes_it() -> None:
    assert Product.__tablename__ == "products"
    assert Warehouse.__tablename__ == "warehouses"
    engine = create_async_engine(_database_url())
    sessions = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    customer_id, user_id = uuid4(), uuid4()
    async with sessions() as session, session.begin():
        session.add(
            User(
                id=user_id,
                username="seller",
                email="seller@example.test",
                display_name="Seller",
                password_hash="argon2id",  # noqa: S106
            )
        )
        session.add(
            Customer(
                id=customer_id,
                code="CUS-001",
                document_type="RUC",
                document_number="80000001-1",
                name="Customer",
                payment_term_days=0,
            )
        )
        session.add(DocumentSequence(id=uuid4(), document_type="INVOICE", series="A", prefix="A-", padding=4))
        session.add(DocumentSequence(id=uuid4(), document_type="CREDIT_NOTE", series="A", prefix="NC-", padding=4))

    async with sessions() as session, session.begin():
        document = await sales_service.issue_document(
            session,
            {
                "customer_id": customer_id,
                "document_type": "INVOICE",
                "series": "A",
                "document_date": date(2026, 9, 19),
                "lines": [
                    {
                        "description": "Eggs",
                        "quantity": Decimal("2"),
                        "unit_price": Decimal("100"),
                        "tax_rate": Decimal("0.10"),
                    }
                ],
            },
            user_id,
        )
        account = await session.scalar(
            select(AccountsReceivable).where(AccountsReceivable.commercial_document_id == document.id)
        )
        assert account is not None and account.balance == Decimal("220.00")
        credit_note = await sales_service.issue_document(
            session,
            {
                "customer_id": customer_id,
                "document_type": "CREDIT_NOTE",
                "series": "A",
                "document_date": date(2026, 9, 19),
                "original_document_id": document.id,
                "lines": [
                    {
                        "description": "Return",
                        "quantity": Decimal("0.5"),
                        "unit_price": Decimal("100"),
                        "tax_rate": Decimal("0.10"),
                    }
                ],
            },
            user_id,
        )
        assert credit_note.original_document_id == document.id
        assert account.balance == Decimal("165.00")
        payment = CustomerPayment(
            id=uuid4(),
            customer_id=customer_id,
            amount=Decimal("165.00"),
            payment_date=date(2026, 9, 19),
            payment_method_code="cash",
        )
        session.add(payment)
        await session.flush()
        session.add(
            CustomerPaymentAllocation(
                id=uuid4(), payment_id=payment.id, accounts_receivable_id=account.id, amount=Decimal("165.00")
            )
        )
        await session.flush()
        await sales_service.confirm_payment(session, payment.id, user_id)
        assert account.status == "PAID"
        assert payment.cash_movement_id is not None
    await engine.dispose()
