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
            *[FakeResult(scalar=Decimal("10.00")) for _ in range(6)],
        ]
    )

    result = await reader.dashboard(session, ReportFilter(date_from=date(2026, 1, 1), date_to=date(2026, 1, 31)))

    assert result["sales_documents"] == 2
    assert result["sales_total"] == Decimal("100.00")
    assert result["cash_balance"] == Decimal("10.00")
    assert session.statements[0][1] is not None
    assert "date_from" in session.statements[0][1]


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
