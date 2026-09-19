# mypy: ignore-errors

from collections.abc import Awaitable, Callable
from datetime import date
from decimal import Decimal
from importlib import import_module
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Cookie, Depends, Header, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from avicola_pro.modules.settings.domain.rules import (
    format_sequence_number,
    normalize_code,
    validate_tax_rate,
    validate_validity_range,
)
from avicola_pro.shared.api.errors import ConflictError, ForbiddenError, UnauthorizedError
from avicola_pro.shared.infrastructure.database import DatabaseResources

_identity = import_module("avicola_pro.modules.identity.application.authentication")
_auth_api = import_module("avicola_pro.modules.identity.api.auth")
_authorization = import_module("avicola_pro.modules.identity.application.authorization")
_settings_models = import_module("avicola_pro.modules.settings.infrastructure.models")
_party_models = import_module("avicola_pro.modules.parties.infrastructure.models")
_catalog_models = import_module("avicola_pro.modules.catalog.infrastructure.models")
AuthenticationService: Any = _identity.AuthenticationService
InvalidSessionError = _identity.InvalidSessionError
SessionReuseError = _identity.SessionReuseError
UserAccount: Any = _identity.UserAccount
AuthorizationPort: Any = _authorization.AuthorizationPort
CompanyProfile: Any = _settings_models.CompanyProfile
TaxRate: Any = _settings_models.TaxRate
DocumentSequence: Any = _settings_models.DocumentSequence
Customer: Any = _party_models.Customer
Supplier: Any = _party_models.Supplier
Product: Any = _catalog_models.Product
ProductCategory: Any = _catalog_models.ProductCategory
CSRF_HEADER = _auth_api.CSRF_HEADER
request_context = _auth_api.request_context


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Page[T](BaseModel):
    items: list[T]
    offset: int
    limit: int
    total: int


class CompanyPayload(StrictRequest):
    legal_name: str = Field(min_length=1, max_length=200)
    tax_id: str = Field(min_length=1, max_length=32)
    trade_name: str | None = Field(default=None, max_length=200)
    address: str | None = Field(default=None, max_length=500)
    timezone: str = Field(default="America/Asuncion", max_length=64)
    version: int = Field(default=1, ge=1)


class TaxPayload(StrictRequest):
    code: str = Field(min_length=2, max_length=32)
    name: str = Field(min_length=1, max_length=80)
    rate: Decimal = Field(ge=0, le=1)
    valid_from: date
    valid_to: date | None = None


class PartyPayload(StrictRequest):
    code: str = Field(min_length=2, max_length=32)
    document_type: str = Field(min_length=1, max_length=16)
    document_number: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=200)
    payment_term_days: int = Field(default=0, ge=0, le=3650)


class CategoryPayload(StrictRequest):
    code: str = Field(min_length=2, max_length=32)
    name: str = Field(min_length=1, max_length=120)


class ProductPayload(StrictRequest):
    sku: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    product_type: str = Field(pattern=r"^(PRODUCT|INPUT|SERVICE)$")
    base_unit_code: str = Field(min_length=1, max_length=32)
    category_id: UUID | None = None
    tracks_lot: bool = False
    tracks_expiration: bool = False


class SequencePayload(StrictRequest):
    document_type: str = Field(min_length=1, max_length=64)
    series: str = Field(min_length=1, max_length=16)
    prefix: str = Field(default="", max_length=16)
    padding: int = Field(default=7, ge=1, le=18)


def build_settings_router(
    authentication: AuthenticationService,
    authorization: AuthorizationPort,
    database: DatabaseResources,
    audit: Any,
    cookie_name: str = "avicola_session",
) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["settings-catalog"])

    async def current_user(
        request: Request, token: str | None = Cookie(default=None, alias=cookie_name)
    ) -> UserAccount:
        try:
            return await authentication.current_session(token, request_context(request))
        except (InvalidSessionError, SessionReuseError):
            raise UnauthorizedError(code="authentication_required", detail="Authentication required") from None

    def require(permission: str) -> Callable[..., Awaitable[UserAccount]]:
        async def dependency(user: Annotated[UserAccount, Depends(current_user)]) -> UserAccount:
            if not await authorization.has_permission(user.id, permission):
                raise ForbiddenError(code="permission_denied", detail="Permission denied")
            return user

        return dependency

    async def csrf_user(
        request: Request,
        user: Annotated[UserAccount, Depends(current_user)],
        csrf: str | None = Header(default=None, alias=CSRF_HEADER),
    ) -> UserAccount:
        del user
        try:
            return await authentication.validate_mutation(
                request.cookies.get(cookie_name), csrf, request_context(request)
            )
        except (InvalidSessionError, SessionReuseError):
            raise UnauthorizedError(code="authentication_required", detail="Authentication required") from None

    async def add_audit(
        session: AsyncSession, user: UserAccount, request: Request, action: str, resource: str, resource_id: str
    ) -> None:
        audit_record = import_module("avicola_pro.modules.audit.application.writer").AuditRecord
        audit.add(
            session,
            audit_record(
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

    @router.get("/company-profile", response_model=None)
    async def company_profile(_: Annotated[UserAccount, Depends(require("settings.manage"))]) -> CompanyProfile | None:
        async with database.session_factory() as session:
            return await session.scalar(select(CompanyProfile).where(CompanyProfile.singleton_key == 1))

    @router.put("/company-profile", response_model=None)
    async def save_company(
        payload: CompanyPayload,
        request: Request,
        user: Annotated[UserAccount, Depends(require("settings.manage"))],
        _: Annotated[UserAccount, Depends(csrf_user)],
    ) -> CompanyProfile:
        async with database.session_factory() as session, session.begin():
            profile = await session.scalar(
                select(CompanyProfile).where(CompanyProfile.singleton_key == 1).with_for_update()
            )
            if profile is None:
                profile = CompanyProfile(
                    singleton_key=1, base_currency="PYG", **payload.model_dump(exclude={"version"})
                )
                session.add(profile)
            elif profile.version != payload.version:
                raise ForbiddenError(code="version_conflict", detail="The company profile changed; reload it")
            else:
                for key, value in payload.model_dump(exclude={"version"}).items():
                    setattr(profile, key, value)
                profile.version += 1
            await add_audit(session, user, request, "settings.company.update", "company_profile", "1")
            return profile

    @router.get("/tax-rates", response_model=None)
    async def tax_rates(
        user: Annotated[UserAccount, Depends(require("settings.manage"))],
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
    ) -> Page[Any]:
        del user
        async with database.session_factory() as session:
            items = list(
                (
                    await session.scalars(
                        select(TaxRate).order_by(TaxRate.valid_from.desc()).offset(offset).limit(limit)
                    )
                ).all()
            )
            total = await session.scalar(select(func.count()).select_from(TaxRate))
            return Page(items=items, offset=offset, limit=limit, total=total or 0)

    @router.post("/tax-rates", response_model=None, status_code=201)
    async def create_tax(
        payload: TaxPayload,
        request: Request,
        user: Annotated[UserAccount, Depends(require("settings.manage"))],
        _: Annotated[UserAccount, Depends(csrf_user)],
    ) -> TaxRate:
        try:
            validate_validity_range(payload.valid_from, payload.valid_to)
            rate = validate_tax_rate(payload.rate)
        except ValueError as exc:
            raise ForbiddenError(code="invalid_validity", detail=str(exc)) from exc
        async with database.session_factory() as session, session.begin():
            item = TaxRate(id=uuid4(), **payload.model_dump(exclude={"rate"}), rate=rate)
            session.add(item)
            await add_audit(session, user, request, "settings.tax_rate.create", "tax_rate", str(item.id))
            return item

    @router.post("/document-sequences", response_model=None, status_code=201)
    async def create_sequence(
        payload: SequencePayload,
        request: Request,
        user: Annotated[UserAccount, Depends(require("settings.manage"))],
        _: Annotated[UserAccount, Depends(csrf_user)],
    ) -> DocumentSequence:
        try:
            document_type = normalize_code(payload.document_type)
            series = normalize_code(payload.series)
        except ValueError as exc:
            raise ForbiddenError(code="invalid_sequence", detail=str(exc)) from exc
        async with database.session_factory() as session, session.begin():
            item = DocumentSequence(
                id=uuid4(),
                document_type=document_type,
                series=series,
                prefix=payload.prefix,
                padding=payload.padding,
            )
            session.add(item)
            await add_audit(session, user, request, "settings.sequence.create", "document_sequence", str(item.id))
            return item

    @router.post("/document-sequences/{sequence_id}/next", response_model=None)
    async def consume_sequence(
        sequence_id: UUID,
        request: Request,
        user: Annotated[UserAccount, Depends(require("settings.manage"))],
        _: Annotated[UserAccount, Depends(csrf_user)],
    ) -> dict[str, object]:
        async with database.session_factory() as session, session.begin():
            item = await session.scalar(
                select(DocumentSequence).where(DocumentSequence.id == sequence_id).with_for_update()
            )
            if item is None or not item.is_active:
                raise ForbiddenError(code="sequence_unavailable", detail="Sequence is unavailable")
            item.current_number += 1
            value = format_sequence_number(item.prefix, item.current_number, item.padding)
            await add_audit(session, user, request, "settings.sequence.consume", "document_sequence", str(item.id))
            return {"id": item.id, "number": item.current_number, "formatted": value}

    @router.get("/parties/{party_type}")
    async def list_parties(
        party_type: str,
        user: Annotated[UserAccount, Depends(require("parties.manage"))],
        search: str = "",
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
    ) -> Page[dict[str, object]]:
        model = Customer if party_type == "customers" else Supplier if party_type == "suppliers" else None
        if model is None:
            raise ForbiddenError(code="invalid_party_type", detail="Unknown party type")
        del user
        async with database.session_factory() as session:
            filters = [model.is_active.is_(True)]
            if search:
                filters.append(or_(model.code.ilike(f"%{search}%"), model.name.ilike(f"%{search}%")))
            query = select(model).where(*filters)
            items = list((await session.scalars(query.order_by(model.name).offset(offset).limit(limit))).all())
            total = await session.scalar(select(func.count()).select_from(model).where(*filters))
            return Page(
                items=[{k: v for k, v in item.__dict__.items() if not k.startswith("_")} for item in items],
                offset=offset,
                limit=limit,
                total=total or 0,
            )

    @router.post("/parties/{party_type}", status_code=201)
    async def create_party(
        party_type: str,
        payload: PartyPayload,
        request: Request,
        user: Annotated[UserAccount, Depends(require("parties.manage"))],
        _: Annotated[UserAccount, Depends(csrf_user)],
    ) -> dict[str, object]:
        model = Customer if party_type == "customers" else Supplier if party_type == "suppliers" else None
        if model is None:
            raise ForbiddenError(code="invalid_party_type", detail="Unknown party type")
        values = payload.model_dump()
        try:
            values["code"] = normalize_code(str(values["code"]))
        except ValueError as exc:
            raise ForbiddenError(code="invalid_code", detail=str(exc)) from exc
        if model is Customer:
            values["contacts"] = {}
            values["credit_limit"] = 0
        async with database.session_factory() as session, session.begin():
            item = model(id=uuid4(), **values)
            session.add(item)
            await add_audit(session, user, request, f"parties.{party_type[:-1]}.create", party_type, str(item.id))
            return {k: v for k, v in item.__dict__.items() if not k.startswith("_")}

    @router.get("/catalog/categories", response_model=None)
    async def categories(
        user: Annotated[UserAccount, Depends(require("catalog.read"))],
        search: str = "",
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
    ) -> Page[Any]:
        del user
        async with database.session_factory() as session:
            query = select(ProductCategory).where(ProductCategory.is_active.is_(True))
            if search:
                query = query.where(
                    or_(ProductCategory.code.ilike(f"%{search}%"), ProductCategory.name.ilike(f"%{search}%"))
                )
            items = list(
                (await session.scalars(query.order_by(ProductCategory.name).offset(offset).limit(limit))).all()
            )
            total = await session.scalar(
                select(func.count()).select_from(ProductCategory).where(ProductCategory.is_active.is_(True))
            )
            return Page(items=items, offset=offset, limit=limit, total=total or 0)

    @router.post("/catalog/categories", response_model=None, status_code=201)
    async def create_category(
        payload: CategoryPayload,
        request: Request,
        user: Annotated[UserAccount, Depends(require("catalog.manage"))],
        _: Annotated[UserAccount, Depends(csrf_user)],
    ) -> ProductCategory:
        async with database.session_factory() as session, session.begin():
            try:
                code = normalize_code(payload.code)
            except ValueError as exc:
                raise ForbiddenError(code="invalid_code", detail=str(exc)) from exc
            item = ProductCategory(id=uuid4(), code=code, name=payload.name)
            session.add(item)
            await add_audit(session, user, request, "catalog.category.create", "product_category", str(item.id))
            return item

    @router.get("/catalog/products", response_model=None)
    async def products(
        user: Annotated[UserAccount, Depends(require("catalog.read"))],
        search: str = "",
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
    ) -> Page[Any]:
        del user
        async with database.session_factory() as session:
            query = select(Product).where(Product.is_active.is_(True))
            if search:
                query = query.where(or_(Product.sku.ilike(f"%{search}%"), Product.name.ilike(f"%{search}%")))
            items = list((await session.scalars(query.order_by(Product.name).offset(offset).limit(limit))).all())
            total = await session.scalar(select(func.count()).select_from(Product).where(Product.is_active.is_(True)))
            return Page(items=items, offset=offset, limit=limit, total=total or 0)

    @router.post("/catalog/products", response_model=None, status_code=201)
    async def create_product(
        payload: ProductPayload,
        request: Request,
        user: Annotated[UserAccount, Depends(require("catalog.manage"))],
        _: Annotated[UserAccount, Depends(csrf_user)],
    ) -> Product:
        try:
            sku = normalize_code(payload.sku)
        except ValueError as exc:
            raise ForbiddenError(code="invalid_code", detail=str(exc)) from exc
        async with database.session_factory() as session, session.begin():
            item = Product(id=uuid4(), sku=sku, **payload.model_dump(exclude={"sku"}))
            session.add(item)
            await add_audit(session, user, request, "catalog.product.create", "product", str(item.id))
            return item

    @router.patch("/catalog/products/{product_id}", response_model=None)
    async def update_product(
        product_id: UUID,
        payload: ProductPayload,
        request: Request,
        user: Annotated[UserAccount, Depends(require("catalog.manage"))],
        _: Annotated[UserAccount, Depends(csrf_user)],
        version: int = Query(..., ge=1),
    ) -> Product:
        async with database.session_factory() as session, session.begin():
            item = await session.scalar(select(Product).where(Product.id == product_id).with_for_update())
            if item is None:
                raise ForbiddenError(code="not_found", detail="Product not found")
            if item.version != version:
                raise ConflictError(code="version_conflict", detail="The product changed; reload it")
            values = payload.model_dump()
            try:
                values["sku"] = normalize_code(values["sku"])
            except ValueError as exc:
                raise ForbiddenError(code="invalid_code", detail=str(exc)) from exc
            for key, value in values.items():
                setattr(item, key, value)
            item.version += 1
            await add_audit(session, user, request, "catalog.product.update", "product", str(item.id))
            return item

    @router.post("/catalog/products/{product_id}/deactivate", response_model=None)
    async def deactivate_product(
        product_id: UUID,
        request: Request,
        user: Annotated[UserAccount, Depends(require("catalog.manage"))],
        _: Annotated[UserAccount, Depends(csrf_user)],
    ) -> Product:
        async with database.session_factory() as session, session.begin():
            item = await session.scalar(select(Product).where(Product.id == product_id).with_for_update())
            if item is None:
                raise ForbiddenError(code="not_found", detail="Product not found")
            item.is_active = False
            item.version += 1
            await add_audit(session, user, request, "catalog.product.deactivate", "product", str(item.id))
            return item

    return router
