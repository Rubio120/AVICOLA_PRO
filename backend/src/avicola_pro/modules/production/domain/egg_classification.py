from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from avicola_pro.modules.production.domain.egg_rules import validate_egg_count


def validate_egg_allocations(total_egg_count: int, allocations: Sequence[tuple[UUID, int]]) -> None:
    """Ensure a production total is fully and uniquely allocated to configured categories."""

    validate_egg_count(total_egg_count)
    category_ids: set[UUID] = set()
    allocated_count = 0
    for category_id, egg_count in allocations:
        if category_id in category_ids:
            raise ValueError("egg classification contains a duplicate category")
        category_ids.add(category_id)
        validate_egg_count(egg_count)
        allocated_count += egg_count
    if allocated_count != total_egg_count:
        raise ValueError("egg category allocations must equal the production event count")
