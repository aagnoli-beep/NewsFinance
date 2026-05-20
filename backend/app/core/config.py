from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    env: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000"
    cors_origin_regex: str = ""

    database_url: str = Field(default="postgresql+asyncpg://localhost/newsfinance")
    redis_url: str = Field(default="redis://localhost:6379/0")

    anthropic_api_key: str = ""
    voyage_api_key: str = ""

    polygon_api_key: str = ""
    marketaux_api_key: str = ""
    finnhub_api_key: str = ""
    fred_api_key: str = ""

    resend_api_key: str = ""
    auth_secret: str = "change-me"
    allowed_email: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
