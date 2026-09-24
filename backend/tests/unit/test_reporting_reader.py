from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from avicola_pro.modules.reporting.domain.rules import ReportFilter, build_xlsx
from avicola_pro.modules.reporting.infrastructure import reader


class FakeResult:
    def __init__(
        self,
        *,
        row: Any = None,
        scalar: Any = None,
        mappings: list[dict[str, Any]] | None = None,
    ):
        self._row = row
        self._scalar = scalar
        self._mappings = mappings or []

    def one(self) -> Any:
        return self._row

    def scalar_one(self) -> Any:
        return self._scalar

    def mappings(self) -> list[dict[str, Any]]:
        return self._mappings

    def scalar(self) -> Any:
        return self._scalar


class FakeSession:
    def __init__(self, results: list[FakeResult]):
        self.results = iter(results)
        self.statements: list[tuple[object, dict[str, Any] | None]] = []

    async def execute(self, statement: object, params: dict[str, Any] | None = None) -> FakeResult:
        self.statements.append((statement, params))
        return next(self.results)


@pytest.mark.asyncio
async def test_dashboard_aggregates_confirmed_operational_facts() -> None:
    session = FakeSession(
        [
            FakeResult(row=SimpleNamespace(count=2, total=Decimal("100.00"))),
            FakeResult(
                row=SimpleNamespace(
                    egg_count=12_000,
                    average_live_birds=Decimal("1000"),
                    feed_kg=Decimal("200"),
                    feed_records=2,
                    feed_records_in_kg=2,
                    costed_feed_records=2,
                    confirmed_feed_cost=Decimal("125000"),
                    saleable_egg_count=25_000,
                    new_customer_count=1,
                    unassigned_invoice_count=0,
                )
            ),
            *[FakeResult(scalar=Decimal("10.00")) for _ in range(6)],
        ]
    )

    result = await reader.dashboard(session, ReportFilter(date_from=date(2026, 1, 1), date_to=date(2026, 1, 31)))

    assert result["sales_documents"] == 2
    assert result["sales_total"] == Decimal("100.00")
    assert result["cash_balance"] == Decimal("10.00")
    assert result["poultry_metrics"]["posture"].value == Decimal("12")
    assert result["poultry_metrics"]["feed_per_bird"].value == Decimal("0.2")
    assert result["poultry_metrics"]["feed_conversion"].value == Decimal("0.2")
    assert result["poultry_metrics"]["feed_cost_per_egg"].value == Decimal("5")
    assert session.statements[0][1] is not None
    assert "date_from" in session.statements[0][1]


@pytest.mark.asyncio
async def test_dashboard_marks_feed_metrics_unavailable_when_unit_is_not_kg() -> None:
    session = FakeSession(
        [
            FakeResult(row=SimpleNamespace(count=0, total=Decimal("0"))),
            FakeResult(
                row=SimpleNamespace(
                    egg_count=0,
                    average_live_birds=None,
                    feed_kg=Decimal("0"),
                    feed_records=1,
                    feed_records_in_kg=0,
                    costed_feed_records=0,
                    confirmed_feed_cost=Decimal("0"),
                    saleable_egg_count=0,
                    new_customer_count=0,
                    unassigned_invoice_count=0,
                )
            ),
            *[FakeResult(scalar=Decimal("0")) for _ in range(6)],
        ]
    )

    result = await reader.dashboard(session, ReportFilter())

    assert result["poultry_metrics"]["feed_per_bird"].available is False
    assert result["poultry_metrics"]["feed_per_bird"].reason == "feed_unit_not_kg_or_unconfirmed"


@pytest.mark.asyncio
async def test_dashboard_marks_metrics_unavailable_for_missing_birds_cost_and_customer_identity() -> None:
    session = FakeSession(
        [
            FakeResult(row=SimpleNamespace(count=0, total=Decimal("0"))),
            FakeResult(
                row=SimpleNamespace(
                    egg_count=0,
                    average_live_birds=None,
                    feed_kg=Decimal("20"),
                    feed_records=1,
                    feed_records_in_kg=1,
                    costed_feed_records=0,
                    confirmed_feed_cost=Decimal("0"),
                    saleable_egg_count=0,
                    new_customer_count=0,
                    unassigned_invoice_count=1,
                )
            ),
            *[FakeResult(scalar=Decimal("0")) for _ in range(6)],
        ]
    )

    result = await reader.dashboard(session, ReportFilter())
    metrics = result["poultry_metrics"]

    assert metrics["posture"].reason == "average_live_birds_missing"
    assert metrics["feed_per_bird"].reason == "average_live_birds_missing"
    assert metrics["feed_conversion"].reason == "egg_count_is_zero"
    assert metrics["feed_cost_per_egg"].reason == "feed_cost_unconfirmed"
    assert metrics["average_ticket"].reason == "issued_invoice_count_is_zero"
    assert metrics["new_customers"].reason == "customer_identity_missing"


@pytest.mark.asyncio
async def test_dashboard_marks_feed_unavailable_when_no_feed_records_exist() -> None:
    session = FakeSession(
        [
            FakeResult(row=SimpleNamespace(count=0, total=Decimal("0"))),
            FakeResult(
                row=SimpleNamespace(
                    egg_count=0,
                    average_live_birds=Decimal("0"),
                    feed_kg=Decimal("0"),
                    feed_records=0,
                    feed_records_in_kg=0,
                    costed_feed_records=0,
                    confirmed_feed_cost=Decimal("0"),
                    saleable_egg_count=0,
                    new_customer_count=0,
                    unassigned_invoice_count=0,
                )
            ),
            *[FakeResult(scalar=Decimal("0")) for _ in range(6)],
        ]
    )

    result = await reader.dashboard(session, ReportFilter())

    assert result["poultry_metrics"]["posture"].reason == "average_live_birds_is_zero"
    assert result["poultry_metrics"]["feed_per_bird"].reason == "feed_data_missing"
    assert result["poultry_metrics"]["feed_conversion"].reason == "feed_data_missing"
    assert result["poultry_metrics"]["feed_cost_per_egg"].reason == "feed_data_missing"


@pytest.mark.asyncio
async def test_profitability_returns_paged_issued_documents() -> None:
    document_id = uuid4()
    session = FakeSession(
        [
            FakeResult(scalar=3),
            FakeResult(
                mappings=[
                    {
                        "id": document_id,
                        "document_date": date(2026, 1, 2),
                        "document_type": "INVOICE",
                        "customer_name_snapshot": "Cliente sintético",
                        "net_total": Decimal("55.00"),
                    }
                ]
            ),
        ]
    )

    rows, total = await reader.profitability(session, ReportFilter(offset=1, limit=1))

    assert total == 3
    assert rows[0]["id"] == document_id
    assert rows[0]["document_type"] == "INVOICE"
    assert rows[0]["revenue"] == Decimal("55.00")
    assert rows[0]["cost"] is None
    assert rows[0]["margin"] is None
    assert session.statements[1][1] is not None
    assert session.statements[1][1]["offset"] == 1


@pytest.mark.asyncio
async def test_commercial_sales_separates_channels_and_nets_issued_credit_notes() -> None:
    session = FakeSession(
        [
            FakeResult(
                mappings=[
                    {
                        "channel": "WHOLESALE",
                        "invoices": 4,
                        "credit_notes": 1,
                        "customers_with_documents": 3,
                        "net_revenue": Decimal("850.00"),
                    }
                ]
            )
        ]
    )

    rows = await reader.commercial_sales(session, date(2026, 1, 1), date(2026, 1, 31), "WHOLESALE")

    assert rows[0]["channel"] == "WHOLESALE"
    assert rows[0]["net_revenue"] == Decimal("850.00")
    statement, params = session.statements[0]
    assert "CREDIT_NOTE" in str(statement)
    assert "ISSUED" in str(statement)
    assert params == {"date_from": date(2026, 1, 1), "date_to": date(2026, 1, 31), "channel": "WHOLESALE"}


def test_xlsx_is_open_xml_and_never_turns_user_strings_into_formulas() -> None:
    import io
    from zipfile import ZipFile

    workbook = build_xlsx(
        ["customer", "amount"],
        [["=1+1", Decimal("12.50")]],
    )

    with ZipFile(io.BytesIO(workbook)) as archive:
        assert {"[Content_Types].xml", "xl/workbook.xml", "xl/worksheets/sheet1.xml"} <= set(archive.namelist())
        worksheet = archive.read("xl/worksheets/sheet1.xml")
    assert b't="inlineStr"' in worksheet
    assert b"=1+1" in worksheet
    assert b"12.50" in worksheet
    assert b"<f>" not in worksheet
