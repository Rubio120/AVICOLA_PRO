from decimal import Decimal


class CashConflictError(ValueError):
    pass


def calculate_expected_balance(opening_balance: Decimal, signed_amounts: list[Decimal]) -> Decimal:
    return opening_balance + sum(signed_amounts, Decimal("0"))


def validate_movement(amount: Decimal, direction: str) -> None:
    if amount <= 0:
        raise CashConflictError("movement amount must be positive")
    if direction not in {"IN", "OUT"}:
        raise CashConflictError("movement direction is invalid")


def validate_available_balance(expected_balance: Decimal, amount: Decimal, direction: str) -> None:
    if direction == "OUT" and expected_balance - amount < 0:
        raise CashConflictError("cash balance cannot be negative")


def validate_reversal(session_status: str, reason: str) -> None:
    if session_status not in {"OPEN", "REOPENED"}:
        raise CashConflictError("cash session must be open for reversal")
    if not reason.strip():
        raise CashConflictError("reversal reason is required")
