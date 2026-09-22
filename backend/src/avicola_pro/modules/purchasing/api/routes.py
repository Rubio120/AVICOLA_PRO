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

from avicola_pro.modules.purchasing.application.service import (
    PurchaseNotFoundError,
    purchasing_service,
)
from avicola_pro.modules.purchasing.domain.rules import PurchaseConflictError
from avicola_pro.shared.api.errors import ConflictError, ForbiddenError, UnauthorizedError
from avicola_pro.shared.infrastructure.database import DatabaseResources

_identity = import_module("avicola_pro.modules.identity.application.authentication")
_auth = import_module("avicola_pro.modules.identity.api.auth")
_models = import_module("avicola_pro.modules.purchasing.infrastructure.models")
AuthenticationService: Any = _identity.AuthenticationService
InvalidSessionError = _identity.InvalidSessionError
SessionReuseError = _identity.SessionReuseError
UserAccount: Any = _identity.UserAccount
CSRF_HEADER = _auth.CSRF_HEADER
request_context = _auth.request_context
PurchaseOrder: Any = _models.PurchaseOrder
PurchaseReceipt: Any = _models.PurchaseReceipt
PurchaseReceiptLine: Any = _models.PurchaseReceiptLine
SupplierDocument: Any = _models.SupplierDocument


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class OrderLinePayload(StrictModel):
    product_id: UUID
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    unit_price: Decimal = Field(ge=0, max_digits=18, decimal_places=6)
    discount_rate: Decimal = Field(default=Decimal("0"), ge=0, le=1, max_digits=9, decimal_places=6)
    tax_rate: Decimal = Field(default=Decimal("0"), ge=0, le=1, max_digits=9, decimal_places=6)


class OrderPayload(StrictModel):
    supplier_id: UUID
    order_date: date
    lines: list[OrderLinePayload] = Field(min_length=1, max_length=500)


class ReceiptLinePayload(StrictModel):
    purchase_order_line_id: UUID
    product_id: UUID
    inventory_lot_id: UUID | None = None
    lot_code: str | None = Field(default=None, max_length=80)
    expiration_date: date | None = None
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    unit_cost: Decimal = Field(ge=0, max_digits=18, decimal_places=6)


class ReceiptPayload(StrictModel):
    purchase_order_id: UUID
    warehouse_id: UUID
    receipt_date: date
    idempotency_key: str | None = Field(default=None, max_length=128)
    lines: list[ReceiptLinePayload] = Field(min_length=1, max_length=500)


class SupplierDocumentPayload(StrictModel):
    supplier_id: UUID
    document_type: str = Field(default="INVOICE", min_length=1, max_length=24)
    external_number: str = Field(min_length=1, max_length=64)
    document_date: date
    total: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    subtotal: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=2)
    tax_total: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=2)


class PaymentAllocationPayload(StrictModel):
    accounts_payable_id: UUID
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)


class PaymentPayload(StrictModel):
    supplier_id: UUID
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    payment_date: date
    payment_method_code: str = Field(min_length=1, max_length=32)
    idempotency_key: str | None = Field(default=None, max_length=128)
    allocations: list[PaymentAllocationPayload] = Field(min_length=1, max_length=500)


class ReversalPayload(StrictModel):
    reason: str = Field(min_length=1, max_length=500)


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    supplier_id: UUID
    order_date: date
    status: str
    subtotal: Decimal
    tax_total: Decimal
    total: Decimal


class ReceiptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    purchase_order_id: UUID
    warehouse_id: UUID
    status: str
    inventory_document_id: UUID | None


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    supplier_id: UUID
    amount: Decimal
    status: str
    cash_movement_id: UUID | None


def build_purchasing_router(
    authentication: AuthenticationService, authorization: Any, database: DatabaseResources, audit: Any, cookie_name: str
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/purchasing", tags=["purchasing"])

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
        request: Request, _: Any = Depends(current_user), csrf: str | None = Header(default=None, alias=CSRF_HEADER)
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
                "purchasing",
                resource_id,
                UUID(request.state.correlation_id),
                request.client.host if request.client else None,
                request.headers.get("user-agent"),
                None,
                None,
            ),
        )

    def conflict(exc: Exception) -> ConflictError:
        return ConflictError(code="invalid_purchasing_operation", detail=str(exc))

    @router.get("/orders", response_model=list[OrderResponse])
    async def orders(_: Any = Depends(require("purchases.orders.create"))) -> list[OrderResponse]:  # noqa: B008
        async with database.session_factory() as session:
            return [
                OrderResponse.model_validate(item)
                for item in (
                    await session.scalars(select(PurchaseOrder).order_by(PurchaseOrder.order_date.desc()))
                ).all()
            ]

    @router.post("/orders", response_model=OrderResponse, status_code=201)
    async def create_order(
        payload: OrderPayload,
        request: Request,
        user: Any = Depends(require("purchases.orders.create")),
        _: Any = Depends(csrf_user),
    ) -> OrderResponse:  # noqa: B008
        async with database.session_factory() as session, session.begin():
            order = await purchasing_service.create_order(
                session, payload.supplier_id, payload.order_date, [line.model_dump() for line in payload.lines]
            )
            add_audit(session, user, request, "purchases.order.create", str(order.id))
            return OrderResponse.model_validate(order)

    @router.post("/orders/{order_id}/approve", response_model=OrderResponse)
    async def approve(
        order_id: UUID,
        request: Request,
        user: Any = Depends(require("purchases.orders.approve")),
        _: Any = Depends(csrf_user),
    ) -> OrderResponse:  # noqa: B008
        async with database.session_factory() as session, session.begin():
            try:
                order = await purchasing_service.approve_order(session, order_id, user.id)
            except (PurchaseNotFoundError, PurchaseConflictError) as exc:
                raise conflict(exc) from None
            add_audit(session, user, request, "purchases.order.approve", str(order.id))
            return OrderResponse.model_validate(order)

    @router.post("/receipts", response_model=ReceiptResponse, status_code=201)
    async def create_receipt(
        payload: ReceiptPayload,
        request: Request,
        user: Any = Depends(require("purchases.receipts.confirm")),
        _: Any = Depends(csrf_user),
    ) -> ReceiptResponse:  # noqa: B008
        async with database.session_factory() as session, session.begin():
            if payload.idempotency_key:
                existing = await session.scalar(
                    select(PurchaseReceipt).where(PurchaseReceipt.idempotency_key == payload.idempotency_key)
                )
                if existing:
                    return ReceiptResponse.model_validate(existing)
            receipt = PurchaseReceipt(
                id=uuid4(),
                purchase_order_id=payload.purchase_order_id,
                warehouse_id=payload.warehouse_id,
                receipt_date=payload.receipt_date,
                idempotency_key=payload.idempotency_key,
            )
            session.add(receipt)
            await session.flush()
            for line in payload.lines:
                session.add(PurchaseReceiptLine(id=uuid4(), receipt_id=receipt.id, **line.model_dump()))
            add_audit(session, user, request, "purchases.receipt.create", str(receipt.id))
            return ReceiptResponse.model_validate(receipt)

    @router.post("/receipts/{receipt_id}/confirm", response_model=ReceiptResponse)
    async def confirm_receipt(
        receipt_id: UUID,
        request: Request,
        user: Any = Depends(require("purchases.receipts.confirm")),
        _: Any = Depends(csrf_user),
    ) -> ReceiptResponse:  # noqa: B008
        async with database.session_factory() as session, session.begin():
            try:
                receipt = await purchasing_service.confirm_receipt(session, receipt_id, user.id)
            except (PurchaseNotFoundError, PurchaseConflictError) as exc:
                raise conflict(exc) from None
            add_audit(session, user, request, "purchases.receipt.confirm", str(receipt.id))
            return ReceiptResponse.model_validate(receipt)

    @router.post("/supplier-documents", status_code=201)
    async def create_document(
        payload: SupplierDocumentPayload,
        request: Request,
        user: Any = Depends(require("purchases.documents.create")),
        _: Any = Depends(csrf_user),
    ) -> dict[str, str]:  # noqa: B008
        async with database.session_factory() as session, session.begin():
            document = await purchasing_service.create_supplier_document(session, payload.model_dump())
            add_audit(session, user, request, "purchases.supplier_document.create", str(document.id))
            return {"id": str(document.id)}

    @router.post("/payments", status_code=201)
    async def create_payment(
        payload: PaymentPayload,
        request: Request,
        user: Any = Depends(require("purchases.payments.create")),
        _: Any = Depends(csrf_user),
    ) -> PaymentResponse:  # noqa: B008
        async with database.session_factory() as session, session.begin():
            try:
                payment, _ = await purchasing_service.create_payment(
                    session,
                    payload.supplier_id,
                    payload.amount,
                    payload.payment_date,
                    payload.payment_method_code,
                    payload.idempotency_key,
                    [allocation.model_dump() for allocation in payload.allocations],
                )
            except PurchaseConflictError as exc:
                raise conflict(exc) from None
            add_audit(session, user, request, "purchases.payment.create", str(payment.id))
            return PaymentResponse.model_validate(payment)

    @router.post("/payments/{payment_id}/confirm", response_model=PaymentResponse)
    async def confirm_payment(
        payment_id: UUID,
        request: Request,
        user: Any = Depends(require("purchases.payments.create")),
        _: Any = Depends(csrf_user),
    ) -> PaymentResponse:  # noqa: B008
        async with database.session_factory() as session, session.begin():
            try:
                payment = await purchasing_service.confirm_payment(session, payment_id, user.id)
            except (PurchaseNotFoundError, PurchaseConflictError) as exc:
                raise conflict(exc) from None
            add_audit(session, user, request, "purchases.payment.confirm", str(payment.id))
            return PaymentResponse.model_validate(payment)

    @router.post("/payments/{payment_id}/reverse", response_model=PaymentResponse)
    async def reverse_payment(
        payment_id: UUID,
        payload: ReversalPayload,
        request: Request,
        user: Any = Depends(require("purchases.payments.reverse")),
        _: Any = Depends(csrf_user),
    ) -> PaymentResponse:  # noqa: B008
        async with database.session_factory() as session, session.begin():
            try:
                payment = await purchasing_service.reverse_payment(session, payment_id, user.id, payload.reason)
            except (PurchaseNotFoundError, PurchaseConflictError) as exc:
                raise conflict(exc) from None
            add_audit(session, user, request, "purchases.payment.reverse", str(payment.id))
            return PaymentResponse.model_validate(payment)

    return router
