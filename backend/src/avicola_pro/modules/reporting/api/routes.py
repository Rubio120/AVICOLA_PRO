# ruff: noqa: B008
from __future__ import annotations

from datetime import date
from importlib import import_module
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict

from avicola_pro.modules.reporting.domain.rules import ReportFilter, build_csv
from avicola_pro.shared.api.errors import ForbiddenError, UnauthorizedError


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


class ProfitabilityRow(BaseModel):
    id: UUID
    date: date
    customer: str
    revenue: str
    cost: str
    margin: str


class PageResponse(BaseModel):
    items: list[ProfitabilityRow]
    offset: int
    limit: int
    total: int


def build_reporting_router(
    authentication: Any, authorization: Any, database: Any, audit: Any, cookie_name: str
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

    def require(permission: str) -> Any:
        async def dependency(user: Any = Depends(current_user)) -> Any:
            if not await authorization.has_permission(user.id, permission):
                raise ForbiddenError(code="permission_denied", detail="Permission denied")
            return user

        return dependency

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

    def audit_export(session: Any, user: Any, request: Request, report_name: str) -> None:
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
                {"format": "csv"},
            ),
        )

    @router.get("/dashboard", response_model=DashboardResponse)
    async def dashboard(
        report_filters: ReportFilter = Depends(filters),
        _: Any = Depends(require("reports.profitability.read")),
    ) -> DashboardResponse:
        async with database.session_factory() as session:
            values = await reader.dashboard(session, report_filters)
            payload = {key: str(value) if key != "sales_documents" else value for key, value in values.items()}
            return DashboardResponse(**payload)

    @router.get("/profitability", response_model=PageResponse)
    async def profitability(
        report_filters: ReportFilter = Depends(filters),
        _: Any = Depends(require("reports.profitability.read")),
    ) -> PageResponse:
        async with database.session_factory() as session:
            items, total = await reader.profitability(session, report_filters)
            rows = [
                ProfitabilityRow(
                    **{key: str(value) if key not in {"id", "date"} else value for key, value in item.items()}
                )
                for item in items
            ]
            return PageResponse(items=rows, offset=report_filters.offset, limit=report_filters.limit, total=total)

    @router.get("/profitability.csv")
    async def profitability_csv(
        request: Request,
        report_filters: ReportFilter = Depends(filters),
        user: Any = Depends(require("reports.export")),
    ) -> Response:
        if report_filters.offset > 1000:
            raise ForbiddenError(code="export_limit_exceeded", detail="CSV export is limited to 1000 rows")
        export_filters = ReportFilter(
            date_from=report_filters.date_from,
            date_to=report_filters.date_to,
            offset=report_filters.offset,
            limit=min(report_filters.limit, report_filters.export_limit),
        )
        async with database.session_factory() as session, session.begin():
            items, _ = await reader.profitability(session, export_filters)
            csv_body = build_csv(
                ["id", "date", "customer", "revenue", "cost", "margin"],
                [[item[key] for key in ("id", "date", "customer", "revenue", "cost", "margin")] for item in items],
            )
            audit_export(session, user, request, "profitability")
        return Response(
            content=csv_body,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=profitability.csv"},
        )

    return router
