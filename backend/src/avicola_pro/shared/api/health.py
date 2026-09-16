from __future__ import annotations

from fastapi import APIRouter, Request

from avicola_pro import __version__
from avicola_pro.shared.api.middleware import current_correlation_id
from avicola_pro.shared.api.problem import problem_response
from avicola_pro.shared.infrastructure.database import Database

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def live(request: Request) -> dict[str, str]:
    return {
        "status": "ok",
        "service": request.app.title,
        "version": __version__,
    }


@router.get("/ready")
async def ready(request: Request):  # type: ignore[no-untyped-def]
    database: Database = request.app.state.database
    try:
        await database.check_ready()
    except Exception:  # Database drivers expose several operational exception types.
        return problem_response(
            status=503,
            title="Service Unavailable",
            detail="Database is unavailable",
            instance=request.url.path,
            code="database_unavailable",
            correlation_id=current_correlation_id(),
        )
    return {"status": "ready", "database": "available"}
