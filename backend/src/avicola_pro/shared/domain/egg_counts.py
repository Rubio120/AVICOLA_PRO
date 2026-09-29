from __future__ import annotations

MAX_EGG_COUNT = 999_999_999_999_999_999


def validate_egg_count(count: int) -> None:
    """Validate a count representable by the database egg-count columns."""
    if isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= MAX_EGG_COUNT:
        raise ValueError("egg count must be a nonnegative whole number within the supported range")
