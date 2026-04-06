"""Platform-wide configuration using pydantic-settings."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class EventBusBackend(StrEnum):
    MEMORY = "memory"
    REDIS = "redis"
    NATS = "nats"


class LLMProviderConfig(BaseSettings):
    """Configuration for a single LLM provider."""

    model_config = SettingsConfigDict(extra="ignore")

    name: str
    api_key: SecretStr = SecretStr("")
    base_url: str = ""
    model: str = "gpt-4o-mini"
    max_tokens: int = 4096
    temperature: float = 0.1
    priority: int = 0
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    timeout_seconds: float = 30.0
    enabled: bool = True


class TelegramConfig(BaseSettings):
    """Telegram bot configuration."""

    model_config = SettingsConfigDict(env_prefix="TELEGRAM_")

    bot_token: SecretStr = SecretStr("")
    webhook_url: str = ""
    webhook_secret: SecretStr = SecretStr("")
    rate_limit_messages: int = 30
    rate_limit_window_seconds: int = 60


class RedisConfig(BaseSettings):
    """Redis connection configuration."""

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    url: str = "redis://localhost:6379/0"
    max_connections: int = 20


class NatsConfig(BaseSettings):
    """NATS connection configuration."""

    model_config = SettingsConfigDict(env_prefix="NATS_")

    url: str = "nats://localhost:4222"
    max_reconnect_attempts: int = 10


class VclawSettings(BaseSettings):
    """Root settings for the Vclaw platform."""

    model_config = SettingsConfigDict(
        env_prefix="VCLAW_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8080

    event_bus_backend: EventBusBackend = EventBusBackend.MEMORY
    agent_plugin_dirs: list[str] = Field(default_factory=lambda: ["plugins"])
    agent_scan_entrypoints: bool = True

    max_concurrent_agents: int = 10
    agent_timeout_seconds: float = 60.0
    orchestrator_max_retries: int = 3

    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    nats: NatsConfig = Field(default_factory=NatsConfig)

    llm_providers: list[dict[str, Any]] = Field(default_factory=list)

    otel_service_name: str = "vclaw"
    otel_exporter_endpoint: str = ""

    def get_llm_provider_configs(self) -> list[LLMProviderConfig]:
        return [LLMProviderConfig(**p) for p in self.llm_providers]
