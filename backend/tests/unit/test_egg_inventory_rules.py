from __future__ import annotations

from decimal import Decimal

import pytest

from avicola_pro.modules.inventory.domain.egg_units import (
    from_base_egg_units,
    to_base_egg_units,
    validate_egg_category_saleable,
)


def test_to_base_egg_units_converts_an_explicit_synthetic_package_size() -> None:
    assert to_base_egg_units(Decimal("2"), units_per_package=12) == 24


def test_to_base_egg_units_allows_fractional_presentation_only_when_result_is_whole_eggs() -> None:
    assert to_base_egg_units(Decimal("0.5"), units_per_package=12) == 6


def test_to_base_egg_units_rejects_fractional_resulting_egg_units() -> None:
    with pytest.raises(ValueError, match="whole eggs"):
        to_base_egg_units(Decimal("0.1"), units_per_package=12)


@pytest.mark.parametrize("factor", [0, -1, True])
def test_to_base_egg_units_rejects_invalid_conversion_factor(factor: int) -> None:
    with pytest.raises(ValueError, match="conversion factor"):
        to_base_egg_units(Decimal("1"), units_per_package=factor)


def test_to_base_egg_units_rejects_nonpositive_or_nonfinite_quantity() -> None:
    for quantity in (Decimal("0"), Decimal("-1"), Decimal("NaN"), Decimal("Infinity")):
        with pytest.raises(ValueError, match="quantity"):
            to_base_egg_units(quantity, units_per_package=12)


def test_to_base_egg_units_rejects_integer_overflow() -> None:
    with pytest.raises(ValueError, match="supported range"):
        to_base_egg_units(Decimal("1000000000000000000"), units_per_package=12)


def test_from_base_egg_units_returns_complete_packages_and_remainder() -> None:
    assert from_base_egg_units(29, units_per_package=12) == (2, 5)


@pytest.mark.parametrize("egg_count", [-1, 1_000_000_000_000_000_000, True])
def test_from_base_egg_units_rejects_invalid_base_count(egg_count: int) -> None:
    with pytest.raises(ValueError, match="egg count"):
        from_base_egg_units(egg_count, units_per_package=12)


def test_egg_category_is_sellable_only_when_explicitly_active_and_saleable() -> None:
    validate_egg_category_saleable(is_active=True, is_saleable=True)
    with pytest.raises(ValueError, match="not configured for sale"):
        validate_egg_category_saleable(is_active=True, is_saleable=False)
    with pytest.raises(ValueError, match="inactive"):
        validate_egg_category_saleable(is_active=False, is_saleable=True)
