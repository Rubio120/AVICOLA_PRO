from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from importlib import import_module
from typing import Any
from uuid import UUID, uuid4

from avicola_pro.modules.costing.domain.rules import (
    CostingConflictError,
    allocate_by_weight,
    calculate_cost_per_bird,
    eligible_source_status,
    ensure_run_transition,
)

_models = import_module("avicola_pro.modules.costing.infrastructure.models")
select: Any = import_module("sqlalchemy").select
CostEvent: Any = _models.CostEvent
CostRun: Any = _models.CostRun
CostRunSnapshot: Any = _models.CostRunSnapshot
CostAllocation: Any = _models.CostAllocation
ProfitabilitySnapshot: Any = _models.ProfitabilitySnapshot


class CostingNotFoundError(LookupError):
    pass


class CostingService:
    async def record_event(self, session: Any, payload: dict[str, Any], actor_user_id: UUID) -> Any:
        key = payload.get("idempotency_key")
        if key:
            existing = await session.scalar(select(CostEvent).where(CostEvent.idempotency_key == key))
            if existing is not None:
                return existing
        if not eligible_source_status(payload.get("status", "CONFIRMED")):
            raise CostingConflictError("only confirmed source events can be recorded")
        amount = Decimal(str(payload["amount"]))
        if amount < 0 or payload.get("currency_code", "PYG") != "PYG":
            raise CostingConflictError("cost event must be non-negative PYG")
        event = CostEvent(
            id=uuid4(),
            event_type=payload["event_type"],
            source_type=payload["source_type"],
            source_id=payload["source_id"],
            cost_center_id=payload.get("cost_center_id"),
            effective_date=payload["effective_date"],
            amount=amount,
            currency_code="PYG",
            status="CONFIRMED",
            idempotency_key=key,
            reversal_of_id=payload.get("reversal_of_id"),
            actor_user_id=actor_user_id,
            event_metadata=payload.get("metadata", {}),
        )
        session.add(event)
        await session.flush()
        return event

    async def create_run(self, session: Any, run_date: date, actor_user_id: UUID) -> Any:
        latest = await session.scalar(
            select(CostRun).where(CostRun.run_date == run_date).order_by(CostRun.version.desc()).limit(1)
        )
        run = CostRun(
            id=uuid4(),
            run_date=run_date,
            version=(latest.version + 1 if latest else 1),
            created_by=actor_user_id,
        )
        session.add(run)
        await session.flush()
        return run

    async def reverse_event(self, session: Any, event_id: UUID, actor_user_id: UUID, reason: str) -> Any:
        original = await session.scalar(select(CostEvent).where(CostEvent.id == event_id).with_for_update())
        if original is None:
            raise CostingNotFoundError("cost event not found")
        if original.status != "CONFIRMED":
            raise CostingConflictError("only confirmed cost events can be reversed")
        existing = await session.scalar(select(CostEvent).where(CostEvent.reversal_of_id == event_id))
        if existing is not None:
            raise CostingConflictError("cost event is already reversed")
        if not reason.strip():
            raise CostingConflictError("reversal reason is required")
        reversal = CostEvent(
            id=uuid4(),
            event_type="REVERSAL",
            source_type="cost_reversal",
            source_id=original.id,
            cost_center_id=original.cost_center_id,
            effective_date=date.today(),
            amount=original.amount,
            currency_code=original.currency_code,
            status="CONFIRMED",
            reversal_of_id=original.id,
            actor_user_id=actor_user_id,
            event_metadata={"reason": reason},
        )
        session.add(reversal)
        await session.flush()
        return reversal

    async def calculate_run(
        self, session: Any, run_id: UUID, actor_user_id: UUID, targets: list[dict[str, Any]]
    ) -> list[Any]:
        run = await session.scalar(select(CostRun).where(CostRun.id == run_id).with_for_update())
        if run is None:
            raise CostingNotFoundError("cost run not found")
        if run.status == "CLOSED":
            raise CostingConflictError("closed cost run is immutable")
        ensure_run_transition(run.status, "CALCULATING")
        run.status = "CALCULATING"
        events = list(
            (
                await session.scalars(
                    select(CostEvent).where(CostEvent.status == "CONFIRMED", CostEvent.effective_date <= run.run_date)
                )
            ).all()
        )
        total = sum((item.amount if item.event_type != "REVERSAL" else -item.amount for item in events), Decimal("0"))
        weights = {str(item["target_id"]): Decimal(str(item["weight"])) for item in targets}
        allocations = allocate_by_weight(total, weights) if targets else {}
        for event in events:
            event_allocations = allocate_by_weight(event.amount, weights) if targets else {}
            for item in targets:
                session.add(
                    CostAllocation(
                        id=uuid4(),
                        cost_event_id=event.id,
                        target_type=item["target_type"],
                        target_id=item["target_id"],
                        weight=item["weight"],
                        amount=event_allocations[str(item["target_id"])],
                    )
                )
        snapshots: list[Any] = []
        for item in targets:
            target_id = item["target_id"]
            target_cost = allocations[str(target_id)]
            snapshot = CostRunSnapshot(
                id=uuid4(),
                cost_run_id=run.id,
                target_type=item["target_type"],
                target_id=target_id,
                total_cost=target_cost,
                quantity=Decimal(str(item.get("quantity", "0"))),
                cost_per_unit=calculate_cost_per_bird(target_cost, Decimal(str(item.get("quantity", "0")))),
            )
            session.add(snapshot)
            snapshots.append(snapshot)
        await session.flush()
        return snapshots

    async def close_run(self, session: Any, run_id: UUID, actor_user_id: UUID) -> Any:
        run = await session.scalar(select(CostRun).where(CostRun.id == run_id).with_for_update())
        if run is None:
            raise CostingNotFoundError("cost run not found")
        ensure_run_transition(run.status, "CLOSED")
        run.status = "CLOSED"
        run.closed_at = datetime.now(UTC)
        await session.flush()
        return run

    async def calculate_profitability(self, session: Any, run_id: UUID, facts: list[dict[str, Any]]) -> list[Any]:
        run = await session.scalar(select(CostRun).where(CostRun.id == run_id).with_for_update())
        if run is None:
            raise CostingNotFoundError("cost run not found")
        if run.status == "CLOSED":
            raise CostingConflictError("closed cost run is immutable")
        snapshots: list[Any] = []
        for fact in facts:
            if not eligible_source_status(fact.get("status", "")):
                continue
            revenue = Decimal(str(fact["revenue"]))
            cost = Decimal(str(fact["cost"]))
            if revenue < 0 or cost < 0:
                raise CostingConflictError("profitability values must be non-negative")
            margin = revenue - cost
            snapshot = ProfitabilitySnapshot(
                id=uuid4(),
                cost_run_id=run.id,
                source_id=fact["source_id"],
                revenue=revenue,
                cost=cost,
                margin=margin,
                margin_rate=(margin / revenue if revenue else None),
                notes=fact.get("notes"),
            )
            session.add(snapshot)
            snapshots.append(snapshot)
        await session.flush()
        return snapshots


costing_service = CostingService()
