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

from avicola_pro.modules.catalog.infrastructure.models import Farm, House
from avicola_pro.modules.identity.infrastructure.models import User
from avicola_pro.modules.production.application.service import ProductionConflictError, production_service
from avicola_pro.modules.production.infrastructure.models import BirdMovementEvent, Flock, FlockBalance

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _database_url() -> str:
    return os.environ["AVICOLA_TEST_DATABASE_URL"]


@pytest.fixture(autouse=True)
def migrated_database() -> None:
    environment = os.environ.copy()
    environment["AVICOLA_DATABASE_URL"] = _database_url()
    environment["AVICOLA_SESSION_HMAC_KEY"] = "jUrUWz89-ZPO0xh7ppRVm50Pt-un53S_NSfNCACPXaM"
    for command in (("downgrade", "base"), ("upgrade", "head")):
        subprocess.run([sys.executable, "-m", "alembic", *command], cwd=BACKEND_ROOT, env=environment, check=True)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_activation_mortality_and_close_preserve_flock_invariants() -> None:
    engine = create_async_engine(_database_url())
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    actor = uuid4()
    flock_id = uuid4()
    async with factory() as session, session.begin():
        session.add(
            User(
                id=actor,
                username="production",
                email="production@example.test",
                display_name="Production",
                password_hash="argon2id",  # noqa: S106 - synthetic fixture value
            )
        )
        farm_id = uuid4()
        session.add(Farm(id=farm_id, code="FARM-P", name="Production farm"))
        house_id = uuid4()
        session.add(House(id=house_id, farm_id=farm_id, code="H-01", name="House 1", capacity=100))
        session.add(
            Flock(
                id=flock_id,
                code="FLOCK-001",
                purpose="Broilers",
                entry_date=date(2026, 9, 19),
                planned_initial_quantity=Decimal("50"),
            )
        )
        await session.flush()
        flock = await production_service.activate(session, flock_id, actor)
        assert flock.status == "ACTIVE"
        assignment = await production_service.assign_house(
            session, flock_id, house_id, date(2026, 9, 19), Decimal("50")
        )
        assert assignment.quantity == Decimal("50")
        daily = await production_service.record_daily(
            session, flock_id, date(2026, 9, 19), Decimal("50"), Decimal("1.25"), "ok"
        )
        assert daily.observed_birds == Decimal("50")
        await production_service.activate(session, flock_id, actor)
        balance = await session.scalar(select(FlockBalance).where(FlockBalance.flock_id == flock_id))
        assert balance is not None and balance.live_birds == Decimal("50.0000")
        initial_count = await session.scalar(
            select(BirdMovementEvent.id)
            .where(BirdMovementEvent.flock_id == flock_id)
            .where(BirdMovementEvent.movement_type == "INITIAL")
        )
        assert initial_count is not None
        await production_service.record_mortality(session, flock_id, date(2026, 9, 19), Decimal("5"), "Natural", actor)
        first_idempotent = await production_service.record_mortality(
            session, flock_id, date(2026, 9, 19), Decimal("1"), "Keyed", actor, idempotency_key="mortality-1"
        )
        repeated_idempotent = await production_service.record_mortality(
            session, flock_id, date(2026, 9, 19), Decimal("1"), "Keyed", actor, idempotency_key="mortality-1"
        )
        assert repeated_idempotent.id == first_idempotent.id
        with pytest.raises(ProductionConflictError, match="zero"):
            await production_service.close(session, flock_id)
        await production_service.adjust(
            session, flock_id, "CORRECTION_OUT", date(2026, 9, 19), Decimal("44"), "Authorized close adjustment"
        )
        closed = await production_service.close(session, flock_id, True)
        assert closed.status == "CLOSED"
    await engine.dispose()
