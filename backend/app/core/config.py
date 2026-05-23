"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings.

    Reads from environment variables and a local ``.env`` file. Every external
    credential is optional — when missing, the corresponding service falls
    back to demo data so the application stays fully functional end-to-end.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # AWS Bedrock
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_region: str = "us-east-1"
    bedrock_model_id: str = "amazon.nova-pro-v1:0"

    # Datadog
    datadog_api_key: str | None = None
    datadog_app_key: str | None = None
    datadog_site: str = "datadoghq.com"

    # Grafana
    grafana_url: str | None = None
    grafana_api_key: str | None = None

    # New Relic
    new_relic_user_key: str | None = None
    new_relic_account_id: str | None = None

    # Slack webhook for auto-posting analyses (optional)
    slack_webhook_url: str | None = None

    # Server
    port: int = 8000
    cors_origins: List[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )
    log_level: str = "INFO"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    # ── Derived flags ──────────────────────────────────────────────────────

    @property
    def bedrock_enabled(self) -> bool:
        return bool(self.aws_access_key_id and self.aws_secret_access_key)

    @property
    def datadog_enabled(self) -> bool:
        return bool(self.datadog_api_key and self.datadog_app_key)

    @property
    def grafana_enabled(self) -> bool:
        return bool(self.grafana_url and self.grafana_api_key)

    @property
    def newrelic_enabled(self) -> bool:
        return bool(self.new_relic_user_key and self.new_relic_account_id)

    @property
    def slack_enabled(self) -> bool:
        return bool(self.slack_webhook_url)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a process-wide cached Settings instance."""
    return Settings()
