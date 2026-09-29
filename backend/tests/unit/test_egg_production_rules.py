from __future__ import annotations

import pytest

from avicola_pro.modules.production.domain.egg_rules import validate_egg_count


@pytest.mark.parametrize("count", [0, 1, 12, 999_999_999_999_999_999])
def test_validate_egg_count_accepts_nonnegative_whole_egg_counts(count: int) -> None:
    validate_egg_count(count)


@pytest.mark.parametrize("count", [-1, 1_000_000_000_000_000_000, True])
def test_validate_egg_count_rejects_invalid_counts(count: int) -> None:
    with pytest.raises(ValueError, match="egg count"):
        validate_egg_count(count)
