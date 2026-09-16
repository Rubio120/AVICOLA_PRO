from __future__ import annotations


class ApplicationError(Exception):
    status_code = 400
    title = "Bad Request"

    def __init__(self, *, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class ConflictError(ApplicationError):
    status_code = 409
    title = "Conflict"
