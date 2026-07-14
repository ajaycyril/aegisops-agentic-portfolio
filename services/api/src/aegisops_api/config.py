from functools import lru_cache
from pathlib import Path

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="local", validation_alias="APP_ENV")
    public_app_url: AnyHttpUrl | None = Field(default=None, validation_alias="PUBLIC_APP_URL")
    api_base_url: AnyHttpUrl | None = Field(default=None, validation_alias="API_BASE_URL")
    database_url: str | None = Field(default=None, validation_alias="DATABASE_URL")
    redis_url: str | None = Field(default=None, validation_alias="REDIS_URL")
    opa_base_url: AnyHttpUrl | None = Field(default=None, validation_alias="OPA_BASE_URL")
    workflow_config_dir: Path | None = Field(default=None, validation_alias="WORKFLOW_CONFIG_DIR")
    configured_connectors: str = Field(default="", validation_alias="CONFIGURED_CONNECTORS")
    max_agent_run_seconds: int = Field(default=300, validation_alias="MAX_AGENT_RUN_SECONDS")
    max_agent_tool_calls: int = Field(default=25, validation_alias="MAX_AGENT_TOOL_CALLS")
    max_agent_estimated_usd: float = Field(default=1.0, validation_alias="MAX_AGENT_ESTIMATED_USD")
    require_human_approval: bool = Field(default=True, validation_alias="REQUIRE_HUMAN_APPROVAL")


@lru_cache
def get_settings() -> Settings:
    return Settings()
