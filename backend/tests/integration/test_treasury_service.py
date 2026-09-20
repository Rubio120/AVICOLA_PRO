from __future__ import annotations

import os
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from avicola_pro.modules.identity.infrastructure.models import User
from avicola_pro.modules.treasury.application.service import CashConflictError, CashNotFoundError, treasury_service
from avicola_pro.modules.treasury.infrastructure.models import CashAccount
from avicola_pro.shared.infrastructure.models import load_persistence_models


def _database_url() -> str:
    return os.environ["AVICOLA_TEST_DATABASE_URL"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cash_day_open_movement_close_reopen_and_reverse() -> None:
    load_persistence_models()
    engine = create_async_engine(_database_url())
    user_id = uuid4()
    account_id = uuid4()
    destination_account_id = uuid4()
    suffix = str(user_id).replace("-", "")[:8]
    async with engine.begin() as connection:
        await connection.run_sync(lambda sync: None)
    async with engine.connect() as connection:
        from sqlalchemy.ext.asyncio import AsyncSession

        async with AsyncSession(bind=connection) as session, session.begin():
            session.add(
                User(
                    id=user_id,
                    username=f"cash-service-{suffix}",
                    email=f"cash-service-{suffix}@example.test",
                    display_name="Cash Service",
                    password_hash="test-hash",  # noqa: S106
                )
            )
            session.add(CashAccount(id=account_id, code=f"SERVICE-{suffix}", name="Service cash"))
            session.add(CashAccount(id=destination_account_id, code=f"DESTINATION-{suffix}", name="Destination cash"))
    async with engine.connect() as connection:
        from sqlalchemy.ext.asyncio import AsyncSession

        async with AsyncSession(bind=connection) as session, session.begin():
            cash_session = await treasury_service.open_session(session, account_id, user_id, Decimal("100.00"))
            with pytest.raises(CashConflictError, match="already has an open"):
                await treasury_service.open_session(session, account_id, user_id, Decimal("0"))
            with pytest.raises(CashNotFoundError, match="cash session not found"):
                await treasury_service.create_movement(
                    session,
                    uuid4(),
                    account_id,
                    user_id,
                    "INCOME",
                    "IN",
                    Decimal("1.00"),
                    date(2026, 9, 19),
                )
            movement = await treasury_service.create_movement(
                session,
                cash_session.id,
                account_id,
                user_id,
                "INCOME",
                "IN",
                Decimal("25.00"),
                date(2026, 9, 19),
            )
            duplicate = await treasury_service.create_movement(
                session,
                cash_session.id,
                account_id,
                user_id,
                "INCOME",
                "IN",
                Decimal("25.00"),
                date(2026, 9, 19),
                idempotency_key=f"cash-day-income-{suffix}",
            )
            same_duplicate = await treasury_service.create_movement(
                session,
                cash_session.id,
                account_id,
                user_id,
                "INCOME",
                "IN",
                Decimal("25.00"),
                date(2026, 9, 19),
                idempotency_key=f"cash-day-income-{suffix}",
            )
            destination = await treasury_service.open_session(session, destination_account_id, user_id, Decimal("0"))
            transfer = await treasury_service.transfer(
                session,
                cash_session.id,
                destination.id,
                account_id,
                destination_account_id,
                user_id,
                Decimal("40.00"),
                date(2026, 9, 19),
                "Transfer",
            )
            closed = await treasury_service.close_session(session, cash_session.id, user_id, Decimal("110.00"))
            assert closed.expected_balance == Decimal("110.00")
            assert duplicate.id == same_duplicate.id
            assert transfer.amount == Decimal("40.00")
            reopened = await treasury_service.reopen_session(session, cash_session.id, user_id, "Correction")
            reversal = await treasury_service.reverse_movement(session, movement.id, user_id, "Correction")
            assert reopened.status == "REOPENED"
            assert reversal.reversal_of_id == movement.id
            with pytest.raises(CashConflictError, match="already reversed"):
                await treasury_service.reverse_movement(session, movement.id, user_id, "Duplicate")
            await treasury_service.close_session(session, destination.id, user_id, Decimal("40.00"))
            with pytest.raises(CashConflictError, match="only an open"):
                await treasury_service.close_session(session, destination.id, user_id, Decimal("40.00"))
            with pytest.raises(CashConflictError, match="closed session"):
                await treasury_service.reopen_session(session, cash_session.id, user_id, "")
    await engine.dispose()
