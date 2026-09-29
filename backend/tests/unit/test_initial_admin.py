from __future__ import annotations

from types import TracebackType
from typing import Self, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from avicola_pro.bootstrap.initial_admin import InitialAdministratorBootstrapper
from avicola_pro.modules.identity.application.bootstrap import (
    BootstrapAlreadyCompletedError,
    BootstrapIdentity,
)
from avicola_pro.modules.identity.application.credentials import Argon2PasswordService, PasswordPolicy


class _Transaction:
    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


class _Role:
    def __init__(self, role_id: UUID) -> None:
        self.id = role_id


class _ExistingAdministratorSession:
    def __init__(self) -> None:
        self._scalar_results = iter((_Role(uuid4()), uuid4(), None))

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    def begin(self) -> _Transaction:
        return _Transaction()

    async def execute(self, statement: object, parameters: object) -> None:
        del statement, parameters

    async def scalar(self, statement: object) -> object:
        del statement
        return next(self._scalar_results)

    def add(self, instance: object) -> None:
        raise AssertionError(f"bootstrap tried to persist {instance!r}")

    async def flush(self) -> None:
        raise AssertionError("bootstrap tried to flush")


class _ExistingAdministratorSessionFactory:
    def __call__(self) -> _ExistingAdministratorSession:
        return _ExistingAdministratorSession()


@pytest.mark.asyncio
async def test_existing_administrator_does_not_invoke_temporary_password_generator() -> None:
    policy = PasswordPolicy(min_length=12, max_length=128)
    generator_calls = 0

    def unexpected_generator(password_policy: PasswordPolicy) -> str:
        nonlocal generator_calls
        generator_calls += 1
        raise AssertionError(f"generator invoked with {password_policy!r}")

    bootstrapper = InitialAdministratorBootstrapper(
        session_factory=cast(
            async_sessionmaker[AsyncSession],
            _ExistingAdministratorSessionFactory(),
        ),
        password_service=Argon2PasswordService(policy, time_cost=1, memory_cost_kib=8_192, parallelism=1),
        password_policy=policy,
        temporary_password_generator=unexpected_generator,
    )

    with pytest.raises(BootstrapAlreadyCompletedError):
        await bootstrapper.create(
            BootstrapIdentity.from_input(
                username="second.admin",
                email="second.admin@example.test",
                display_name="Second Administrator",
            )
        )

    assert generator_calls == 0
