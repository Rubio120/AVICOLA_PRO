from decimal import Decimal

import pytest

from avicola_pro.modules.purchasing.domain.rules import (
    PurchaseConflictError,
    apply_payment,
    calculate_line_total,
    next_order_status,
)


def test_calculate_line_total_applies_discount_then_tax_with_money_rounding() -> None:
    assert calculate_line_total(Decimal("10"), Decimal("3"), Decimal("0.10"), Decimal("0.05")) == (
        Decimal("28.35"),
        Decimal("1.35"),
    )


def test_order_status_progresses_from_approved_to_partial_and_received() -> None:
    assert next_order_status("APPROVED", Decimal("2"), Decimal("5")) == "PARTIALLY_RECEIVED"
    assert next_order_status("PARTIALLY_RECEIVED", Decimal("5"), Decimal("5")) == "RECEIVED"


def test_payment_cannot_exceed_payment_or_account_balance() -> None:
    assert apply_payment(Decimal("100"), Decimal("60"), Decimal("100")) == Decimal("40")
    with pytest.raises(PurchaseConflictError, match="payment amount exceeds"):
        apply_payment(Decimal("20"), Decimal("15"), Decimal("10"))
    with pytest.raises(PurchaseConflictError, match="account balance"):
        apply_payment(Decimal("100"), Decimal("95"), Decimal("10"))


def test_purchase_rules_reject_invalid_progressions_and_payment_amount() -> None:
    assert next_order_status("APPROVED", Decimal("0"), Decimal("5")) == "APPROVED"
    with pytest.raises(PurchaseConflictError, match="must be approved"):
        next_order_status("DRAFT", Decimal("1"), Decimal("5"))
    with pytest.raises(PurchaseConflictError, match="exceeds ordered"):
        next_order_status("APPROVED", Decimal("6"), Decimal("5"))
    with pytest.raises(PurchaseConflictError, match="must be positive"):
        apply_payment(Decimal("0"), Decimal("0"), Decimal("10"))
