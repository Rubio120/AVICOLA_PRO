from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from importlib import import_module
from typing import Any
from uuid import UUID, uuid4

from avicola_pro.modules.production.domain.egg_classification import validate_egg_allocations
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
InventoryConflictError: Any = import_module("avicola_pro.modules.inventory.application.service").InventoryConflictError
postgres_insert: Any = import_module("sqlalchemy.dialects.postgresql").insert
select: Any = _sqlalchemy.select
func: Any = _sqlalchemy.func
AsyncSession: Any = Any
House: Any = _catalog_models.House
Product: Any = _catalog_models.Product
Warehouse: Any = _catalog_models.Warehouse
InventoryDocument: Any = _inventory_models.InventoryDocument
InventoryDocumentLine: Any = _inventory_models.InventoryDocumentLine
InventoryMovement: Any = _inventory_models.InventoryMovement
EggCategory: Any = _inventory_models.EggCategory
EggProductionAllocation: Any = _inventory_models.EggProductionAllocation
EggProductionClassification: Any = _inventory_models.EggProductionClassification
BirdAdjustmentEvent: Any = _production_models.BirdAdjustmentEvent
BirdMovementEvent: Any = _production_models.BirdMovementEvent
FeedConsumption: Any = _production_models.FeedConsumption
Flock: Any = _production_models.Flock
FlockBalance: Any = _production_models.FlockBalance
FlockDailyRecord: Any = _production_models.FlockDailyRecord
FlockHouseAssignment: Any = _production_models.FlockHouseAssignment
EggProductionEvent: Any = _production_models.EggProductionEvent
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

    async def record_egg_production(
        self,
        session: AsyncSession,
        flock_id: UUID,
        house_id: UUID,
        occurred_on: date,
        egg_count: int,
        idempotency_key: str,
        actor_user_id: UUID,
    ) -> tuple[EggProductionEvent, bool]:
        from avicola_pro.modules.production.domain.egg_rules import validate_egg_count

        try:
            validate_egg_count(egg_count)
        except ValueError as exc:
            raise ProductionConflictError(str(exc)) from exc
        existing = await session.scalar(
            select(EggProductionEvent).where(EggProductionEvent.idempotency_key == idempotency_key)
        )
        if existing is not None:
            same_request = (
                existing.flock_id == flock_id
                and existing.house_id == house_id
                and existing.occurred_on == occurred_on
                and existing.egg_count == egg_count
                and existing.actor_user_id == actor_user_id
            )
            if not same_request:
                raise ProductionConflictError("Idempotency key was already used for a different egg record")
            return existing, False
        flock = await session.scalar(select(Flock).where(Flock.id == flock_id).with_for_update())
        if flock is None or flock.status != "ACTIVE" or occurred_on < flock.entry_date:
            raise ProductionConflictError("Egg production requires an active flock on or before the record date")
        assignment = await session.scalar(
            select(FlockHouseAssignment.id).where(
                FlockHouseAssignment.flock_id == flock_id,
                FlockHouseAssignment.house_id == house_id,
                FlockHouseAssignment.valid_from <= occurred_on,
                FlockHouseAssignment.valid_until.is_(None) | (FlockHouseAssignment.valid_until >= occurred_on),
            )
        )
        if assignment is None:
            raise ProductionConflictError("The flock is not assigned to this house on the record date")

        event_id = uuid4()
        statement = (
            postgres_insert(EggProductionEvent)
            .values(
                id=event_id,
                flock_id=flock_id,
                house_id=house_id,
                occurred_on=occurred_on,
                egg_count=egg_count,
                idempotency_key=idempotency_key,
                actor_user_id=actor_user_id,
                status="CONFIRMED",
            )
            .on_conflict_do_nothing(index_elements=[EggProductionEvent.idempotency_key])
            .returning(EggProductionEvent.id)
        )
        inserted_id = await session.scalar(statement)
        if inserted_id is None:
            existing = await session.scalar(
                select(EggProductionEvent).where(EggProductionEvent.idempotency_key == idempotency_key)
            )
            if existing is None:
                raise ProductionConflictError("Egg production could not be recorded; retry the request")
            same_request = (
                existing.flock_id == flock_id
                and existing.house_id == house_id
                and existing.occurred_on == occurred_on
                and existing.egg_count == egg_count
                and existing.actor_user_id == actor_user_id
            )
            if not same_request:
                raise ProductionConflictError("Idempotency key was already used for a different egg record")
            return existing, False
        event = await session.get(EggProductionEvent, inserted_id)
        if event is None:
            raise ProductionConflictError("Egg production record could not be loaded after creation")
        return event, True

    async def list_egg_production(
        self,
        session: AsyncSession,
        date_from: date,
        date_to: date,
        flock_id: UUID | None = None,
        house_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EggProductionEvent]:
        statement = select(EggProductionEvent).where(
            EggProductionEvent.occurred_on >= date_from,
            EggProductionEvent.occurred_on <= date_to,
        )
        if flock_id is not None:
            statement = statement.where(EggProductionEvent.flock_id == flock_id)
        if house_id is not None:
            statement = statement.where(EggProductionEvent.house_id == house_id)
        result = await session.scalars(
            statement.order_by(EggProductionEvent.occurred_on.desc(), EggProductionEvent.id).limit(limit).offset(offset)
        )
        return list(result.all())

    async def list_unclassified_egg_production(
        self,
        session: AsyncSession,
        date_from: date,
        date_to: date,
        flock_id: UUID | None = None,
        house_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EggProductionEvent]:
        classified_ids = select(EggProductionClassification.production_event_id)
        statement = select(EggProductionEvent).where(
            EggProductionEvent.occurred_on >= date_from,
            EggProductionEvent.occurred_on <= date_to,
            ~EggProductionEvent.id.in_(classified_ids),
        )
        if flock_id is not None:
            statement = statement.where(EggProductionEvent.flock_id == flock_id)
        if house_id is not None:
            statement = statement.where(EggProductionEvent.house_id == house_id)
        result = await session.scalars(
            statement.order_by(EggProductionEvent.occurred_on.desc(), EggProductionEvent.id).limit(limit).offset(offset)
        )
        return list(result.all())

    async def classify_egg_production(
        self,
        session: AsyncSession,
        production_event_id: UUID,
        warehouse_id: UUID,
        allocations: list[tuple[UUID, int]],
        idempotency_key: str,
        actor_user_id: UUID,
    ) -> tuple[EggProductionClassification, bool]:
        event = await session.scalar(
            select(EggProductionEvent).where(EggProductionEvent.id == production_event_id).with_for_update()
        )
        if event is None:
            raise ProductionNotFoundError("Egg production event not found")
        try:
            validate_egg_allocations(event.egg_count, allocations)
        except ValueError as exc:
            raise ProductionConflictError(str(exc)) from exc

        existing = await session.scalar(
            select(EggProductionClassification)
            .where(EggProductionClassification.idempotency_key == idempotency_key)
            .with_for_update()
        )
        if existing is not None:
            if existing.production_event_id != production_event_id or existing.warehouse_id != warehouse_id:
                raise ProductionConflictError("Idempotency key was already used for a different classification")
            saved_allocations = list(
                (
                    await session.scalars(
                        select(EggProductionAllocation).where(EggProductionAllocation.classification_id == existing.id)
                    )
                ).all()
            )
            if {(item.category_id, item.egg_count) for item in saved_allocations} != set(allocations):
                raise ProductionConflictError("Idempotency key was already used for a different classification")
            return existing, False

        previous = await session.scalar(
            select(EggProductionClassification)
            .where(EggProductionClassification.production_event_id == event.id)
            .with_for_update()
        )
        if previous is not None:
            raise ProductionConflictError("Egg production event is already classified")
        warehouse = await session.scalar(
            select(Warehouse).where(Warehouse.id == warehouse_id, Warehouse.is_active.is_(True)).with_for_update()
        )
        if warehouse is None:
            raise ProductionConflictError("An active receiving warehouse is required")
        category_ids = {category_id for category_id, count in allocations}
        categories_by_id: dict[UUID, tuple[Any, Any]] = {}
        if category_ids:
            rows = await session.execute(
                select(EggCategory, Product)
                .join(Product, Product.id == EggCategory.product_id)
                .where(EggCategory.id.in_(category_ids))
                .with_for_update()
            )
            categories_by_id = {category.id: (category, product) for category, product in rows.all()}
        if set(categories_by_id) != category_ids:
            raise ProductionConflictError("Every allocation must reference a configured egg category")
        for category, product in categories_by_id.values():
            if not category.is_active or not product.is_active:
                raise ProductionConflictError("Egg category and mapped product must be active")

        inventory_document: InventoryDocument | None = None
        positive_allocations = [(category_id, count) for category_id, count in allocations if count > 0]
        if positive_allocations:
            inventory_document = InventoryDocument(
                id=uuid4(),
                document_type="RECEIPT",
                effective_date=event.occurred_on,
                warehouse_id=warehouse_id,
                source_type="egg_production",
                source_id=event.id,
                reason="Clasificación de producción de huevos",
            )
            session.add(inventory_document)
            await session.flush()
            for ordinal, (category_id, egg_count) in enumerate(positive_allocations, start=1):
                category, product = categories_by_id[category_id]
                session.add(
                    InventoryDocumentLine(
                        id=uuid4(),
                        document_id=inventory_document.id,
                        ordinal=ordinal,
                        product_id=product.id,
                        quantity=Decimal(egg_count),
                        unit_cost=Decimal("0"),
                        direction="IN",
                    )
                )
            await session.flush()

        classification = EggProductionClassification(
            id=uuid4(),
            production_event_id=event.id,
            warehouse_id=warehouse_id,
            inventory_document_id=inventory_document.id if inventory_document else None,
            idempotency_key=idempotency_key,
            actor_user_id=actor_user_id,
        )
        session.add(classification)
        for category_id, egg_count in allocations:
            session.add(
                EggProductionAllocation(
                    id=uuid4(),
                    classification_id=classification.id,
                    category_id=category_id,
                    egg_count=egg_count,
                )
            )
        await session.flush()
        if inventory_document is not None:
            try:
                await inventory_service.confirm(session, inventory_document.id, actor_user_id)
            except InventoryConflictError as exc:
                raise ProductionConflictError(str(exc)) from exc
        return classification, True

    async def list_egg_production_options(self, session: AsyncSession, on_date: date) -> list[dict[str, Any]]:
        statement = (
            select(Flock.id, Flock.code, House.id, House.code)
            .join(FlockHouseAssignment, FlockHouseAssignment.flock_id == Flock.id)
            .join(House, House.id == FlockHouseAssignment.house_id)
            .where(
                Flock.status == "ACTIVE",
                Flock.entry_date <= on_date,
                FlockHouseAssignment.valid_from <= on_date,
                FlockHouseAssignment.valid_until.is_(None) | (FlockHouseAssignment.valid_until >= on_date),
            )
            .order_by(Flock.code, House.code)
        )
        result = await session.execute(statement)
        return [
            {"flock_id": flock_id, "flock_code": flock_code, "house_id": house_id, "house_code": house_code}
            for flock_id, flock_code, house_id, house_code in result.all()
        ]

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
