from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Header, Query, Request
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from avicola_pro.modules.identity.api.auth import CSRF_HEADER, request_context
from avicola_pro.modules.identity.application.administration import AdministrationPort
from avicola_pro.modules.identity.application.authentication import (
    AuthenticationService,
    CsrfValidationError,
    InvalidSessionError,
    SessionReuseError,
    UserAccount,
)
from avicola_pro.modules.identity.application.authorization import AuthorizationPort
from avicola_pro.shared.api.errors import ForbiddenError, UnauthorizedError
from avicola_pro.shared.infrastructure.config import Settings


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CreateUserRequest(StrictRequest):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    email: str = Field(min_length=3, max_length=320)
    display_name: str = Field(min_length=1, max_length=160)
    password: SecretStr = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.casefold()
        if normalized.count("@") != 1 or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("must be a valid email address")
        return normalized


class StatusRequest(StrictRequest):
    status: str = Field(pattern=r"^(ACTIVE|INACTIVE)$")


class ReplaceRolesRequest(StrictRequest):
    role_ids: list[UUID] = Field(max_length=32)


class UserResponse(BaseModel):
    id: UUID
    username: str
    email: str
    display_name: str
    status: str
    must_change_password: bool
    roles: tuple[str, ...]


class RoleResponse(BaseModel):
    id: UUID
    code: str
    name: str
    description: str | None
    is_system: bool
    is_active: bool


class PermissionResponse(BaseModel):
    id: UUID
    key: str
    description: str


class AuditResponse(BaseModel):
    id: UUID
    actor_username: str | None
    action: str
    resource_type: str
    resource_id: str | None
    outcome: str
    correlation_id: UUID
    created_at: datetime


class Page[T](BaseModel):
    items: list[T]
    offset: int
    limit: int
    total: int


def build_admin_router(
    authentication: AuthenticationService,
    authorization: AuthorizationPort,
    administration: AdministrationPort,
    settings: Settings,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["identity-administration"])

    async def current_user(
        request: Request,
        session_token: str | None = Cookie(default=None, alias=settings.session_cookie_name),
    ) -> UserAccount:
        try:
            return await authentication.current_session(session_token, request_context(request))
        except (InvalidSessionError, SessionReuseError):
            raise UnauthorizedError(code="authentication_required", detail="Authentication required") from None

    def require(permission: str) -> Callable[..., Awaitable[UserAccount]]:
        async def dependency(user: Annotated[UserAccount, Depends(current_user)], request: Request) -> UserAccount:
            if not await authorization.has_permission(user.id, permission):
                raise ForbiddenError(code="permission_denied", detail="Permission denied")
            return user

        return dependency

    async def csrf_guard(
        request: Request,
        user: Annotated[UserAccount, Depends(current_user)],
        session_token: str | None = Cookie(default=None, alias=settings.session_cookie_name),
        csrf_token: str | None = Header(default=None, alias=CSRF_HEADER),
    ) -> UserAccount:
        try:
            return await authentication.validate_mutation(session_token, csrf_token, request_context(request))
        except (InvalidSessionError, SessionReuseError):
            raise UnauthorizedError(code="authentication_required", detail="Authentication required") from None
        except CsrfValidationError:
            raise ForbiddenError(code="csrf_validation_failed", detail="CSRF validation failed") from None

    @router.get("/users", response_model=Page[UserResponse])
    async def list_users(
        user: Annotated[UserAccount, Depends(require("users.manage"))],
        offset: int = Query(default=0, ge=0, le=100_000),
        limit: int = Query(default=50, ge=1, le=100),
    ) -> Page[UserResponse]:
        del user
        items, total = await administration.list_users(offset=offset, limit=limit)
        return Page(
            items=[
                UserResponse(
                    id=item.id,
                    username=item.username,
                    email=item.email,
                    display_name=item.display_name,
                    status=item.status,
                    must_change_password=item.must_change_password,
                    roles=item.roles,
                )
                for item in items
            ],
            offset=offset,
            limit=limit,
            total=total,
        )

    @router.post("/users", response_model=UserResponse, status_code=201)
    async def create_user(
        payload: CreateUserRequest,
        request: Request,
        user: Annotated[UserAccount, Depends(require("users.manage"))],
        _: Annotated[UserAccount, Depends(csrf_guard)],
    ) -> UserResponse:
        created = await administration.create_user(
            actor=user,
            context=request_context(request),
            username=payload.username,
            email=payload.email,
            display_name=payload.display_name,
            password=payload.password.get_secret_value(),
        )
        return UserResponse(
            id=created.id,
            username=created.username,
            email=created.email,
            display_name=created.display_name,
            status=created.status,
            must_change_password=created.must_change_password,
            roles=(),
        )

    @router.patch("/users/{user_id}/status", status_code=204)
    async def set_user_status(
        user_id: UUID,
        payload: StatusRequest,
        request: Request,
        user: Annotated[UserAccount, Depends(require("users.manage"))],
        _: Annotated[UserAccount, Depends(csrf_guard)],
    ) -> None:
        await administration.set_user_status(
            actor=user, context=request_context(request), user_id=user_id, status=payload.status
        )

    @router.put("/users/{user_id}/roles", status_code=204)
    async def replace_user_roles(
        user_id: UUID,
        payload: ReplaceRolesRequest,
        request: Request,
        user: Annotated[UserAccount, Depends(require("roles.manage"))],
        _: Annotated[UserAccount, Depends(csrf_guard)],
    ) -> None:
        await administration.replace_user_roles(
            actor=user, context=request_context(request), user_id=user_id, role_ids=payload.role_ids
        )

    @router.get("/roles", response_model=Page[RoleResponse])
    async def list_roles(
        user: Annotated[UserAccount, Depends(require("roles.manage"))],
        offset: int = Query(default=0, ge=0, le=100_000),
        limit: int = Query(default=50, ge=1, le=100),
    ) -> Page[RoleResponse]:
        del user
        items, total = await administration.list_roles(offset=offset, limit=limit)
        return Page(
            items=[RoleResponse.model_validate(item, from_attributes=True) for item in items],
            offset=offset,
            limit=limit,
            total=total,
        )

    @router.get("/permissions", response_model=Page[PermissionResponse])
    async def list_permissions(
        user: Annotated[UserAccount, Depends(require("roles.manage"))],
        offset: int = Query(default=0, ge=0, le=100_000),
        limit: int = Query(default=100, ge=1, le=100),
    ) -> Page[PermissionResponse]:
        del user
        items, total = await administration.list_permissions(offset=offset, limit=limit)
        return Page(
            items=[PermissionResponse.model_validate(item, from_attributes=True) for item in items],
            offset=offset,
            limit=limit,
            total=total,
        )

    @router.get("/audit-events", response_model=Page[AuditResponse])
    async def list_audit_events(
        user: Annotated[UserAccount, Depends(require("audit.read"))],
        offset: int = Query(default=0, ge=0, le=100_000),
        limit: int = Query(default=50, ge=1, le=100),
    ) -> Page[AuditResponse]:
        del user
        items, total = await administration.list_audit_events(offset=offset, limit=limit)
        return Page(
            items=[AuditResponse.model_validate(item, from_attributes=True) for item in items],
            offset=offset,
            limit=limit,
            total=total,
        )

    return router
