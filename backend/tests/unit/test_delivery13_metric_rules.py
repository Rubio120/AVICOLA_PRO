from collections.abc import Callable
from decimal import Decimal

import pytest

from avicola_pro.modules.reporting.domain.poultry_metrics import (
    average_ticket,
    feed_conversion,
    feed_cost_per_egg,
    feed_per_bird,
    posture_rate,
    stock_coverage_days,
)


def test_posture_reports_eggs_per_average_live_bird_without_assuming_a_percent() -> None:
    result = posture_rate(850, Decimal("1000"))

    assert result.value == Decimal("0.85")
    assert result.unit == "eggs/bird/period"
    assert result.available


def test_posture_is_unavailable_when_no_live_birds_are_observed() -> None:
    result = posture_rate(0, Decimal("0"))

    assert result.value is None
    assert not result.available
    assert result.reason == "average_live_birds_is_zero"


def test_feed_per_bird_uses_decimal_kg_per_bird_for_the_selected_period() -> None:
    result = feed_per_bird(Decimal("200"), Decimal("1000"))

    assert result.value == Decimal("0.2")
    assert result.unit == "kg/bird/period"


def test_feed_conversion_is_kg_per_dozen_eggs() -> None:
    result = feed_conversion(Decimal("200"), 12_000)

    assert result.value == Decimal("0.2")
    assert result.unit == "kg/dozen"


def test_feed_conversion_is_unavailable_without_eggs() -> None:
    result = feed_conversion(Decimal("200"), 0)

    assert result.value is None
    assert not result.available
    assert result.reason == "egg_count_is_zero"


def test_feed_cost_per_egg_uses_confirmed_cost_and_saleable_eggs() -> None:
    result = feed_cost_per_egg(Decimal("125000"), 25_000)

    assert result.value == Decimal("5")
    assert result.unit == "currency/egg"


def test_average_ticket_divides_net_sales_by_issued_invoices() -> None:
    result = average_ticket(Decimal("900000"), 30)

    assert result.value == Decimal("30000")
    assert result.unit == "currency/invoice"


def test_stock_coverage_uses_the_thirty_day_average_sales_rate() -> None:
    result = stock_coverage_days(Decimal("900"), 3_000)

    assert result.value == Decimal("9")
    assert result.unit == "days"


def test_stock_coverage_preserves_decimal_net_sales_after_credit_notes() -> None:
    result = stock_coverage_days(Decimal("900"), Decimal("85.5"))

    assert result.value == Decimal("900") * Decimal("30") / Decimal("85.5")
    assert result.available


@pytest.mark.parametrize(
    ("function", "arguments"),
    [
        (posture_rate, (Decimal("-1"), Decimal("2"))),
        (feed_per_bird, (Decimal("1"), Decimal("-1"))),
        (feed_conversion, (Decimal("-1"), 12)),
        (feed_cost_per_egg, (Decimal("-1"), 1)),
        (average_ticket, (Decimal("-1"), 1)),
        (stock_coverage_days, (Decimal("1"), -1)),
        (stock_coverage_days, (Decimal("1"), Decimal("-0.5"))),
    ],
)
def test_metric_rules_reject_negative_facts(function: Callable[..., object], arguments: tuple[object, ...]) -> None:
    with pytest.raises(ValueError, match="nonnegative"):
        function(*arguments)


@pytest.mark.parametrize(
    ("function", "arguments"),
    [
        (feed_conversion, (Decimal("1"), True)),
        (feed_cost_per_egg, (Decimal("1"), True)),
        (average_ticket, (Decimal("1"), True)),
    ],
)
def test_count_metrics_reject_booleans_as_counts(
    function: Callable[..., object], arguments: tuple[object, ...]
) -> None:
    with pytest.raises(ValueError, match="nonnegative integer"):
        function(*arguments)
