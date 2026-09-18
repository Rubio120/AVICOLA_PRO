from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from avicola_pro import __version__
from avicola_pro.modules.audit.infrastructure.security import SQLAlchemySecurityEventWriter
from avicola_pro.modules.audit.infrastructure.writer import SQLAlchemyFunctionalAuditWriter
from avicola_pro.modules.identity.api.admin import build_admin_router
from avicola_pro.modules.identity.api.auth import CSRF_HEADER, build_auth_router
from avicola_pro.modules.identity.api.middleware import ForcedPasswordChangeMiddleware
from avicola_pro.modules.identity.application.authentication import AuthenticationService
from avicola_pro.modules.identity.application.credentials import Argon2PasswordService, PasswordPolicy
from avicola_pro.modules.identity.application.sessions import SessionTokenService
from avicola_pro.modules.identity.infrastructure.administration import SQLAlchemyAdministrationService
from avicola_pro.modules.identity.infrastructure.authentication import (
    SQLAlchemyAuthenticationRepository,
)
from avicola_pro.modules.identity.infrastructure.authorization import SQLAlchemyAuthorizationService
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
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Correlation-ID", CSRF_HEADER],
        expose_headers=["X-Correlation-ID", CSRF_HEADER],
    )
    session_factory = getattr(database_resources, "session_factory", None)
    if session_factory is not None:
        password_policy = PasswordPolicy(
            min_length=resolved_settings.password_min_length,
            max_length=resolved_settings.password_max_length,
        )
        authentication = AuthenticationService(
            repository=SQLAlchemyAuthenticationRepository(session_factory),
            security_events=SQLAlchemySecurityEventWriter(session_factory),
            password_service=Argon2PasswordService(password_policy),
            token_service=SessionTokenService(
                resolved_settings.session_hmac_key.get_secret_value(),
                session_token_bytes=resolved_settings.session_token_bytes,
                csrf_token_bytes=resolved_settings.csrf_token_bytes,
            ),
            idle_timeout_seconds=resolved_settings.session_idle_timeout_seconds,
            absolute_timeout_seconds=resolved_settings.session_absolute_timeout_seconds,
            rotation_interval_seconds=resolved_settings.session_rotation_interval_seconds,
            max_failed_attempts=resolved_settings.login_max_failed_attempts,
            lockout_seconds=resolved_settings.login_lockout_seconds,
            rate_limit_attempts=resolved_settings.login_rate_limit_attempts,
            rate_limit_window_seconds=resolved_settings.login_rate_limit_window_seconds,
        )
        application.state.authentication = authentication
        administration = SQLAlchemyAdministrationService(
            session_factory,
            Argon2PasswordService(password_policy),
            SQLAlchemyFunctionalAuditWriter(),
        )
        authorization = SQLAlchemyAuthorizationService(session_factory)
        application.state.authorization = authorization
        application.include_router(
            build_admin_router(
                authentication,
                authorization,
                administration,
                SQLAlchemySecurityEventWriter(session_factory),
                resolved_settings,
            )
        )
        application.add_middleware(
            ForcedPasswordChangeMiddleware,
            service=authentication,
            cookie_name=resolved_settings.session_cookie_name,
        )
        application.include_router(build_auth_router(authentication, resolved_settings))
    application.add_middleware(CorrelationIdMiddleware)
    install_error_handlers(application)
    application.include_router(health_router)
    return application
