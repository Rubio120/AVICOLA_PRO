from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")


def normalize_code(value: str) -> str:
    code = value.strip().casefold()
    if not _CODE_PATTERN.fullmatch(code):
        raise ValueError("code must contain 2-64 lowercase letters, numbers, '_' or '-'")
    return code


def ensure_base_currency(value: str) -> str:
    currency = value.strip().upper()
    if currency != "PYG":
        raise ValueError("V1 only supports PYG as transaction currency")
    return currency


def validate_tax_rate(value: Decimal) -> Decimal:
    rate = Decimal(value)
    if rate < Decimal("0") or rate > Decimal("1"):
        raise ValueError("tax rate must be between 0 and 1")
    return rate.quantize(Decimal("0.000001"))


def validate_validity_range(valid_from: date, valid_to: date | None) -> None:
    """Ensure a versioned master record has a forward or open validity range."""

    if valid_to is not None and valid_to < valid_from:
        raise ValueError("valid_to must not precede valid_from")


def format_sequence_number(prefix: str, number: int, padding: int) -> str:
    """Format a consumed sequence value without allowing zero or negative numbers."""

    if number < 1:
        raise ValueError("sequence number must be positive")
    if padding < 1 or padding > 18:
        raise ValueError("sequence padding must be between 1 and 18")
    return f"{prefix}{number:0{padding}d}"
