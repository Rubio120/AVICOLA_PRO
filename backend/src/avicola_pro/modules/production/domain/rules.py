from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

QUANTITY_SCALE = Decimal("0.0000")


def _quantity(value: Decimal) -> Decimal:
    return value.quantize(QUANTITY_SCALE, rounding=ROUND_HALF_UP)


def apply_bird_delta(current: Decimal, delta: Decimal) -> Decimal:
    result = _quantity(current + delta)
    if result < 0:
        raise ValueError("live bird balance cannot be negative")
    return result


def ensure_house_capacity(existing: Decimal, requested: Decimal, capacity: int) -> None:
    if existing + requested > Decimal(capacity):
        raise ValueError("house capacity exceeded")


def ensure_zero_balance_for_close(balance: Decimal, authorized_adjustment: bool) -> None:
    if balance != 0 and not authorized_adjustment:
        raise ValueError("flock balance must be zero before closing")
