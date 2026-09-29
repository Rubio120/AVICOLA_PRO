from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class MetricResult:
    value: Decimal | None
    unit: str
    available: bool
    reason: str | None = None


def _validate_nonnegative(value: Decimal, name: str) -> None:
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise ValueError(f"{name} must be finite and nonnegative")


def _ratio(
    numerator: Decimal,
    denominator: Decimal,
    *,
    unit: str,
    zero_reason: str,
    multiplier: Decimal = Decimal("1"),
) -> MetricResult:
    _validate_nonnegative(numerator, "numerator")
    _validate_nonnegative(denominator, "denominator")
    if denominator == 0:
        return MetricResult(value=None, unit=unit, available=False, reason=zero_reason)
    return MetricResult(value=(numerator / denominator) * multiplier, unit=unit, available=True)


def posture_rate(egg_count: int, average_live_birds: Decimal) -> MetricResult:
    if isinstance(egg_count, bool) or not isinstance(egg_count, int) or egg_count < 0:
        raise ValueError("egg_count must be a nonnegative integer")
    _validate_nonnegative(average_live_birds, "average_live_birds")
    return _ratio(
        Decimal(egg_count),
        average_live_birds,
        unit="eggs/bird/period",
        zero_reason="average_live_birds_is_zero",
    )


def feed_per_bird(feed_kg: Decimal, average_live_birds: Decimal) -> MetricResult:
    return _ratio(
        feed_kg,
        average_live_birds,
        unit="kg/bird/period",
        zero_reason="average_live_birds_is_zero",
    )


def feed_conversion(feed_kg: Decimal, egg_count: int) -> MetricResult:
    if isinstance(egg_count, bool) or not isinstance(egg_count, int) or egg_count < 0:
        raise ValueError("egg_count must be a nonnegative integer")
    return _ratio(
        feed_kg * Decimal("12"),
        Decimal(egg_count),
        unit="kg/dozen",
        zero_reason="egg_count_is_zero",
    )


def feed_cost_per_egg(confirmed_feed_cost: Decimal, saleable_egg_count: int) -> MetricResult:
    if isinstance(saleable_egg_count, bool) or not isinstance(saleable_egg_count, int) or saleable_egg_count < 0:
        raise ValueError("saleable_egg_count must be a nonnegative integer")
    return _ratio(
        confirmed_feed_cost,
        Decimal(saleable_egg_count),
        unit="currency/egg",
        zero_reason="saleable_egg_count_is_zero",
    )


def average_ticket(net_sales: Decimal, issued_invoice_count: int) -> MetricResult:
    if isinstance(issued_invoice_count, bool) or not isinstance(issued_invoice_count, int) or issued_invoice_count < 0:
        raise ValueError("issued_invoice_count must be a nonnegative integer")
    return _ratio(
        net_sales,
        Decimal(issued_invoice_count),
        unit="currency/invoice",
        zero_reason="issued_invoice_count_is_zero",
    )


def stock_coverage_days(saleable_stock: Decimal, sales_last_30_days: Decimal | int) -> MetricResult:
    if (
        isinstance(sales_last_30_days, bool)
        or not isinstance(sales_last_30_days, (Decimal, int))
        or not Decimal(sales_last_30_days).is_finite()
        or sales_last_30_days < 0
    ):
        raise ValueError("sales_last_30_days must be finite and nonnegative")
    return _ratio(
        saleable_stock * Decimal("30"),
        Decimal(sales_last_30_days),
        unit="days",
        zero_reason="sales_last_30_days_is_zero",
    )
