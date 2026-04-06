"""Platform configuration via environment variables with Pydantic v2 Settings."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings


class RedisConfig(BaseSettings):
    host: str = Field(default="localhost", alias="REDIS_HOST")
    port: int = Field(default=6379, alias="REDIS_PORT")
    password: SecretStr | None = Field(default=None, alias="REDIS_PASSWORD")
    db: int = Field(default=0, alias="REDIS_DB")
    max_connections: int = Field(default=20, alias="REDIS_MAX_CONNECTIONS")
    stream_prefix: str = Field(default="vclaw:stream", alias="REDIS_STREAM_PREFIX")
    consumer_group: str = Field(default="vclaw-workers", alias="REDIS_CONSUMER_GROUP")

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def url(self) -> str:
        if self.password:
            return f"redis://:{self.password.get_secret_value()}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


class TelegramConfig(BaseSettings):
    bot_token: SecretStr = Field(alias="TELEGRAM_BOT_TOKEN")
    webhook_url: str | None = Field(default=None, alias="TELEGRAM_WEBHOOK_URL")
    webhook_secret: SecretStr | None = Field(default=None, alias="TELEGRAM_WEBHOOK_SECRET")
    polling_timeout: int = Field(default=30, alias="TELEGRAM_POLLING_TIMEOUT")
    max_connections: int = Field(default=40, alias="TELEGRAM_MAX_CONNECTIONS")
    allowed_updates: list[str] = Field(
        default=["message", "callback_query", "inline_query"],
        alias="TELEGRAM_ALLOWED_UPDATES",
    )

    model_config = {"env_file": ".env", "extra": "ignore"}


class LLMProviderConfig(BaseSettings):
    openrouter_api_key: SecretStr | None = Field(default=None, alias="OPENROUTER_API_KEY")
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1", alias="OPENROUTER_BASE_URL"
    )
    openrouter_free_model: str = Field(
        default="mistralai/mistral-7b-instruct:free", alias="OPENROUTER_FREE_MODEL"
    )

    anthropic_api_key: SecretStr | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(
        default="claude-3-5-haiku-20241022", alias="ANTHROPIC_MODEL"
    )

    openai_api_key: SecretStr | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")

    # Cost-aware routing priority (first = cheapest/preferred)
    provider_priority: list[str] = Field(
        default=["openrouter_free", "anthropic", "openai"],
        alias="LLM_PROVIDER_PRIORITY",
    )
    max_retries_per_provider: int = Field(default=2, alias="LLM_MAX_RETRIES_PER_PROVIDER")
    request_timeout_seconds: int = Field(default=30, alias="LLM_REQUEST_TIMEOUT")

    model_config = {"env_file": ".env", "extra": "ignore"}


class OrchestratorConfig(BaseSettings):
    max_concurrent_tasks: int = Field(default=50, alias="ORCH_MAX_CONCURRENT_TASKS")
    task_timeout_seconds: int = Field(default=120, alias="ORCH_TASK_TIMEOUT")
    max_subtask_depth: int = Field(default=3, alias="ORCH_MAX_SUBTASK_DEPTH")
    result_aggregation_timeout: int = Field(default=30, alias="ORCH_AGGREGATION_TIMEOUT")
    idempotency_ttl_seconds: int = Field(default=86400, alias="ORCH_IDEMPOTENCY_TTL")

    model_config = {"env_file": ".env", "extra": "ignore"}


class ObservabilityConfig(BaseSettings):
    otel_endpoint: str | None = Field(default=None, alias="OTEL_EXPORTER_OTLP_ENDPOINT")
    otel_service_name: str = Field(default="vclaw-platform", alias="OTEL_SERVICE_NAME")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", alias="LOG_LEVEL"
    )
    log_format: Literal["json", "text"] = Field(default="json", alias="LOG_FORMAT")

    model_config = {"env_file": ".env", "extra": "ignore"}


class AgentConfig(BaseSettings):
    plugin_dirs: list[str] = Field(
        default=["vclaw/agents"], alias="AGENT_PLUGIN_DIRS"
    )
    health_check_interval_seconds: int = Field(default=30, alias="AGENT_HEALTH_CHECK_INTERVAL")
    max_agent_instances: int = Field(default=10, alias="AGENT_MAX_INSTANCES")

    model_config = {"env_file": ".env", "extra": "ignore"}

    @field_validator("plugin_dirs", mode="before")
    @classmethod
    def parse_plugin_dirs(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [d.strip() for d in v.split(",")]
        return v


class Settings(BaseSettings):
    environment: Literal["development", "staging", "production"] = Field(
        default="development", alias="ENVIRONMENT"
    )
    debug: bool = Field(default=False, alias="DEBUG")
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    api_workers: int = Field(default=4, alias="API_WORKERS")

    redis: RedisConfig = Field(default_factory=RedisConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    llm: LLMProviderConfig = Field(default_factory=LLMProviderConfig)
    orchestrator: OrchestratorConfig = Field(default_factory=OrchestratorConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    agents: AgentConfig = Field(default_factory=AgentConfig)

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
