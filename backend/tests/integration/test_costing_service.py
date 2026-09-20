from __future__ import annotations

import os
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from avicola_pro.modules.costing.application.service import costing_service
from avicola_pro.modules.costing.domain.rules import CostingConflictError
from avicola_pro.modules.costing.infrastructure.models import CostEvent
from avicola_pro.shared.infrastructure.models import load_persistence_models


@pytest.mark.integration
@pytest.mark.asyncio
async def test_costing_run_allocates_confirmed_events_and_closes_immutably() -> None:
    load_persistence_models()
    engine = create_async_engine(os.environ["AVICOLA_TEST_DATABASE_URL"])
    actor = uuid4()
    target_a, target_b = uuid4(), uuid4()
    async with engine.connect() as connection, AsyncSession(bind=connection) as session, session.begin():
        event = await costing_service.record_event(
            session,
            {
                "event_type": "FEED",
                "source_type": "feed_consumption",
                "source_id": uuid4(),
                "effective_date": date(2026, 9, 20),
                "amount": Decimal("100.00"),
                "idempotency_key": "cost-test-event-1",
                "status": "CONFIRMED",
            },
            actor,
        )
        assert event.status == "CONFIRMED"
        duplicate_payload = {
            "event_type": event.event_type,
            "source_type": event.source_type,
            "source_id": event.source_id,
            "effective_date": event.effective_date,
            "amount": event.amount,
            "idempotency_key": "cost-test-event-1",
            "status": "CONFIRMED",
        }
        assert await costing_service.record_event(session, duplicate_payload, actor) is event
        session.add(
            CostEvent(
                id=uuid4(),
                event_type="FEED",
                source_type="feed_consumption",
                source_id=uuid4(),
                effective_date=date(2026, 9, 20),
                amount=Decimal("25.00"),
                status="DRAFT",
            )
        )
        run = await costing_service.create_run(session, date(2026, 9, 20), actor)
        snapshots = await costing_service.calculate_run(
            session,
            run.id,
            actor,
            [
                {"target_type": "flock", "target_id": target_a, "weight": Decimal("1"), "quantity": Decimal("2")},
                {"target_type": "flock", "target_id": target_b, "weight": Decimal("2"), "quantity": Decimal("3")},
            ],
        )
        assert [item.total_cost for item in snapshots] == [Decimal("33.33"), Decimal("66.67")]
        profitability = await costing_service.calculate_profitability(
            session,
            run.id,
            [
                {"source_id": uuid4(), "status": "CONFIRMED", "revenue": Decimal("200"), "cost": Decimal("100")},
                {"source_id": uuid4(), "status": "DRAFT", "revenue": Decimal("999"), "cost": Decimal("1")},
            ],
        )
        assert len(profitability) == 1
        assert profitability[0].margin == Decimal("100")
        closed = await costing_service.close_run(session, run.id, actor)
        assert closed.status == "CLOSED"
        with pytest.raises(CostingConflictError, match="closed"):
            await costing_service.calculate_run(session, run.id, actor, [])
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cost_event_reversal_is_append_only_and_single_use() -> None:
    load_persistence_models()
    engine = create_async_engine(os.environ["AVICOLA_TEST_DATABASE_URL"])
    actor = uuid4()
    async with engine.connect() as connection, AsyncSession(bind=connection) as session, session.begin():
        event = await costing_service.record_event(
            session,
            {
                "event_type": "PURCHASE",
                "source_type": "supplier_document",
                "source_id": uuid4(),
                "effective_date": date(2026, 9, 20),
                "amount": Decimal("50.00"),
                "idempotency_key": f"cost-reversal-{uuid4()}",
                "status": "CONFIRMED",
            },
            actor,
        )
        reversal = await costing_service.reverse_event(session, event.id, actor, "Correction")
        assert reversal.event_type == "REVERSAL"
        assert reversal.reversal_of_id == event.id
        with pytest.raises(CostingConflictError, match="already reversed"):
            await costing_service.reverse_event(session, event.id, actor, "Duplicate")
        second = await costing_service.record_event(
            session,
            {
                "event_type": "PURCHASE",
                "source_type": "supplier_document",
                "source_id": uuid4(),
                "effective_date": date(2026, 9, 20),
                "amount": Decimal("10.00"),
                "idempotency_key": f"cost-reversal-reason-{uuid4()}",
                "status": "CONFIRMED",
            },
            actor,
        )
        with pytest.raises(CostingConflictError, match="reason"):
            await costing_service.reverse_event(session, second.id, actor, "")
    await engine.dispose()
