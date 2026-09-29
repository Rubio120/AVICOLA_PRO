from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, DateTime, Index, Integer, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from avicola_pro.shared.infrastructure.models import Base


class CostCenter(Base):
    __tablename__ = "cost_centers"
    __table_args__ = (UniqueConstraint("code", name="uq_cost_centers_code"),)
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))


class CostEvent(Base):
    __tablename__ = "cost_events"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_cost_events_idempotency"),
        CheckConstraint("amount >= 0", name="cost_events_amount_nonnegative"),
        CheckConstraint("status in ('DRAFT','CONFIRMED','REVERSED')", name="cost_events_status_valid"),
        Index("ix_cost_events_status_date", "status", "effective_date"),
    )
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    cost_center_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, server_default=text("'PYG'"))
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'CONFIRMED'"))
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    reversal_of_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    actor_user_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    event_metadata: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class CostAllocation(Base):
    __tablename__ = "cost_allocations"
    __table_args__ = (
        UniqueConstraint("cost_event_id", "target_type", "target_id", name="uq_cost_allocations_target"),
        CheckConstraint("amount >= 0 and weight > 0", name="cost_allocations_values"),
    )
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    cost_event_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    weight: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)


class CostRun(Base):
    __tablename__ = "cost_runs"
    __table_args__ = (
        UniqueConstraint("run_date", "version", name="uq_cost_runs_date_version"),
        CheckConstraint("status in ('DRAFT','CALCULATING','CLOSED')", name="cost_runs_status_valid"),
    )
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    run_date: Mapped[date] = mapped_column(Date, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'DRAFT'"))
    created_by: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CostRunSnapshot(Base):
    __tablename__ = "cost_run_snapshots"
    __table_args__ = (UniqueConstraint("cost_run_id", "target_type", "target_id", name="uq_cost_run_snapshot_target"),)
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    cost_run_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, server_default=text("0"))
    cost_per_unit: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))


class ProfitabilitySnapshot(Base):
    __tablename__ = "profitability_snapshots"
    __table_args__ = (UniqueConstraint("cost_run_id", "source_id", name="uq_profitability_run_source"),)
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    cost_run_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    source_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    revenue: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    margin: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    margin_rate: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    notes: Mapped[str | None] = mapped_column(Text)
