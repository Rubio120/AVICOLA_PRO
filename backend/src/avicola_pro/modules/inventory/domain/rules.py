from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, localcontext

QUANTITY_SCALE = Decimal("0.0001")
COST_SCALE = Decimal("0.000001")
MONEY_SCALE = Decimal("0.01")


class InventoryRuleError(ValueError):
    """Raised when an inventory invariant would be violated."""


@dataclass(frozen=True, slots=True)
class InboundResult:
    quantity: Decimal
    value: Decimal
    average_cost: Decimal


@dataclass(frozen=True, slots=True)
class OutboundResult:
    quantity: Decimal
    value: Decimal
    unit_cost: Decimal


def quantize_quantity(value: Decimal) -> Decimal:
    if value <= 0:
        raise InventoryRuleError("quantity must be positive")
    return value.quantize(QUANTITY_SCALE, rounding=ROUND_HALF_UP)


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_SCALE, rounding=ROUND_HALF_UP)


def _cost(value: Decimal) -> Decimal:
    return value.quantize(COST_SCALE, rounding=ROUND_HALF_UP)


def calculate_inbound(
    current_quantity: Decimal,
    current_value: Decimal,
    incoming_quantity: Decimal,
    incoming_unit_cost: Decimal,
) -> InboundResult:
    quantity = quantize_quantity(incoming_quantity)
    if current_quantity < 0 or current_value < 0 or incoming_unit_cost < 0:
        raise InventoryRuleError("inventory values cannot be negative")
    with localcontext() as context:
        context.prec = 40
        new_quantity = current_quantity + quantity
        new_value = _money(current_value + (quantity * incoming_unit_cost))
        average = _cost(new_value / new_quantity) if new_quantity else Decimal("0")
    return InboundResult(new_quantity.quantize(QUANTITY_SCALE), new_value, average)


def calculate_outbound(
    current_quantity: Decimal,
    current_value: Decimal,
    outgoing_quantity: Decimal,
) -> OutboundResult:
    quantity = quantize_quantity(outgoing_quantity)
    if current_quantity < 0 or current_value < 0:
        raise InventoryRuleError("inventory values cannot be negative")
    if quantity > current_quantity:
        raise InventoryRuleError("insufficient stock")
    with localcontext() as context:
        context.prec = 40
        average = _cost(current_value / current_quantity) if current_quantity else Decimal("0")
        remaining_quantity = (current_quantity - quantity).quantize(QUANTITY_SCALE)
        remaining_value = _money(current_value - (quantity * average))
        if remaining_quantity == 0:
            remaining_value = Decimal("0.00")
    return OutboundResult(remaining_quantity, remaining_value, average)
