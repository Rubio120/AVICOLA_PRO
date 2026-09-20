# ruff: noqa: B008
from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import date
from decimal import Decimal
from importlib import import_module
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Cookie, Depends, Header, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from avicola_pro.modules.costing.application.service import costing_service
from avicola_pro.modules.costing.domain.rules import CostingConflictError
from avicola_pro.shared.api.errors import ForbiddenError, UnauthorizedError

_models = import_module("avicola_pro.modules.costing.infrastructure.models")
CostEvent: Any = _models.CostEvent
CostRun: Any = _models.CostRun
CostRunSnapshot: Any = _models.CostRunSnapshot
CostCenter: Any = _models.CostCenter


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class EventPayload(StrictModel):
    event_type: str = Field(min_length=1, max_length=32)
    source_type: str = Field(min_length=1, max_length=64)
    source_id: UUID
    effective_date: date
    amount: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    idempotency_key: str = Field(min_length=1, max_length=128)
    metadata: dict[str, object] = Field(default_factory=dict)


class CostCenterPayload(StrictModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=120)


class RunPayload(StrictModel):
    run_date: date


class TargetPayload(StrictModel):
    target_type: str = Field(min_length=1, max_length=32)
    target_id: UUID
    weight: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    quantity: Decimal = Field(ge=0, max_digits=18, decimal_places=4)


class CalculatePayload(StrictModel):
    targets: list[TargetPayload] = Field(min_length=1, max_length=500)


class ProfitabilityFact(StrictModel):
    source_id: UUID
    status: str = Field(pattern=r"^(CONFIRMED|DRAFT|REVERSED)$")
    revenue: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    cost: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    notes: str | None = Field(default=None, max_length=500)


class ProfitabilityPayload(StrictModel):
    facts: list[ProfitabilityFact] = Field(min_length=1, max_length=500)


class ReversalPayload(StrictModel):
    reason: str = Field(min_length=1, max_length=500)


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    run_date: date
    version: int
    status: str


class SnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    cost_run_id: UUID
    target_type: str
    target_id: UUID
    total_cost: Decimal
    quantity: Decimal
    cost_per_unit: Decimal | None


def build_costing_router(
    authentication: Any, authorization: Any, database: Any, audit: Any, cookie_name: str
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/costing", tags=["costing"])
    _auth = import_module("avicola_pro.modules.identity.api.auth")
    _identity = import_module("avicola_pro.modules.identity.application.authentication")

    async def current_user(request: Request, token: str | None = Cookie(default=None, alias=cookie_name)) -> Any:
        try:
            return await authentication.current_session(token, _auth.request_context(request))
        except (_identity.InvalidSessionError, _identity.SessionReuseError):
            raise UnauthorizedError(code="authentication_required", detail="Authentication required") from None

    def require(permission: str) -> Callable[..., Awaitable[Any]]:
        async def dependency(user: Any = Depends(current_user)) -> Any:
            if not await authorization.has_permission(user.id, permission):
                raise ForbiddenError(code="permission_denied", detail="Permission denied")
            return user

        return dependency

    async def csrf_user(
        request: Request,
        _: Any = Depends(current_user),
        csrf: str | None = Header(default=None, alias=_auth.CSRF_HEADER),
    ) -> None:
        try:
            await authentication.validate_mutation(
                request.cookies.get(cookie_name), csrf, _auth.request_context(request)
            )
        except (_identity.InvalidSessionError, _identity.SessionReuseError):
            raise UnauthorizedError(code="authentication_required", detail="Authentication required") from None

    def audit_row(session: Any, user: Any, request: Request, action: str, resource_id: str) -> None:
        record = import_module("avicola_pro.modules.audit.application.writer").AuditRecord
        audit.add(
            session,
            record(
                user.id,
                user.username,
                action,
                "costing",
                resource_id,
                UUID(request.state.correlation_id),
                request.client.host if request.client else None,
                request.headers.get("user-agent"),
                None,
                None,
            ),
        )

    @router.post("/events", status_code=201)
    async def record_event(
        payload: EventPayload,
        request: Request,
        user: Any = Depends(require("costs.recalculate")),
        _: Any = Depends(csrf_user),
    ) -> dict[str, Any]:
        async with database.session_factory() as session, session.begin():
            try:
                event = await costing_service.record_event(session, payload.model_dump(), user.id)
            except CostingConflictError as exc:
                raise ForbiddenError(code="invalid_cost_event", detail=str(exc)) from None
            audit_row(session, user, request, "cost.event.record", str(event.id))
            return {"id": event.id, "status": event.status}

    @router.get("/centers")
    async def centers(_: Any = Depends(require("reports.profitability.read"))) -> list[dict[str, Any]]:
        async with database.session_factory() as session:
            rows = (
                await session.scalars(
                    select(CostCenter).where(CostCenter.is_active.is_(True)).order_by(CostCenter.code)
                )
            ).all()
            return [{"id": row.id, "code": row.code, "name": row.name} for row in rows]

    @router.post("/centers", status_code=201)
    async def create_center(
        payload: CostCenterPayload,
        request: Request,
        user: Any = Depends(require("costs.recalculate")),
        _: Any = Depends(csrf_user),
    ) -> dict[str, Any]:
        async with database.session_factory() as session, session.begin():
            center = CostCenter(id=uuid4(), **payload.model_dump())
            session.add(center)
            await session.flush()
            audit_row(session, user, request, "cost.center.create", str(center.id))
            return {"id": center.id, "code": center.code, "name": center.name}

    @router.post("/runs", response_model=RunResponse, status_code=201)
    async def create_run(
        payload: RunPayload,
        request: Request,
        user: Any = Depends(require("costs.recalculate")),
        _: Any = Depends(csrf_user),
    ) -> RunResponse:
        async with database.session_factory() as session, session.begin():
            run = await costing_service.create_run(session, payload.run_date, user.id)
            audit_row(session, user, request, "cost.run.create", str(run.id))
            return RunResponse.model_validate(run)

    @router.post("/events/{event_id}/reverse", status_code=201)
    async def reverse_event(
        event_id: UUID,
        payload: ReversalPayload,
        request: Request,
        user: Any = Depends(require("costs.recalculate")),
        _: Any = Depends(csrf_user),
    ) -> dict[str, Any]:
        async with database.session_factory() as session, session.begin():
            try:
                event = await costing_service.reverse_event(session, event_id, user.id, payload.reason)
            except CostingConflictError as exc:
                raise ForbiddenError(code="invalid_cost_reversal", detail=str(exc)) from None
            audit_row(session, user, request, "cost.event.reverse", str(event.id))
            return {"id": event.id, "reversal_of_id": event.reversal_of_id, "status": event.status}

    @router.get("/runs", response_model=list[RunResponse])
    async def runs(_: Any = Depends(require("reports.profitability.read"))) -> list[RunResponse]:
        async with database.session_factory() as session:
            rows = (
                await session.scalars(select(CostRun).order_by(CostRun.run_date.desc(), CostRun.version.desc()))
            ).all()
            return [RunResponse.model_validate(item) for item in rows]

    @router.post("/runs/{run_id}/calculate", response_model=list[SnapshotResponse])
    async def calculate_run(
        run_id: UUID,
        payload: CalculatePayload,
        request: Request,
        user: Any = Depends(require("costs.recalculate")),
        _: Any = Depends(csrf_user),
    ) -> list[SnapshotResponse]:
        async with database.session_factory() as session, session.begin():
            try:
                snapshots = await costing_service.calculate_run(
                    session, run_id, user.id, [item.model_dump() for item in payload.targets]
                )
            except CostingConflictError as exc:
                raise ForbiddenError(code="invalid_cost_run", detail=str(exc)) from None
            audit_row(session, user, request, "cost.run.calculate", str(run_id))
            return [SnapshotResponse.model_validate(item) for item in snapshots]

    @router.post("/runs/{run_id}/close", response_model=RunResponse)
    async def close_run(
        run_id: UUID,
        request: Request,
        user: Any = Depends(require("costs.recalculate")),
        _: Any = Depends(csrf_user),
    ) -> RunResponse:
        async with database.session_factory() as session, session.begin():
            try:
                run = await costing_service.close_run(session, run_id, user.id)
            except CostingConflictError as exc:
                raise ForbiddenError(code="invalid_cost_run", detail=str(exc)) from None
            audit_row(session, user, request, "cost.run.close", str(run_id))
            return RunResponse.model_validate(run)

    @router.post("/runs/{run_id}/profitability")
    async def profitability(
        run_id: UUID,
        payload: ProfitabilityPayload,
        request: Request,
        user: Any = Depends(require("costs.recalculate")),
        _: Any = Depends(csrf_user),
    ) -> list[dict[str, Any]]:
        async with database.session_factory() as session, session.begin():
            try:
                rows = await costing_service.calculate_profitability(
                    session, run_id, [item.model_dump() for item in payload.facts]
                )
            except CostingConflictError as exc:
                raise ForbiddenError(code="invalid_profitability", detail=str(exc)) from None
            audit_row(session, user, request, "cost.run.profitability", str(run_id))
            return [{"id": row.id, "margin": row.margin, "margin_rate": row.margin_rate} for row in rows]

    @router.get("/runs/{run_id}/snapshots", response_model=list[SnapshotResponse])
    async def snapshots(
        run_id: UUID,
        _: Any = Depends(require("reports.profitability.read")),
    ) -> list[SnapshotResponse]:
        async with database.session_factory() as session:
            rows = (await session.scalars(select(CostRunSnapshot).where(CostRunSnapshot.cost_run_id == run_id))).all()
            return [SnapshotResponse.model_validate(item) for item in rows]

    return router
