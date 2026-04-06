"""Unit tests for the InMemoryEventBus."""
from __future__ import annotations

import asyncio

import pytest

from vclaw.domain.events.bus_events import CloudEvent, EventType
from vclaw.infrastructure.eventbus import InMemoryEventBus


@pytest.fixture
async def bus():
    b = InMemoryEventBus()
    await b.start()
    yield b
    await b.stop()


@pytest.mark.asyncio
async def test_publish_and_subscribe():
    bus = InMemoryEventBus()
    await bus.start()

    received: list[CloudEvent] = []

    async def handler(event: CloudEvent) -> None:
        received.append(event)

    await bus.subscribe([EventType.TASK_CREATED], handler, consumer_name="test-consumer")

    event = CloudEvent.create(
        EventType.TASK_CREATED,
        data={"task_id": "t1"},
        subject="t1",
    )
    await bus.publish(event)
    await asyncio.sleep(0.1)

    assert len(received) == 1
    assert received[0].id == event.id
    assert received[0].type == EventType.TASK_CREATED

    await bus.stop()


@pytest.mark.asyncio
async def test_health_check():
    bus = InMemoryEventBus()
    assert not await bus.health_check()
    await bus.start()
    assert await bus.health_check()
    await bus.stop()
    assert not await bus.health_check()


@pytest.mark.asyncio
async def test_multiple_handlers():
    bus = InMemoryEventBus()
    await bus.start()

    counts: list[int] = [0, 0]

    async def handler1(event: CloudEvent) -> None:
        counts[0] += 1

    async def handler2(event: CloudEvent) -> None:
        counts[1] += 1

    await bus.subscribe([EventType.TASK_COMPLETED], handler1, "c1")
    await bus.subscribe([EventType.TASK_COMPLETED], handler2, "c2")

    event = CloudEvent.create(EventType.TASK_COMPLETED, data={})
    await bus.publish(event)
    await asyncio.sleep(0.1)

    assert counts[0] == 1
    assert counts[1] == 1

    await bus.stop()


@pytest.mark.asyncio
async def test_cloud_event_schema():
    event = CloudEvent.create(
        EventType.AGENT_TASK_ASSIGNED,
        data={"subtask_id": "s1"},
        subject="task-1",
        tenant_id="tenant-1",
        trace_id="trace-abc",
    )
    assert event.specversion == "1.0"
    assert event.source == "vclaw-platform"
    assert event.type == EventType.AGENT_TASK_ASSIGNED
    assert event.data["subtask_id"] == "s1"
    assert event.tenant_id == "tenant-1"
    assert event.trace_id == "trace-abc"
