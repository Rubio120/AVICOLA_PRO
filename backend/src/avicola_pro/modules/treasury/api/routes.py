# ruff: noqa: B008
from __future__ import annotations

from datetime import date
from decimal import Decimal
from importlib import import_module
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Header, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from avicola_pro.modules.treasury.application.service import CashNotFoundError, treasury_service
from avicola_pro.modules.treasury.domain.rules import CashConflictError
from avicola_pro.shared.api.errors import ForbiddenError, UnauthorizedError

_models = import_module("avicola_pro.modules.treasury.infrastructure.models")
CashAccount: Any = _models.CashAccount


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AccountPayload(StrictModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=120)
    account_type: str = Field(default="CASH", max_length=16)


class OpenPayload(StrictModel):
    account_id: UUID
    opening_balance: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=2)


class MovementPayload(StrictModel):
    session_id: UUID
    account_id: UUID
    movement_type: str = Field(pattern=r"^(INCOME|EXPENSE)$")
    direction: str = Field(pattern=r"^(IN|OUT)$")
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    effective_date: date
    payment_method_code: str | None = Field(default=None, max_length=32)
    reason: str | None = Field(default=None, max_length=500)
    idempotency_key: str | None = Field(default=None, max_length=128)


class TransferPayload(StrictModel):
    source_session_id: UUID
    destination_session_id: UUID
    source_account_id: UUID
    destination_account_id: UUID
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    transfer_date: date
    reason: str | None = Field(default=None, max_length=500)


class ClosePayload(StrictModel):
    counted_balance: Decimal = Field(ge=0, max_digits=18, decimal_places=2)


class ReopenPayload(StrictModel):
    reason: str = Field(min_length=1, max_length=500)


class ReversePayload(StrictModel):
    reason: str = Field(min_length=1, max_length=500)


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    code: str
    name: str
    account_type: str
    currency_code: str
    is_active: bool


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    cash_account_id: UUID
    status: str
    opening_balance: Decimal
    expected_balance: Decimal | None
    counted_balance: Decimal | None
    difference: Decimal | None


class MovementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    cash_session_id: UUID
    cash_account_id: UUID
    movement_type: str
    direction: str
    amount: Decimal
    status: str
    reversal_of_id: UUID | None


class TransferResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    source_movement_id: UUID
    destination_movement_id: UUID
    amount: Decimal


def build_treasury_router(
    authentication: Any,
    authorization: Any,
    database: Any,
    audit: Any,
    cookie_name: str,
    *,
    security_events: Any,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/treasury", tags=["treasury"])
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
        resource_type="treasury",
    )

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

    def audit_row(session: Any, user: Any, request: Request, action: str, resource: str, resource_id: str) -> None:
        record = import_module("avicola_pro.modules.audit.application.writer").AuditRecord
        audit.add(
            session,
            record(
                user.id,
                user.username,
                action,
                resource,
                resource_id,
                UUID(request.state.correlation_id),
                request.client.host if request.client else None,
                request.headers.get("user-agent"),
                None,
                None,
            ),
        )

    def conflict(exc: Exception) -> ForbiddenError:
        return ForbiddenError(code="invalid_cash_operation", detail=str(exc))

    @router.get("/accounts", response_model=list[AccountResponse])
    async def accounts(_: Any = Depends(require("cash.movements.create"))) -> list[AccountResponse]:
        async with database.session_factory() as session:
            return [
                AccountResponse.model_validate(item)
                for item in (
                    await session.scalars(
                        select(CashAccount).where(CashAccount.is_active.is_(True)).order_by(CashAccount.code)
                    )
                ).all()
            ]

    @router.post("/accounts", response_model=AccountResponse, status_code=201)
    async def create_account(
        payload: AccountPayload,
        request: Request,
        user: Any = Depends(require("cash.movements.create")),
        _: Any = Depends(csrf_user),
    ) -> AccountResponse:
        async with database.session_factory() as session, session.begin():
            item = CashAccount(
                id=__import__("uuid").uuid4(), currency_code="PYG", is_active=True, **payload.model_dump()
            )
            session.add(item)
            audit_row(session, user, request, "cash.account.create", "cash_account", str(item.id))
            return AccountResponse.model_validate(item)

    @router.post("/sessions", response_model=SessionResponse, status_code=201)
    async def open_session(
        payload: OpenPayload,
        request: Request,
        user: Any = Depends(require("cash.movements.create")),
        _: Any = Depends(csrf_user),
    ) -> SessionResponse:
        async with database.session_factory() as session, session.begin():
            try:
                item = await treasury_service.open_session(
                    session, payload.account_id, user.id, payload.opening_balance
                )
            except (CashConflictError, CashNotFoundError) as exc:
                raise conflict(exc) from None
            audit_row(session, user, request, "cash.session.open", "cash_session", str(item.id))
            return SessionResponse.model_validate(item)

    @router.post("/movements", response_model=MovementResponse, status_code=201)
    async def create_movement(
        payload: MovementPayload,
        request: Request,
        user: Any = Depends(require("cash.movements.create")),
        _: Any = Depends(csrf_user),
    ) -> MovementResponse:
        async with database.session_factory() as session, session.begin():
            try:
                item = await treasury_service.create_movement(session, **payload.model_dump(), user_id=user.id)
            except (CashConflictError, CashNotFoundError) as exc:
                raise conflict(exc) from None
            audit_row(session, user, request, "cash.movement.create", "cash_movement", str(item.id))
            return MovementResponse.model_validate(item)

    @router.post("/transfers", response_model=TransferResponse, status_code=201)
    async def transfer(
        payload: TransferPayload,
        request: Request,
        user: Any = Depends(require("cash.movements.create")),
        _: Any = Depends(csrf_user),
    ) -> TransferResponse:
        async with database.session_factory() as session, session.begin():
            try:
                item = await treasury_service.transfer(session, **payload.model_dump(), user_id=user.id)
            except (CashConflictError, CashNotFoundError) as exc:
                raise conflict(exc) from None
            audit_row(session, user, request, "cash.transfer.create", "cash_transfer", str(item.id))
            return TransferResponse.model_validate(item)

    @router.post("/sessions/{session_id}/close", response_model=SessionResponse)
    async def close(
        session_id: UUID,
        payload: ClosePayload,
        request: Request,
        user: Any = Depends(require("cash.closings.execute")),
        _: Any = Depends(csrf_user),
    ) -> SessionResponse:
        async with database.session_factory() as session, session.begin():
            try:
                item = await treasury_service.close_session(session, session_id, user.id, payload.counted_balance)
            except (CashConflictError, CashNotFoundError) as exc:
                raise conflict(exc) from None
            audit_row(session, user, request, "cash.session.close", "cash_session", str(item.id))
            return SessionResponse.model_validate(item)

    @router.post("/sessions/{session_id}/reopen", response_model=SessionResponse)
    async def reopen(
        session_id: UUID,
        payload: ReopenPayload,
        request: Request,
        user: Any = Depends(require("cash.closings.execute")),
        _: Any = Depends(csrf_user),
    ) -> SessionResponse:
        async with database.session_factory() as session, session.begin():
            try:
                item = await treasury_service.reopen_session(session, session_id, user.id, payload.reason)
            except (CashConflictError, CashNotFoundError) as exc:
                raise conflict(exc) from None
            audit_row(session, user, request, "cash.session.reopen", "cash_session", str(item.id))
            return SessionResponse.model_validate(item)

    @router.post("/movements/{movement_id}/reverse", response_model=MovementResponse)
    async def reverse(
        movement_id: UUID,
        payload: ReversePayload,
        request: Request,
        user: Any = Depends(require("cash.movements.reverse")),
        _: Any = Depends(csrf_user),
    ) -> MovementResponse:
        async with database.session_factory() as session, session.begin():
            try:
                item = await treasury_service.reverse_movement(session, movement_id, user.id, payload.reason)
            except (CashConflictError, CashNotFoundError) as exc:
                raise conflict(exc) from None
            audit_row(session, user, request, "cash.movement.reverse", "cash_movement", str(item.id))
            return MovementResponse.model_validate(item)

    return router
