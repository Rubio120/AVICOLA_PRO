from decimal import Decimal

import pytest

from avicola_pro.modules.costing.domain.rules import (
    CostingConflictError,
    allocate_by_weight,
    calculate_cost_per_bird,
    eligible_source_status,
    ensure_run_transition,
)


def test_allocate_by_weight_conserves_cost_and_assigns_rounding_residual() -> None:
    allocations = allocate_by_weight(Decimal("100.00"), {"a": Decimal("1"), "b": Decimal("2")})
    assert allocations == {"a": Decimal("33.33"), "b": Decimal("66.67")}
    assert sum(allocations.values(), Decimal("0")) == Decimal("100.00")


def test_allocate_by_weight_rejects_empty_or_negative_weights() -> None:
    with pytest.raises(CostingConflictError, match="weight"):
        allocate_by_weight(Decimal("10"), {"a": Decimal("0")})
    with pytest.raises(CostingConflictError, match="non-negative"):
        allocate_by_weight(Decimal("-1"), {"a": Decimal("1")})


def test_cost_per_bird_explicitly_handles_zero_birds() -> None:
    assert calculate_cost_per_bird(Decimal("100"), Decimal("0")) is None
    assert calculate_cost_per_bird(Decimal("100"), Decimal("4")) == Decimal("25.00")


def test_run_state_machine_is_strict_and_closed_runs_are_immutable() -> None:
    ensure_run_transition("DRAFT", "CALCULATING")
    ensure_run_transition("CALCULATING", "CLOSED")
    with pytest.raises(CostingConflictError, match="transition"):
        ensure_run_transition("CLOSED", "CALCULATING")


def test_only_confirmed_source_status_is_eligible() -> None:
    assert eligible_source_status("CONFIRMED")
    assert not eligible_source_status("DRAFT")
    assert not eligible_source_status("REVERSED")
