from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from importlib import import_module
from typing import Any
from uuid import UUID, uuid4

from avicola_pro.modules.inventory.domain.rules import calculate_inbound, calculate_outbound

_sqlalchemy = import_module("sqlalchemy")
_postgresql = import_module("sqlalchemy.dialects.postgresql")
_models = import_module("avicola_pro.modules.inventory.infrastructure.models")
select: Any = _sqlalchemy.select
insert: Any = _postgresql.insert
AsyncSession: Any = Any
InventoryBalance: Any = _models.InventoryBalance
InventoryDocument: Any = _models.InventoryDocument
InventoryDocumentLine: Any = _models.InventoryDocumentLine
InventoryMovement: Any = _models.InventoryMovement
InventoryCostVariance: Any = _models.InventoryCostVariance


class InventoryNotFoundError(LookupError):
    pass


class InventoryConflictError(ValueError):
    pass


class InventoryService:
    async def confirm(self, session: AsyncSession, document_id: UUID, actor_user_id: UUID) -> InventoryDocument:
        document = await session.scalar(
            select(InventoryDocument).where(InventoryDocument.id == document_id).with_for_update()
        )
        if document is None:
            raise InventoryNotFoundError("Inventory document not found")
        if document.status == "CONFIRMED":
            return document
        if document.status != "DRAFT":
            raise InventoryConflictError("Only draft documents can be confirmed")
        lines = list(
            (
                await session.scalars(
                    select(InventoryDocumentLine)
                    .where(InventoryDocumentLine.document_id == document.id)
                    .order_by(
                        InventoryDocumentLine.product_id,
                        InventoryDocumentLine.inventory_lot_id,
                        InventoryDocumentLine.ordinal,
                    )
                )
            ).all()
        )
        if not lines:
            raise InventoryConflictError("Inventory document must contain a line")
        if document.document_type == "TRANSFER" and document.destination_warehouse_id is None:
            raise InventoryConflictError("Transfer destination is required")
        for line in lines:
            if document.document_type == "TRANSFER":
                if document.warehouse_id is None:
                    raise InventoryConflictError("Transfer source is required")
                cost = await self._apply_out(
                    session, document, line, document.warehouse_id, actor_user_id, "TRANSFER_OUT"
                )
                await self._apply_in(
                    session, document, line, document.destination_warehouse_id, actor_user_id, cost, "TRANSFER_IN"
                )
            else:
                if document.warehouse_id is None:
                    raise InventoryConflictError("Warehouse is required")
                is_inbound = document.document_type == "RECEIPT" or (
                    document.document_type == "ADJUSTMENT" and line.direction == "IN"
                )
                if is_inbound:
                    await self._apply_in(
                        session,
                        document,
                        line,
                        document.warehouse_id,
                        actor_user_id,
                        line.unit_cost,
                        document.document_type,
                    )
                else:
                    await self._apply_out(
                        session, document, line, document.warehouse_id, actor_user_id, document.document_type
                    )
        document.status = "CONFIRMED"
        document.confirmed_at = datetime.now(UTC)
        document.confirmed_by = actor_user_id
        document.version += 1
        return document

    async def reverse(
        self, session: AsyncSession, document_id: UUID, actor_user_id: UUID, reason: str
    ) -> InventoryDocument:
        await session.flush()
        original = await session.scalar(
            select(InventoryDocument).where(InventoryDocument.id == document_id).with_for_update()
        )
        if original is None:
            raise InventoryNotFoundError("Inventory document not found")
        if original.status == "REVERSED":
            raise InventoryConflictError("Inventory document is already reversed")
        if original.status != "CONFIRMED":
            raise InventoryConflictError("Only confirmed documents can be reversed")
        movements = list(
            (
                await session.scalars(
                    select(InventoryMovement)
                    .where(InventoryMovement.document_id == original.id)
                    .order_by(InventoryMovement.occurred_at, InventoryMovement.id)
                )
            ).all()
        )
        if not movements:
            raise InventoryConflictError("Confirmed document has no movements")
        movement_ids = [item.id for item in movements]
        if await session.scalar(select(InventoryMovement.id).where(InventoryMovement.reversal_of_id.in_(movement_ids))):
            raise InventoryConflictError("Inventory document is already reversed")
        reversal = InventoryDocument(
            id=uuid4(),
            document_type="ADJUSTMENT",
            effective_date=date.today(),
            warehouse_id=movements[0].warehouse_id,
            reason=reason,
            reversal_of_id=original.id,
            reversal_reason=reason,
        )
        session.add(reversal)
        await session.flush()
        for ordinal, movement in enumerate(movements, start=1):
            line = InventoryDocumentLine(
                id=uuid4(),
                document_id=reversal.id,
                ordinal=ordinal,
                product_id=movement.product_id,
                inventory_lot_id=movement.inventory_lot_id,
                quantity=abs(movement.quantity_delta),
                unit_cost=movement.unit_cost,
                direction="IN" if movement.quantity_delta < 0 else "OUT",
            )
            session.add(line)
            await session.flush()
            if movement.quantity_delta < 0:
                await self._apply_in(
                    session,
                    reversal,
                    line,
                    movement.warehouse_id,
                    actor_user_id,
                    movement.unit_cost,
                    "REVERSAL",
                    movement.id,
                )
            else:
                await self._apply_out(
                    session, reversal, line, movement.warehouse_id, actor_user_id, "REVERSAL", movement.id
                )
            await session.flush()
            compensation = await session.scalar(
                select(InventoryMovement)
                .where(InventoryMovement.document_id == reversal.id, InventoryMovement.line_id == line.id)
                .order_by(InventoryMovement.occurred_at.desc())
            )
            if compensation is not None:
                variance = movement.value_delta + compensation.value_delta
                if variance != 0:
                    session.add(
                        InventoryCostVariance(
                            id=uuid4(),
                            original_movement_id=movement.id,
                            reversal_movement_id=compensation.id,
                            amount=variance,
                        )
                    )
        original.status = "REVERSED"
        original.reversed_at = datetime.now(UTC)
        original.reversed_by = actor_user_id
        original.version += 1
        reversal.status = "CONFIRMED"
        reversal.confirmed_at = datetime.now(UTC)
        reversal.confirmed_by = actor_user_id
        reversal.version += 1
        await session.flush()
        return reversal

    async def _balance(
        self, session: AsyncSession, warehouse_id: UUID, product_id: UUID, lot_id: UUID | None
    ) -> InventoryBalance:
        await session.execute(
            insert(InventoryBalance)
            .values(
                id=uuid4(),
                warehouse_id=warehouse_id,
                product_id=product_id,
                inventory_lot_id=lot_id,
            )
            .on_conflict_do_nothing()
        )
        lot_filter = (
            InventoryBalance.inventory_lot_id.is_(None)
            if lot_id is None
            else InventoryBalance.inventory_lot_id == lot_id
        )
        statement = (
            select(InventoryBalance)
            .where(InventoryBalance.warehouse_id == warehouse_id, InventoryBalance.product_id == product_id, lot_filter)
            .with_for_update()
        )
        balance = await session.scalar(statement)
        if balance is None:
            raise InventoryConflictError("Inventory balance could not be locked")
        return balance

    async def _apply_in(
        self,
        session: AsyncSession,
        document: InventoryDocument,
        line: InventoryDocumentLine,
        warehouse_id: UUID,
        actor_user_id: UUID,
        unit_cost: Decimal,
        movement_type: str,
        reversal_of_id: UUID | None = None,
    ) -> None:
        balance = await self._balance(session, warehouse_id, line.product_id, line.inventory_lot_id)
        previous_value = balance.inventory_value
        result = calculate_inbound(balance.quantity, balance.inventory_value, line.quantity, unit_cost)
        balance.quantity = result.quantity
        balance.inventory_value = result.value
        balance.average_cost = result.average_cost
        balance.version += 1
        session.add(
            InventoryMovement(
                id=uuid4(),
                document_id=document.id,
                line_id=line.id,
                product_id=line.product_id,
                inventory_lot_id=line.inventory_lot_id,
                warehouse_id=warehouse_id,
                movement_type=movement_type,
                quantity_delta=line.quantity,
                unit_cost=unit_cost,
                value_delta=result.value - previous_value,
                effective_date=document.effective_date,
                actor_user_id=actor_user_id,
                reversal_of_id=reversal_of_id,
            )
        )

    async def _apply_out(
        self,
        session: AsyncSession,
        document: InventoryDocument,
        line: InventoryDocumentLine,
        warehouse_id: UUID,
        actor_user_id: UUID,
        movement_type: str,
        reversal_of_id: UUID | None = None,
    ) -> Decimal:
        balance = await self._balance(session, warehouse_id, line.product_id, line.inventory_lot_id)
        previous_value = balance.inventory_value
        result = calculate_outbound(balance.quantity, balance.inventory_value, line.quantity)
        balance.quantity = result.quantity
        balance.inventory_value = result.value
        balance.average_cost = Decimal("0") if result.quantity == 0 else result.unit_cost
        balance.version += 1
        session.add(
            InventoryMovement(
                id=uuid4(),
                document_id=document.id,
                line_id=line.id,
                product_id=line.product_id,
                inventory_lot_id=line.inventory_lot_id,
                warehouse_id=warehouse_id,
                movement_type=movement_type,
                quantity_delta=-line.quantity,
                unit_cost=result.unit_cost,
                value_delta=result.value - previous_value,
                effective_date=document.effective_date,
                actor_user_id=actor_user_id,
                reversal_of_id=reversal_of_id,
            )
        )
        return result.unit_cost


inventory_service = InventoryService()
