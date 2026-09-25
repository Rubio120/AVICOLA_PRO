from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from avicola_pro.shared.infrastructure.models import Base


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    __table_args__ = (
        CheckConstraint(
            "status in ('DRAFT','APPROVED','PARTIALLY_RECEIVED','RECEIVED','CANCELLED')",
            name="purchase_order_status_valid",
        ),
        CheckConstraint("total >= 0", name="purchase_order_total_nonnegative"),
        Index("ix_purchase_orders_supplier_status", "supplier_id", "status"),
    )
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    supplier_id: Mapped[UUID] = mapped_column(ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False)
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, server_default=text("'PYG'"))
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default=text("'DRAFT'"))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, server_default=text("0"))
    tax_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, server_default=text("0"))
    total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, server_default=text("0"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class PurchaseOrderLine(Base):
    __tablename__ = "purchase_order_lines"
    __table_args__ = (
        UniqueConstraint("purchase_order_id", "ordinal", name="uq_purchase_order_line_ordinal"),
        CheckConstraint(
            "quantity > 0 and received_quantity >= 0 and received_quantity <= quantity",
            name="purchase_order_line_quantities",
        ),
        CheckConstraint(
            "unit_price >= 0 and discount_rate between 0 and 1 and tax_rate between 0 and 1",
            name="purchase_order_line_rates",
        ),
    )
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    purchase_order_id: Mapped[UUID] = mapped_column(
        ForeignKey("purchase_orders.id", ondelete="RESTRICT"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    received_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, server_default=text("0"))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    discount_rate: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False, server_default=text("0"))
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False, server_default=text("0"))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, server_default=text("0"))
    total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, server_default=text("0"))


class PurchaseReceipt(Base):
    __tablename__ = "purchase_receipts"
    __table_args__ = (
        CheckConstraint("status in ('DRAFT','CONFIRMED','REVERSED')", name="purchase_receipt_status_valid"),
        UniqueConstraint("idempotency_key", name="uq_purchase_receipt_idempotency"),
    )
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    purchase_order_id: Mapped[UUID] = mapped_column(
        ForeignKey("purchase_orders.id", ondelete="RESTRICT"), nullable=False
    )
    warehouse_id: Mapped[UUID] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False)
    receipt_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'DRAFT'"))
    inventory_document_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("inventory_documents.id", ondelete="RESTRICT")
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reversed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    reversal_reason: Mapped[str | None] = mapped_column(String(500))


class PurchaseReceiptLine(Base):
    __tablename__ = "purchase_receipt_lines"
    __table_args__ = (CheckConstraint("quantity > 0 and unit_cost >= 0", name="purchase_receipt_line_values"),)
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    receipt_id: Mapped[UUID] = mapped_column(ForeignKey("purchase_receipts.id", ondelete="RESTRICT"), nullable=False)
    purchase_order_line_id: Mapped[UUID] = mapped_column(
        ForeignKey("purchase_order_lines.id", ondelete="RESTRICT"), nullable=False
    )
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    inventory_lot_id: Mapped[UUID | None] = mapped_column(ForeignKey("inventory_lots.id", ondelete="RESTRICT"))
    lot_code: Mapped[str | None] = mapped_column(String(80))
    expiration_date: Mapped[date | None] = mapped_column(Date)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)


class SupplierDocument(Base):
    __tablename__ = "supplier_documents"
    __table_args__ = (
        UniqueConstraint("supplier_id", "document_type", "external_number", name="uq_supplier_document_number"),
        CheckConstraint("total >= 0", name="supplier_document_total_nonnegative"),
    )
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    supplier_id: Mapped[UUID] = mapped_column(ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False)
    document_type: Mapped[str] = mapped_column(String(24), nullable=False, server_default=text("'INVOICE'"))
    external_number: Mapped[str] = mapped_column(String(64), nullable=False)
    document_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, server_default=text("'PYG'"))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, server_default=text("0"))
    tax_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, server_default=text("0"))
    total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'CONFIRMED'"))


class SupplierDocumentLine(Base):
    __tablename__ = "supplier_document_lines"
    __table_args__ = (CheckConstraint("quantity > 0 and unit_price >= 0", name="supplier_document_line_values"),)
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    supplier_document_id: Mapped[UUID] = mapped_column(
        ForeignKey("supplier_documents.id", ondelete="RESTRICT"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[UUID | None] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"))
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False, server_default=text("0"))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, server_default=text("0"))
    total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)


class SupplierDocumentReceipt(Base):
    __tablename__ = "supplier_document_receipts"
    __table_args__ = (UniqueConstraint("supplier_document_id", "receipt_id", name="uq_supplier_document_receipt"),)
    supplier_document_id: Mapped[UUID] = mapped_column(
        ForeignKey("supplier_documents.id", ondelete="RESTRICT"), primary_key=True
    )
    receipt_id: Mapped[UUID] = mapped_column(ForeignKey("purchase_receipts.id", ondelete="RESTRICT"), primary_key=True)


class AccountsPayable(Base):
    __tablename__ = "accounts_payable"
    __table_args__ = (
        CheckConstraint("original_amount >= 0 and applied_amount >= 0 and balance >= 0", name="ap_balance_nonnegative"),
    )
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    supplier_document_id: Mapped[UUID] = mapped_column(
        ForeignKey("supplier_documents.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    supplier_id: Mapped[UUID] = mapped_column(ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False)
    original_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    applied_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, server_default=text("0"))
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'OPEN'"))


class SupplierPayment(Base):
    __tablename__ = "supplier_payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="supplier_payment_positive"),
        CheckConstraint("status in ('DRAFT','CONFIRMED','REVERSED')", name="supplier_payment_status_valid"),
        UniqueConstraint("idempotency_key", name="uq_supplier_payment_idempotency"),
        Index("ix_supplier_payments_supplier_status", "supplier_id", "status"),
    )
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    supplier_id: Mapped[UUID] = mapped_column(ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    payment_method_code: Mapped[str] = mapped_column(
        ForeignKey("payment_methods.code", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'DRAFT'"))
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    cash_movement_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    reversal_of_id: Mapped[UUID | None] = mapped_column(ForeignKey("supplier_payments.id", ondelete="RESTRICT"))
    reversal_reason: Mapped[str | None] = mapped_column(String(500))


class SupplierPaymentAllocation(Base):
    __tablename__ = "supplier_payment_allocations"
    __table_args__ = (CheckConstraint("amount > 0", name="supplier_allocation_positive"),)
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    payment_id: Mapped[UUID] = mapped_column(ForeignKey("supplier_payments.id", ondelete="RESTRICT"), nullable=False)
    accounts_payable_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts_payable.id", ondelete="RESTRICT"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
