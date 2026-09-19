from decimal import Decimal

import pytest

from avicola_pro.modules.production.domain.rules import (
    apply_bird_delta,
    ensure_house_capacity,
    ensure_zero_balance_for_close,
)


def test_apply_bird_delta_rejects_negative_live_balance() -> None:
    with pytest.raises(ValueError, match="negative"):
        apply_bird_delta(Decimal("3"), Decimal("-4"))


def test_apply_bird_delta_quantizes_live_balance() -> None:
    assert apply_bird_delta(Decimal("10"), Decimal("-2.5")) == Decimal("7.5000")


def test_house_capacity_is_checked_against_existing_assignments() -> None:
    ensure_house_capacity(Decimal("80"), Decimal("20"), 100)
    with pytest.raises(ValueError, match="capacity"):
        ensure_house_capacity(Decimal("80"), Decimal("21"), 100)


def test_close_requires_zero_or_authorized_adjustment() -> None:
    with pytest.raises(ValueError, match="zero"):
        ensure_zero_balance_for_close(Decimal("1"), False)
    ensure_zero_balance_for_close(Decimal("1"), True)
