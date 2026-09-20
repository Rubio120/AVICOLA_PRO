from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from avicola_pro.modules.reporting.domain.rules import ReportFilter
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
                        "customer_name_snapshot": "Cliente sintético",
                        "total": Decimal("55.00"),
                    }
                ]
            ),
        ]
    )

    rows, total = await reader.profitability(session, ReportFilter(offset=1, limit=1))

    assert total == 3
    assert rows[0]["id"] == document_id
    assert rows[0]["margin"] == Decimal("55.00")
    assert session.statements[1][1] is not None
    assert session.statements[1][1]["offset"] == 1
