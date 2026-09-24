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

from avicola_pro.modules.catalog.infrastructure.models import Farm, House, Product, Warehouse
from avicola_pro.modules.identity.infrastructure.models import User
from avicola_pro.modules.inventory.infrastructure.models import (
    EggCategory,
    EggProductionAllocation,
    EggProductionClassification,
    InventoryBalance,
)
from avicola_pro.modules.production.application.service import ProductionConflictError, production_service
from avicola_pro.modules.production.infrastructure.models import (
    BirdMovementEvent,
    EggProductionEvent,
    Flock,
    FlockBalance,
)
from avicola_pro.modules.settings.infrastructure.models import UnitOfMeasure

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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_egg_production_requires_assignment_and_idempotently_records_confirmed_facts() -> None:
    engine = create_async_engine(_database_url())
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    actor = uuid4()
    flock_id = uuid4()
    farm_id = uuid4()
    house_id = uuid4()
    record_date = date(2026, 9, 19)
    async with factory() as session, session.begin():
        session.add(
            User(
                id=actor,
                username="egg-production",
                email="egg-production@example.test",
                display_name="Egg Production",
                password_hash="argon2id",  # noqa: S106 - synthetic fixture value
            )
        )
        session.add(Farm(id=farm_id, code="FARM-E", name="Egg farm"))
        session.add(House(id=house_id, farm_id=farm_id, code="H-E", name="Egg house", capacity=100))
        session.add(
            Flock(
                id=flock_id,
                code="FLOCK-EGG-001",
                purpose="Layers",
                entry_date=record_date,
                planned_initial_quantity=Decimal("50"),
            )
        )
        await session.flush()
        await production_service.activate(session, flock_id, actor)
        await production_service.assign_house(session, flock_id, house_id, record_date, Decimal("50"))
        first, created = await production_service.record_egg_production(
            session, flock_id, house_id, record_date, 120, "egg-run-1", actor
        )
        repeated, repeated_created = await production_service.record_egg_production(
            session, flock_id, house_id, record_date, 120, "egg-run-1", actor
        )
        assert created and not repeated_created
        assert first.id == repeated.id
        with pytest.raises(ProductionConflictError, match="different egg record"):
            await production_service.record_egg_production(
                session, flock_id, house_id, record_date, 121, "egg-run-1", actor
            )
        listed = await production_service.list_egg_production(session, record_date, record_date, flock_id, house_id)
        assert len(listed) == 1
        assert listed[0].egg_count == 120
        assert listed[0].status == "CONFIRMED"
        assert await session.scalar(select(EggProductionEvent.id).where(EggProductionEvent.id == first.id)) is not None
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_egg_production_classification_posts_atomic_stock_and_is_idempotent() -> None:
    engine = create_async_engine(_database_url())
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    actor, flock_id, farm_id, house_id = uuid4(), uuid4(), uuid4(), uuid4()
    warehouse_id, product_id, category_id = uuid4(), uuid4(), uuid4()
    record_date = date(2026, 9, 19)
    async with factory() as session, session.begin():
        session.add(
            User(
                id=actor,
                username="egg-classifier",
                email="egg-classifier@example.test",
                display_name="Egg Classifier",
                password_hash="argon2id",  # noqa: S106 - synthetic fixture value
            )
        )
        session.add(Farm(id=farm_id, code="FARM-CLASS", name="Classification farm"))
        session.add(House(id=house_id, farm_id=farm_id, code="H-CLASS", name="Classification house", capacity=100))
        session.add(Warehouse(id=warehouse_id, code="WH-CLASS", name="Classification warehouse", is_active=True))
        session.add(UnitOfMeasure(code="egg_unit", name="Synthetic individual egg", precision=0))
        session.add(
            Product(
                id=product_id,
                sku="EGG-SYNTHETIC",
                name="Synthetic egg inventory item",
                product_type="PRODUCT",
                base_unit_code="egg_unit",
                is_active=True,
            )
        )
        session.add(
            EggCategory(
                id=category_id,
                code="SYNTHETIC-CAT",
                name="Synthetic test category",
                product_id=product_id,
                is_saleable=True,
            )
        )
        session.add(
            Flock(
                id=flock_id,
                code="FLOCK-CLASS",
                purpose="Layers",
                entry_date=record_date,
                planned_initial_quantity=Decimal("50"),
            )
        )
        await session.flush()
        await production_service.activate(session, flock_id, actor)
        await production_service.assign_house(session, flock_id, house_id, record_date, Decimal("50"))
        event, _ = await production_service.record_egg_production(
            session, flock_id, house_id, record_date, 120, "egg-classification-source", actor
        )
        with pytest.raises(ProductionConflictError, match="must equal"):
            await production_service.classify_egg_production(
                session, event.id, warehouse_id, [(category_id, 119)], "egg-classification-invalid", actor
            )
        assert await session.scalar(select(EggProductionClassification.id)) is None
        classification, created = await production_service.classify_egg_production(
            session, event.id, warehouse_id, [(category_id, 120)], "egg-classification-valid", actor
        )
        repeated, repeated_created = await production_service.classify_egg_production(
            session, event.id, warehouse_id, [(category_id, 120)], "egg-classification-valid", actor
        )
        assert created and not repeated_created
        assert classification.id == repeated.id
        assert await session.scalar(select(EggProductionAllocation.egg_count)) == 120
        balance = await session.scalar(select(InventoryBalance).where(InventoryBalance.warehouse_id == warehouse_id))
        assert balance is not None and balance.quantity == Decimal("120.0000")
        assert classification.inventory_document_id is not None
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_zero_egg_production_classifies_without_creating_stock_document() -> None:
    engine = create_async_engine(_database_url())
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    actor, flock_id, farm_id, house_id, warehouse_id = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
    record_date = date(2026, 9, 19)
    async with factory() as session, session.begin():
        session.add(
            User(
                id=actor,
                username="zero-egg-classifier",
                email="zero-egg-classifier@example.test",
                display_name="Zero Egg Classifier",
                password_hash="argon2id",  # noqa: S106 - synthetic fixture value
            )
        )
        session.add(Farm(id=farm_id, code="FARM-ZERO", name="Zero farm"))
        session.add(House(id=house_id, farm_id=farm_id, code="H-ZERO", name="Zero house", capacity=100))
        session.add(Warehouse(id=warehouse_id, code="WH-ZERO", name="Zero warehouse", is_active=True))
        session.add(
            Flock(
                id=flock_id,
                code="FLOCK-ZERO",
                purpose="Layers",
                entry_date=record_date,
                planned_initial_quantity=Decimal("50"),
            )
        )
        await session.flush()
        await production_service.activate(session, flock_id, actor)
        await production_service.assign_house(session, flock_id, house_id, record_date, Decimal("50"))
        event, _ = await production_service.record_egg_production(
            session, flock_id, house_id, record_date, 0, "egg-zero-source", actor
        )
        classification, created = await production_service.classify_egg_production(
            session, event.id, warehouse_id, [], "egg-zero-classification", actor
        )
        assert created and classification.inventory_document_id is None
        assert await session.scalar(select(InventoryBalance.id)) is None
    await engine.dispose()
