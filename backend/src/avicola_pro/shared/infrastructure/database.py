from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Protocol

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from avicola_pro.shared.infrastructure.config import Settings


class Database(Protocol):
    async def check_ready(self) -> None: ...

    async def dispose(self) -> None: ...


class DatabaseResources:
    def __init__(self, settings: Settings) -> None:
        self._command_timeout = settings.database_command_timeout_seconds
        self.engine: AsyncEngine = create_async_engine(
            settings.database_url.get_secret_value(),
            pool_pre_ping=True,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_timeout=settings.database_pool_timeout_seconds,
        )
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    async def check_ready(self) -> None:
        async with asyncio.timeout(self._command_timeout):
            async with self.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.session_factory() as session:
            try:
                yield session
            except BaseException:
                await session.rollback()
                raise

    async def dispose(self) -> None:
        await self.engine.dispose()


def create_database_resources(settings: Settings) -> DatabaseResources:
    return DatabaseResources(settings)
