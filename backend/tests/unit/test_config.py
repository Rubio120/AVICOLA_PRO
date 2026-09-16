from __future__ import annotations

import pytest
from pydantic import ValidationError

from avicola_pro.shared.infrastructure.config import Environment, Settings

VALID_DATABASE_URL = "postgresql+psycopg://avicola:local-password@127.0.0.1:5432/avicola_pro"


def test_local_settings_accept_postgresql_and_apply_business_defaults() -> None:
    settings = Settings(
        _env_file=None,
        environment=Environment.LOCAL,
        database_url=VALID_DATABASE_URL,
    )

    assert settings.environment is Environment.LOCAL
    assert settings.timezone == "America/Asuncion"
    assert settings.base_currency == "PYG"


def test_settings_reject_non_postgresql_database() -> None:
    with pytest.raises(ValidationError, match=r"postgresql\+psycopg"):
        Settings(_env_file=None, database_url="sqlite:///avicola.db")


def test_settings_forbid_unknown_environment_values() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        Settings(  # type: ignore[call-arg]
            _env_file=None,
            database_url=VALID_DATABASE_URL,
            unknown_setting="value",
        )


def test_production_settings_reject_debug() -> None:
    with pytest.raises(ValidationError, match="debug"):
        Settings(
            _env_file=None,
            environment=Environment.PRODUCTION,
            debug=True,
            database_url=VALID_DATABASE_URL,
            cors_origins=["https://avicola.example"],
        )


def test_production_settings_reject_placeholder_credentials() -> None:
    with pytest.raises(ValidationError, match="placeholder"):
        Settings(
            _env_file=None,
            environment=Environment.PRODUCTION,
            database_url="postgresql+psycopg://avicola:local-development-only@db/avicola",
            cors_origins=["https://avicola.example"],
        )


def test_production_settings_reject_wildcard_cors() -> None:
    with pytest.raises(ValidationError, match="wildcard"):
        Settings(
            _env_file=None,
            environment=Environment.PRODUCTION,
            database_url=VALID_DATABASE_URL,
            cors_origins=["*"],
        )


def test_production_settings_require_json_logs() -> None:
    with pytest.raises(ValidationError, match="JSON"):
        Settings(
            _env_file=None,
            environment=Environment.PRODUCTION,
            database_url=VALID_DATABASE_URL,
            cors_origins=["https://avicola.example"],
            log_format="console",
        )


def test_database_credentials_are_redacted_from_repr() -> None:
    settings = Settings(_env_file=None, database_url=VALID_DATABASE_URL)

    assert "local-password" not in repr(settings)
