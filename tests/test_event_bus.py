"""Tests for the in-memory event bus."""

from __future__ import annotations

import asyncio

import pytest

from vclaw.domain.events import CloudEvent, EventTypes
from vclaw.infrastructure.event_bus.memory import InMemoryEventBus


@pytest.mark.asyncio
async def test_publish_and_subscribe() -> None:
    bus = InMemoryEventBus()
    await bus.start()

    received: list[CloudEvent] = []

    async def handler(event: CloudEvent) -> None:
        received.append(event)

    await bus.subscribe(EventTypes.MESSAGE_RECEIVED, handler)

    event = CloudEvent(
        type=EventTypes.MESSAGE_RECEIVED,
        data={"text": "hello"},
    )
    await bus.publish(event)

    await asyncio.sleep(0.05)

    assert len(received) == 1
    assert received[0].data["text"] == "hello"
    assert received[0].type == EventTypes.MESSAGE_RECEIVED

    await bus.stop()


@pytest.mark.asyncio
async def test_unsubscribe() -> None:
    bus = InMemoryEventBus()
    await bus.start()

    received: list[CloudEvent] = []

    async def handler(event: CloudEvent) -> None:
        received.append(event)

    await bus.subscribe(EventTypes.MESSAGE_RECEIVED, handler)
    await bus.unsubscribe(EventTypes.MESSAGE_RECEIVED, handler)

    await bus.publish(CloudEvent(type=EventTypes.MESSAGE_RECEIVED, data={}))
    await asyncio.sleep(0.05)

    assert len(received) == 0
    await bus.stop()


@pytest.mark.asyncio
async def test_handler_error_goes_to_dlq() -> None:
    bus = InMemoryEventBus()
    await bus.start()

    async def bad_handler(event: CloudEvent) -> None:
        raise ValueError("test error")

    await bus.subscribe(EventTypes.MESSAGE_RECEIVED, bad_handler)

    await bus.publish(CloudEvent(type=EventTypes.MESSAGE_RECEIVED, data={}))
    await asyncio.sleep(0.1)

    assert len(bus.dlq) == 1
    assert "bad_handler" in bus.dlq[0][1]

    await bus.stop()


@pytest.mark.asyncio
async def test_no_publish_when_stopped() -> None:
    bus = InMemoryEventBus()

    received: list[CloudEvent] = []

    async def handler(event: CloudEvent) -> None:
        received.append(event)

    await bus.subscribe(EventTypes.MESSAGE_RECEIVED, handler)
    await bus.publish(CloudEvent(type=EventTypes.MESSAGE_RECEIVED, data={}))
    await asyncio.sleep(0.05)

    assert len(received) == 0


@pytest.mark.asyncio
async def test_backpressure_semaphore() -> None:
    bus = InMemoryEventBus(max_concurrent=2)
    await bus.start()

    active = 0
    max_active = 0

    async def slow_handler(event: CloudEvent) -> None:
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.1)
        active -= 1

    await bus.subscribe(EventTypes.MESSAGE_RECEIVED, slow_handler)

    for _ in range(5):
        await bus.publish(CloudEvent(type=EventTypes.MESSAGE_RECEIVED, data={}))

    await asyncio.sleep(0.5)
    assert max_active <= 2

    await bus.stop()
