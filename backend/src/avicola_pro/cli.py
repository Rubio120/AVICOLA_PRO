from __future__ import annotations

import asyncio
import selectors
import sys
from typing import Annotated

import typer
from sqlalchemy.exc import SQLAlchemyError

from avicola_pro.bootstrap.initial_admin import InitialAdministratorBootstrapper
from avicola_pro.modules.identity.application.bootstrap import (
    BootstrapAlreadyCompletedError,
    BootstrapConfigurationError,
    BootstrapIdentity,
    BootstrapResult,
)
from avicola_pro.modules.identity.application.credentials import Argon2PasswordService, PasswordPolicy
from avicola_pro.shared.infrastructure.config import get_settings
from avicola_pro.shared.infrastructure.database import create_database_resources

app = typer.Typer(help="Herramientas operativas seguras de AVÍCOLA PRO.", no_args_is_help=True)


@app.callback()
def cli() -> None:
    """Expose grouped operational commands."""


async def _create_initial_administrator(identity: BootstrapIdentity) -> BootstrapResult:
    settings = get_settings()
    resources = create_database_resources(settings)
    policy = PasswordPolicy(settings.password_min_length, settings.password_max_length)
    bootstrapper = InitialAdministratorBootstrapper(
        session_factory=resources.session_factory,
        password_service=Argon2PasswordService(policy),
        password_policy=policy,
    )
    try:
        return await bootstrapper.create(identity)
    finally:
        await resources.dispose()


def _run_bootstrap(identity: BootstrapIdentity) -> BootstrapResult:
    if sys.platform == "win32":
        return asyncio.run(
            _create_initial_administrator(identity),
            loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()),
        )
    return asyncio.run(_create_initial_administrator(identity))


@app.command("bootstrap-admin")
def bootstrap_admin(
    username: Annotated[str, typer.Option(help="Nombre de usuario inicial.")],
    email: Annotated[str, typer.Option(help="Correo del administrador inicial.")],
    name: Annotated[str, typer.Option(help="Nombre visible del administrador inicial.")],
) -> None:
    """Create the first administrator and display its temporary password once."""
    try:
        identity = BootstrapIdentity.from_input(username=username, email=email, display_name=name)
    except ValueError:
        typer.echo("Los datos del administrador inicial no son válidos.", err=True)
        raise typer.Exit(code=2) from None

    try:
        result = _run_bootstrap(identity)
    except BootstrapAlreadyCompletedError:
        typer.echo("El bootstrap del administrador inicial ya fue realizado; no se modificó ningún dato.", err=True)
        raise typer.Exit(code=1) from None
    except BootstrapConfigurationError:
        typer.echo("No se puede realizar el bootstrap con la configuración actual.", err=True)
        raise typer.Exit(code=1) from None
    except (SQLAlchemyError, ValueError):
        typer.echo("No se pudo completar el bootstrap del administrador inicial.", err=True)
        raise typer.Exit(code=1) from None

    typer.echo("Administrador inicial creado.")
    typer.echo(f"Contraseña temporal: {result.temporary_password}")
    typer.echo("Guárdela ahora: no volverá a mostrarse y deberá cambiarse en el primer acceso.")
