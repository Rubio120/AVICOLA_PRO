from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


class CostingConflictError(ValueError):
    """Raised when a costing invariant would be violated."""


CENT = Decimal("0.01")


def allocate_by_weight(total: Decimal, weights: dict[str, Decimal]) -> dict[str, Decimal]:
    if total < 0:
        raise CostingConflictError("total cost must be non-negative")
    if not weights or any(weight <= 0 for weight in weights.values()):
        raise CostingConflictError("allocation weight must be positive")
    weight_total = sum(weights.values(), Decimal("0"))
    result: dict[str, Decimal] = {}
    keys = list(weights)
    for key in keys[:-1]:
        result[key] = (total * weights[key] / weight_total).quantize(CENT, rounding=ROUND_HALF_UP)
    result[keys[-1]] = total - sum(result.values(), Decimal("0"))
    return result


def calculate_cost_per_bird(total: Decimal, birds: Decimal) -> Decimal | None:
    if total < 0 or birds < 0:
        raise CostingConflictError("cost and birds must be non-negative")
    if birds == 0:
        return None
    return (total / birds).quantize(CENT, rounding=ROUND_HALF_UP)


def ensure_run_transition(current: str, target: str) -> None:
    if (current, target) not in {("DRAFT", "CALCULATING"), ("CALCULATING", "CLOSED")}:
        raise CostingConflictError("invalid costing run transition")


def eligible_source_status(status: str) -> bool:
    return status == "CONFIRMED"
