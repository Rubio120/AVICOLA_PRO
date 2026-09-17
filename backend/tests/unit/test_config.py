from __future__ import annotations

import pytest
from pydantic import ValidationError

from avicola_pro.shared.infrastructure.config import Environment, Settings

VALID_DATABASE_URL = "postgresql+psycopg://avicola:local-password@127.0.0.1:5432/avicola_pro"
VALID_SESSION_HMAC_KEY = "test-session-hmac-key-that-is-long-enough-for-security"


def test_local_settings_accept_postgresql_and_apply_business_defaults() -> None:
    settings = Settings(
        _env_file=None,
        environment=Environment.LOCAL,
        database_url=VALID_DATABASE_URL,
        session_hmac_key=VALID_SESSION_HMAC_KEY,
    )

    assert settings.environment is Environment.LOCAL
    assert settings.timezone == "America/Asuncion"
    assert settings.base_currency == "PYG"


def test_settings_provide_safe_opaque_session_and_authentication_defaults() -> None:
    """A weakened cookie, token, password, or login-throttling default is a security bug."""
    settings = Settings(
        _env_file=None,
        environment=Environment.LOCAL,
        database_url=VALID_DATABASE_URL,
        session_hmac_key=VALID_SESSION_HMAC_KEY,
    )

    assert settings.session_cookie_name == "avicola_session"
    assert settings.session_cookie_http_only is True
    assert settings.session_cookie_secure is False
    assert settings.session_cookie_samesite == "lax"
    assert settings.session_idle_timeout_seconds == 1_800
    assert settings.session_absolute_timeout_seconds == 28_800
    assert settings.session_rotation_interval_seconds == 900
    assert settings.session_token_bytes == 32
    assert settings.session_token_entropy_bits == 256
    assert settings.csrf_token_bytes == 32
    assert settings.password_min_length == 12
    assert settings.password_max_length == 128
    assert settings.login_max_failed_attempts == 5
    assert settings.login_lockout_seconds == 900
    assert settings.login_rate_limit_attempts == 5
    assert settings.login_rate_limit_window_seconds == 60


@pytest.mark.parametrize("environment", [Environment.STAGING, Environment.PRODUCTION])
def test_nonlocal_settings_require_a_strong_nonplaceholder_hmac_key_and_secure_cookie(
    environment: Environment,
) -> None:
    """Accepting a placeholder HMAC key or insecure session cookie enables session forgery or theft."""
    with pytest.raises(ValidationError, match="session_cookie_secure"):
        Settings(
            _env_file=None,
            environment=environment,
            database_url=VALID_DATABASE_URL,
            cors_origins=["https://avicola.example"],
            log_format="json",
            session_hmac_key="placeholder-session-hmac-key-that-is-long-enough",
        )

    with pytest.raises(ValidationError, match="session_hmac_key"):
        Settings(
            _env_file=None,
            environment=environment,
            database_url=VALID_DATABASE_URL,
            cors_origins=["https://avicola.example"],
            log_format="json",
            session_cookie_secure=True,
            session_hmac_key="too-short",
        )

    with pytest.raises(ValidationError, match="session_hmac_key"):
        Settings(
            _env_file=None,
            environment=environment,
            database_url=VALID_DATABASE_URL,
            cors_origins=["https://avicola.example"],
            log_format="json",
            session_cookie_secure=True,
            session_hmac_key="placeholder-session-hmac-key-that-is-long-enough",
        )


def test_settings_reject_inconsistent_session_lifetimes_and_token_entropy() -> None:
    """Allowing a rotation beyond idle expiry or insufficient entropy weakens the opaque-session contract."""
    with pytest.raises(ValidationError, match="session_rotation_interval_seconds"):
        Settings(
            _env_file=None,
            database_url=VALID_DATABASE_URL,
            session_hmac_key=VALID_SESSION_HMAC_KEY,
            session_idle_timeout_seconds=900,
            session_rotation_interval_seconds=901,
        )

    with pytest.raises(ValidationError, match="session_token_entropy_bits"):
        Settings(
            _env_file=None,
            database_url=VALID_DATABASE_URL,
            session_hmac_key=VALID_SESSION_HMAC_KEY,
            session_token_bytes=32,
            session_token_entropy_bits=255,
        )


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
            session_hmac_key=VALID_SESSION_HMAC_KEY,
            cors_origins=["https://avicola.example"],
        )


def test_production_settings_reject_placeholder_credentials() -> None:
    with pytest.raises(ValidationError, match="placeholder"):
        Settings(
            _env_file=None,
            environment=Environment.PRODUCTION,
            database_url="postgresql+psycopg://avicola:local-development-only@db/avicola",
            session_hmac_key=VALID_SESSION_HMAC_KEY,
            session_cookie_secure=True,
            cors_origins=["https://avicola.example"],
            log_format="json",
        )


def test_production_settings_reject_wildcard_cors() -> None:
    with pytest.raises(ValidationError, match="wildcard"):
        Settings(
            _env_file=None,
            environment=Environment.PRODUCTION,
            database_url=VALID_DATABASE_URL,
            session_hmac_key=VALID_SESSION_HMAC_KEY,
            cors_origins=["*"],
            log_format="json",
        )


def test_production_settings_require_json_logs() -> None:
    with pytest.raises(ValidationError, match="JSON"):
        Settings(
            _env_file=None,
            environment=Environment.PRODUCTION,
            database_url=VALID_DATABASE_URL,
            session_hmac_key=VALID_SESSION_HMAC_KEY,
            cors_origins=["https://avicola.example"],
            log_format="console",
        )


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql+psycopg://avicola:password@db-host",
        "postgresql+psycopg://:password@db-host/avicola",
        "postgresql+psycopg://avicola@db-host/avicola",
        "postgresql+psycopg:///avicola",
    ],
)
def test_production_settings_require_complete_database_coordinates(database_url: str) -> None:
    with pytest.raises(ValidationError, match="host, database, username, and password"):
        Settings(
            _env_file=None,
            environment=Environment.PRODUCTION,
            database_url=database_url,
            session_hmac_key=VALID_SESSION_HMAC_KEY,
            session_cookie_secure=True,
            cors_origins=["https://avicola.example"],
            log_format="json",
        )


def test_database_credentials_are_redacted_from_repr() -> None:
    settings = Settings(
        _env_file=None,
        database_url=VALID_DATABASE_URL,
        session_hmac_key=VALID_SESSION_HMAC_KEY,
    )

    assert "local-password" not in repr(settings)
