"""Tests for Telegram gateway and rate limiter."""

from __future__ import annotations

import pytest

from vclaw.config import TelegramConfig
from vclaw.domain.events import EventTypes
from vclaw.infrastructure.event_bus.memory import InMemoryEventBus
from vclaw.infrastructure.telegram.gateway import TelegramGateway
from vclaw.infrastructure.telegram.rate_limiter import RateLimiter


def test_rate_limiter_allows_within_limit() -> None:
    limiter = RateLimiter(max_requests=3, window_seconds=60)
    assert limiter.allow("user1")
    assert limiter.allow("user1")
    assert limiter.allow("user1")
    assert not limiter.allow("user1")


def test_rate_limiter_separate_keys() -> None:
    limiter = RateLimiter(max_requests=1, window_seconds=60)
    assert limiter.allow("user1")
    assert limiter.allow("user2")
    assert not limiter.allow("user1")


def test_rate_limiter_remaining() -> None:
    limiter = RateLimiter(max_requests=5, window_seconds=60)
    assert limiter.remaining("user1") == 5
    limiter.allow("user1")
    assert limiter.remaining("user1") == 4


def test_rate_limiter_reset() -> None:
    limiter = RateLimiter(max_requests=1, window_seconds=60)
    limiter.allow("user1")
    assert not limiter.allow("user1")
    limiter.reset("user1")
    assert limiter.allow("user1")


@pytest.mark.asyncio
async def test_gateway_normalize_message() -> None:
    bus = InMemoryEventBus()
    config = TelegramConfig()
    gateway = TelegramGateway(config=config, event_bus=bus)

    update = {
        "update_id": 123456,
        "message": {
            "message_id": 1,
            "from": {"id": 789, "first_name": "Test"},
            "chat": {"id": 456, "type": "private"},
            "text": "Hello Vclaw",
        },
    }

    msg = gateway.normalize_update(update)
    assert msg is not None
    assert msg.text == "Hello Vclaw"
    assert msg.chat_id == "456"
    assert msg.user_id == "789"


@pytest.mark.asyncio
async def test_gateway_normalize_callback() -> None:
    bus = InMemoryEventBus()
    config = TelegramConfig()
    gateway = TelegramGateway(config=config, event_bus=bus)

    update = {
        "update_id": 123457,
        "callback_query": {
            "id": "cb1",
            "from": {"id": 789},
            "message": {"chat": {"id": 456}},
            "data": "button_pressed",
        },
    }

    msg = gateway.normalize_update(update)
    assert msg is not None
    assert msg.text == "button_pressed"


@pytest.mark.asyncio
async def test_gateway_normalize_empty_update() -> None:
    bus = InMemoryEventBus()
    config = TelegramConfig()
    gateway = TelegramGateway(config=config, event_bus=bus)

    msg = gateway.normalize_update({"update_id": 123})
    assert msg is None


@pytest.mark.asyncio
async def test_gateway_process_update() -> None:
    bus = InMemoryEventBus()
    await bus.start()

    received_events: list = []

    async def capture(event):
        received_events.append(event)

    await bus.subscribe(EventTypes.MESSAGE_NORMALIZED, capture)

    config = TelegramConfig()
    gateway = TelegramGateway(config=config, event_bus=bus)

    update = {
        "update_id": 100,
        "message": {
            "message_id": 1,
            "from": {"id": 1},
            "chat": {"id": 2},
            "text": "test message",
        },
    }

    result = await gateway.process_update(update)
    assert result is True

    import asyncio

    await asyncio.sleep(0.05)

    assert len(received_events) == 1
    assert received_events[0].data["text"] == "test message"

    await bus.stop()


@pytest.mark.asyncio
async def test_gateway_rate_limit() -> None:
    bus = InMemoryEventBus()
    await bus.start()

    config = TelegramConfig()
    limiter = RateLimiter(max_requests=1, window_seconds=60)
    gateway = TelegramGateway(config=config, event_bus=bus, rate_limiter=limiter)

    update = {
        "update_id": 200,
        "message": {
            "message_id": 1,
            "from": {"id": 1},
            "chat": {"id": 999},
            "text": "first",
        },
    }

    assert await gateway.process_update(update) is True
    update["update_id"] = 201
    assert await gateway.process_update(update) is False

    await bus.stop()
