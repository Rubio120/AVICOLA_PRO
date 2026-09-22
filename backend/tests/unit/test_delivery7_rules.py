from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from avicola_pro.modules.sales.application import service as sales_module
from avicola_pro.modules.sales.application.service import DisabledFiscalProvider, SalesNotFoundError, sales_service
from avicola_pro.modules.sales.domain.rules import (
    SalesConflictError,
    apply_customer_payment,
    calculate_document_totals,
    validate_credit_note_amount,
)


def test_document_totals_split_exempt_and_vat_bases_with_half_up_rounding() -> None:
    totals = calculate_document_totals(
        [
            {
                "quantity": Decimal("3"),
                "unit_price": Decimal("10"),
                "discount_rate": Decimal("0"),
                "tax_rate": Decimal("0"),
            },
            {
                "quantity": Decimal("2"),
                "unit_price": Decimal("100"),
                "discount_rate": Decimal("0.10"),
                "tax_rate": Decimal("0.10"),
            },
            {
                "quantity": Decimal("1"),
                "unit_price": Decimal("50"),
                "discount_rate": Decimal("0"),
                "tax_rate": Decimal("0.05"),
            },
        ]
    )
    assert totals["exempt_subtotal"] == Decimal("30.00")
    assert totals["vat_10_base"] == Decimal("180.00")
    assert totals["vat_10_amount"] == Decimal("18.00")
    assert totals["vat_5_base"] == Decimal("50.00")
    assert totals["vat_5_amount"] == Decimal("2.50")
    assert totals["total"] == Decimal("280.50")


def test_rejects_unsupported_tax_rate_and_overapplied_credit() -> None:
    with pytest.raises(SalesConflictError, match="only exempt"):
        calculate_document_totals([{"quantity": Decimal("1"), "unit_price": Decimal("1"), "tax_rate": Decimal("0.18")}])
    with pytest.raises(SalesConflictError, match="exceed"):
        validate_credit_note_amount(Decimal("100"), Decimal("90"), Decimal("11"))


def test_customer_payment_cannot_overapply() -> None:
    assert apply_customer_payment(Decimal("100"), Decimal("40"), Decimal("100")) == Decimal("60")
    with pytest.raises(SalesConflictError, match="balance"):
        apply_customer_payment(Decimal("200"), Decimal("101"), Decimal("100"))


@pytest.mark.asyncio
async def test_sales_service_rejects_empty_orders_and_missing_resources() -> None:
    class Session:
        async def scalar(self, _query: object) -> None:
            return None

    with pytest.raises(SalesConflictError, match="must contain"):
        await sales_service.create_order(Session(), uuid4(), date.today(), [])
    with pytest.raises(SalesNotFoundError, match="order"):
        await sales_service.confirm_order(Session(), uuid4())
    with pytest.raises(SalesConflictError, match="customer"):
        await sales_service.issue_document(
            Session(),
            {
                "customer_id": uuid4(),
                "document_type": "INVOICE",
                "series": "A",
                "document_date": date.today(),
                "lines": [],
            },
            uuid4(),
        )
    with pytest.raises(SalesNotFoundError, match="payment"):
        await sales_service.confirm_payment(Session(), uuid4(), uuid4())
    await DisabledFiscalProvider().submit(object())


@pytest.mark.asyncio
async def test_confirm_delivery_updates_order_and_creates_inventory_document() -> None:
    delivery = sales_module.SalesDelivery(
        id=uuid4(),
        sales_order_id=uuid4(),
        customer_id=uuid4(),
        warehouse_id=uuid4(),
        delivery_date=date.today(),
        status="DRAFT",
    )
    order = sales_module.SalesOrder(
        id=delivery.sales_order_id,
        customer_id=delivery.customer_id,
        order_date=date.today(),
        status="CONFIRMED",
        total=Decimal("10"),
    )
    order_line = sales_module.SalesOrderLine(
        id=uuid4(),
        sales_order_id=order.id,
        ordinal=1,
        product_id=uuid4(),
        quantity=Decimal("2"),
        delivered_quantity=Decimal("0"),
        unit_price=Decimal("5"),
    )
    delivery_line = sales_module.SalesDeliveryLine(
        id=uuid4(),
        delivery_id=delivery.id,
        sales_order_line_id=order_line.id,
        product_id=order_line.product_id,
        quantity=Decimal("1"),
    )

    class Result:
        def __init__(self, items: list[object]) -> None:
            self.items = items

        def all(self) -> list[object]:
            return self.items

    class Session:
        def __init__(self) -> None:
            self.scalar_calls = 0
            self.scalars_calls = 0

        async def scalar(self, _query: object) -> object:
            self.scalar_calls += 1
            return delivery if self.scalar_calls == 1 else order

        async def scalars(self, _query: object) -> Result:
            self.scalars_calls += 1
            return Result([delivery_line] if self.scalars_calls == 1 else [order_line])

        def add(self, _: object) -> None:
            return None

        async def flush(self) -> None:
            return None

    class Inventory:
        async def confirm(self, _session: object, _document_id: object, _actor: object) -> object:
            return object()

    original_inventory = sales_module.inventory_service
    sales_module.inventory_service = Inventory()
    try:
        result = await sales_service.confirm_delivery(Session(), delivery.id, uuid4())
    finally:
        sales_module.inventory_service = original_inventory
    assert result.status == "CONFIRMED"
    assert order.status == "PARTIALLY_FULFILLED"
