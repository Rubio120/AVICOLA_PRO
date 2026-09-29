from __future__ import annotations

import logging
import sys

import structlog

from avicola_pro.shared.infrastructure.config import LogFormat, Settings


def configure_logging(settings: Settings) -> None:
    renderer: structlog.types.Processor = (
        structlog.dev.ConsoleRenderer(colors=False)
        if settings.log_format is LogFormat.CONSOLE
        else structlog.processors.JSONRenderer()
    )
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=settings.log_level, force=True)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.stdlib.add_log_level,
            renderer,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
