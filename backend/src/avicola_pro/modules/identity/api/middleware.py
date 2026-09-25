from __future__ import annotations

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from avicola_pro.modules.identity.api.auth import request_context
from avicola_pro.modules.identity.application.authentication import AuthenticationService
from avicola_pro.shared.api.middleware import current_correlation_id
from avicola_pro.shared.api.problem import problem_response

_FORCED_CHANGE_ALLOWED_PATHS = frozenset(
    {
        "/api/v1/auth/me",
        "/api/v1/auth/change-password",
        "/api/v1/auth/logout",
    }
)


class ForcedPasswordChangeMiddleware(BaseHTTPMiddleware):
    """Deny every non-allowlisted API route for forced-change sessions."""

    def __init__(self, app: object, *, service: AuthenticationService, cookie_name: str) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._service = service
        self._cookie_name = cookie_name

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        session_token = request.cookies.get(self._cookie_name)
        should_check = (
            session_token is not None
            and request.url.path.startswith("/api/v1/")
            and request.url.path not in _FORCED_CHANGE_ALLOWED_PATHS
        )
        if should_check:
            context = request_context(request)
            user = await self._service.password_change_is_required(session_token, context)
            if user is not None:
                await self._service.record_password_change_required(user, context)
                return problem_response(
                    status=403,
                    title="Forbidden",
                    detail="Password change required",
                    instance=request.url.path,
                    code="password_change_required",
                    correlation_id=current_correlation_id(),
                )
        return await call_next(request)
