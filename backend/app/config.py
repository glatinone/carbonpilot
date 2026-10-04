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

    # Endpoint override, for a gateway or proxy that speaks the Gemini API.
    #
    # This has to be accepted *here* even though the google-genai SDK reads
    # GOOGLE_GEMINI_BASE_URL from the process environment itself: pydantic-settings
    # only loads keys that map to a field, so a value that lives solely in .env
    # never reaches os.environ, the SDK falls back to Google's own endpoint, and a
    # gateway key is then rejected as invalid — the agent degrades to the
    # deterministic router and the only visible symptom is a quiet fallback.
    # Declaring it makes it loaded; gemini_agent exports it before building the
    # client. Verified against google-genai 1.75.0 (_base_url.get_base_url).
    gemini_base_url: str = Field(
        default="",
        validation_alias=AliasChoices("GOOGLE_GEMINI_BASE_URL", "gemini_base_url"),
    )

    # Refuse to boot when the LLM path must be live (e.g. a demo where the
    # offline fallback would only be discovered on stage). The field name alone
    # maps to REQUIRE_LLM; the alias accepts the documented CARBONPILOT_ name
    # too, case-insensitively.
    require_llm: bool = Field(
        default=False,
        validation_alias=AliasChoices("CARBONPILOT_REQUIRE_LLM", "require_llm"),
    )

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Climatiq (optional, secret). When a key is set the agent can corroborate a
    # curated factor against the live published one and cite it. The curated
    # library stays the calculation source of truth, so a rehearsed demo cannot
    # move because a third party changed a number.
    climatiq_api_key: str = ""
    climatiq_base_url: str = "https://api.climatiq.io"
    climatiq_data_version: str = "^33"
    climatiq_timeout_s: float = 8.0

    @property
    def climatiq_enabled(self) -> bool:
        return bool(self.climatiq_api_key.strip())

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
