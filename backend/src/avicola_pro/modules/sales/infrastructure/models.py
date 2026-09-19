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


class SalesOrder(Base):
    __tablename__ = "sales_orders"
    __table_args__ = (
        CheckConstraint(
            "status in ('DRAFT','CONFIRMED','PARTIALLY_FULFILLED','FULFILLED','CANCELLED')",
            name="sales_order_status_valid",
        ),
    )
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False)
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default=text("'DRAFT'"))
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, server_default=text("'PYG'"))
    total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, server_default=text("0"))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class SalesOrderLine(Base):
    __tablename__ = "sales_order_lines"
    __table_args__ = (
        UniqueConstraint("sales_order_id", "ordinal", name="uq_sales_order_line_ordinal"),
        CheckConstraint("quantity > 0 and unit_price >= 0", name="sales_order_line_values"),
    )
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    sales_order_id: Mapped[UUID] = mapped_column(ForeignKey("sales_orders.id", ondelete="RESTRICT"), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    delivered_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, server_default=text("0"))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    discount_rate: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False, server_default=text("0"))
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False, server_default=text("0"))


class SalesDelivery(Base):
    __tablename__ = "sales_deliveries"
    __table_args__ = (
        CheckConstraint("status in ('DRAFT','CONFIRMED','REVERSED')", name="sales_delivery_status_valid"),
        UniqueConstraint("idempotency_key", name="uq_sales_delivery_idempotency"),
    )
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    sales_order_id: Mapped[UUID] = mapped_column(ForeignKey("sales_orders.id", ondelete="RESTRICT"), nullable=False)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False)
    warehouse_id: Mapped[UUID] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False)
    delivery_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'DRAFT'"))
    inventory_document_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("inventory_documents.id", ondelete="RESTRICT")
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))


class SalesDeliveryLine(Base):
    __tablename__ = "sales_delivery_lines"
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    delivery_id: Mapped[UUID] = mapped_column(ForeignKey("sales_deliveries.id", ondelete="RESTRICT"), nullable=False)
    sales_order_line_id: Mapped[UUID] = mapped_column(
        ForeignKey("sales_order_lines.id", ondelete="RESTRICT"), nullable=False
    )
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    inventory_lot_id: Mapped[UUID | None] = mapped_column(ForeignKey("inventory_lots.id", ondelete="RESTRICT"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)


class CommercialDocument(Base):
    __tablename__ = "commercial_documents"
    __table_args__ = (
        UniqueConstraint("document_type", "series", "number", name="uq_commercial_document_number"),
        CheckConstraint("total >= 0", name="commercial_document_total_nonnegative"),
        Index("ix_commercial_documents_customer_status", "customer_id", "status"),
    )
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    document_type: Mapped[str] = mapped_column(String(24), nullable=False, server_default=text("'INVOICE'"))
    series: Mapped[str] = mapped_column(String(16), nullable=False)
    number: Mapped[str] = mapped_column(String(32), nullable=False)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False)
    customer_name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    customer_document_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    document_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, server_default=text("'PYG'"))
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default=text("'ISSUED'"))
    exempt_subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, server_default=text("0"))
    vat_5_base: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, server_default=text("0"))
    vat_5_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, server_default=text("0"))
    vat_10_base: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, server_default=text("0"))
    vat_10_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, server_default=text("0"))
    discount_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, server_default=text("0"))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, server_default=text("0"))
    tax_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, server_default=text("0"))
    total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    original_document_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("commercial_documents.id", ondelete="RESTRICT")
    )
    confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class CommercialDocumentLine(Base):
    __tablename__ = "commercial_document_lines"
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    commercial_document_id: Mapped[UUID] = mapped_column(
        ForeignKey("commercial_documents.id", ondelete="RESTRICT"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[UUID | None] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"))
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    discount_rate: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False, server_default=text("0"))
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    base_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)


class CommercialDocumentRelation(Base):
    __tablename__ = "commercial_document_relations"
    source_document_id: Mapped[UUID] = mapped_column(
        ForeignKey("commercial_documents.id", ondelete="RESTRICT"), primary_key=True
    )
    target_type: Mapped[str] = mapped_column(String(24), primary_key=True)
    target_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)


class AccountsReceivable(Base):
    __tablename__ = "accounts_receivable"
    __table_args__ = (
        CheckConstraint("original_amount >= 0 and applied_amount >= 0 and balance >= 0", name="ar_balance_nonnegative"),
    )
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    commercial_document_id: Mapped[UUID] = mapped_column(
        ForeignKey("commercial_documents.id", ondelete="RESTRICT"), unique=True, nullable=False
    )
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False)
    original_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    applied_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, server_default=text("0"))
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'OPEN'"))


class CustomerPayment(Base):
    __tablename__ = "customer_payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="customer_payment_positive"),
        UniqueConstraint("idempotency_key", name="uq_customer_payment_idempotency"),
    )
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False)
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


class CustomerPaymentAllocation(Base):
    __tablename__ = "customer_payment_allocations"
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    payment_id: Mapped[UUID] = mapped_column(ForeignKey("customer_payments.id", ondelete="RESTRICT"), nullable=False)
    accounts_receivable_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts_receivable.id", ondelete="RESTRICT"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
