from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, Integer, Numeric, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from avicola_pro.shared.infrastructure.models import Base


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        Index("ix_customers_name", "name"),
        UniqueConstraint("code", name="uq_customers_code"),
        CheckConstraint("credit_limit >= 0", name="credit_limit_nonnegative"),
        CheckConstraint("payment_term_days >= 0", name="customer_payment_term_nonnegative"),
    )
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    document_type: Mapped[str] = mapped_column(String(16), nullable=False)
    document_number: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    contacts: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    credit_limit: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, server_default=text("0"))
    payment_term_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class Supplier(Base):
    __tablename__ = "suppliers"
    __table_args__ = (
        Index("ix_suppliers_name", "name"),
        UniqueConstraint("code", name="uq_suppliers_code"),
        CheckConstraint("payment_term_days >= 0", name="supplier_payment_term_nonnegative"),
    )
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    document_type: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'RUC'"))
    document_number: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    contacts: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    payment_term_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
