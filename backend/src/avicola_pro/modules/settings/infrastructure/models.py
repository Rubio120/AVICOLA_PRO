from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from avicola_pro.shared.infrastructure.models import Base


class CompanyProfile(Base):
    __tablename__ = "company_profile"
    __table_args__ = (
        CheckConstraint("singleton_key = 1", name="singleton_key_one"),
        CheckConstraint("base_currency = 'PYG'", name="base_currency_pyg"),
    )
    singleton_key: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    legal_name: Mapped[str] = mapped_column(String(200), nullable=False)
    tax_id: Mapped[str] = mapped_column(String(32), nullable=False)
    trade_name: Mapped[str | None] = mapped_column(String(200))
    address: Mapped[str | None] = mapped_column(String(500))
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default=text("'PYG'"))
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, server_default=text("'America/Asuncion'"))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class Currency(Base):
    __tablename__ = "currencies"
    code: Mapped[str] = mapped_column(String(3), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    decimals: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("2"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class PaymentMethod(Base):
    __tablename__ = "payment_methods"
    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class UnitOfMeasure(Base):
    __tablename__ = "units_of_measure"
    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    precision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("4"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class TaxRate(Base):
    __tablename__ = "tax_rates"
    __table_args__ = (
        UniqueConstraint("code", "valid_from", name="uq_tax_rates_code_valid_from"),
        CheckConstraint("rate >= 0 and rate <= 1", name="rate_range"),
        CheckConstraint("valid_to is null or valid_to >= valid_from", name="validity_order"),
    )
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class Stamp(Base):
    __tablename__ = "stamps"
    __table_args__ = (UniqueConstraint("establishment", "number", name="uq_stamps_establishment_number"),)
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    establishment: Mapped[str] = mapped_column(String(10), nullable=False)
    number: Mapped[str] = mapped_column(String(32), nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class DocumentSequence(Base):
    __tablename__ = "document_sequences"
    __table_args__ = (UniqueConstraint("document_type", "series", name="uq_document_sequences_type_series"),)
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    document_type: Mapped[str] = mapped_column(String(64), nullable=False)
    series: Mapped[str] = mapped_column(String(16), nullable=False)
    prefix: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("''"))
    current_number: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    padding: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("7"))
    stamp_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("stamps.id", ondelete="RESTRICT")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
