from __future__ import annotations

from datetime import date
from decimal import Decimal
from importlib import import_module
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Cookie, Depends, Header, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from avicola_pro.modules.inventory.application.service import (
    InventoryConflictError,
    InventoryNotFoundError,
    inventory_service,
)
from avicola_pro.shared.api.errors import ForbiddenError, UnauthorizedError
from avicola_pro.shared.infrastructure.database import DatabaseResources

_inventory_models = import_module("avicola_pro.modules.inventory.infrastructure.models")
InventoryBalance: Any = _inventory_models.InventoryBalance
InventoryDocument: Any = _inventory_models.InventoryDocument
InventoryDocumentLine: Any = _inventory_models.InventoryDocumentLine

_identity = import_module("avicola_pro.modules.identity.application.authentication")
_auth_api = import_module("avicola_pro.modules.identity.api.auth")
AuthenticationService: Any = _identity.AuthenticationService
InvalidSessionError = _identity.InvalidSessionError
SessionReuseError = _identity.SessionReuseError
UserAccount: Any = _identity.UserAccount
CSRF_HEADER = _auth_api.CSRF_HEADER
request_context = _auth_api.request_context


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class InventoryLinePayload(StrictRequest):
    ordinal: int = Field(ge=1)
    product_id: UUID
    inventory_lot_id: UUID | None = None
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    unit_cost: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=6)
    direction: str = Field(default="IN", pattern=r"^(IN|OUT)$")


class InventoryDocumentPayload(StrictRequest):
    document_type: str = Field(pattern=r"^(RECEIPT|ISSUE|TRANSFER|ADJUSTMENT)$")
    effective_date: date
    warehouse_id: UUID | None = None
    destination_warehouse_id: UUID | None = None
    reason: str | None = Field(default=None, max_length=500)
    idempotency_key: str | None = Field(default=None, max_length=128)
    lines: list[InventoryLinePayload] = Field(min_length=1, max_length=500)


class ReversalPayload(StrictRequest):
    reason: str = Field(min_length=1, max_length=500)


class InventoryDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_type: str
    series: str
    number: str
    effective_date: date
    status: str
    warehouse_id: UUID | None
    destination_warehouse_id: UUID | None
    reason: str | None
    version: int


class Page[T](BaseModel):
    items: list[T]
    offset: int
    limit: int
    total: int


def _document_response(document: Any) -> InventoryDocumentResponse:
    return InventoryDocumentResponse.model_validate(document)


def build_inventory_router(
    authentication: AuthenticationService,
    authorization: Any,
    database: DatabaseResources,
    audit: Any,
    cookie_name: str = "avicola_session",
    *,
    security_events: Any,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/inventory", tags=["inventory"])

    async def current_user(
        request: Request, token: str | None = Cookie(default=None, alias=cookie_name)
    ) -> UserAccount:
        try:
            return await authentication.current_session(token, request_context(request))
        except (InvalidSessionError, SessionReuseError):
            raise UnauthorizedError(code="authentication_required", detail="Authentication required") from None

    require = _auth_api.build_permission_dependency(
        current_user=current_user,
        authorization=authorization,
        security_events=security_events,
        resource_type="inventory",
    )

    async def csrf_user(
        request: Request,
        user: Any = Depends(current_user),  # noqa: B008
        csrf: str | None = Header(default=None, alias=CSRF_HEADER),
    ) -> UserAccount:
        del user
        try:
            return await authentication.validate_mutation(
                request.cookies.get(cookie_name), csrf, request_context(request)
            )
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
                "inventory_document",
                resource_id,
                UUID(request.state.correlation_id),
                request.client.host if request.client else None,
                request.headers.get("user-agent"),
                None,
                None,
            ),
        )

    @router.get("/balances", response_model=Page[Any])
    async def balances(
        _: Any = Depends(require("inventory.products.read")),  # noqa: B008
        warehouse_id: UUID | None = None,
        product_id: UUID | None = None,
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
    ) -> Page[Any]:
        async with database.session_factory() as session:
            query = select(InventoryBalance)
            if warehouse_id:
                query = query.where(InventoryBalance.warehouse_id == warehouse_id)
            if product_id:
                query = query.where(InventoryBalance.product_id == product_id)
            items = list(
                (await session.scalars(query.order_by(InventoryBalance.product_id).offset(offset).limit(limit))).all()
            )
            total = await session.scalar(select(func.count()).select_from(query.subquery()))
            return Page(items=items, offset=offset, limit=limit, total=total or 0)

    @router.post("/documents", status_code=201, response_model=InventoryDocumentResponse)
    async def create_document(
        payload: InventoryDocumentPayload,
        request: Request,
        user: Any = Depends(require("inventory.movements.create")),  # noqa: B008
        _: Any = Depends(csrf_user),  # noqa: B008
    ) -> InventoryDocumentResponse:
        async with database.session_factory() as session, session.begin():
            if payload.idempotency_key:
                existing = await session.scalar(
                    select(InventoryDocument).where(InventoryDocument.idempotency_key == payload.idempotency_key)
                )
                if existing is not None:
                    return _document_response(existing)
            document = InventoryDocument(
                id=uuid4(),
                document_type=payload.document_type,
                effective_date=payload.effective_date,
                warehouse_id=payload.warehouse_id,
                destination_warehouse_id=payload.destination_warehouse_id,
                reason=payload.reason,
                idempotency_key=payload.idempotency_key,
            )
            session.add(document)
            for line_payload in payload.lines:
                session.add(InventoryDocumentLine(id=uuid4(), document_id=document.id, **line_payload.model_dump()))
            add_audit(session, user, request, "inventory.document.create", str(document.id))
            return _document_response(document)

    @router.post("/documents/{document_id}/confirm", response_model=InventoryDocumentResponse)
    async def confirm_document(
        document_id: UUID,
        request: Request,
        user: Any = Depends(require("inventory.movements.create")),  # noqa: B008
        _: Any = Depends(csrf_user),  # noqa: B008
    ) -> InventoryDocumentResponse:
        async with database.session_factory() as session, session.begin():
            try:
                document = await inventory_service.confirm(session, document_id, user.id)
            except InventoryNotFoundError as exc:
                raise ForbiddenError(code="not_found", detail=str(exc)) from exc
            except InventoryConflictError as exc:
                raise ForbiddenError(code="invalid_inventory_operation", detail=str(exc)) from exc
            add_audit(session, user, request, "inventory.document.confirm", str(document.id))
            return _document_response(document)

    @router.post("/documents/{document_id}/reverse", response_model=InventoryDocumentResponse)
    async def reverse_document(
        document_id: UUID,
        payload: ReversalPayload,
        request: Request,
        user: Any = Depends(require("inventory.adjustments.approve")),  # noqa: B008
        _: Any = Depends(csrf_user),  # noqa: B008
    ) -> InventoryDocumentResponse:
        async with database.session_factory() as session, session.begin():
            try:
                document = await inventory_service.reverse(session, document_id, user.id, payload.reason)
            except InventoryNotFoundError as exc:
                raise ForbiddenError(code="not_found", detail=str(exc)) from exc
            except InventoryConflictError as exc:
                raise ForbiddenError(code="invalid_inventory_operation", detail=str(exc)) from exc
            add_audit(session, user, request, "inventory.document.reverse", str(document.id))
            return _document_response(document)

    return router
