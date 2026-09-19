from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


class PurchaseConflictError(ValueError):
    """Raised when a purchasing invariant would be violated."""


MONEY = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def calculate_line_total(
    unit_price: Decimal, quantity: Decimal, discount_rate: Decimal, tax_rate: Decimal
) -> tuple[Decimal, Decimal]:
    subtotal = money(unit_price * quantity)
    discount = money(subtotal * discount_rate)
    taxable = subtotal - discount
    tax = money(taxable * tax_rate)
    return money(taxable + tax), tax


def next_order_status(status: str, received: Decimal, ordered: Decimal) -> str:
    if status not in {"APPROVED", "PARTIALLY_RECEIVED"}:
        raise PurchaseConflictError("order must be approved before receiving")
    if received <= 0:
        return "APPROVED"
    if received < ordered:
        return "PARTIALLY_RECEIVED"
    if received == ordered:
        return "RECEIVED"
    raise PurchaseConflictError("received quantity exceeds ordered quantity")


def apply_payment(payment_amount: Decimal, allocated_amount: Decimal, account_balance: Decimal) -> Decimal:
    if payment_amount <= 0:
        raise PurchaseConflictError("payment amount must be positive")
    if allocated_amount > payment_amount:
        raise PurchaseConflictError("payment amount exceeds payment")
    if allocated_amount > account_balance:
        raise PurchaseConflictError("payment amount exceeds account balance")
    return money(account_balance - allocated_amount)
