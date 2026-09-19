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

from avicola_pro.modules.production.application.service import (
    ProductionConflictError,
    ProductionNotFoundError,
    production_service,
)
from avicola_pro.shared.api.errors import ForbiddenError, UnauthorizedError
from avicola_pro.shared.infrastructure.database import DatabaseResources

_identity = __import__("avicola_pro.modules.identity.application.authentication", fromlist=["AuthenticationService"])
_auth = __import__("avicola_pro.modules.identity.api.auth", fromlist=["CSRF_HEADER", "request_context"])
AuthenticationService: Any = _identity.AuthenticationService
InvalidSessionError = _identity.InvalidSessionError
SessionReuseError = _identity.SessionReuseError
UserAccount: Any = _identity.UserAccount
CSRF_HEADER = _auth.CSRF_HEADER
request_context = _auth.request_context
_models = import_module("avicola_pro.modules.production.infrastructure.models")
Flock: Any = _models.Flock
FlockBalance: Any = _models.FlockBalance


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class FlockPayload(StrictModel):
    code: str = Field(min_length=1, max_length=64)
    purpose: str = Field(min_length=1, max_length=120)
    breed: str | None = Field(default=None, max_length=120)
    entry_date: date
    planned_initial_quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)


class MortalityPayload(StrictModel):
    occurred_on: date
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    cause: str = Field(min_length=1, max_length=300)
    house_id: UUID | None = None
    idempotency_key: str | None = Field(default=None, max_length=128)


class AdjustmentPayload(StrictModel):
    adjustment_type: str = Field(pattern=r"^(CORRECTION_IN|CORRECTION_OUT)$")
    occurred_on: date
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    reason: str = Field(min_length=1, max_length=500)
    idempotency_key: str | None = Field(default=None, max_length=128)


class AssignmentPayload(StrictModel):
    house_id: UUID
    valid_from: date
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)


class DailyPayload(StrictModel):
    record_date: date
    observed_birds: Decimal = Field(ge=0, max_digits=18, decimal_places=4)
    average_weight: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=6)
    notes: str | None = Field(default=None, max_length=500)


class FeedPayload(StrictModel):
    product_id: UUID
    warehouse_id: UUID
    house_id: UUID | None = None
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    occurred_on: date


class FlockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    code: str
    purpose: str
    status: str
    entry_date: date
    planned_initial_quantity: Decimal


class BalanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    flock_id: UUID
    live_birds: Decimal


def build_production_router(
    authentication: AuthenticationService, authorization: Any, database: DatabaseResources, audit: Any, cookie_name: str
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/production", tags=["production"])

    async def current_user(
        request: Request, token: str | None = Cookie(default=None, alias=cookie_name)
    ) -> UserAccount:
        try:
            return await authentication.current_session(token, request_context(request))
        except (InvalidSessionError, SessionReuseError):
            raise UnauthorizedError(code="authentication_required", detail="Authentication required") from None

    def require(permission: str) -> Callable[..., Awaitable[UserAccount]]:
        async def dependency(user: Any = Depends(current_user)) -> Any:  # noqa: B008
            if not await authorization.has_permission(user.id, permission):
                raise ForbiddenError(code="permission_denied", detail="Permission denied")
            return user

        return dependency

    async def csrf_user(
        request: Request,
        _: Any = Depends(current_user),  # noqa: B008
        csrf: str | None = Header(default=None, alias=CSRF_HEADER),  # noqa: B008
    ) -> None:  # noqa: B008
        try:
            await authentication.validate_mutation(request.cookies.get(cookie_name), csrf, request_context(request))
        except (InvalidSessionError, SessionReuseError):
            raise UnauthorizedError(code="authentication_required", detail="Authentication required") from None

    def add_audit(session: Any, user: UserAccount, request: Request, action: str, resource_id: str) -> None:
        record = import_module("avicola_pro.modules.audit.application.writer").AuditRecord
        audit.add(
            session,
            record(
                user.id,
                user.username,
                action,
                "production",
                resource_id,
                UUID(request.state.correlation_id),
                request.client.host if request.client else None,
                request.headers.get("user-agent"),
                None,
                None,
            ),
        )

    @router.get("/flocks", response_model=list[FlockResponse])
    async def flocks(_: Any = Depends(require("production.mortality.record"))) -> list[FlockResponse]:  # noqa: B008
        async with database.session_factory() as session:
            return [
                FlockResponse.model_validate(item)
                for item in (await session.scalars(select(Flock).order_by(Flock.entry_date.desc()))).all()
            ]

    @router.get("/balances", response_model=list[BalanceResponse])
    async def balances(_: Any = Depends(require("production.mortality.record"))) -> list[BalanceResponse]:  # noqa: B008
        async with database.session_factory() as session:
            return [
                BalanceResponse.model_validate(item) for item in (await session.scalars(select(FlockBalance))).all()
            ]

    @router.post("/flocks", response_model=FlockResponse, status_code=201)
    async def create_flock(
        payload: FlockPayload,
        request: Request,
        _: Any = Depends(require("production.flocks.manage")),  # noqa: B008
        __: Any = Depends(csrf_user),  # noqa: B008
    ) -> FlockResponse:  # noqa: B008
        async with database.session_factory() as session, session.begin():
            flock = Flock(id=uuid4(), status="DRAFT", **payload.model_dump())
            session.add(flock)
            await session.flush()
            add_audit(session, _, request, "production.flock.create", str(flock.id))
            return FlockResponse.model_validate(flock)

    @router.post("/flocks/{flock_id}/activate", response_model=FlockResponse)
    async def activate(
        flock_id: UUID,
        request: Request,
        user: Any = Depends(require("production.flocks.manage")),  # noqa: B008
        _: Any = Depends(csrf_user),  # noqa: B008
    ) -> FlockResponse:  # noqa: B008
        async with database.session_factory() as session, session.begin():
            try:
                flock = await production_service.activate(session, flock_id, user.id)
                add_audit(session, user, request, "production.flock.activate", str(flock.id))
                return FlockResponse.model_validate(flock)
            except ProductionNotFoundError as exc:
                raise ForbiddenError(code="not_found", detail=str(exc)) from None
            except ProductionConflictError as exc:
                raise ForbiddenError(code="invalid_production_operation", detail=str(exc)) from None

    @router.post("/flocks/{flock_id}/mortality", status_code=201)
    async def mortality(
        flock_id: UUID,
        payload: MortalityPayload,
        request: Request,
        user: Any = Depends(require("production.mortality.record")),  # noqa: B008
        _: Any = Depends(csrf_user),  # noqa: B008
    ) -> dict[str, str]:  # noqa: B008
        async with database.session_factory() as session, session.begin():
            try:
                event = await production_service.record_mortality(
                    session,
                    flock_id,
                    payload.occurred_on,
                    payload.quantity,
                    payload.cause,
                    user.id,
                    payload.house_id,
                    payload.idempotency_key,
                )
            except ProductionConflictError as exc:
                raise ForbiddenError(code="invalid_production_operation", detail=str(exc)) from None
            add_audit(session, user, request, "production.mortality.create", str(event.id))
            return {"id": str(event.id)}

    @router.post("/flocks/{flock_id}/adjustments", status_code=201)
    async def adjustment(
        flock_id: UUID,
        payload: AdjustmentPayload,
        request: Request,
        _: Any = Depends(require("production.adjustments.approve")),  # noqa: B008
        __: Any = Depends(csrf_user),  # noqa: B008
    ) -> dict[str, str]:  # noqa: B008
        async with database.session_factory() as session, session.begin():
            try:
                event = await production_service.adjust(session, flock_id, **payload.model_dump())
            except ProductionConflictError as exc:
                raise ForbiddenError(code="invalid_production_operation", detail=str(exc)) from None
            add_audit(session, _, request, "production.adjustment.create", str(event.id))
            return {"id": str(event.id)}

    @router.post("/flocks/{flock_id}/assignments", status_code=201)
    async def assignment(
        flock_id: UUID,
        payload: AssignmentPayload,
        request: Request,
        _: Any = Depends(require("production.flocks.manage")),  # noqa: B008
        __: Any = Depends(csrf_user),  # noqa: B008
    ) -> dict[str, str]:  # noqa: B008
        async with database.session_factory() as session, session.begin():
            try:
                item = await production_service.assign_house(session, flock_id, **payload.model_dump())
            except (ProductionConflictError, ProductionNotFoundError) as exc:
                raise ForbiddenError(code="invalid_production_operation", detail=str(exc)) from None
            add_audit(session, _, request, "production.assignment.create", str(item.id))
            return {"id": str(item.id)}

    @router.post("/flocks/{flock_id}/daily-records", status_code=201)
    async def daily(
        flock_id: UUID,
        payload: DailyPayload,
        request: Request,
        _: Any = Depends(require("production.mortality.record")),  # noqa: B008
        __: Any = Depends(csrf_user),  # noqa: B008
    ) -> dict[str, str]:  # noqa: B008
        async with database.session_factory() as session, session.begin():
            item = await production_service.record_daily(session, flock_id, **payload.model_dump())
            add_audit(session, _, request, "production.daily_record.create", str(item.id))
            return {"id": str(item.id)}

    @router.post("/flocks/{flock_id}/feed", status_code=201)
    async def feed(
        flock_id: UUID,
        payload: FeedPayload,
        request: Request,
        user: Any = Depends(require("production.feed.record")),  # noqa: B008
        _: Any = Depends(csrf_user),  # noqa: B008
    ) -> dict[str, str]:  # noqa: B008
        async with database.session_factory() as session, session.begin():
            try:
                item = await production_service.record_feed(
                    session, flock_id, actor_user_id=user.id, **payload.model_dump()
                )
            except (ProductionConflictError, ProductionNotFoundError) as exc:
                raise ForbiddenError(code="invalid_production_operation", detail=str(exc)) from None
            add_audit(session, user, request, "production.feed.create", str(item.id))
            return {"id": str(item.id)}

    @router.post("/flocks/{flock_id}/close", response_model=FlockResponse)
    async def close(
        flock_id: UUID,
        request: Request,
        user: Any = Depends(require("production.flocks.manage")),  # noqa: B008
        _: Any = Depends(csrf_user),  # noqa: B008
    ) -> FlockResponse:  # noqa: B008
        async with database.session_factory() as session, session.begin():
            try:
                authorized = await authorization.has_permission(user.id, "production.adjustments.approve")
                flock = await production_service.close(session, flock_id, authorized)
                add_audit(session, user, request, "production.flock.close", str(flock.id))
                return FlockResponse.model_validate(flock)
            except (ProductionConflictError, ProductionNotFoundError) as exc:
                raise ForbiddenError(code="invalid_production_operation", detail=str(exc)) from None

    return router
