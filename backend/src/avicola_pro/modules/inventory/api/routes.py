from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from importlib import import_module
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Cookie, Depends, Header, Query, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select

from avicola_pro.modules.inventory.application.service import (
    InventoryConflictError,
    InventoryNotFoundError,
    inventory_service,
)
from avicola_pro.shared.api.errors import ForbiddenError, UnauthorizedError
from avicola_pro.shared.infrastructure.database import DatabaseResources

_inventory_models = import_module("avicola_pro.modules.inventory.infrastructure.models")
_catalog_models = import_module("avicola_pro.modules.catalog.infrastructure.models")
_settings_models = import_module("avicola_pro.modules.settings.infrastructure.models")
InventoryBalance: Any = _inventory_models.InventoryBalance
InventoryDocument: Any = _inventory_models.InventoryDocument
InventoryDocumentLine: Any = _inventory_models.InventoryDocumentLine
EggCategory: Any = _inventory_models.EggCategory
EggPresentationConversion: Any = _inventory_models.EggPresentationConversion
Product: Any = _catalog_models.Product
Warehouse: Any = _catalog_models.Warehouse
UnitOfMeasure: Any = _settings_models.UnitOfMeasure

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


class EggCategoryPayload(StrictRequest):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=120)
    product_id: UUID
    is_saleable: bool
    is_active: bool


class EggCategoryUpdatePayload(StrictRequest):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    is_saleable: bool | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def require_an_update(self) -> EggCategoryUpdatePayload:
        if self.name is None and self.is_saleable is None and self.is_active is None:
            raise ValueError("at least one category field must be updated")
        return self


class EggConversionPayload(StrictRequest):
    unit_code: str = Field(min_length=1, max_length=32)
    units_per_package: int = Field(gt=0, le=2_147_483_647, strict=True)


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


class EggCategoryResponse(BaseModel):
    id: UUID
    code: str
    name: str
    product_id: UUID
    product_sku: str
    base_unit_code: str
    is_saleable: bool
    is_active: bool


class EggConversionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    category_id: UUID
    unit_code: str
    version: int
    units_per_package: int


class EggBalanceResponse(BaseModel):
    category_id: UUID
    category_code: str
    category_name: str
    product_id: UUID
    product_sku: str
    warehouse_id: UUID | None
    quantity_eggs: Decimal
    inventory_value: Decimal


class EggProductOption(BaseModel):
    id: UUID
    sku: str
    name: str
    base_unit_code: str


class EggWarehouseOption(BaseModel):
    id: UUID
    code: str
    name: str


class EggUnitOption(BaseModel):
    code: str
    name: str
    precision: int


class EggConfigurationOptionsResponse(BaseModel):
    products: list[EggProductOption]
    warehouses: list[EggWarehouseOption]
    units: list[EggUnitOption]


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

    def add_audit(
        session: Any,
        user: UserAccount,
        request: Request,
        action: str,
        resource_id: str,
        resource_type: str = "inventory_document",
    ) -> None:
        record = import_module("avicola_pro.modules.audit.application.writer").AuditRecord
        audit.add(
            session,
            record(
                user.id,
                user.username,
                action,
                resource_type,
                resource_id,
                UUID(request.state.correlation_id),
                request.client.host if request.client else None,
                request.headers.get("user-agent"),
                None,
                None,
            ),
        )

    @router.get("/egg-categories", response_model=list[EggCategoryResponse])
    async def egg_categories(
        _: Any = Depends(require("inventory.products.read")),  # noqa: B008
    ) -> list[EggCategoryResponse]:  # noqa: B008
        async with database.session_factory() as session:
            rows = await session.execute(
                select(EggCategory, Product)
                .join(Product, Product.id == EggCategory.product_id)
                .order_by(EggCategory.code)
            )
            return [
                EggCategoryResponse(
                    id=category.id,
                    code=category.code,
                    name=category.name,
                    product_id=product.id,
                    product_sku=product.sku,
                    base_unit_code=product.base_unit_code,
                    is_saleable=category.is_saleable,
                    is_active=category.is_active,
                )
                for category, product in rows.all()
            ]

    @router.get("/egg-configuration-options", response_model=EggConfigurationOptionsResponse)
    async def egg_configuration_options(
        _: Any = Depends(require("inventory.products.read")),  # noqa: B008
    ) -> EggConfigurationOptionsResponse:  # noqa: B008
        async with database.session_factory() as session:
            products = await session.scalars(
                select(Product)
                .where(Product.is_active.is_(True), Product.product_type == "PRODUCT")
                .order_by(Product.name)
                .limit(500)
            )
            warehouses = await session.scalars(
                select(Warehouse).where(Warehouse.is_active.is_(True)).order_by(Warehouse.code).limit(500)
            )
            units = await session.scalars(
                select(UnitOfMeasure).where(UnitOfMeasure.is_active.is_(True)).order_by(UnitOfMeasure.code).limit(500)
            )
            return EggConfigurationOptionsResponse(
                products=[EggProductOption.model_validate(item) for item in products.all()],
                warehouses=[EggWarehouseOption.model_validate(item) for item in warehouses.all()],
                units=[EggUnitOption.model_validate(item) for item in units.all()],
            )

    @router.post("/egg-categories", response_model=EggCategoryResponse, status_code=201)
    async def create_egg_category(
        payload: EggCategoryPayload,
        request: Request,
        user: Any = Depends(require("inventory.egg_categories.manage")),  # noqa: B008
        _: Any = Depends(csrf_user),  # noqa: B008
    ) -> EggCategoryResponse:  # noqa: B008
        async with database.session_factory() as session, session.begin():
            product = await session.scalar(
                select(Product)
                .where(Product.id == payload.product_id, Product.is_active.is_(True), Product.product_type == "PRODUCT")
                .with_for_update()
            )
            if product is None:
                raise ForbiddenError(code="invalid_egg_category", detail="An active inventory product is required")
            if product.base_unit_code != "unit":
                raise ForbiddenError(
                    code="invalid_egg_category",
                    detail="Egg category product must use the individual egg unit",
                )
            if await session.scalar(select(EggCategory.id).where(EggCategory.code == payload.code)) is not None:
                raise ForbiddenError(code="invalid_egg_category", detail="Egg category code is already in use")
            if await session.scalar(select(EggCategory.id).where(EggCategory.product_id == product.id)) is not None:
                raise ForbiddenError(code="invalid_egg_category", detail="Product is already mapped to an egg category")
            category = EggCategory(id=uuid4(), **payload.model_dump())
            session.add(category)
            await session.flush()
            add_audit(session, user, request, "inventory.egg_category.create", str(category.id), "egg_category")
            return EggCategoryResponse(
                id=category.id,
                code=category.code,
                name=category.name,
                product_id=product.id,
                product_sku=product.sku,
                base_unit_code=product.base_unit_code,
                is_saleable=category.is_saleable,
                is_active=category.is_active,
            )

    @router.patch("/egg-categories/{category_id}", response_model=EggCategoryResponse)
    async def update_egg_category(
        category_id: UUID,
        payload: EggCategoryUpdatePayload,
        request: Request,
        user: Any = Depends(require("inventory.egg_categories.manage")),  # noqa: B008
        _: Any = Depends(csrf_user),  # noqa: B008
    ) -> EggCategoryResponse:  # noqa: B008
        async with database.session_factory() as session, session.begin():
            category = await session.scalar(select(EggCategory).where(EggCategory.id == category_id).with_for_update())
            if category is None:
                raise ForbiddenError(code="not_found", detail="Egg category not found")
            product = await session.get(Product, category.product_id)
            if product is None:
                raise ForbiddenError(code="invalid_egg_category", detail="Mapped product was not found")
            for field, value in payload.model_dump(exclude_unset=True).items():
                setattr(category, field, value)
            category.updated_at = datetime.now(UTC)
            await session.flush()
            add_audit(session, user, request, "inventory.egg_category.update", str(category.id), "egg_category")
            return EggCategoryResponse(
                id=category.id,
                code=category.code,
                name=category.name,
                product_id=product.id,
                product_sku=product.sku,
                base_unit_code=product.base_unit_code,
                is_saleable=category.is_saleable,
                is_active=category.is_active,
            )

    @router.get("/egg-categories/{category_id}/conversions", response_model=list[EggConversionResponse])
    async def egg_conversions(
        category_id: UUID,
        _: Any = Depends(require("inventory.products.read")),  # noqa: B008
    ) -> list[EggConversionResponse]:  # noqa: B008
        async with database.session_factory() as session:
            rows = await session.scalars(
                select(EggPresentationConversion)
                .where(EggPresentationConversion.category_id == category_id)
                .order_by(EggPresentationConversion.unit_code, EggPresentationConversion.version.desc())
            )
            return [EggConversionResponse.model_validate(item) for item in rows.all()]

    @router.post(
        "/egg-categories/{category_id}/conversions",
        response_model=EggConversionResponse,
        status_code=201,
    )
    async def create_egg_conversion(
        category_id: UUID,
        payload: EggConversionPayload,
        request: Request,
        user: Any = Depends(require("inventory.egg_categories.manage")),  # noqa: B008
        _: Any = Depends(csrf_user),  # noqa: B008
    ) -> EggConversionResponse:  # noqa: B008
        async with database.session_factory() as session, session.begin():
            category = await session.scalar(
                select(EggCategory)
                .where(EggCategory.id == category_id, EggCategory.is_active.is_(True))
                .with_for_update()
            )
            unit = await session.scalar(
                select(UnitOfMeasure).where(UnitOfMeasure.code == payload.unit_code, UnitOfMeasure.is_active.is_(True))
            )
            if category is None or unit is None:
                raise ForbiddenError(
                    code="invalid_egg_conversion", detail="Active category and unit of measure are required"
                )
            current_version = await session.scalar(
                select(func.max(EggPresentationConversion.version)).where(
                    EggPresentationConversion.category_id == category_id,
                    EggPresentationConversion.unit_code == payload.unit_code,
                )
            )
            conversion = EggPresentationConversion(
                id=uuid4(),
                category_id=category_id,
                unit_code=payload.unit_code,
                version=(current_version or 0) + 1,
                units_per_package=payload.units_per_package,
            )
            session.add(conversion)
            await session.flush()
            add_audit(session, user, request, "inventory.egg_conversion.create", str(conversion.id), "egg_conversion")
            return EggConversionResponse.model_validate(conversion)

    @router.get("/egg-balances", response_model=Page[EggBalanceResponse])
    async def egg_balances(
        _: Any = Depends(require("inventory.products.read")),  # noqa: B008
        category_id: UUID | None = None,
        warehouse_id: UUID | None = None,
        offset: int = Query(0, ge=0),  # noqa: B008
        limit: int = Query(50, ge=1, le=100),  # noqa: B008
    ) -> Page[EggBalanceResponse]:  # noqa: B008
        async with database.session_factory() as session:
            query = (
                select(
                    EggCategory.id.label("category_id"),
                    EggCategory.code.label("category_code"),
                    EggCategory.name.label("category_name"),
                    Product.id.label("product_id"),
                    Product.sku.label("product_sku"),
                    InventoryBalance.warehouse_id.label("warehouse_id"),
                    func.coalesce(func.sum(InventoryBalance.quantity), 0).label("quantity_eggs"),
                    func.coalesce(func.sum(InventoryBalance.inventory_value), 0).label("inventory_value"),
                )
                .join(Product, Product.id == EggCategory.product_id)
                .outerjoin(InventoryBalance, InventoryBalance.product_id == Product.id)
                .group_by(EggCategory.id, Product.id, InventoryBalance.warehouse_id)
            )
            if category_id is not None:
                query = query.where(EggCategory.id == category_id)
            if warehouse_id is not None:
                query = query.where(InventoryBalance.warehouse_id == warehouse_id)
            rows = (
                (
                    await session.execute(
                        query.order_by(EggCategory.code, InventoryBalance.warehouse_id).offset(offset).limit(limit)
                    )
                )
                .mappings()
                .all()
            )
            total = await session.scalar(select(func.count()).select_from(query.subquery()))
            return Page(
                items=[EggBalanceResponse.model_validate(row) for row in rows],
                offset=offset,
                limit=limit,
                total=total or 0,
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
