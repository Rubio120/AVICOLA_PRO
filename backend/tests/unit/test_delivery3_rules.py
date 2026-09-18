from decimal import Decimal

import pytest

from avicola_pro.modules.settings.domain.rules import (
    ensure_base_currency,
    format_sequence_number,
    normalize_code,
    validate_tax_rate,
    validate_validity_range,
)


def test_normalize_code_is_stable_and_rejects_invalid_values() -> None:
    assert normalize_code("  AbC-01 ") == "abc-01"
    with pytest.raises(ValueError, match="code"):
        normalize_code("a")


def test_v1_accepts_only_pyg_for_transaction_currency() -> None:
    assert ensure_base_currency(" pyg ") == "PYG"
    with pytest.raises(ValueError, match="PYG"):
        ensure_base_currency("USD")


def test_tax_rates_are_decimal_fractions_between_zero_and_one() -> None:
    assert validate_tax_rate(Decimal("0.10")) == Decimal("0.10")
    with pytest.raises(ValueError, match="tax rate"):
        validate_tax_rate(Decimal("1.01"))


def test_validity_range_rejects_an_end_before_the_start() -> None:
    from datetime import date

    validate_validity_range(date(2026, 1, 1), date(2026, 1, 31))
    with pytest.raises(ValueError, match="valid_to"):
        validate_validity_range(date(2026, 2, 1), date(2026, 1, 31))


def test_sequence_number_is_padded_and_never_reuses_zero() -> None:
    assert format_sequence_number("FAC", 1, 7) == "FAC0000001"
    with pytest.raises(ValueError, match="positive"):
        format_sequence_number("FAC", 0, 7)
