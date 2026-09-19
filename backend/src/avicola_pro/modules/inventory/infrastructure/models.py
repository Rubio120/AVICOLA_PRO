from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from avicola_pro.shared.infrastructure.models import Base


class InventoryLot(Base):
    __tablename__ = "inventory_lots"
    __table_args__ = (
        CheckConstraint("lot_code <> ''", name="inventory_lot_code_nonempty"),
        CheckConstraint(
            "expiration_date is null or manufacture_date is null or expiration_date >= manufacture_date",
            name="inventory_lot_dates_order",
        ),
    )
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    lot_code: Mapped[str] = mapped_column(String(80), nullable=False)
    manufacture_date: Mapped[date | None] = mapped_column(Date)
    expiration_date: Mapped[date | None] = mapped_column(Date)
    supplier_id: Mapped[UUID | None] = mapped_column(ForeignKey("suppliers.id", ondelete="RESTRICT"))


class InventoryDocument(Base):
    __tablename__ = "inventory_documents"
    __table_args__ = (
        CheckConstraint(
            "document_type in ('RECEIPT','ISSUE','TRANSFER','ADJUSTMENT')", name="inventory_document_type_valid"
        ),
        CheckConstraint("status in ('DRAFT','CONFIRMED','REVERSED')", name="inventory_document_status_valid"),
        CheckConstraint("reversed_at is null or status = 'REVERSED'", name="inventory_document_reversed_state"),
    )
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    document_type: Mapped[str] = mapped_column(String(16), nullable=False)
    series: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("''"))
    number: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("''"))
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'DRAFT'"))
    source_type: Mapped[str | None] = mapped_column(String(64))
    source_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    warehouse_id: Mapped[UUID | None] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"))
    destination_warehouse_id: Mapped[UUID | None] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"))
    reason: Mapped[str | None] = mapped_column(String(500))
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reversed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    reversal_of_id: Mapped[UUID | None] = mapped_column(ForeignKey("inventory_documents.id", ondelete="RESTRICT"))
    reversal_reason: Mapped[str | None] = mapped_column(String(500))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class InventoryDocumentLine(Base):
    __tablename__ = "inventory_document_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="inventory_line_quantity_positive"),
        CheckConstraint("unit_cost >= 0", name="inventory_line_cost_nonnegative"),
        CheckConstraint("direction in ('IN','OUT')", name="inventory_line_direction_valid"),
    )
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("inventory_documents.id", ondelete="RESTRICT"), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    inventory_lot_id: Mapped[UUID | None] = mapped_column(ForeignKey("inventory_lots.id", ondelete="RESTRICT"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, server_default=text("0"))
    direction: Mapped[str] = mapped_column(String(3), nullable=False, server_default=text("'IN'"))


class InventoryMovement(Base):
    __tablename__ = "inventory_movements"
    __table_args__ = (
        CheckConstraint(
            "movement_type in ('RECEIPT','ISSUE','TRANSFER_IN','TRANSFER_OUT','ADJUSTMENT','REVERSAL')",
            name="inventory_movement_type_valid",
        ),
        CheckConstraint("quantity_delta <> 0", name="inventory_movement_delta_nonzero"),
        CheckConstraint("value_delta is not null", name="inventory_movement_value_required"),
    )
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("inventory_documents.id", ondelete="RESTRICT"), nullable=False)
    line_id: Mapped[UUID] = mapped_column(
        ForeignKey("inventory_document_lines.id", ondelete="RESTRICT"), nullable=False
    )
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    inventory_lot_id: Mapped[UUID | None] = mapped_column(ForeignKey("inventory_lots.id", ondelete="RESTRICT"))
    warehouse_id: Mapped[UUID] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False)
    movement_type: Mapped[str] = mapped_column(String(16), nullable=False)
    quantity_delta: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    value_delta: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    original_unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    original_value_delta: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    actor_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    reversal_of_id: Mapped[UUID | None] = mapped_column(ForeignKey("inventory_movements.id", ondelete="RESTRICT"))


class InventoryBalance(Base):
    __tablename__ = "inventory_balances"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="inventory_balance_quantity_nonnegative"),
        CheckConstraint("inventory_value >= 0", name="inventory_balance_value_nonnegative"),
    )
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    warehouse_id: Mapped[UUID] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False)
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    inventory_lot_id: Mapped[UUID | None] = mapped_column(ForeignKey("inventory_lots.id", ondelete="RESTRICT"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, server_default=text("0"))
    inventory_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, server_default=text("0"))
    average_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, server_default=text("0"))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class InventoryCostVariance(Base):
    __tablename__ = "inventory_cost_variances"
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    original_movement_id: Mapped[UUID] = mapped_column(
        ForeignKey("inventory_movements.id", ondelete="RESTRICT"), nullable=False
    )
    reversal_movement_id: Mapped[UUID] = mapped_column(
        ForeignKey("inventory_movements.id", ondelete="RESTRICT"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
