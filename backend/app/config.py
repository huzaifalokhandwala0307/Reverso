from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application settings
    APP_NAME: str = "BlackBoxRAG API"
    APP_ENV: str = "development"
    DEBUG: bool = False
    HOST: str = "[IP_ADDRESS]"
    PORT: int = 8000

    # Database settings
    # Default SQLite for lightweight local runs/tests, Postgres for production/compose
    DATABASE_URL: str = Field(
        default="sqlite:///./blackboxrag.db",
        description="SQLAlchemy database connection URL",
    )
    TEST_DATABASE_URL: str | None = Field(
        default=None,
        description="Optional database URL specifically for tests",
    )


settings = Settings()
