from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from avicola_pro.shared.infrastructure.models import Base


class Flock(Base):
    __tablename__ = "flocks"
    __table_args__ = (CheckConstraint("planned_initial_quantity > 0", name="flock_initial_positive"),)
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    purpose: Mapped[str] = mapped_column(String(120), nullable=False)
    breed: Mapped[str | None] = mapped_column(String(120))
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    planned_initial_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'DRAFT'"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class FlockHouseAssignment(Base):
    __tablename__ = "flock_house_assignments"
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    flock_id: Mapped[UUID] = mapped_column(ForeignKey("flocks.id", ondelete="RESTRICT"), nullable=False)
    house_id: Mapped[UUID] = mapped_column(ForeignKey("houses.id", ondelete="RESTRICT"), nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[date | None] = mapped_column(Date)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)


class FlockBalance(Base):
    __tablename__ = "flock_balances"
    flock_id: Mapped[UUID] = mapped_column(ForeignKey("flocks.id", ondelete="RESTRICT"), primary_key=True)
    live_birds: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, server_default=text("0"))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    __table_args__ = (CheckConstraint("live_birds >= 0", name="flock_balance_nonnegative"),)


class BirdMovementEvent(Base):
    __tablename__ = "bird_movement_events"
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    flock_id: Mapped[UUID] = mapped_column(ForeignKey("flocks.id", ondelete="RESTRICT"), nullable=False)
    house_id: Mapped[UUID | None] = mapped_column(ForeignKey("houses.id", ondelete="RESTRICT"))
    movement_type: Mapped[str] = mapped_column(String(16), nullable=False)
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'CONFIRMED'"))
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True)
    reversal_of_id: Mapped[UUID | None] = mapped_column(ForeignKey("bird_movement_events.id", ondelete="RESTRICT"))


class MortalityEvent(Base):
    __tablename__ = "mortality_events"
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    flock_id: Mapped[UUID] = mapped_column(ForeignKey("flocks.id", ondelete="RESTRICT"), nullable=False)
    house_id: Mapped[UUID | None] = mapped_column(ForeignKey("houses.id", ondelete="RESTRICT"))
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    cause: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'CONFIRMED'"))
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True)
    reversal_of_id: Mapped[UUID | None] = mapped_column(ForeignKey("mortality_events.id", ondelete="RESTRICT"))


class BirdAdjustmentEvent(Base):
    __tablename__ = "bird_adjustment_events"
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    flock_id: Mapped[UUID] = mapped_column(ForeignKey("flocks.id", ondelete="RESTRICT"), nullable=False)
    adjustment_type: Mapped[str] = mapped_column(String(20), nullable=False)
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True)


class FlockDailyRecord(Base):
    __tablename__ = "flock_daily_records"
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    flock_id: Mapped[UUID] = mapped_column(ForeignKey("flocks.id", ondelete="RESTRICT"), nullable=False)
    record_date: Mapped[date] = mapped_column(Date, nullable=False)
    observed_birds: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    average_weight: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    notes: Mapped[str | None] = mapped_column(String(500))


class FeedConsumption(Base):
    __tablename__ = "feed_consumption"
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    flock_id: Mapped[UUID] = mapped_column(ForeignKey("flocks.id", ondelete="RESTRICT"), nullable=False)
    house_id: Mapped[UUID | None] = mapped_column(ForeignKey("houses.id", ondelete="RESTRICT"))
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    warehouse_id: Mapped[UUID] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    inventory_movement_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("inventory_movements.id", ondelete="RESTRICT")
    )
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False)
