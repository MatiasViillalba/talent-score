"""Application settings, loaded and validated from the environment."""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly typed application configuration.

    Every field without a default is a required environment variable;
    Pydantic raises a ``ValidationError`` at startup if it is missing,
    so the process fails fast instead of crashing later on first use.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Core
    ENVIRONMENT: Literal["development", "test", "staging", "production"] = "development"
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    # Database
    DATABASE_URL: str

    # Redis / Celery
    REDIS_URL: str
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

    # Anthropic
    ANTHROPIC_API_KEY: str
    RESUME_PARSER_MODEL: str = "claude-sonnet-4-6"

    # Stripe
    STRIPE_API_KEY: str
    STRIPE_WEBHOOK_SECRET: str

    # Email
    SMTP_HOST: str
    SMTP_PORT: int = 1025

    # Business rules
    DEFAULT_MONTHLY_CV_QUOTA: int = 100
    HIGH_MATCH_THRESHOLD: int = 80
    REPORTS_RETENTION_DAYS: int = 30
    STORAGE_DIR: str = "storage"
    CORS_ALLOWED_ORIGINS: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    @field_validator("CORS_ALLOWED_ORIGINS", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: str | list[str]) -> str | list[str]:
        """Split the comma-separated origin list coming from the environment.

        The field is annotated with ``NoDecode`` because pydantic-settings
        otherwise JSON-decodes complex types inside the environment source,
        which fails before any validator runs.

        Args:
            value: The raw value from the environment or a default list.

        Returns:
            A list of origin strings, or the original list unchanged.
        """
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide cached ``Settings`` instance.

    Returns:
        The validated application settings, built once per process.
    """
    return Settings()
