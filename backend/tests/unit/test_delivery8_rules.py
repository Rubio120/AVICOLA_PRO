from decimal import Decimal

import pytest

from avicola_pro.modules.treasury.domain.rules import (
    CashConflictError,
    calculate_expected_balance,
    validate_available_balance,
    validate_movement,
    validate_reversal,
)


def test_expected_balance_sums_inflows_and_outflows() -> None:
    assert calculate_expected_balance(Decimal("100.00"), [Decimal("25"), Decimal("-10")]) == Decimal("115.00")


def test_movement_requires_positive_amount_and_known_direction() -> None:
    with pytest.raises(CashConflictError, match="positive"):
        validate_movement(Decimal("0"), "IN")
    with pytest.raises(CashConflictError, match="direction"):
        validate_movement(Decimal("10"), "SIDEWAYS")


def test_reversal_requires_open_or_reopened_session() -> None:
    validate_reversal("OPEN", "correction")
    validate_reversal("REOPENED", "correction")
    with pytest.raises(CashConflictError, match="open"):
        validate_reversal("CLOSED", "correction")
    with pytest.raises(CashConflictError, match="reason"):
        validate_reversal("OPEN", "")


def test_cash_cannot_go_negative() -> None:
    validate_available_balance(Decimal("10"), Decimal("10"), "OUT")
    with pytest.raises(CashConflictError, match="negative"):
        validate_available_balance(Decimal("10"), Decimal("10.01"), "OUT")
