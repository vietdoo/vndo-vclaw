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
    KAFKA = "kafka"


class PersistenceBackend(StrEnum):
    MEMORY = "memory"
    POSTGRES = "postgres"


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


class KafkaConfig(BaseSettings):
    """Kafka connection configuration."""

    model_config = SettingsConfigDict(env_prefix="KAFKA_")

    bootstrap_servers: str = "localhost:9092"
    consumer_group: str = "vclaw"
    topic_prefix: str = "vclaw."
    auto_offset_reset: str = "earliest"
    max_concurrent: int = 50


class PostgresConfig(BaseSettings):
    """PostgreSQL connection configuration."""

    model_config = SettingsConfigDict(env_prefix="POSTGRES_")

    dsn: str = "postgresql://vclaw:vclaw@localhost:5432/vclaw"
    min_pool_size: int = 5
    max_pool_size: int = 20


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
    persistence_backend: str = "memory"
    agent_plugin_dirs: list[str] = Field(default_factory=lambda: ["plugins"])
    agent_scan_entrypoints: bool = True

    max_concurrent_agents: int = 10
    agent_timeout_seconds: float = 60.0
    orchestrator_max_retries: int = 3

    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    kafka: KafkaConfig = Field(default_factory=KafkaConfig)
    postgres: PostgresConfig = Field(default_factory=PostgresConfig)

    enable_event_logging: bool = True

    llm_providers: list[dict[str, Any]] = Field(default_factory=list)

    otel_service_name: str = "vclaw"
    otel_exporter_endpoint: str = ""

    def get_llm_provider_configs(self) -> list[LLMProviderConfig]:
        return [LLMProviderConfig(**p) for p in self.llm_providers]
