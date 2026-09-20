from datetime import date
from decimal import Decimal

import pytest

from avicola_pro.modules.reporting.domain.rules import (
    ReportFilter,
    build_csv,
    confirmed_statuses,
)


def test_report_filter_rejects_unbounded_pages() -> None:
    with pytest.raises(ValueError):
        ReportFilter(offset=0, limit=101)


def test_report_filter_rejects_invalid_range_and_offset() -> None:
    with pytest.raises(ValueError):
        ReportFilter(offset=100_001)
    with pytest.raises(ValueError):
        ReportFilter(date_from=date(2026, 2, 1), date_to=date(2026, 1, 1))


def test_report_filter_preserves_date_range_and_caps_export() -> None:
    filters = ReportFilter(date_from=date(2026, 1, 1), date_to=date(2026, 1, 31), offset=10, limit=20)

    assert filters.date_from == date(2026, 1, 1)
    assert filters.date_to == date(2026, 1, 31)
    assert filters.export_limit == 1000


def test_confirmed_statuses_exclude_drafts_and_reversals() -> None:
    assert "ISSUED" in confirmed_statuses("sales")
    assert "DRAFT" not in confirmed_statuses("sales")
    assert "REVERSED" not in confirmed_statuses("sales")


def test_build_csv_serializes_decimal_and_newlines_safely() -> None:
    result = build_csv(
        ["metric", "amount"],
        [["revenue", Decimal("1234.50")], ["note", "line\nbreak"]],
    )

    assert result.startswith("metric,amount\r\n")
    assert '"line\nbreak"' in result
