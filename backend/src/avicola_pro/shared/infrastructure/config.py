from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Any, Self

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

    @model_validator(mode="after")
    def validate_secure_environment(self) -> Self:
        if self.environment not in {Environment.STAGING, Environment.PRODUCTION}:
            return self
        if self.debug:
            raise ValueError("debug must be disabled in staging and production")
        if self.log_format is not LogFormat.JSON:
            raise ValueError("JSON logging is required in staging and production")
        if "*" in self.cors_origins:
            raise ValueError("wildcard CORS origin is forbidden in staging and production")
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
