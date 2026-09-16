from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from avicola_pro.shared.api.errors import ApplicationError
from avicola_pro.shared.api.middleware import current_correlation_id
from avicola_pro.shared.api.problem import problem_response


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApplicationError)
    async def handle_application_error(request: Request, exc: ApplicationError):  # type: ignore[no-untyped-def]
        return problem_response(
            status=exc.status_code,
            title=exc.title,
            detail=exc.detail,
            instance=request.url.path,
            code=exc.code,
            correlation_id=current_correlation_id(),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):  # type: ignore[no-untyped-def]
        field_errors = [
            {
                "field": ".".join(str(part) for part in error["loc"] if part not in {"body", "query", "path"}),
                "message": error["msg"],
                "code": error["type"],
            }
            for error in exc.errors()
        ]
        return problem_response(
            status=422,
            title="Unprocessable Entity",
            detail="Request validation failed",
            instance=request.url.path,
            code="validation_error",
            correlation_id=current_correlation_id(),
            field_errors=field_errors,
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException):  # type: ignore[no-untyped-def]
        return problem_response(
            status=exc.status_code,
            detail=str(exc.detail),
            instance=request.url.path,
            code="http_error",
            correlation_id=current_correlation_id(),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, _: Exception):  # type: ignore[no-untyped-def]
        return problem_response(
            status=500,
            title="Internal Server Error",
            detail="An unexpected error occurred",
            instance=request.url.path,
            code="internal_error",
            correlation_id=current_correlation_id(),
        )
