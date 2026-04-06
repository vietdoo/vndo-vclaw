"""Tests for the Kafka event bus (unit tests using mocks — no real broker needed)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from vclaw.domain.events import CloudEvent, EventTypes
from vclaw.infrastructure.event_bus.kafka_bus import KafkaEventBus


@pytest.fixture
def kafka_bus() -> KafkaEventBus:
    return KafkaEventBus(
        bootstrap_servers="localhost:9092",
        consumer_group="test",
        topic_prefix="test.",
    )


def test_topic_name(kafka_bus: KafkaEventBus) -> None:
    assert kafka_bus._topic_name("vclaw.message.received") == "test.vclaw-message-received"


@pytest.mark.asyncio
async def test_subscribe_adds_handler(kafka_bus: KafkaEventBus) -> None:
    handler = AsyncMock()
    await kafka_bus.subscribe(EventTypes.MESSAGE_RECEIVED, handler)
    assert EventTypes.MESSAGE_RECEIVED in kafka_bus._handlers
    assert handler in kafka_bus._handlers[EventTypes.MESSAGE_RECEIVED]


@pytest.mark.asyncio
async def test_unsubscribe_removes_handler(kafka_bus: KafkaEventBus) -> None:
    handler = AsyncMock()
    await kafka_bus.subscribe(EventTypes.MESSAGE_RECEIVED, handler)
    await kafka_bus.unsubscribe(EventTypes.MESSAGE_RECEIVED, handler)
    assert handler not in kafka_bus._handlers[EventTypes.MESSAGE_RECEIVED]


@pytest.mark.asyncio
async def test_publish_without_producer_logs_error(kafka_bus: KafkaEventBus) -> None:
    event = CloudEvent(type=EventTypes.MESSAGE_RECEIVED, data={"text": "hi"})
    await kafka_bus.publish(event)


@pytest.mark.asyncio
async def test_process_message_calls_handlers(kafka_bus: KafkaEventBus) -> None:
    received: list[CloudEvent] = []

    async def handler(event: CloudEvent) -> None:
        received.append(event)

    kafka_bus._handlers[EventTypes.MESSAGE_RECEIVED].append(handler)

    event = CloudEvent(type=EventTypes.MESSAGE_RECEIVED, data={"text": "test"})
    await kafka_bus._process_message(
        EventTypes.MESSAGE_RECEIVED, event.model_dump(mode="json")
    )

    assert len(received) == 1
    assert received[0].data["text"] == "test"


@pytest.mark.asyncio
async def test_process_message_handler_error_goes_to_dlq(kafka_bus: KafkaEventBus) -> None:
    async def bad_handler(event: CloudEvent) -> None:
        raise ValueError("boom")

    kafka_bus._handlers[EventTypes.MESSAGE_RECEIVED].append(bad_handler)

    mock_producer = AsyncMock()
    kafka_bus._producer = mock_producer

    event = CloudEvent(type=EventTypes.MESSAGE_RECEIVED, data={})
    await kafka_bus._process_message(
        EventTypes.MESSAGE_RECEIVED, event.model_dump(mode="json")
    )

    mock_producer.send_and_wait.assert_called_once()


@pytest.mark.asyncio
async def test_stop_without_start(kafka_bus: KafkaEventBus) -> None:
    await kafka_bus.stop()
