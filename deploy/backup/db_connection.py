from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

ALLOWED_OPTIONS = {
    "application_name",
    "channel_binding",
    "connect_timeout",
    "gssencmode",
    "sslcert",
    "sslcrl",
    "sslcrldir",
    "sslkey",
    "sslmode",
    "sslrootcert",
    "target_session_attrs",
}
INTEGER_OPTIONS = {"connect_timeout", "port"}


class DatabaseUrlError(ValueError):
    pass


def read_secret_file(path_variable: str, target_variable: str, environ: dict[str, str] | None = None) -> str:
    environment = os.environ if environ is None else environ
    path = environment.get(path_variable)
    if not path:
        raise DatabaseUrlError(f"Required file setting is missing: {path_variable}")
    try:
        value = Path(path).read_text(encoding="utf-8").rstrip("\r\n")
    except OSError:
        raise DatabaseUrlError(f"Required file is unavailable: {path_variable}") from None
    if not value or "\n" in value or "\r" in value:
        raise DatabaseUrlError(f"Required file is empty or malformed: {path_variable}")
    environment[target_variable] = value
    return value


def _service_value(name: str, value: str) -> str:
    if "\n" in value or "\r" in value:
        raise DatabaseUrlError("Database connection setting contains a line break")
    if value and value[-1].isspace():
        raise DatabaseUrlError("Database connection setting has trailing whitespace")
    if name in INTEGER_OPTIONS and (not value.isascii() or not value.isdecimal() or int(value) > 2_147_483_647):
        raise DatabaseUrlError(f"Invalid integer database connection setting: {name}")
    return value


def service_section(service_name: str, database_url: str) -> str:
    parsed = urlsplit(database_url)
    if parsed.scheme != "postgresql+psycopg" or not parsed.hostname or not parsed.path.strip("/"):
        raise DatabaseUrlError("Database URL must identify a PostgreSQL host and database")
    try:
        port = parsed.port or 5432
    except ValueError:
        raise DatabaseUrlError("Database URL has an invalid port") from None
    username = unquote(parsed.username or "")
    password = unquote(parsed.password or "")
    database = unquote(parsed.path.lstrip("/"))
    if not username or not password or not database:
        raise DatabaseUrlError("Database URL must include username, password and database")

    values = {
        "host": parsed.hostname,
        "port": str(port),
        "user": username,
        "password": password,
        "dbname": database,
    }
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if key not in ALLOWED_OPTIONS:
            raise DatabaseUrlError(f"Unsupported libpq option: {key}")
        values[key] = value
    if not service_name.replace("_", "").isalnum():
        raise DatabaseUrlError("Invalid PostgreSQL service name")
    lines = [f"[{service_name}]"]
    lines.extend(f"{key}={_service_value(key, value)}" for key, value in values.items())
    return "\n".join(lines)


def write_service_file(path: Path, services: dict[str, str]) -> None:
    content = "\n\n".join(service_section(name, url) for name, url in services.items()) + "\n"
    path.write_text(content, encoding="utf-8")
    path.chmod(0o600)
