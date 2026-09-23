# ruff: noqa: B008
from __future__ import annotations

from datetime import date
from decimal import Decimal
from importlib import import_module
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Cookie, Depends, Header, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from avicola_pro.modules.sales.application.service import SalesNotFoundError, sales_service
from avicola_pro.modules.sales.domain.rules import SalesConflictError
from avicola_pro.shared.api.errors import ForbiddenError, UnauthorizedError
from avicola_pro.shared.infrastructure.database import DatabaseResources

_identity = import_module("avicola_pro.modules.identity.application.authentication")
_auth = import_module("avicola_pro.modules.identity.api.auth")
_models = import_module("avicola_pro.modules.sales.infrastructure.models")
AuthenticationService: Any = _identity.AuthenticationService
InvalidSessionError = _identity.InvalidSessionError
SessionReuseError = _identity.SessionReuseError
UserAccount: Any = _identity.UserAccount
CSRF_HEADER = _auth.CSRF_HEADER
request_context = _auth.request_context
SalesOrder: Any = _models.SalesOrder
SalesOrderLine: Any = _models.SalesOrderLine
SalesDelivery: Any = _models.SalesDelivery
SalesDeliveryLine: Any = _models.SalesDeliveryLine
CommercialDocument: Any = _models.CommercialDocument
CustomerPayment: Any = _models.CustomerPayment
CustomerPaymentAllocation: Any = _models.CustomerPaymentAllocation


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class OrderLine(StrictModel):
    product_id: UUID
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    unit_price: Decimal = Field(ge=0, max_digits=18, decimal_places=6)
    discount_rate: Decimal = Field(default=Decimal("0"), ge=0, le=1)
    tax_rate: Decimal = Field(default=Decimal("0"), ge=0, le=1)


class OrderPayload(StrictModel):
    customer_id: UUID
    order_date: date
    lines: list[OrderLine] = Field(min_length=1, max_length=500)


class DeliveryLine(StrictModel):
    sales_order_line_id: UUID
    product_id: UUID
    inventory_lot_id: UUID | None = None
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)


class DeliveryPayload(StrictModel):
    sales_order_id: UUID
    customer_id: UUID
    warehouse_id: UUID
    delivery_date: date
    idempotency_key: str | None = Field(default=None, max_length=128)
    lines: list[DeliveryLine] = Field(min_length=1, max_length=500)


class DocumentLine(StrictModel):
    description: str = Field(min_length=1, max_length=300)
    product_id: UUID | None = None
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    unit_price: Decimal = Field(ge=0, max_digits=18, decimal_places=6)
    discount_rate: Decimal = Field(default=Decimal("0"), ge=0, le=1)
    tax_rate: Decimal = Field(ge=0, le=1)


class DocumentPayload(StrictModel):
    customer_id: UUID
    document_type: str = Field(pattern=r"^(INVOICE|CREDIT_NOTE)$")
    series: str = Field(min_length=1, max_length=16)
    document_date: date
    original_document_id: UUID | None = None
    lines: list[DocumentLine] = Field(min_length=1, max_length=500)


class PaymentAllocation(StrictModel):
    accounts_receivable_id: UUID
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)


class PaymentPayload(StrictModel):
    customer_id: UUID
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    payment_date: date
    payment_method_code: str = Field(min_length=1, max_length=32)
    idempotency_key: str | None = Field(default=None, max_length=128)
    allocations: list[PaymentAllocation] = Field(min_length=1, max_length=500)


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    customer_id: UUID
    order_date: date
    status: str
    total: Decimal


class DeliveryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    sales_order_id: UUID
    status: str
    inventory_document_id: UUID | None


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    document_type: str
    series: str
    number: str
    customer_id: UUID
    total: Decimal
    status: str


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    customer_id: UUID
    amount: Decimal
    status: str
    cash_movement_id: UUID | None


def build_sales_router(
    authentication: AuthenticationService,
    authorization: Any,
    database: DatabaseResources,
    audit: Any,
    cookie_name: str,
    *,
    security_events: Any,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/sales", tags=["sales"])

    async def current_user(
        request: Request, token: str | None = Cookie(default=None, alias=cookie_name)
    ) -> UserAccount:
        try:
            return await authentication.current_session(token, request_context(request))
        except (InvalidSessionError, SessionReuseError):
            raise UnauthorizedError(code="authentication_required", detail="Authentication required") from None

    require = _auth.build_permission_dependency(
        current_user=current_user,
        authorization=authorization,
        security_events=security_events,
        resource_type="sales",
    )

    async def csrf_user(
        request: Request, _: Any = Depends(current_user), csrf: str | None = Header(default=None, alias=CSRF_HEADER)
    ) -> None:
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
                "sales",
                resource_id,
                UUID(request.state.correlation_id),
                request.client.host if request.client else None,
                request.headers.get("user-agent"),
                None,
                None,
            ),
        )

    def conflict(exc: Exception) -> ForbiddenError:
        return ForbiddenError(code="invalid_sales_operation", detail=str(exc))

    @router.get("/orders", response_model=list[OrderResponse])
    async def orders(_: Any = Depends(require("sales.orders.create"))) -> list[OrderResponse]:
        async with database.session_factory() as session:
            return [
                OrderResponse.model_validate(item)
                for item in (await session.scalars(select(SalesOrder).order_by(SalesOrder.order_date.desc()))).all()
            ]

    @router.post("/orders", response_model=OrderResponse, status_code=201)
    async def create_order(
        payload: OrderPayload,
        request: Request,
        user: Any = Depends(require("sales.orders.create")),
        _: Any = Depends(csrf_user),
    ) -> OrderResponse:
        async with database.session_factory() as session, session.begin():
            try:
                order = await sales_service.create_order(
                    session, payload.customer_id, payload.order_date, [line.model_dump() for line in payload.lines]
                )
            except SalesConflictError as exc:
                raise conflict(exc) from None
            add_audit(session, user, request, "sales.order.create", str(order.id))
            return OrderResponse.model_validate(order)

    @router.post("/orders/{order_id}/confirm", response_model=OrderResponse)
    async def confirm_order(
        order_id: UUID,
        request: Request,
        user: Any = Depends(require("sales.orders.create")),
        _: Any = Depends(csrf_user),
    ) -> OrderResponse:
        async with database.session_factory() as session, session.begin():
            try:
                order = await sales_service.confirm_order(session, order_id)
            except (SalesConflictError, SalesNotFoundError) as exc:
                raise conflict(exc) from None
            add_audit(session, user, request, "sales.order.confirm", str(order.id))
            return OrderResponse.model_validate(order)

    @router.post("/deliveries", response_model=DeliveryResponse, status_code=201)
    async def create_delivery(
        payload: DeliveryPayload,
        request: Request,
        user: Any = Depends(require("sales.orders.create")),
        _: Any = Depends(csrf_user),
    ) -> DeliveryResponse:
        async with database.session_factory() as session, session.begin():
            existing = (
                await session.scalar(
                    select(SalesDelivery).where(SalesDelivery.idempotency_key == payload.idempotency_key)
                )
                if payload.idempotency_key
                else None
            )
            if existing:
                return DeliveryResponse.model_validate(existing)
            delivery = SalesDelivery(id=uuid4(), **payload.model_dump(exclude={"lines"}))
            session.add(delivery)
            await session.flush()
            for line in payload.lines:
                session.add(SalesDeliveryLine(id=uuid4(), delivery_id=delivery.id, **line.model_dump()))
            add_audit(session, user, request, "sales.delivery.create", str(delivery.id))
            return DeliveryResponse.model_validate(delivery)

    @router.post("/deliveries/{delivery_id}/confirm", response_model=DeliveryResponse)
    async def confirm_delivery(
        delivery_id: UUID,
        request: Request,
        user: Any = Depends(require("sales.orders.create")),
        _: Any = Depends(csrf_user),
    ) -> DeliveryResponse:
        async with database.session_factory() as session, session.begin():
            try:
                delivery = await sales_service.confirm_delivery(session, delivery_id, user.id)
            except (SalesConflictError, SalesNotFoundError) as exc:
                raise conflict(exc) from None
            add_audit(session, user, request, "sales.delivery.confirm", str(delivery.id))
            return DeliveryResponse.model_validate(delivery)

    @router.post("/documents", response_model=DocumentResponse, status_code=201)
    async def issue_document(
        payload: DocumentPayload,
        request: Request,
        user: Any = Depends(require("sales.documents.issue")),
        _: Any = Depends(csrf_user),
    ) -> DocumentResponse:
        async with database.session_factory() as session, session.begin():
            try:
                document = await sales_service.issue_document(session, payload.model_dump(), user.id)
            except SalesConflictError as exc:
                raise conflict(exc) from None
            add_audit(session, user, request, "sales.document.issue", str(document.id))
            return DocumentResponse.model_validate(document)

    @router.post("/payments", response_model=PaymentResponse, status_code=201)
    async def create_payment(
        payload: PaymentPayload,
        request: Request,
        user: Any = Depends(require("sales.documents.issue")),
        _: Any = Depends(csrf_user),
    ) -> PaymentResponse:
        async with database.session_factory() as session, session.begin():
            existing = (
                await session.scalar(
                    select(CustomerPayment).where(CustomerPayment.idempotency_key == payload.idempotency_key)
                )
                if payload.idempotency_key
                else None
            )
            if existing:
                return PaymentResponse.model_validate(existing)
            payment = CustomerPayment(
                id=uuid4(),
                customer_id=payload.customer_id,
                amount=payload.amount,
                payment_date=payload.payment_date,
                payment_method_code=payload.payment_method_code,
                idempotency_key=payload.idempotency_key,
            )
            session.add(payment)
            await session.flush()
            for allocation in payload.allocations:
                session.add(CustomerPaymentAllocation(id=uuid4(), payment_id=payment.id, **allocation.model_dump()))
            add_audit(session, user, request, "sales.payment.create", str(payment.id))
            return PaymentResponse.model_validate(payment)

    @router.post("/payments/{payment_id}/confirm", response_model=PaymentResponse)
    async def confirm_payment(
        payment_id: UUID,
        request: Request,
        user: Any = Depends(require("sales.documents.issue")),
        _: Any = Depends(csrf_user),
    ) -> PaymentResponse:
        async with database.session_factory() as session, session.begin():
            try:
                payment = await sales_service.confirm_payment(session, payment_id, user.id)
            except (SalesConflictError, SalesNotFoundError) as exc:
                raise conflict(exc) from None
            add_audit(session, user, request, "sales.payment.confirm", str(payment.id))
            return PaymentResponse.model_validate(payment)

    return router
