from __future__ import annotations

import os
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from avicola_pro.modules.catalog.infrastructure.models import Farm, House, Product, Warehouse
from avicola_pro.modules.identity.infrastructure.models import User
from avicola_pro.modules.inventory.application.service import inventory_service
from avicola_pro.modules.inventory.infrastructure.models import (
    EggCategory,
    EggProductionAllocation,
    EggProductionClassification,
    InventoryBalance,
    InventoryDocument,
    InventoryDocumentLine,
    InventoryMovement,
)
from avicola_pro.modules.parties.infrastructure.models import Customer
from avicola_pro.modules.production.infrastructure.models import (
    EggProductionEvent,
    FeedConsumption,
    Flock,
    FlockDailyRecord,
    MortalityEvent,
)
from avicola_pro.modules.reporting.domain.rules import ReportFilter
from avicola_pro.modules.reporting.infrastructure.reader import dashboard
from avicola_pro.modules.sales.infrastructure.models import CommercialDocument, CommercialDocumentLine
from avicola_pro.shared.infrastructure.models import load_persistence_models

PERIOD_FROM = date(2026, 1, 2)
PERIOD_TO = date(2026, 1, 31)


def _database_url() -> str:
    return os.environ["AVICOLA_TEST_DATABASE_URL"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dashboard_aggregates_confirmed_poultry_and_commercial_facts_across_flocks() -> None:
    result = await _dashboard_fixture(include_reversed_feed=False, include_unlinked_feed=False)

    metrics = result["poultry_metrics"]
    assert metrics["posture"].value == Decimal("4")
    assert metrics["feed_per_bird"].value == Decimal("0.3")
    assert metrics["feed_conversion"].value == Decimal("0.9")
    assert metrics["feed_cost_per_egg"].value == Decimal("0.27")
    assert metrics["average_ticket"].value == Decimal("1250")
    assert metrics["new_customers"].value == Decimal("1")
    assert result["daily_mortality"] == [{"occurred_on": date(2026, 1, 10), "deaths": Decimal("3")}]
    ages = [
        age for age in result["active_flock_ages"] if age["flock_code"].startswith(("FLOCK-A-", "FLOCK-B-"))
    ]
    assert [(age["flock_code"].split("-")[1], age["days_since_entry"]) for age in ages] == [
        ("A", (date.today() - PERIOD_FROM).days),
        ("B", (date.today() - PERIOD_FROM).days),
    ]
    assert all(age["as_of"] == date.today() for age in ages)
    feed_by_house = result["feed_consumption_by_house"]
    assert len(feed_by_house) == 1
    assert feed_by_house[0]["house_code"].startswith("HOUSE-")
    assert feed_by_house[0]["unit_code"] == "kg"
    assert feed_by_house[0]["quantity"] == Decimal("90.0000")
    assert result["sales_documents"] == 2
    assert result["sales_total"] == Decimal("2500")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dashboard_excludes_feed_consumption_from_reversed_inventory_issue() -> None:
    result = await _dashboard_fixture(include_reversed_feed=True, include_unlinked_feed=False)

    metrics = result["poultry_metrics"]
    assert metrics["feed_per_bird"].available is True
    assert metrics["feed_per_bird"].value == Decimal("0.3")
    assert metrics["feed_conversion"].value == Decimal("0.9")
    assert metrics["feed_cost_per_egg"].value == Decimal("0.27")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dashboard_excludes_feed_consumption_without_confirmed_inventory_movement() -> None:
    result = await _dashboard_fixture(include_reversed_feed=False, include_unlinked_feed=True)

    metrics = result["poultry_metrics"]
    assert metrics["feed_per_bird"].available is True
    assert metrics["feed_per_bird"].value == Decimal("0.3")
    assert metrics["feed_conversion"].value == Decimal("0.9")
    assert metrics["feed_cost_per_egg"].value == Decimal("0.27")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_feed_cost_per_egg_does_not_double_count_reclassified_eggs() -> None:
    result = await _dashboard_fixture(
        include_reversed_feed=False,
        include_unlinked_feed=False,
        include_reversed_classification=True,
    )

    metric = result["poultry_metrics"]["feed_cost_per_egg"]
    assert metric.available is True
    assert metric.value == Decimal("0.27")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dashboard_calculates_coverage_from_base_unit_egg_sales() -> None:
    result = await _dashboard_fixture(include_reversed_feed=False, include_unlinked_feed=False)

    coverage = result["poultry_metrics"]["stock_coverage"]
    assert coverage.available is True
    assert coverage.value == Decimal("900") * Decimal("30") / Decimal("85")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dashboard_applies_channel_to_commercial_metrics_and_coverage() -> None:
    result = await _dashboard_fixture(
        include_reversed_feed=False,
        include_unlinked_feed=False,
        include_wholesale_invoice=True,
        channel="WHOLESALE",
    )

    metrics = result["poultry_metrics"]
    assert result["sales_documents"] == 1
    assert result["sales_total"] == Decimal("800")
    assert metrics["average_ticket"].value == Decimal("800")
    assert metrics["new_customers"].value == Decimal("1")
    assert metrics["stock_coverage"].value == Decimal("900")


async def _dashboard_fixture(
    *,
    include_reversed_feed: bool,
    include_unlinked_feed: bool,
    include_reversed_classification: bool = False,
    include_wholesale_invoice: bool = False,
    channel: str | None = None,
) -> dict[str, Any]:
    load_persistence_models()
    engine = create_async_engine(_database_url())
    try:
        async with engine.connect() as connection:
            outer_transaction = await connection.begin()
            try:
                async with (
                    AsyncSession(
                        bind=connection,
                        expire_on_commit=False,
                        join_transaction_mode="create_savepoint",
                    ) as session,
                    session.begin(),
                ):
                    await _seed_fixture(
                        session,
                        include_reversed_feed=include_reversed_feed,
                        include_unlinked_feed=include_unlinked_feed,
                        include_reversed_classification=include_reversed_classification,
                        include_wholesale_invoice=include_wholesale_invoice,
                    )
                    result = await dashboard(
                        session,
                        ReportFilter(date_from=PERIOD_FROM, date_to=PERIOD_TO, channel=channel),
                    )
                return result
            finally:
                if outer_transaction.is_active:
                    await outer_transaction.rollback()
    finally:
        await engine.dispose()


async def _seed_fixture(
    session: AsyncSession,
    *,
    include_reversed_feed: bool,
    include_unlinked_feed: bool,
    include_reversed_classification: bool = False,
    include_wholesale_invoice: bool = False,
) -> None:
    suffix = uuid4().hex[:10]
    actor_id = uuid4()
    farm_id = uuid4()
    house_id = uuid4()
    warehouse_id = uuid4()
    flock_a_id, flock_b_id = uuid4(), uuid4()
    feed_a_id, feed_b_id, egg_saleable_id, egg_other_id = (uuid4() for _ in range(4))

    session.add(
        User(
            id=actor_id,
            username=f"metric-{suffix}",
            email=f"metric-{suffix}@example.test",
            display_name="Synthetic reporting fixture",
            password_hash="fixture-hash",  # noqa: S106 - synthetic test fixture, never a credential
        )
    )
    session.add(Farm(id=farm_id, code=f"METRIC-{suffix}", name="Synthetic metric farm"))
    session.add(
        House(
            id=house_id,
            farm_id=farm_id,
            code=f"HOUSE-{suffix}",
            name="Synthetic metric house",
            capacity=1000,
        )
    )
    session.add(Warehouse(id=warehouse_id, code=f"WH-{suffix}", name="Synthetic metric warehouse"))
    for flock_id, code in ((flock_a_id, "A"), (flock_b_id, "B")):
        session.add(
            Flock(
                id=flock_id,
                code=f"FLOCK-{code}-{suffix}",
                purpose="Synthetic layers",
                entry_date=PERIOD_FROM,
                planned_initial_quantity=Decimal("500"),
                status="ACTIVE",
            )
        )
    products = (
        Product(
            id=feed_a_id,
            sku=f"FEED-A-{suffix}",
            name="Synthetic feed A",
            product_type="INPUT",
            base_unit_code="kg",
        ),
        Product(
            id=feed_b_id,
            sku=f"FEED-B-{suffix}",
            name="Synthetic feed B",
            product_type="INPUT",
            base_unit_code="kg",
        ),
        Product(
            id=egg_saleable_id,
            sku=f"EGG-S-{suffix}",
            name="Synthetic saleable egg unit",
            product_type="PRODUCT",
            base_unit_code="unit",
        ),
        Product(
            id=egg_other_id,
            sku=f"EGG-N-{suffix}",
            name="Synthetic non-saleable egg unit",
            product_type="PRODUCT",
            base_unit_code="unit",
        ),
    )
    session.add_all(products)
    reversed_mortality_id = uuid4()
    session.add_all(
        (
            MortalityEvent(
                id=uuid4(),
                flock_id=flock_a_id,
                house_id=house_id,
                occurred_on=date(2026, 1, 10),
                quantity=Decimal("1"),
                cause="Synthetic recorded mortality",
            ),
            MortalityEvent(
                id=uuid4(),
                flock_id=flock_b_id,
                house_id=house_id,
                occurred_on=date(2026, 1, 10),
                quantity=Decimal("2"),
                cause="Synthetic recorded mortality",
            ),
            MortalityEvent(
                id=reversed_mortality_id,
                flock_id=flock_a_id,
                house_id=house_id,
                occurred_on=date(2026, 1, 11),
                quantity=Decimal("4"),
                cause="Synthetic reversed mortality",
            ),
            MortalityEvent(
                id=uuid4(),
                flock_id=flock_a_id,
                house_id=house_id,
                occurred_on=date(2026, 1, 11),
                quantity=Decimal("4"),
                cause="Synthetic mortality correction",
                reversal_of_id=reversed_mortality_id,
            ),
        )
    )
    saleable_category_id, other_category_id = uuid4(), uuid4()
    session.add_all(
        (
            EggCategory(
                id=saleable_category_id,
                code=f"SALEABLE-{suffix}",
                name="Synthetic saleable category",
                product_id=egg_saleable_id,
                is_saleable=True,
            ),
            EggCategory(
                id=other_category_id,
                code=f"OTHER-{suffix}",
                name="Synthetic non-saleable category",
                product_id=egg_other_id,
                is_saleable=False,
            ),
        )
    )

    await session.flush()
    for flock_id, birds_by_day in (
        (flock_a_id, (Decimal("100"), Decimal("110"))),
        (flock_b_id, (Decimal("200"), Decimal("190"))),
    ):
        for record_date, observed_birds in zip((date(2026, 1, 10), date(2026, 1, 11)), birds_by_day, strict=True):
            session.add(
                FlockDailyRecord(
                    id=uuid4(),
                    flock_id=flock_id,
                    record_date=record_date,
                    observed_birds=observed_birds,
                )
            )

    egg_a_id, egg_b_id, reversed_egg_id = uuid4(), uuid4(), uuid4()
    session.add_all(
        (
            EggProductionEvent(
                id=egg_a_id,
                flock_id=flock_a_id,
                house_id=house_id,
                occurred_on=date(2026, 1, 10),
                egg_count=600,
                idempotency_key=f"egg-a-{suffix}",
                actor_user_id=actor_id,
            ),
            EggProductionEvent(
                id=egg_b_id,
                flock_id=flock_b_id,
                house_id=house_id,
                occurred_on=date(2026, 1, 11),
                egg_count=600,
                idempotency_key=f"egg-b-{suffix}",
                actor_user_id=actor_id,
            ),
            EggProductionEvent(
                id=reversed_egg_id,
                flock_id=flock_a_id,
                house_id=house_id,
                occurred_on=date(2026, 1, 10),
                egg_count=400,
                idempotency_key=f"egg-reversed-{suffix}",
                actor_user_id=actor_id,
            ),
            EggProductionEvent(
                id=uuid4(),
                flock_id=flock_a_id,
                house_id=house_id,
                occurred_on=date(2026, 1, 10),
                egg_count=400,
                idempotency_key=f"egg-reversal-{suffix}",
                actor_user_id=actor_id,
                reversal_of_id=reversed_egg_id,
            ),
            EggProductionEvent(
                id=uuid4(),
                flock_id=flock_a_id,
                house_id=house_id,
                occurred_on=date(2026, 1, 1),
                egg_count=900,
                idempotency_key=f"egg-outside-period-{suffix}",
                actor_user_id=actor_id,
            ),
        )
    )
    await session.flush()
    classification_a_id, classification_b_id = uuid4(), uuid4()
    reversed_classification_document_id = uuid4()
    active_classification_document_id = uuid4()
    if include_reversed_classification:
        now = datetime.now(UTC)
        session.add_all(
            (
                InventoryDocument(
                    id=reversed_classification_document_id,
                    document_type="RECEIPT",
                    effective_date=date(2026, 1, 11),
                    warehouse_id=warehouse_id,
                    status="REVERSED",
                    reversed_at=now,
                    reversed_by=actor_id,
                    reversal_reason="Synthetic reclassification fixture",
                ),
                InventoryDocument(
                    id=active_classification_document_id,
                    document_type="RECEIPT",
                    effective_date=date(2026, 1, 11),
                    warehouse_id=warehouse_id,
                    status="CONFIRMED",
                    confirmed_at=now,
                    confirmed_by=actor_id,
                ),
            )
        )
        await session.flush()
    session.add_all(
        (
            EggProductionClassification(
                id=classification_a_id,
                production_event_id=egg_a_id,
                warehouse_id=warehouse_id,
                idempotency_key=f"class-a-{suffix}",
                actor_user_id=actor_id,
            ),
            EggProductionClassification(
                id=classification_b_id,
                production_event_id=egg_b_id,
                warehouse_id=warehouse_id,
                inventory_document_id=(
                    reversed_classification_document_id if include_reversed_classification else None
                ),
                idempotency_key=f"class-b-{suffix}",
                actor_user_id=actor_id,
            ),
        )
    )
    await session.flush()
    session.add_all(
        (
            EggProductionAllocation(
                id=uuid4(), classification_id=classification_a_id, category_id=saleable_category_id, egg_count=600
            ),
            EggProductionAllocation(
                id=uuid4(), classification_id=classification_b_id, category_id=saleable_category_id, egg_count=400
            ),
            EggProductionAllocation(
                id=uuid4(), classification_id=classification_b_id, category_id=other_category_id, egg_count=200
            ),
        )
    )
    if include_reversed_classification:
        replacement_classification_id = uuid4()
        session.add(
            EggProductionClassification(
                id=replacement_classification_id,
                production_event_id=egg_b_id,
                warehouse_id=warehouse_id,
                inventory_document_id=active_classification_document_id,
                idempotency_key=f"class-b-replacement-{suffix}",
                actor_user_id=actor_id,
            )
        )
        await session.flush()
        session.add_all(
            (
                EggProductionAllocation(
                    id=uuid4(),
                    classification_id=replacement_classification_id,
                    category_id=saleable_category_id,
                    egg_count=400,
                ),
                EggProductionAllocation(
                    id=uuid4(),
                    classification_id=replacement_classification_id,
                    category_id=other_category_id,
                    egg_count=200,
                ),
            )
        )

    feed_consumptions = [
        (flock_a_id, feed_a_id, Decimal("60"), Decimal("2")),
        (flock_b_id, feed_b_id, Decimal("30"), Decimal("5")),
    ]
    for index, (flock_id, product_id, quantity, unit_cost) in enumerate(feed_consumptions):
        movement_id = await _post_feed_issue(
            session,
            actor_id=actor_id,
            warehouse_id=warehouse_id,
            product_id=product_id,
            quantity=quantity,
            receipt_quantity=Decimal("100"),
            receipt_cost=unit_cost,
            suffix=f"{suffix}-{index}",
        )
        session.add(
            FeedConsumption(
                id=uuid4(),
                flock_id=flock_id,
                product_id=product_id,
                house_id=house_id,
                warehouse_id=warehouse_id,
                quantity=quantity,
                inventory_movement_id=movement_id,
                occurred_on=date(2026, 1, 10 + index),
            )
        )

    if include_reversed_feed:
        reversed_feed_movement_id = await _post_feed_issue(
            session,
            actor_id=actor_id,
            warehouse_id=warehouse_id,
            product_id=feed_a_id,
            quantity=Decimal("10"),
            receipt_quantity=Decimal("20"),
            receipt_cost=Decimal("2"),
            suffix=f"{suffix}-reversed",
        )
        reversed_movement = await session.get(InventoryMovement, reversed_feed_movement_id)
        assert reversed_movement is not None
        reversed_document_id = reversed_movement.document_id
        session.add(
            FeedConsumption(
                id=uuid4(),
                flock_id=flock_a_id,
                product_id=feed_a_id,
                warehouse_id=warehouse_id,
                quantity=Decimal("10"),
                inventory_movement_id=reversed_feed_movement_id,
                occurred_on=date(2026, 1, 10),
            )
        )
        await session.flush()
        await inventory_service.reverse(session, reversed_document_id, actor_id, "Synthetic reversal fixture")
    if include_unlinked_feed:
        session.add(
            FeedConsumption(
                id=uuid4(),
                flock_id=flock_a_id,
                product_id=feed_a_id,
                warehouse_id=warehouse_id,
                quantity=Decimal("5"),
                occurred_on=date(2026, 1, 10),
            )
        )

    customer_old_id, customer_new_id = uuid4(), uuid4()
    customer_wholesale_id = uuid4()
    session.add_all(
        (
            Customer(
                id=customer_old_id,
                code=f"CUSTOMER-OLD-{suffix}",
                document_type="RUC",
                document_number=f"800{suffix}",
                name="Synthetic prior customer",
            ),
            Customer(
                id=customer_new_id,
                code=f"CUSTOMER-NEW-{suffix}",
                document_type="RUC",
                document_number=f"801{suffix}",
                name="Synthetic new customer",
            ),
            *(
                [
                    Customer(
                        id=customer_wholesale_id,
                        code=f"CUSTOMER-WHOLESALE-{suffix}",
                        document_type="RUC",
                        document_number=f"802{suffix}",
                        name="Synthetic wholesale customer",
                    )
                ]
                if include_wholesale_invoice
                else []
            ),
        )
    )
    await session.flush()
    invoice_old = _commercial_document(
        customer_id=customer_old_id,
        document_type="INVOICE",
        document_date=date(2026, 1, 1),
        total=Decimal("5000"),
        suffix=f"old-{suffix}",
    )
    invoice_a = _commercial_document(
        customer_id=customer_old_id,
        document_type="INVOICE",
        document_date=date(2026, 1, 10),
        total=Decimal("1000"),
        suffix=f"a-{suffix}",
    )
    invoice_b = _commercial_document(
        customer_id=customer_new_id,
        document_type="INVOICE",
        document_date=date(2026, 1, 11),
        total=Decimal("2000"),
        suffix=f"b-{suffix}",
    )
    credit_note = _commercial_document(
        customer_id=customer_new_id,
        document_type="CREDIT_NOTE",
        document_date=date(2026, 1, 12),
        total=Decimal("500"),
        suffix=f"credit-{suffix}",
        original_document_id=invoice_b.id,
    )
    draft_invoice = _commercial_document(
        customer_id=customer_new_id,
        document_type="INVOICE",
        document_date=date(2026, 1, 15),
        total=Decimal("9000"),
        suffix=f"draft-{suffix}",
        status="DRAFT",
    )
    outside_invoice = _commercial_document(
        customer_id=customer_new_id,
        document_type="INVOICE",
        document_date=date(2026, 2, 1),
        total=Decimal("7000"),
        suffix=f"outside-{suffix}",
    )
    reversed_invoice = _commercial_document(
        customer_id=customer_new_id,
        document_type="INVOICE",
        document_date=date(2026, 1, 20),
        total=Decimal("8000"),
        suffix=f"reversed-{suffix}",
        status="REVERSED",
    )
    wholesale_invoice = (
        _commercial_document(
            customer_id=customer_wholesale_id,
            document_type="INVOICE",
            document_date=date(2026, 1, 13),
            total=Decimal("800"),
            suffix=f"wholesale-{suffix}",
            channel="WHOLESALE",
        )
        if include_wholesale_invoice
        else None
    )
    documents = [invoice_old, invoice_a, invoice_b, credit_note, draft_invoice, outside_invoice, reversed_invoice]
    if wholesale_invoice is not None:
        documents.append(wholesale_invoice)
    session.add_all(documents)
    await session.flush()
    for document, quantity, unit_price in (
        (invoice_a, Decimal("40"), Decimal("25")),
        (invoice_b, Decimal("60"), Decimal("100") / Decimal("3")),
        (credit_note, Decimal("15"), Decimal("100") / Decimal("3")),
        (draft_invoice, Decimal("100"), Decimal("90")),
        (outside_invoice, Decimal("500"), Decimal("14")),
        (reversed_invoice, Decimal("200"), Decimal("40")),
    ):
        session.add(
            CommercialDocumentLine(
                id=uuid4(),
                commercial_document_id=document.id,
                ordinal=1,
                product_id=egg_saleable_id,
                description="Synthetic egg units",
                quantity=quantity,
                unit_price=unit_price,
                tax_rate=Decimal("0"),
                base_amount=unit_price * quantity,
                tax_amount=Decimal("0"),
                total=unit_price * quantity,
            )
        )
    if wholesale_invoice is not None:
        session.add(
            CommercialDocumentLine(
                id=uuid4(),
                commercial_document_id=wholesale_invoice.id,
                ordinal=1,
                product_id=egg_saleable_id,
                description="Synthetic wholesale egg units",
                quantity=Decimal("30"),
                unit_price=Decimal("800") / Decimal("30"),
                tax_rate=Decimal("0"),
                base_amount=Decimal("800"),
                tax_amount=Decimal("0"),
                total=Decimal("800"),
            )
        )

    session.add(
        InventoryBalance(
            id=uuid4(),
            warehouse_id=warehouse_id,
            product_id=egg_saleable_id,
            quantity=Decimal("900"),
            inventory_value=Decimal("0"),
            average_cost=Decimal("0"),
        )
    )
    await session.flush()


async def _post_feed_issue(
    session: AsyncSession,
    *,
    actor_id: UUID,
    warehouse_id: UUID,
    product_id: UUID,
    quantity: Decimal,
    receipt_quantity: Decimal,
    receipt_cost: Decimal,
    suffix: str,
) -> UUID:
    receipt = InventoryDocument(
        id=uuid4(),
        document_type="RECEIPT",
        effective_date=date(2026, 1, 10),
        warehouse_id=warehouse_id,
    )
    session.add(receipt)
    await session.flush()
    session.add(
        InventoryDocumentLine(
            id=uuid4(),
            document_id=receipt.id,
            ordinal=1,
            product_id=product_id,
            quantity=receipt_quantity,
            unit_cost=receipt_cost,
            direction="IN",
        )
    )
    await session.flush()
    await inventory_service.confirm(session, receipt.id, actor_id)

    issue = InventoryDocument(
        id=uuid4(),
        document_type="ISSUE",
        effective_date=date(2026, 1, 10),
        warehouse_id=warehouse_id,
        reason=f"Synthetic feed issue {suffix}",
    )
    session.add(issue)
    await session.flush()
    session.add(
        InventoryDocumentLine(
            id=uuid4(),
            document_id=issue.id,
            ordinal=1,
            product_id=product_id,
            quantity=quantity,
            unit_cost=Decimal("0"),
            direction="OUT",
        )
    )
    await session.flush()
    await inventory_service.confirm(session, issue.id, actor_id)
    movement = await session.scalar(select(InventoryMovement).where(InventoryMovement.document_id == issue.id))
    assert movement is not None
    return movement.id


def _commercial_document(
    *,
    customer_id: UUID,
    document_type: str,
    document_date: date,
    total: Decimal,
    suffix: str,
    status: str = "ISSUED",
    original_document_id: UUID | None = None,
    channel: str = "RETAIL",
) -> CommercialDocument:
    return CommercialDocument(
        id=uuid4(),
        document_type=document_type,
        series="SYN",
        number=suffix,
        customer_id=customer_id,
        customer_name_snapshot="Synthetic customer",
        customer_document_snapshot="RUC:SYNTHETIC",
        document_date=document_date,
        channel=channel,
        status=status,
        total=total,
        original_document_id=original_document_id,
    )

