from __future__ import annotations

import ipaddress
from collections.abc import Awaitable, Callable
from typing import NoReturn
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Header, Request, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from avicola_pro.modules.identity.application.authentication import (
    AuthenticationService,
    CsrfValidationError,
    InvalidCredentialsError,
    InvalidSessionError,
    PasswordChangeError,
    PasswordChangeRequiredError,
    RequestContext,
    SecurityEventData,
    SecurityEventWriter,
    SessionReuseError,
    UserAccount,
)
from avicola_pro.modules.identity.application.authorization import AuthorizationPort
from avicola_pro.modules.identity.application.credentials import PasswordPolicyError
from avicola_pro.modules.identity.application.sessions import IssuedSessionTokens
from avicola_pro.shared.api.errors import ApplicationError, ForbiddenError, UnauthorizedError
from avicola_pro.shared.infrastructure.config import Settings

CSRF_HEADER = "X-CSRF-Token"


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LoginRequest(StrictRequest):
    identity: str = Field(min_length=1, max_length=320)
    password: SecretStr = Field(min_length=1, max_length=256)


class ChangePasswordRequest(StrictRequest):
    current_password: SecretStr = Field(min_length=1, max_length=256)
    new_password: SecretStr = Field(min_length=1, max_length=256)


class UserResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    username: str
    email: str
    display_name: str
    must_change_password: bool


def _user_response(user: UserAccount) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        must_change_password=user.must_change_password,
    )


def request_context(request: Request) -> RequestContext:
    candidate_ip = request.client.host if request.client else None
    try:
        ip_address = str(ipaddress.ip_address(candidate_ip)) if candidate_ip else None
    except ValueError:
        ip_address = None
    return RequestContext(
        correlation_id=request.state.correlation_id,
        ip_address=ip_address,
        user_agent=request.headers.get("user-agent", "")[:512] or None,
    )


def build_permission_dependency(
    *,
    current_user: Callable[..., Awaitable[UserAccount]],
    authorization: AuthorizationPort,
    security_events: SecurityEventWriter,
    resource_type: str,
) -> Callable[[str], Callable[..., Awaitable[UserAccount]]]:
    """Build a permission guard that durably records authenticated denials."""

    def require(permission: str) -> Callable[..., Awaitable[UserAccount]]:
        async def dependency(
            request: Request,
            user: UserAccount = Depends(current_user),  # noqa: B008
        ) -> UserAccount:
            if not await authorization.has_permission(user.id, permission):
                await security_events.write(
                    SecurityEventData(
                        actor_user_id=user.id,
                        actor_username=user.username,
                        event_type="authorization.denied",
                        outcome="DENIED",
                        context=request_context(request),
                        metadata={
                            "permission": permission,
                            "resource_type": resource_type,
                            "resource_id": request.url.path,
                        },
                    )
                )
                raise ForbiddenError(code="permission_denied", detail="Permission denied")
            return user

        return dependency

    return require


def _set_session_cookie(response: Response, settings: Settings, tokens: IssuedSessionTokens) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=tokens.session_token,
        max_age=settings.session_absolute_timeout_seconds,
        httponly=settings.session_cookie_http_only,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        path=settings.session_cookie_path,
    )
    response.headers[CSRF_HEADER] = tokens.csrf_token


def _delete_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        httponly=settings.session_cookie_http_only,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        path=settings.session_cookie_path,
    )


def _raise_auth_error(exc: Exception) -> NoReturn:
    if isinstance(exc, SessionReuseError):
        raise UnauthorizedError(code="session_reused", detail="Session is no longer valid") from None
    if isinstance(exc, InvalidSessionError):
        raise UnauthorizedError(code="invalid_session", detail="Authentication required") from None
    if isinstance(exc, CsrfValidationError):
        raise ForbiddenError(code="csrf_validation_failed", detail="CSRF validation failed") from None
    if isinstance(exc, PasswordChangeRequiredError):
        raise ForbiddenError(code="password_change_required", detail="Password change required") from None
    if isinstance(exc, PasswordChangeError):
        raise UnauthorizedError(code="invalid_current_password", detail="Current password is invalid") from None
    raise exc


def build_auth_router(service: AuthenticationService, settings: Settings) -> APIRouter:
    """Build the authentication HTTP adapter around one application service."""
    router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])

    @router.post("/login", response_model=UserResponse)
    async def login(payload: LoginRequest, request: Request, response: Response) -> UserResponse:
        try:
            result = await service.login(
                payload.identity,
                payload.password.get_secret_value(),
                request_context(request),
            )
        except InvalidCredentialsError:
            raise UnauthorizedError(code="invalid_credentials", detail="Invalid credentials") from None
        _set_session_cookie(response, settings, result.tokens)
        return _user_response(result.user)

    @router.get("/me", response_model=UserResponse)
    async def me(
        request: Request,
        session_token: str | None = Cookie(default=None, alias=settings.session_cookie_name),
    ) -> UserResponse:
        try:
            user = await service.current_session(session_token, request_context(request))
        except (InvalidSessionError, SessionReuseError) as exc:
            _raise_auth_error(exc)
        return _user_response(user)

    @router.post("/refresh", status_code=204)
    async def refresh(
        request: Request,
        response: Response,
        session_token: str | None = Cookie(default=None, alias=settings.session_cookie_name),
        csrf_token: str | None = Header(default=None, alias=CSRF_HEADER),
    ) -> None:
        try:
            result = await service.refresh(session_token, csrf_token, request_context(request))
        except (InvalidSessionError, SessionReuseError, CsrfValidationError, PasswordChangeRequiredError) as exc:
            _raise_auth_error(exc)
            return
        if result.tokens is not None:
            _set_session_cookie(response, settings, result.tokens)

    @router.post("/logout", status_code=204)
    async def logout(
        request: Request,
        response: Response,
        session_token: str | None = Cookie(default=None, alias=settings.session_cookie_name),
        csrf_token: str | None = Header(default=None, alias=CSRF_HEADER),
    ) -> None:
        try:
            await service.logout(session_token, csrf_token, request_context(request))
        except (InvalidSessionError, SessionReuseError, CsrfValidationError) as exc:
            _raise_auth_error(exc)
            return
        _delete_session_cookie(response, settings)

    @router.post("/change-password", response_model=UserResponse)
    async def change_password(
        payload: ChangePasswordRequest,
        request: Request,
        response: Response,
        session_token: str | None = Cookie(default=None, alias=settings.session_cookie_name),
        csrf_token: str | None = Header(default=None, alias=CSRF_HEADER),
    ) -> UserResponse:
        try:
            result = await service.change_password(
                session_token,
                csrf_token,
                payload.current_password.get_secret_value(),
                payload.new_password.get_secret_value(),
                request_context(request),
            )
        except PasswordPolicyError:
            raise ApplicationError(code="password_policy", detail="New password does not meet policy") from None
        except (InvalidSessionError, SessionReuseError, CsrfValidationError, PasswordChangeError) as exc:
            _raise_auth_error(exc)
        _set_session_cookie(response, settings, result.tokens)
        return _user_response(result.user)

    return router
