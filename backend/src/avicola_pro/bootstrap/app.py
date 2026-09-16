from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from avicola_pro import __version__
from avicola_pro.shared.api.error_handlers import install_error_handlers
from avicola_pro.shared.api.health import router as health_router
from avicola_pro.shared.api.middleware import CorrelationIdMiddleware
from avicola_pro.shared.infrastructure.config import Settings, get_settings
from avicola_pro.shared.infrastructure.database import Database, create_database_resources
from avicola_pro.shared.infrastructure.logging import configure_logging


def create_app(settings: Settings | None = None, *, database: Database | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings)
    database_resources = database or create_database_resources(resolved_settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await database_resources.dispose()

    application = FastAPI(
        title=resolved_settings.app_name,
        version=__version__,
        debug=resolved_settings.debug,
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.state.database = database_resources
    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Correlation-ID"],
    )
    application.add_middleware(CorrelationIdMiddleware)
    install_error_handlers(application)
    application.include_router(health_router)
    return application
