from __future__ import annotations

import re
import uuid
from contextvars import ContextVar

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

CORRELATION_HEADER = "X-Correlation-ID"
MAX_CORRELATION_ID_LENGTH = 64
_VALID_CORRELATION_ID = re.compile(r"^[A-Za-z0-9._:-]+$")
correlation_id_context: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def current_correlation_id() -> str:
    return correlation_id_context.get() or str(uuid.uuid4())


def _resolve_correlation_id(candidate: str | None) -> str:
    if (
        candidate
        and len(candidate) <= MAX_CORRELATION_ID_LENGTH
        and _VALID_CORRELATION_ID.fullmatch(candidate) is not None
    ):
        return candidate
    return str(uuid.uuid4())


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = _resolve_correlation_id(request.headers.get(CORRELATION_HEADER))
        token = correlation_id_context.set(correlation_id)
        request.state.correlation_id = correlation_id
        try:
            response = await call_next(request)
            response.headers[CORRELATION_HEADER] = correlation_id
            return response
        finally:
            correlation_id_context.reset(token)
