from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.routing import APIRoute
from starlette.requests import Request

from avicola_pro.modules.reporting.api.routes import (
    DashboardResponse,
    MetricPeriod,
    build_reporting_router,
    dashboard_payload,
)
from avicola_pro.modules.reporting.domain.poultry_metrics import MetricResult
from avicola_pro.modules.reporting.domain.rules import ReportFilter
from avicola_pro.shared.api.errors import ForbiddenError


def test_dashboard_payload_preserves_counts_and_serializes_available_and_missing_metrics() -> None:
    period = MetricPeriod(date_from=date(2026, 1, 1), date_to=date(2026, 1, 31))
    payload = dashboard_payload(
        {
            "sales_documents": 4,
            "sales_total": Decimal("125.50"),
            "inventory_value": Decimal("50"),
            "live_birds": Decimal("1000"),
            "accounts_payable": Decimal("0"),
            "accounts_receivable": Decimal("0"),
            "cash_balance": Decimal("0"),
            "confirmed_costs": Decimal("125"),
            "daily_mortality": [{"occurred_on": date(2026, 1, 10), "deaths": Decimal("2.0")}],
            "active_flock_ages": [{"flock_code": "SYNTHETIC", "days_since_entry": 10, "as_of": date(2026, 1, 31)}],
            "feed_consumption_by_house": [
                {"house_code": None, "unit_code": "kg", "quantity": Decimal("2.50")}
            ],
            "poultry_metrics": {
                "posture": MetricResult(Decimal("0.9"), "eggs/bird/period", True),
                "feed_per_bird": MetricResult(None, "kg/bird/period", False, "feed_data_missing"),
                "stock_coverage": MetricResult(Decimal("10"), "days", True),
            },
        },
        period=period,
    )

    response = DashboardResponse(**payload)

    assert response.sales_documents == 4
    assert response.sales_total == "125.50"
    assert response.poultry_metrics["posture"].value == "0.9"
    assert response.poultry_metrics["feed_per_bird"].value is None
    assert response.poultry_metrics["feed_per_bird"].reason == "feed_data_missing"
    assert response.daily_mortality[0].deaths == "2.0"
    assert response.active_flock_ages[0].days_since_entry == 10
    assert response.feed_consumption_by_house[0].house_code is None
    assert response.feed_consumption_by_house[0].quantity == "2.50"
    assert response.poultry_metrics["posture"].period == period
    assert response.poultry_metrics["stock_coverage"].period == MetricPeriod(
        date_from=date(2026, 1, 2), date_to=date(2026, 1, 31)
    )


def test_dashboard_route_accepts_and_preserves_channel_filter() -> None:
    router = build_reporting_router(
        object(),
        object(),
        SimpleNamespace(session_factory=lambda: None),
        SimpleNamespace(add=lambda *_: None),
        "session",
        security_events=SimpleNamespace(write=lambda *_: None),
    )
    route = next(
        route for route in router.routes if isinstance(route, APIRoute) and route.path == "/api/v1/reports/dashboard"
    )
    channel_dependency = next(
        dependency for dependency in route.dependant.dependencies if dependency.call.__name__ == "channel_filters"
    )

    report_filter = channel_dependency.call(
        date_from=date(2026, 1, 1),
        date_to=date(2026, 1, 31),
        channel="WHOLESALE",
        offset=0,
        limit=50,
    )

    assert report_filter == ReportFilter(
        date_from=date(2026, 1, 1), date_to=date(2026, 1, 31), channel="WHOLESALE"
    )


@pytest.mark.asyncio
async def test_xlsx_export_uses_channel_filter_audits_and_enforces_row_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    from avicola_pro.modules.reporting.infrastructure import reader

    class Session:
        def begin(self):
            return self

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

    session = Session()
    audit_rows: list[object] = []
    database = SimpleNamespace(session_factory=lambda: session)
    router = build_reporting_router(
        object(),
        object(),
        database,
        SimpleNamespace(add=lambda _session, record: audit_rows.append(record)),
        "session",
        security_events=SimpleNamespace(write=lambda *_: None),
    )
    route = next(
        route
        for route in router.routes
        if isinstance(route, APIRoute) and route.path == "/api/v1/reports/profitability.xlsx"
    )
    seen_filters: list[ReportFilter] = []

    async def fake_profitability(_session: object, report_filters: ReportFilter) -> tuple[list[dict[str, object]], int]:
        seen_filters.append(report_filters)
        return [], 0

    monkeypatch.setattr(reader, "profitability", fake_profitability)
    correlation_id = uuid4()
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/reports/profitability.xlsx",
            "headers": [(b"user-agent", b"reporting-test")],
            "query_string": b"",
            "client": ("127.0.0.1", 1234),
        }
    )
    request.state.correlation_id = str(correlation_id)
    user = SimpleNamespace(id=uuid4(), username="reporter")
    report_filters = ReportFilter(
        date_from=date(2026, 1, 1),
        date_to=date(2026, 1, 31),
        channel="WHOLESALE",
        limit=1000,
    )

    response = await route.endpoint(request, report_filters, user)

    assert response.media_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert seen_filters == [report_filters]
    assert len(audit_rows) == 1
    assert audit_rows[0].action == "report.export"
    assert audit_rows[0].after_data == {"format": "xlsx"}

    with pytest.raises(ForbiddenError, match="1000 rows"):
        await route.endpoint(request, ReportFilter(offset=1, limit=1000), user)
    assert len(seen_filters) == 1
    assert len(audit_rows) == 1

