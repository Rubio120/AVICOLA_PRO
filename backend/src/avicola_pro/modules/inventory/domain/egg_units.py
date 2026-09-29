from __future__ import annotations

from decimal import Decimal

from avicola_pro.shared.domain.egg_counts import MAX_EGG_COUNT, validate_egg_count


def _validate_conversion_factor(units_per_package: int) -> None:
    if (
        isinstance(units_per_package, bool)
        or not isinstance(units_per_package, int)
        or not 0 < units_per_package <= MAX_EGG_COUNT
    ):
        raise ValueError("conversion factor must be a positive whole number within the supported range")


def to_base_egg_units(quantity: Decimal, units_per_package: int) -> int:
    """Convert an explicitly configured presentation quantity to exact whole eggs."""

    _validate_conversion_factor(units_per_package)
    if not isinstance(quantity, Decimal) or not quantity.is_finite() or quantity <= 0:
        raise ValueError("quantity must be a positive finite decimal")
    egg_quantity = quantity * units_per_package
    if egg_quantity != egg_quantity.to_integral_value():
        raise ValueError("conversion must result in whole eggs")
    egg_count = int(egg_quantity)
    validate_egg_count(egg_count)
    return egg_count


def from_base_egg_units(egg_count: int, units_per_package: int) -> tuple[int, int]:
    """Return complete configured packages and remaining individual eggs."""

    _validate_conversion_factor(units_per_package)
    try:
        validate_egg_count(egg_count)
    except ValueError as exc:
        raise ValueError("egg count must be a nonnegative whole number within the supported range") from exc
    return divmod(egg_count, units_per_package)


def validate_egg_category_saleable(*, is_active: bool, is_saleable: bool) -> None:
    """Reject egg sales unless the configured category explicitly allows them."""

    if not is_active:
        raise ValueError("egg category is inactive")
    if not is_saleable:
        raise ValueError("egg category is not configured for sale")
