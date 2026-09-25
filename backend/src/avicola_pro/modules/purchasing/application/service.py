from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from importlib import import_module
from typing import Any
from uuid import UUID, uuid4

from avicola_pro.modules.purchasing.domain.rules import (
    PurchaseConflictError,
    apply_payment,
    calculate_line_total,
    next_order_status,
)

_models = import_module("avicola_pro.modules.purchasing.infrastructure.models")
select: Any = import_module("sqlalchemy").select
func: Any = import_module("sqlalchemy").func
PurchaseOrder: Any = _models.PurchaseOrder
PurchaseOrderLine: Any = _models.PurchaseOrderLine
PurchaseReceipt: Any = _models.PurchaseReceipt
PurchaseReceiptLine: Any = _models.PurchaseReceiptLine
SupplierDocument: Any = _models.SupplierDocument
SupplierDocumentReceipt: Any = _models.SupplierDocumentReceipt
AccountsPayable: Any = _models.AccountsPayable
SupplierPayment: Any = _models.SupplierPayment
SupplierPaymentAllocation: Any = _models.SupplierPaymentAllocation
_inventory = import_module("avicola_pro.modules.inventory.infrastructure.models")
InventoryDocument: Any = _inventory.InventoryDocument
InventoryDocumentLine: Any = _inventory.InventoryDocumentLine
InventoryLot: Any = _inventory.InventoryLot
_inventory_service = import_module("avicola_pro.modules.inventory.application.service")
inventory_service: Any = _inventory_service.inventory_service


class PurchaseNotFoundError(LookupError):
    pass


class PurchaseService:
    async def create_order(self, session: Any, supplier_id: UUID, order_date: date, lines: list[dict[str, Any]]) -> Any:
        if not lines:
            raise PurchaseConflictError("purchase order must contain a line")
        order = PurchaseOrder(id=uuid4(), supplier_id=supplier_id, order_date=order_date, status="DRAFT")
        subtotal = Decimal("0")
        tax_total = Decimal("0")
        session.add(order)
        for ordinal, payload in enumerate(lines, start=1):
            total, tax = calculate_line_total(
                payload["unit_price"],
                payload["quantity"],
                payload.get("discount_rate", Decimal("0")),
                payload.get("tax_rate", Decimal("0")),
            )
            subtotal += total - tax
            tax_total += tax
            session.add(
                PurchaseOrderLine(
                    id=uuid4(), purchase_order_id=order.id, ordinal=ordinal, total=total, tax_amount=tax, **payload
                )
            )
        order.subtotal = subtotal
        order.tax_total = tax_total
        order.total = subtotal + tax_total
        await session.flush()
        return order

    async def approve_order(self, session: Any, order_id: UUID, actor_user_id: UUID) -> Any:
        order = await session.scalar(select(PurchaseOrder).where(PurchaseOrder.id == order_id).with_for_update())
        if order is None:
            raise PurchaseNotFoundError("Purchase order not found")
        if order.status != "DRAFT":
            raise PurchaseConflictError("only draft orders can be approved")
        order.status = "APPROVED"
        order.approved_at = datetime.now(UTC)
        order.approved_by = actor_user_id
        order.version += 1
        await session.flush()
        return order

    async def confirm_receipt(self, session: Any, receipt_id: UUID, actor_user_id: UUID) -> Any:
        receipt = await session.scalar(
            select(PurchaseReceipt).where(PurchaseReceipt.id == receipt_id).with_for_update()
        )
        if receipt is None:
            raise PurchaseNotFoundError("Purchase receipt not found")
        if receipt.status == "CONFIRMED":
            return receipt
        if receipt.status != "DRAFT":
            raise PurchaseConflictError("only draft receipts can be confirmed")
        order = await session.scalar(
            select(PurchaseOrder).where(PurchaseOrder.id == receipt.purchase_order_id).with_for_update()
        )
        if order is None:
            raise PurchaseNotFoundError("Purchase order not found")
        if order.status not in {"APPROVED", "PARTIALLY_RECEIVED"}:
            raise PurchaseConflictError("order must be approved before receiving")
        lines = list(
            (
                await session.scalars(select(PurchaseReceiptLine).where(PurchaseReceiptLine.receipt_id == receipt.id))
            ).all()
        )
        if not lines:
            raise PurchaseConflictError("receipt must contain a line")
        order_lines = {
            line.id: line
            for line in (
                await session.scalars(
                    select(PurchaseOrderLine).where(PurchaseOrderLine.purchase_order_id == order.id).with_for_update()
                )
            ).all()
        }
        inventory_document = InventoryDocument(
            id=uuid4(),
            document_type="RECEIPT",
            effective_date=receipt.receipt_date,
            warehouse_id=receipt.warehouse_id,
            source_type="purchase_receipt",
            source_id=receipt.id,
        )
        session.add(inventory_document)
        await session.flush()
        for ordinal, line in enumerate(lines, start=1):
            order_line = order_lines.get(line.purchase_order_line_id)
            if order_line is None or order_line.product_id != line.product_id:
                raise PurchaseConflictError("receipt line does not belong to order")
            if line.quantity > order_line.quantity - order_line.received_quantity:
                raise PurchaseConflictError("received quantity exceeds ordered quantity")
            if line.inventory_lot_id is None and line.lot_code:
                lot = InventoryLot(
                    id=uuid4(), product_id=line.product_id, lot_code=line.lot_code, expiration_date=line.expiration_date
                )
                session.add(lot)
                await session.flush()
                line.inventory_lot_id = lot.id
            session.add(
                InventoryDocumentLine(
                    id=uuid4(),
                    document_id=inventory_document.id,
                    ordinal=ordinal,
                    product_id=line.product_id,
                    inventory_lot_id=line.inventory_lot_id,
                    quantity=line.quantity,
                    unit_cost=line.unit_cost,
                    direction="IN",
                )
            )
            order_line.received_quantity += line.quantity
        await session.flush()
        await inventory_service.confirm(session, inventory_document.id, actor_user_id)
        received = sum((line.received_quantity for line in order_lines.values()), Decimal("0"))
        ordered = sum((line.quantity for line in order_lines.values()), Decimal("0"))
        order.status = next_order_status(order.status, received, ordered)
        receipt.inventory_document_id = inventory_document.id
        receipt.status = "CONFIRMED"
        receipt.confirmed_at = datetime.now(UTC)
        receipt.confirmed_by = actor_user_id
        await session.flush()
        return receipt

    async def create_supplier_document(self, session: Any, payload: dict[str, Any]) -> Any:
        document = SupplierDocument(id=uuid4(), **payload)
        session.add(document)
        await session.flush()
        session.add(
            AccountsPayable(
                id=uuid4(),
                supplier_document_id=document.id,
                supplier_id=document.supplier_id,
                original_amount=document.total,
                balance=document.total,
                due_date=payload["document_date"],
            )
        )
        await session.flush()
        return document

    async def create_payment(
        self,
        session: Any,
        supplier_id: UUID,
        amount: Decimal,
        payment_date: date,
        payment_method_code: str,
        idempotency_key: str | None,
        allocations: list[dict[str, Any]],
    ) -> tuple[Any, bool]:
        async def existing_payment() -> Any:
            existing = await session.scalar(
                select(SupplierPayment).where(SupplierPayment.idempotency_key == idempotency_key)
            )
            if existing is None:
                return None
            existing_allocations = list(
                (
                    await session.scalars(
                        select(SupplierPaymentAllocation).where(SupplierPaymentAllocation.payment_id == existing.id)
                    )
                ).all()
            )
            requested_allocations = sorted((str(item["accounts_payable_id"]), item["amount"]) for item in allocations)
            stored_allocations = sorted((str(item.accounts_payable_id), item.amount) for item in existing_allocations)
            if (
                existing.supplier_id != supplier_id
                or existing.amount != amount
                or existing.payment_date != payment_date
                or existing.payment_method_code != payment_method_code
                or stored_allocations != requested_allocations
            ):
                raise PurchaseConflictError("idempotency key reused with different payment data")
            return existing

        if idempotency_key:
            await session.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(idempotency_key, 0))))
            existing = await existing_payment()
            if existing is not None:
                return existing, True

        payment = SupplierPayment(
            id=uuid4(),
            supplier_id=supplier_id,
            amount=amount,
            payment_date=payment_date,
            payment_method_code=payment_method_code,
            idempotency_key=idempotency_key,
        )
        session.add(payment)
        await session.flush()
        for allocation in allocations:
            session.add(SupplierPaymentAllocation(id=uuid4(), payment_id=payment.id, **allocation))
        await session.flush()
        return payment, False

    async def confirm_payment(self, session: Any, payment_id: UUID, actor_user_id: UUID) -> Any:
        payment = await session.scalar(
            select(SupplierPayment).where(SupplierPayment.id == payment_id).with_for_update()
        )
        if payment is None:
            raise PurchaseNotFoundError("Supplier payment not found")
        if payment.status == "CONFIRMED":
            return payment
        if payment.status != "DRAFT":
            raise PurchaseConflictError("only draft payments can be confirmed")
        allocations = list(
            (
                await session.scalars(
                    select(SupplierPaymentAllocation).where(SupplierPaymentAllocation.payment_id == payment.id)
                )
            ).all()
        )
        if not allocations:
            raise PurchaseConflictError("payment must have an allocation")
        allocated_total = sum((item.amount for item in allocations), Decimal("0"))
        if allocated_total > payment.amount:
            raise PurchaseConflictError("payment amount exceeds payment")
        for allocation in allocations:
            account = await session.scalar(
                select(AccountsPayable).where(AccountsPayable.id == allocation.accounts_payable_id).with_for_update()
            )
            if account is None or account.supplier_id != payment.supplier_id:
                raise PurchaseConflictError("invalid payable allocation")
            account.balance = apply_payment(payment.amount, allocation.amount, account.balance)
            account.applied_amount += allocation.amount
            account.status = "PAID" if account.balance == 0 else "PARTIALLY_PAID"
        payment.status = "CONFIRMED"
        payment.cash_movement_id = uuid4()
        payment.confirmed_at = datetime.now(UTC)
        payment.confirmed_by = actor_user_id
        await session.flush()
        return payment

    async def reverse_payment(self, session: Any, payment_id: UUID, actor_user_id: UUID, reason: str) -> Any:
        original = await session.scalar(
            select(SupplierPayment).where(SupplierPayment.id == payment_id).with_for_update()
        )
        if original is None:
            raise PurchaseNotFoundError("Supplier payment not found")
        if original.status != "CONFIRMED":
            raise PurchaseConflictError("only confirmed payments can be reversed")
        reversal = SupplierPayment(
            id=uuid4(),
            supplier_id=original.supplier_id,
            amount=original.amount,
            payment_date=date.today(),
            payment_method_code=original.payment_method_code,
            status="CONFIRMED",
            cash_movement_id=uuid4(),
            confirmed_at=datetime.now(UTC),
            confirmed_by=actor_user_id,
            reversal_of_id=original.id,
            reversal_reason=reason,
        )
        session.add(reversal)
        allocations = list(
            (
                await session.scalars(
                    select(SupplierPaymentAllocation).where(SupplierPaymentAllocation.payment_id == original.id)
                )
            ).all()
        )
        for allocation in allocations:
            account = await session.scalar(
                select(AccountsPayable).where(AccountsPayable.id == allocation.accounts_payable_id).with_for_update()
            )
            if account is None:
                raise PurchaseConflictError("payable allocation not found")
            account.applied_amount -= allocation.amount
            account.balance += allocation.amount
            account.status = "OPEN" if account.applied_amount == 0 else "PARTIALLY_PAID"
            session.add(
                SupplierPaymentAllocation(
                    id=uuid4(), payment_id=reversal.id, accounts_payable_id=account.id, amount=allocation.amount
                )
            )
        original.status = "REVERSED"
        await session.flush()
        return reversal


purchasing_service = PurchaseService()
