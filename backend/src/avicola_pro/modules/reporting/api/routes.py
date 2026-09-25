# ruff: noqa: B008
from __future__ import annotations

from datetime import date, timedelta
from importlib import import_module
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict

from avicola_pro.modules.reporting.domain.rules import ReportFilter, build_csv, build_xlsx
from avicola_pro.shared.api.errors import ForbiddenError, UnauthorizedError


class MetricResponse(BaseModel):
    value: str | None
    unit: str
    available: bool
    reason: str | None
    period: MetricPeriod


class MetricPeriod(BaseModel):
    date_from: date | None
    date_to: date | None


class DailyMortalityResponse(BaseModel):
    occurred_on: date
    deaths: str


class ActiveFlockAgeResponse(BaseModel):
    flock_code: str
    days_since_entry: int
    as_of: date


class FeedConsumptionByHouseResponse(BaseModel):
    house_code: str | None
    unit_code: str
    quantity: str


class DashboardResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sales_documents: int
    sales_total: str
    inventory_value: str
    live_birds: str
    accounts_payable: str
    accounts_receivable: str
    cash_balance: str
    confirmed_costs: str
    poultry_metrics: dict[str, MetricResponse]
    daily_mortality: list[DailyMortalityResponse]
    active_flock_ages: list[ActiveFlockAgeResponse]
    feed_consumption_by_house: list[FeedConsumptionByHouseResponse]


class ProfitabilityRow(BaseModel):
    id: UUID
    date: date
    document_type: str
    customer: str
    revenue: str
    cost: str | None
    margin: str | None


class PageResponse(BaseModel):
    items: list[ProfitabilityRow]
    offset: int
    limit: int
    total: int


class CommercialSalesRow(BaseModel):
    channel: str
    invoices: int
    credit_notes: int
    customers_with_documents: int
    net_revenue: str


def dashboard_payload(values: dict[str, Any], *, period: MetricPeriod) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    coverage_to = period.date_to or date.today()
    for key, value in values.items():
        if key == "poultry_metrics":
            payload[key] = {
                name: {
                    "value": None if metric.value is None else str(metric.value),
                    "unit": metric.unit,
                    "available": metric.available,
                    "reason": metric.reason,
                    "period": (
                        MetricPeriod(
                            date_from=coverage_to - timedelta(days=29),
                            date_to=coverage_to,
                        ).model_dump()
                        if name == "stock_coverage"
                        else period.model_dump()
                    ),
                }
                for name, metric in value.items()
            }
        elif key == "sales_documents":
            payload[key] = value
        elif key in {"daily_mortality", "active_flock_ages", "feed_consumption_by_house"}:
            if key == "daily_mortality":
                payload[key] = [{**item, "deaths": str(item["deaths"])} for item in value]
            elif key == "feed_consumption_by_house":
                payload[key] = [{**item, "quantity": str(item["quantity"])} for item in value]
            else:
                payload[key] = value
        else:
            payload[key] = str(value)
    return payload


def build_reporting_router(
    authentication: Any,
    authorization: Any,
    database: Any,
    audit: Any,
    cookie_name: str,
    *,
    security_events: Any,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/reports", tags=["reports"])
    reader = import_module("avicola_pro.modules.reporting.infrastructure.reader")
    _auth = import_module("avicola_pro.modules.identity.api.auth")
    _identity = import_module("avicola_pro.modules.identity.application.authentication")

    async def current_user(request: Request, token: str | None = Cookie(default=None, alias=cookie_name)) -> Any:
        try:
            return await authentication.current_session(token, _auth.request_context(request))
        except (_identity.InvalidSessionError, _identity.SessionReuseError):
            raise UnauthorizedError(code="authentication_required", detail="Authentication required") from None

    require = _auth.build_permission_dependency(
        current_user=current_user,
        authorization=authorization,
        security_events=security_events,
        resource_type="reporting",
    )

    def filters(
        date_from: date | None = Query(default=None),
        date_to: date | None = Query(default=None),
        offset: int = Query(default=0, ge=0, le=100_000),
        limit: int = Query(default=50, ge=1, le=100),
    ) -> ReportFilter:
        try:
            return ReportFilter(date_from=date_from, date_to=date_to, offset=offset, limit=limit)
        except ValueError as exc:
            from fastapi import HTTPException

            raise HTTPException(status_code=422, detail=str(exc)) from exc

    def channel_filters(
        date_from: date | None = Query(default=None),
        date_to: date | None = Query(default=None),
        channel: str | None = Query(default=None, pattern=r"^(WHOLESALE|RETAIL)$"),
        offset: int = Query(default=0, ge=0, le=100_000),
        limit: int = Query(default=50, ge=1, le=100),
    ) -> ReportFilter:
        try:
            return ReportFilter(
                date_from=date_from,
                date_to=date_to,
                channel=channel,
                offset=offset,
                limit=limit,
            )
        except ValueError as exc:
            from fastapi import HTTPException

            raise HTTPException(status_code=422, detail=str(exc)) from exc

    def export_filters(
        date_from: date | None = Query(default=None),
        date_to: date | None = Query(default=None),
        channel: str | None = Query(default=None, pattern=r"^(WHOLESALE|RETAIL)$"),
        offset: int = Query(default=0, ge=0, le=1000),
        limit: int = Query(default=1000, ge=1, le=1000),
    ) -> ReportFilter:
        try:
            return ReportFilter(
                date_from=date_from,
                date_to=date_to,
                channel=channel,
                offset=offset,
                limit=limit,
            )
        except ValueError as exc:
            from fastapi import HTTPException

            raise HTTPException(status_code=422, detail=str(exc)) from exc

    def audit_export(session: Any, user: Any, request: Request, report_name: str, export_format: str = "csv") -> None:
        record = import_module("avicola_pro.modules.audit.application.writer").AuditRecord
        audit.add(
            session,
            record(
                user.id,
                user.username,
                "report.export",
                "report",
                report_name,
                UUID(request.state.correlation_id),
                request.client.host if request.client else None,
                request.headers.get("user-agent"),
                None,
                {"format": export_format},
            ),
        )

    @router.get("/dashboard", response_model=DashboardResponse)
    async def dashboard(
        report_filters: ReportFilter = Depends(channel_filters),
        _: Any = Depends(require("reports.profitability.read")),
    ) -> DashboardResponse:
        async with database.session_factory() as session:
            values = await reader.dashboard(session, report_filters)
            period = MetricPeriod(date_from=report_filters.date_from, date_to=report_filters.date_to)
            return DashboardResponse(**dashboard_payload(values, period=period))

    @router.get("/profitability", response_model=PageResponse)
    async def profitability(
        report_filters: ReportFilter = Depends(channel_filters),
        _: Any = Depends(require("reports.profitability.read")),
    ) -> PageResponse:
        async with database.session_factory() as session:
            items, total = await reader.profitability(session, report_filters)
            rows = [
                ProfitabilityRow(
                    **{
                        key: value if key in {"id", "date"} or value is None else str(value)
                        for key, value in item.items()
                    }
                )
                for item in items
            ]
            return PageResponse(items=rows, offset=report_filters.offset, limit=report_filters.limit, total=total)

    @router.get("/commercial", response_model=list[CommercialSalesRow])
    async def commercial_sales(
        date_from: date | None = Query(default=None),
        date_to: date | None = Query(default=None),
        channel: str | None = Query(default=None, pattern=r"^(WHOLESALE|RETAIL)$"),
        _: Any = Depends(require("reports.profitability.read")),
    ) -> list[CommercialSalesRow]:
        if date_from and date_to and date_from > date_to:
            from fastapi import HTTPException

            raise HTTPException(status_code=422, detail="date_from cannot be after date_to")
        async with database.session_factory() as session:
            rows = await reader.commercial_sales(session, date_from, date_to, channel)
        return [CommercialSalesRow(**{**item, "net_revenue": str(item["net_revenue"])}) for item in rows]

    @router.get("/profitability.csv")
    async def profitability_csv(
        request: Request,
        report_filters: ReportFilter = Depends(export_filters),
        user: Any = Depends(require("reports.export")),
    ) -> Response:
        if report_filters.offset + report_filters.limit > report_filters.export_limit:
            raise ForbiddenError(code="export_limit_exceeded", detail="CSV export is limited to 1000 rows")
        export_filters = ReportFilter(
            date_from=report_filters.date_from,
            date_to=report_filters.date_to,
            channel=report_filters.channel,
            offset=report_filters.offset,
            limit=report_filters.limit,
        )
        async with database.session_factory() as session, session.begin():
            items, _ = await reader.profitability(session, export_filters)
            csv_body = build_csv(
                ["id", "date", "document_type", "channel", "customer", "revenue"],
                [
                    [item[key] for key in ("id", "date", "document_type", "channel", "customer", "revenue")]
                    for item in items
                ],
            )
            audit_export(session, user, request, "profitability")
        return Response(
            content=csv_body,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=profitability.csv"},
        )

    @router.get("/profitability.xlsx")
    async def profitability_xlsx(
        request: Request,
        report_filters: ReportFilter = Depends(export_filters),
        user: Any = Depends(require("reports.export")),
    ) -> Response:
        if report_filters.offset + report_filters.limit > report_filters.export_limit:
            raise ForbiddenError(code="export_limit_exceeded", detail="Excel export is limited to 1000 rows")
        export_filters = ReportFilter(
            date_from=report_filters.date_from,
            date_to=report_filters.date_to,
            channel=report_filters.channel,
            offset=report_filters.offset,
            limit=report_filters.limit,
        )
        async with database.session_factory() as session, session.begin():
            items, _ = await reader.profitability(session, export_filters)
            workbook = build_xlsx(
                ["id", "date", "document_type", "channel", "customer", "revenue"],
                [
                    [item[key] for key in ("id", "date", "document_type", "channel", "customer", "revenue")]
                    for item in items
                ],
            )
            audit_export(session, user, request, "profitability", "xlsx")
        return Response(
            content=workbook,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=profitability.xlsx"},
        )

    return router

