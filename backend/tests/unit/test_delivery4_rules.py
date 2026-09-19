from decimal import Decimal

import pytest

from avicola_pro.modules.inventory.domain.rules import (
    InventoryRuleError,
    calculate_inbound,
    calculate_outbound,
    quantize_quantity,
)


def test_inbound_uses_moving_weighted_average_and_money_rounding() -> None:
    result = calculate_inbound(
        current_quantity=Decimal("10"),
        current_value=Decimal("100.00"),
        incoming_quantity=Decimal("10"),
        incoming_unit_cost=Decimal("20"),
    )

    assert result.quantity == Decimal("20.0000")
    assert result.value == Decimal("300.00")
    assert result.average_cost == Decimal("15.000000")


def test_outbound_uses_current_average_without_changing_remaining_average() -> None:
    result = calculate_outbound(
        current_quantity=Decimal("20"),
        current_value=Decimal("300.00"),
        outgoing_quantity=Decimal("10"),
    )

    assert result.quantity == Decimal("10.0000")
    assert result.value == Decimal("150.00")
    assert result.unit_cost == Decimal("15.000000")


def test_outbound_rejects_negative_stock() -> None:
    with pytest.raises(InventoryRuleError, match="insufficient stock"):
        calculate_outbound(Decimal("5"), Decimal("50"), Decimal("5.0001"))


def test_quantity_is_positive_and_limited_to_four_decimal_places() -> None:
    assert quantize_quantity(Decimal("1.23456")) == Decimal("1.2346")
    with pytest.raises(InventoryRuleError, match="positive"):
        quantize_quantity(Decimal("0"))
