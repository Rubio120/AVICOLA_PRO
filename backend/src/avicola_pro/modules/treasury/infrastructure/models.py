from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from avicola_pro.shared.infrastructure.models import Base


class CashAccount(Base):
    __tablename__ = "cash_accounts"
    __table_args__ = (UniqueConstraint("code", name="uq_cash_accounts_code"),)
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    account_type: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'CASH'"))
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, server_default=text("'PYG'"))
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))


class CashSession(Base):
    __tablename__ = "cash_sessions"
    __table_args__ = (
        CheckConstraint("status in ('OPEN','CLOSED','REOPENED')", name="cash_session_status_valid"),
        Index(
            "uq_cash_sessions_open_account",
            "cash_account_id",
            unique=True,
            postgresql_where=text("status in ('OPEN','REOPENED')"),
        ),
    )
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    cash_account_id: Mapped[UUID] = mapped_column(ForeignKey("cash_accounts.id", ondelete="RESTRICT"), nullable=False)
    opened_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, server_default=text("0"))
    closed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expected_balance: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    counted_balance: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    difference: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'OPEN'"))
    version: Mapped[int] = mapped_column(nullable=False, server_default=text("1"))


class CashMovement(Base):
    __tablename__ = "cash_movements"
    __table_args__ = (
        CheckConstraint(
            "movement_type in ('INCOME','EXPENSE','TRANSFER_IN','TRANSFER_OUT','REVERSAL')",
            name="cash_movement_type_valid",
        ),
        CheckConstraint("direction in ('IN','OUT')", name="cash_movement_direction_valid"),
        CheckConstraint("amount > 0", name="cash_movement_amount_positive"),
        UniqueConstraint("idempotency_key", name="uq_cash_movements_idempotency"),
        Index("ix_cash_movements_session_date", "cash_session_id", "effective_date"),
    )
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    cash_session_id: Mapped[UUID] = mapped_column(ForeignKey("cash_sessions.id", ondelete="RESTRICT"), nullable=False)
    cash_account_id: Mapped[UUID] = mapped_column(ForeignKey("cash_accounts.id", ondelete="RESTRICT"), nullable=False)
    movement_type: Mapped[str] = mapped_column(String(16), nullable=False)
    direction: Mapped[str] = mapped_column(String(3), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    payment_method_code: Mapped[str | None] = mapped_column(ForeignKey("payment_methods.code", ondelete="RESTRICT"))
    source_type: Mapped[str | None] = mapped_column(String(64))
    source_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    reason: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'CONFIRMED'"))
    reversal_of_id: Mapped[UUID | None] = mapped_column(ForeignKey("cash_movements.id", ondelete="RESTRICT"))
    actor_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class CashTransfer(Base):
    __tablename__ = "cash_transfers"
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    source_movement_id: Mapped[UUID] = mapped_column(
        ForeignKey("cash_movements.id", ondelete="RESTRICT"), nullable=False
    )
    destination_movement_id: Mapped[UUID] = mapped_column(
        ForeignKey("cash_movements.id", ondelete="RESTRICT"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    transfer_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500))
