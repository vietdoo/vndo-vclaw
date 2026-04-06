"""Tests for configuration models."""

from __future__ import annotations

from vclaw.config import (
    EventBusBackend,
    KafkaConfig,
    PersistenceBackend,
    PostgresConfig,
    VclawSettings,
)


def test_kafka_config_defaults() -> None:
    cfg = KafkaConfig()
    assert cfg.bootstrap_servers == "localhost:9092"
    assert cfg.consumer_group == "vclaw"
    assert cfg.topic_prefix == "vclaw."


def test_postgres_config_defaults() -> None:
    cfg = PostgresConfig()
    assert "vclaw" in cfg.dsn
    assert cfg.min_pool_size == 5
    assert cfg.max_pool_size == 20


def test_event_bus_backend_has_kafka() -> None:
    assert EventBusBackend.KAFKA == "kafka"


def test_persistence_backend_enum() -> None:
    assert PersistenceBackend.MEMORY == "memory"
    assert PersistenceBackend.POSTGRES == "postgres"


def test_vclaw_settings_includes_kafka_and_postgres() -> None:
    settings = VclawSettings()
    assert hasattr(settings, "kafka")
    assert hasattr(settings, "postgres")
    assert settings.enable_event_logging is True
    assert settings.persistence_backend == "memory"
