from __future__ import annotations

from http import HTTPStatus
from typing import Any

from fastapi.responses import JSONResponse

PROBLEM_CONTENT_TYPE = "application/problem+json"


def problem_response(
    *,
    status: int,
    detail: str,
    instance: str,
    code: str,
    correlation_id: str,
    title: str | None = None,
    field_errors: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    payload: dict[str, Any] = {
        "type": "about:blank",
        "title": title or HTTPStatus(status).phrase,
        "status": status,
        "detail": detail,
        "instance": instance,
        "code": code,
        "correlation_id": correlation_id,
    }
    if field_errors is not None:
        payload["field_errors"] = field_errors
    return JSONResponse(payload, status_code=status, media_type=PROBLEM_CONTENT_TYPE)
