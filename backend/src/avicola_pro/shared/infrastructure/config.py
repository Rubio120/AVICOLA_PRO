from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Any, Literal, Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Environment(StrEnum):
    LOCAL = "local"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class LogFormat(StrEnum):
    CONSOLE = "console"
    JSON = "json"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="AVICOLA_",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="forbid",
    )

    app_name: str = "AVÍCOLA PRO API"
    environment: Environment = Environment.LOCAL
    debug: bool = False
    log_level: str = "INFO"
    log_format: LogFormat = LogFormat.CONSOLE
    database_url: SecretStr
    database_command_timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    database_pool_size: int = Field(default=5, ge=1, le=50)
    database_max_overflow: int = Field(default=5, ge=0, le=50)
    database_pool_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    timezone: str = "America/Asuncion"
    base_currency: str = "PYG"
    session_cookie_name: str = Field(default="avicola_session", min_length=1, max_length=64)
    session_cookie_http_only: Literal[True] = True
    session_cookie_secure: bool = False
    session_cookie_samesite: Literal["lax"] = "lax"
    session_cookie_path: str = "/"
    session_idle_timeout_seconds: int = Field(default=1_800, ge=300, le=86_400)
    session_absolute_timeout_seconds: int = Field(default=28_800, ge=1_800, le=604_800)
    session_rotation_interval_seconds: int = Field(default=900, ge=60, le=86_400)
    session_token_bytes: int = Field(default=32, ge=32, le=64)
    session_token_entropy_bits: int = Field(default=256, ge=256, le=512, multiple_of=8)
    session_hmac_key: SecretStr
    csrf_token_bytes: int = Field(default=32, ge=32, le=64)
    password_min_length: int = Field(default=12, ge=12, le=128)
    password_max_length: int = Field(default=128, ge=12, le=256)
    login_max_failed_attempts: int = Field(default=5, ge=1, le=20)
    login_lockout_seconds: int = Field(default=900, ge=60, le=86_400)
    login_rate_limit_attempts: int = Field(default=5, ge=1, le=100)
    login_rate_limit_window_seconds: int = Field(default=60, ge=1, le=3_600)

    @field_validator("database_url", mode="before")
    @classmethod
    def validate_database_url(cls, value: Any) -> Any:
        raw_value = value.get_secret_value() if isinstance(value, SecretStr) else str(value)
        if not raw_value.startswith("postgresql+psycopg://"):
            raise ValueError("database_url must use postgresql+psycopg")
        return value

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("unsupported log level")
        return normalized

    @field_validator("session_cookie_path")
    @classmethod
    def validate_session_cookie_path(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("session_cookie_path must start with /")
        return value

    @field_validator("session_hmac_key")
    @classmethod
    def validate_session_hmac_key(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("session_hmac_key must contain at least 32 characters")
        return value

    @model_validator(mode="after")
    def validate_secure_environment(self) -> Self:
        if self.session_rotation_interval_seconds > self.session_idle_timeout_seconds:
            raise ValueError("session_rotation_interval_seconds must not exceed session_idle_timeout_seconds")
        if self.session_idle_timeout_seconds > self.session_absolute_timeout_seconds:
            raise ValueError("session_idle_timeout_seconds must not exceed session_absolute_timeout_seconds")
        if self.session_token_entropy_bits > self.session_token_bytes * 8:
            raise ValueError("session_token_entropy_bits cannot exceed session_token_bytes entropy")
        if self.password_min_length > self.password_max_length:
            raise ValueError("password_min_length must not exceed password_max_length")
        if self.environment not in {Environment.STAGING, Environment.PRODUCTION}:
            return self
        if self.debug:
            raise ValueError("debug must be disabled in staging and production")
        if self.log_format is not LogFormat.JSON:
            raise ValueError("JSON logging is required in staging and production")
        if "*" in self.cors_origins:
            raise ValueError("wildcard CORS origin is forbidden in staging and production")
        if not self.session_cookie_secure:
            raise ValueError("session_cookie_secure must be enabled in staging and production")
        hmac_key = self.session_hmac_key.get_secret_value().lower()
        insecure_hmac_markers = ("local-development-only", "placeholder", "changeme", "example")
        if any(marker in hmac_key for marker in insecure_hmac_markers):
            raise ValueError("session_hmac_key placeholder is forbidden in staging and production")
        database_value = self.database_url.get_secret_value().lower()
        database_url = make_url(database_value)
        if not all((database_url.host, database_url.database, database_url.username, database_url.password)):
            raise ValueError(
                "database_url must include host, database, username, and password in staging and production"
            )
        insecure_markers = ("local-development-only", "placeholder", "changeme")
        if any(marker in database_value for marker in insecure_markers):
            raise ValueError("placeholder database credentials are forbidden in staging and production")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
