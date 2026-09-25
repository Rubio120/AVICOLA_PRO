from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from importlib import import_module
from typing import Any
from uuid import UUID, uuid4

from avicola_pro.modules.inventory.domain.egg_units import validate_egg_category_saleable
from avicola_pro.modules.sales.domain.rules import (
    SalesConflictError,
    apply_customer_payment,
    calculate_document_totals,
    validate_credit_note_amount,
)

select: Any = import_module("sqlalchemy").select
func: Any = import_module("sqlalchemy").func
_models = import_module("avicola_pro.modules.sales.infrastructure.models")
SalesOrder: Any = _models.SalesOrder
SalesOrderLine: Any = _models.SalesOrderLine
SalesDelivery: Any = _models.SalesDelivery
SalesDeliveryLine: Any = _models.SalesDeliveryLine
CommercialDocument: Any = _models.CommercialDocument
CommercialDocumentLine: Any = _models.CommercialDocumentLine
CommercialDocumentRelation: Any = _models.CommercialDocumentRelation
AccountsReceivable: Any = _models.AccountsReceivable
CustomerPayment: Any = _models.CustomerPayment
CustomerPaymentAllocation: Any = _models.CustomerPaymentAllocation
Customer: Any = import_module("avicola_pro.modules.parties.infrastructure.models").Customer
DocumentSequence: Any = import_module("avicola_pro.modules.settings.infrastructure.models").DocumentSequence
InventoryDocument: Any = import_module("avicola_pro.modules.inventory.infrastructure.models").InventoryDocument
InventoryDocumentLine: Any = import_module("avicola_pro.modules.inventory.infrastructure.models").InventoryDocumentLine
EggCategory: Any = import_module("avicola_pro.modules.inventory.infrastructure.models").EggCategory
inventory_service: Any = import_module("avicola_pro.modules.inventory.application.service").inventory_service


class SalesNotFoundError(LookupError):
    pass


class DisabledFiscalProvider:
    """V1 adapter: explicitly does not perform network, DNS or persistence."""

    async def submit(self, _: Any) -> None:
        return None


class SalesService:
    async def _ensure_egg_products_are_saleable(self, session: Any, product_ids: set[UUID]) -> None:
        if not product_ids:
            return
        categories = list(
            (
                await session.scalars(
                    select(EggCategory).where(EggCategory.product_id.in_(product_ids)).with_for_update()
                )
            ).all()
        )
        for category in categories:
            try:
                validate_egg_category_saleable(is_active=category.is_active, is_saleable=category.is_saleable)
            except ValueError as exc:
                raise SalesConflictError(str(exc)) from exc

    async def create_order(
        self, session: Any, customer_id: UUID, order_date: date, lines: list[dict[str, Any]], channel: str | None = None
    ) -> Any:
        if not lines:
            raise SalesConflictError("sales order must contain a line")
        if channel not in {"WHOLESALE", "RETAIL"}:
            raise SalesConflictError("a supported sales channel is required")
        order = SalesOrder(
            id=uuid4(),
            customer_id=customer_id,
            order_date=order_date,
            channel=channel,
            status="DRAFT",
            currency_code="PYG",
            total=Decimal("0"),
        )
        session.add(order)
        total = Decimal("0")
        for ordinal, line in enumerate(lines, 1):
            calculated = calculate_document_totals([dict(line)])["total"]
            total += calculated
            session.add(SalesOrderLine(id=uuid4(), sales_order_id=order.id, ordinal=ordinal, **line))
        order.total = total
        await session.flush()
        return order

    async def confirm_order(self, session: Any, order_id: UUID) -> Any:
        order = await session.scalar(select(SalesOrder).where(SalesOrder.id == order_id).with_for_update())
        if order is None:
            raise SalesNotFoundError("Sales order not found")
        if order.status != "DRAFT":
            raise SalesConflictError("only draft orders can be confirmed")
        order.status = "CONFIRMED"
        order.version += 1
        return order

    async def confirm_delivery(self, session: Any, delivery_id: UUID, actor_user_id: UUID) -> Any:
        delivery = await session.scalar(select(SalesDelivery).where(SalesDelivery.id == delivery_id).with_for_update())
        if delivery is None:
            raise SalesNotFoundError("Sales delivery not found")
        if delivery.status == "CONFIRMED":
            return delivery
        if delivery.status != "DRAFT":
            raise SalesConflictError("only draft deliveries can be confirmed")
        order = await session.scalar(
            select(SalesOrder).where(SalesOrder.id == delivery.sales_order_id).with_for_update()
        )
        if order is None or order.status not in {"CONFIRMED", "PARTIALLY_FULFILLED"}:
            raise SalesConflictError("order must be confirmed before delivery")
        lines = list(
            (await session.scalars(select(SalesDeliveryLine).where(SalesDeliveryLine.delivery_id == delivery.id))).all()
        )
        if not lines:
            raise SalesConflictError("delivery must contain a line")
        await self._ensure_egg_products_are_saleable(session, {line.product_id for line in lines})
        order_lines = {
            line.id: line
            for line in (
                await session.scalars(
                    select(SalesOrderLine).where(SalesOrderLine.sales_order_id == order.id).with_for_update()
                )
            ).all()
        }
        document = InventoryDocument(
            id=uuid4(),
            document_type="ISSUE",
            effective_date=delivery.delivery_date,
            warehouse_id=delivery.warehouse_id,
            source_type="sales_delivery",
            source_id=delivery.id,
        )
        session.add(document)
        await session.flush()
        for ordinal, line in enumerate(lines, 1):
            order_line = order_lines.get(line.sales_order_line_id)
            if order_line is None or order_line.product_id != line.product_id:
                raise SalesConflictError("delivery line does not belong to order")
            if line.quantity > order_line.quantity - order_line.delivered_quantity:
                raise SalesConflictError("delivered quantity exceeds ordered quantity")
            session.add(
                InventoryDocumentLine(
                    id=uuid4(),
                    document_id=document.id,
                    ordinal=ordinal,
                    product_id=line.product_id,
                    inventory_lot_id=line.inventory_lot_id,
                    quantity=line.quantity,
                    unit_cost=Decimal("0"),
                    direction="OUT",
                )
            )
            order_line.delivered_quantity += line.quantity
        await session.flush()
        await inventory_service.confirm(session, document.id, actor_user_id)
        delivered = sum((line.delivered_quantity for line in order_lines.values()), Decimal("0"))
        ordered = sum((line.quantity for line in order_lines.values()), Decimal("0"))
        order.status = "FULFILLED" if delivered == ordered else "PARTIALLY_FULFILLED"
        delivery.inventory_document_id = document.id
        delivery.status = "CONFIRMED"
        delivery.confirmed_at = datetime.now(UTC)
        delivery.confirmed_by = actor_user_id
        return delivery

    async def issue_document(self, session: Any, payload: dict[str, Any], actor_user_id: UUID) -> Any:
        customer = await session.scalar(select(Customer).where(Customer.id == payload["customer_id"]).with_for_update())
        if customer is None or not customer.is_active:
            raise SalesConflictError("active customer is required")
        sequence = await session.scalar(
            select(DocumentSequence)
            .where(
                DocumentSequence.document_type == payload["document_type"],
                DocumentSequence.series == payload["series"],
                DocumentSequence.is_active.is_(True),
            )
            .with_for_update()
        )
        if sequence is None:
            raise SalesConflictError("active document sequence is required")
        sequence.current_number += 1
        number = str(sequence.current_number).zfill(sequence.padding)
        lines = [dict(item) for item in payload["lines"]]
        if payload["document_type"] != "CREDIT_NOTE":
            if payload.get("channel") not in {"WHOLESALE", "RETAIL"}:
                raise SalesConflictError("a supported sales channel is required")
            product_ids = {line["product_id"] for line in lines if line.get("product_id") is not None}
            await self._ensure_egg_products_are_saleable(session, product_ids)
        totals = calculate_document_totals(lines)
        original = None
        if payload["document_type"] == "CREDIT_NOTE":
            if payload.get("original_document_id") is None:
                raise SalesConflictError("credit note must reference an original document")
            original = await session.scalar(
                select(CommercialDocument)
                .where(CommercialDocument.id == payload["original_document_id"])
                .with_for_update()
            )
            if original is None or original.document_type == "CREDIT_NOTE":
                raise SalesConflictError("credit note original document is invalid")
            credited = await session.scalar(
                select(func.coalesce(func.sum(CommercialDocument.total), 0)).where(
                    CommercialDocument.original_document_id == original.id,
                    CommercialDocument.document_type == "CREDIT_NOTE",
                )
            )
            validate_credit_note_amount(original.total, Decimal(str(credited or 0)), totals["total"])
        document = CommercialDocument(
            id=uuid4(),
            document_type=payload["document_type"],
            series=payload["series"],
            number=number,
            customer_id=customer.id,
            customer_name_snapshot=customer.name,
            customer_document_snapshot=f"{customer.document_type}:{customer.document_number}",
            document_date=payload["document_date"],
            channel=original.channel if original is not None else payload["channel"],
            original_document_id=payload.get("original_document_id"),
            **{
                key: totals[key]
                for key in (
                    "exempt_subtotal",
                    "vat_5_base",
                    "vat_5_amount",
                    "vat_10_base",
                    "vat_10_amount",
                    "discount_total",
                    "subtotal",
                    "tax_total",
                    "total",
                )
            },
        )
        session.add(document)
        await session.flush()
        for ordinal, line in enumerate(lines, 1):
            session.add(
                CommercialDocumentLine(
                    id=uuid4(),
                    commercial_document_id=document.id,
                    ordinal=ordinal,
                    description=line["description"],
                    product_id=line.get("product_id"),
                    quantity=line["quantity"],
                    unit_price=line["unit_price"],
                    discount_rate=line.get("discount_rate", Decimal("0")),
                    tax_rate=line["tax_rate"],
                    base_amount=line["base"],
                    tax_amount=line["tax_amount"],
                    total=line["total"],
                )
            )
        if document.document_type != "CREDIT_NOTE":
            session.add(
                AccountsReceivable(
                    id=uuid4(),
                    commercial_document_id=document.id,
                    customer_id=customer.id,
                    original_amount=document.total,
                    balance=document.total,
                    due_date=document.document_date + timedelta(days=customer.payment_term_days),
                )
            )
        elif original is not None:
            account = await session.scalar(
                select(AccountsReceivable)
                .where(AccountsReceivable.commercial_document_id == original.id)
                .with_for_update()
            )
            if account is None:
                raise SalesConflictError("original document has no receivable")
            account.original_amount -= document.total
            account.balance = max(Decimal("0"), account.balance - document.total)
            account.status = "PAID" if account.balance == 0 else "PARTIALLY_PAID"
        await session.flush()
        return document

    async def confirm_payment(self, session: Any, payment_id: UUID, actor_user_id: UUID) -> Any:
        payment = await session.scalar(
            select(CustomerPayment).where(CustomerPayment.id == payment_id).with_for_update()
        )
        if payment is None:
            raise SalesNotFoundError("Customer payment not found")
        if payment.status == "CONFIRMED":
            return payment
        if payment.status != "DRAFT":
            raise SalesConflictError("only draft payments can be confirmed")
        allocations = list(
            (
                await session.scalars(
                    select(CustomerPaymentAllocation).where(CustomerPaymentAllocation.payment_id == payment.id)
                )
            ).all()
        )
        if not allocations:
            raise SalesConflictError("payment must contain an allocation")
        allocated = sum((allocation.amount for allocation in allocations), Decimal("0"))
        if allocated != payment.amount:
            raise SalesConflictError("payment allocations must equal payment")
        for allocation in allocations:
            account = await session.scalar(
                select(AccountsReceivable)
                .where(AccountsReceivable.id == allocation.accounts_receivable_id)
                .with_for_update()
            )
            if account is None or account.customer_id != payment.customer_id:
                raise SalesConflictError("receivable does not belong to customer")
            account.balance = apply_customer_payment(payment.amount, allocation.amount, account.balance)
            account.applied_amount += allocation.amount
            account.status = "PAID" if account.balance == 0 else "PARTIALLY_PAID"
        payment.status = "CONFIRMED"
        payment.cash_movement_id = uuid4()
        payment.confirmed_at = datetime.now(UTC)
        payment.confirmed_by = actor_user_id
        return payment


sales_service = SalesService()
