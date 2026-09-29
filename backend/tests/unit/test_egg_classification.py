from __future__ import annotations

from uuid import uuid4

import pytest

from avicola_pro.modules.production.domain.egg_classification import validate_egg_allocations


def test_validates_categories_sum_exactly_to_the_daily_production_count() -> None:
    category_a, category_b = uuid4(), uuid4()
    validate_egg_allocations(17, [(category_a, 12), (category_b, 5)])


def test_accepts_zero_production_without_inventory_allocations() -> None:
    validate_egg_allocations(0, [])


def test_rejects_incomplete_or_excessive_classification() -> None:
    category_id = uuid4()
    with pytest.raises(ValueError, match="must equal"):
        validate_egg_allocations(17, [(category_id, 12)])
    with pytest.raises(ValueError, match="must equal"):
        validate_egg_allocations(17, [(category_id, 18)])


def test_rejects_duplicate_category_allocations() -> None:
    category_id = uuid4()
    with pytest.raises(ValueError, match="duplicate category"):
        validate_egg_allocations(17, [(category_id, 12), (category_id, 5)])


@pytest.mark.parametrize("count", [-1, 1_000_000_000_000_000_000, True])
def test_rejects_invalid_allocation_counts(count: int) -> None:
    with pytest.raises(ValueError, match="egg count"):
        validate_egg_allocations(count, [(uuid4(), count)])
