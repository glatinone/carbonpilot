"""Application configuration.

Secrets live in `.env` only (never config files). See `.env.example`.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(__file__).resolve().parent / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "CarbonPilot API"
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'carbonpilot.db').as_posix()}"

    # Gemini (Google AI Studio). Either var name works; GEMINI_API_KEY wins.
    gemini_api_key: str = ""
    google_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # Refuse to boot when the LLM path must be live (e.g. a demo where the
    # offline fallback would only be discovered on stage). The field name alone
    # maps to REQUIRE_LLM; the alias accepts the documented CARBONPILOT_ name
    # too, case-insensitively.
    require_llm: bool = Field(
        default=False,
        validation_alias=AliasChoices("CARBONPILOT_REQUIRE_LLM", "require_llm"),
    )

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def llm_key(self) -> str:
        return (self.gemini_api_key or self.google_api_key).strip()

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_key)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
