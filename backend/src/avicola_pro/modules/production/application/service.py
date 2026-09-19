from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from importlib import import_module
from typing import Any
from uuid import UUID, uuid4

from avicola_pro.modules.production.domain.rules import (
    apply_bird_delta,
    ensure_house_capacity,
    ensure_zero_balance_for_close,
)

_sqlalchemy = import_module("sqlalchemy")
_catalog_models = import_module("avicola_pro.modules.catalog.infrastructure.models")
_inventory_models = import_module("avicola_pro.modules.inventory.infrastructure.models")
_production_models = import_module("avicola_pro.modules.production.infrastructure.models")
inventory_service: Any = import_module("avicola_pro.modules.inventory.application.service").inventory_service
select: Any = _sqlalchemy.select
func: Any = _sqlalchemy.func
AsyncSession: Any = Any
House: Any = _catalog_models.House
InventoryDocument: Any = _inventory_models.InventoryDocument
InventoryDocumentLine: Any = _inventory_models.InventoryDocumentLine
InventoryMovement: Any = _inventory_models.InventoryMovement
BirdAdjustmentEvent: Any = _production_models.BirdAdjustmentEvent
BirdMovementEvent: Any = _production_models.BirdMovementEvent
FeedConsumption: Any = _production_models.FeedConsumption
Flock: Any = _production_models.Flock
FlockBalance: Any = _production_models.FlockBalance
FlockDailyRecord: Any = _production_models.FlockDailyRecord
FlockHouseAssignment: Any = _production_models.FlockHouseAssignment
MortalityEvent: Any = _production_models.MortalityEvent


class ProductionNotFoundError(LookupError):
    pass


class ProductionConflictError(ValueError):
    pass


class ProductionService:
    async def activate(self, session: AsyncSession, flock_id: UUID, actor_user_id: UUID) -> Flock:
        flock = await session.scalar(select(Flock).where(Flock.id == flock_id).with_for_update())
        if flock is None:
            raise ProductionNotFoundError("Flock not found")
        if flock.status == "ACTIVE":
            return flock
        if flock.status != "DRAFT":
            raise ProductionConflictError("Only draft flocks can be activated")
        balance = await session.scalar(select(FlockBalance).where(FlockBalance.flock_id == flock.id).with_for_update())
        if balance is None:
            balance = FlockBalance(flock_id=flock.id, live_birds=flock.planned_initial_quantity)
            session.add(balance)
        else:
            balance.live_birds = flock.planned_initial_quantity
        existing = await session.scalar(
            select(BirdMovementEvent).where(
                BirdMovementEvent.flock_id == flock.id, BirdMovementEvent.movement_type == "INITIAL"
            )
        )
        if existing is None:
            session.add(
                BirdMovementEvent(
                    id=uuid4(),
                    flock_id=flock.id,
                    movement_type="INITIAL",
                    occurred_on=flock.entry_date,
                    quantity=flock.planned_initial_quantity,
                )
            )
        flock.status = "ACTIVE"
        flock.version += 1
        await session.flush()
        return flock

    async def assign_house(
        self, session: AsyncSession, flock_id: UUID, house_id: UUID, valid_from: date, quantity: Decimal
    ) -> FlockHouseAssignment:
        flock = await session.scalar(select(Flock).where(Flock.id == flock_id).with_for_update())
        house = await session.scalar(select(House).where(House.id == house_id).with_for_update())
        if flock is None or house is None:
            raise ProductionNotFoundError("Flock or house not found")
        if flock.status != "ACTIVE":
            raise ProductionConflictError("Flock must be active")
        existing = await session.scalar(
            select(func.coalesce(func.sum(FlockHouseAssignment.quantity), 0)).where(
                FlockHouseAssignment.house_id == house_id,
                FlockHouseAssignment.valid_from <= valid_from,
                (FlockHouseAssignment.valid_until.is_(None) | (FlockHouseAssignment.valid_until >= valid_from)),
            )
        )
        try:
            ensure_house_capacity(Decimal(existing or 0), quantity, house.capacity)
        except ValueError as exc:
            raise ProductionConflictError(str(exc)) from exc
        assignment = FlockHouseAssignment(
            id=uuid4(), flock_id=flock_id, house_id=house_id, valid_from=valid_from, quantity=quantity
        )
        session.add(assignment)
        return assignment

    async def record_mortality(
        self,
        session: AsyncSession,
        flock_id: UUID,
        occurred_on: date,
        quantity: Decimal,
        cause: str,
        actor_user_id: UUID,
        house_id: UUID | None = None,
        idempotency_key: str | None = None,
    ) -> MortalityEvent:
        if idempotency_key:
            existing = await session.scalar(
                select(MortalityEvent).where(MortalityEvent.idempotency_key == idempotency_key)
            )
            if existing is not None:
                return existing
        balance = await self._locked_balance(session, flock_id)
        try:
            balance.live_birds = apply_bird_delta(balance.live_birds, -quantity)
        except ValueError as exc:
            raise ProductionConflictError(str(exc)) from exc
        balance.version += 1
        event = MortalityEvent(
            id=uuid4(),
            flock_id=flock_id,
            house_id=house_id,
            occurred_on=occurred_on,
            quantity=quantity,
            cause=cause,
            idempotency_key=idempotency_key,
        )
        session.add(event)
        await session.flush()
        return event

    async def adjust(
        self,
        session: AsyncSession,
        flock_id: UUID,
        adjustment_type: str,
        occurred_on: date,
        quantity: Decimal,
        reason: str,
        idempotency_key: str | None = None,
    ) -> BirdAdjustmentEvent:
        if idempotency_key:
            existing = await session.scalar(
                select(BirdAdjustmentEvent).where(BirdAdjustmentEvent.idempotency_key == idempotency_key)
            )
            if existing is not None:
                return existing
        balance = await self._locked_balance(session, flock_id)
        delta = quantity if adjustment_type == "CORRECTION_IN" else -quantity
        try:
            balance.live_birds = apply_bird_delta(balance.live_birds, delta)
        except ValueError as exc:
            raise ProductionConflictError(str(exc)) from exc
        balance.version += 1
        event = BirdAdjustmentEvent(
            id=uuid4(),
            flock_id=flock_id,
            adjustment_type=adjustment_type,
            occurred_on=occurred_on,
            quantity=quantity,
            reason=reason,
            idempotency_key=idempotency_key,
        )
        session.add(event)
        await session.flush()
        return event

    async def record_daily(
        self,
        session: AsyncSession,
        flock_id: UUID,
        record_date: date,
        observed_birds: Decimal,
        average_weight: Decimal | None,
        notes: str | None,
    ) -> FlockDailyRecord:
        record = FlockDailyRecord(
            id=uuid4(),
            flock_id=flock_id,
            record_date=record_date,
            observed_birds=observed_birds,
            average_weight=average_weight,
            notes=notes,
        )
        session.add(record)
        return record

    async def close(self, session: AsyncSession, flock_id: UUID, authorized_adjustment: bool = False) -> Flock:
        flock = await session.scalar(select(Flock).where(Flock.id == flock_id).with_for_update())
        if flock is None:
            raise ProductionNotFoundError("Flock not found")
        balance = await self._locked_balance(session, flock_id)
        try:
            ensure_zero_balance_for_close(balance.live_birds, authorized_adjustment)
        except ValueError as exc:
            raise ProductionConflictError(str(exc)) from exc
        flock.status = "CLOSED"
        flock.closed_at = datetime.now(UTC)
        flock.version += 1
        return flock

    async def record_feed(
        self,
        session: AsyncSession,
        flock_id: UUID,
        product_id: UUID,
        warehouse_id: UUID,
        quantity: Decimal,
        occurred_on: date,
        actor_user_id: UUID,
        house_id: UUID | None = None,
    ) -> FeedConsumption:
        await self._locked_balance(session, flock_id)
        document = InventoryDocument(
            id=uuid4(),
            document_type="ISSUE",
            effective_date=occurred_on,
            warehouse_id=warehouse_id,
            reason="Consumo de alimento",
        )
        session.add(document)
        await session.flush()
        line = InventoryDocumentLine(
            id=uuid4(),
            document_id=document.id,
            ordinal=1,
            product_id=product_id,
            quantity=quantity,
            unit_cost=Decimal("0"),
            direction="OUT",
        )
        session.add(line)
        await session.flush()
        await inventory_service.confirm(session, document.id, actor_user_id)
        await session.flush()
        movement = await session.scalar(select(InventoryMovement).where(InventoryMovement.document_id == document.id))
        consumption = FeedConsumption(
            id=uuid4(),
            flock_id=flock_id,
            house_id=house_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
            quantity=quantity,
            inventory_movement_id=movement.id if movement else None,
            occurred_on=occurred_on,
        )
        session.add(consumption)
        return consumption

    async def _locked_balance(self, session: AsyncSession, flock_id: UUID) -> FlockBalance:
        balance = await session.scalar(select(FlockBalance).where(FlockBalance.flock_id == flock_id).with_for_update())
        if balance is None:
            raise ProductionConflictError("Flock is not active")
        return balance


production_service = ProductionService()
