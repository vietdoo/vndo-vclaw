"""Event bus interface and Redis Streams implementation."""
from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, Callable
from typing import Any

import structlog

from vclaw.domain.events.bus_events import CloudEvent, EventType
from vclaw.domain.exceptions import EventBusError

logger = structlog.get_logger(__name__)

EventHandler = Callable[[CloudEvent], "asyncio.Coroutine[Any, Any, None]"]


class EventBus(ABC):
    """Abstract async pub/sub event bus interface."""

    @abstractmethod
    async def publish(self, event: CloudEvent, stream: str | None = None) -> None:
        """Publish a CloudEvent to the bus."""

    @abstractmethod
    async def subscribe(
        self,
        event_types: list[EventType],
        handler: EventHandler,
        consumer_name: str,
        stream: str | None = None,
    ) -> None:
        """Register a handler for specific event types."""

    @abstractmethod
    async def start(self) -> None:
        """Start the event bus (connect, create streams/topics, etc.)."""

    @abstractmethod
    async def stop(self) -> None:
        """Gracefully stop the event bus."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the bus is operational."""


class RedisStreamEventBus(EventBus):
    """
    Redis Streams-backed event bus.

    Each event type maps to a Redis stream key.
    Consumer groups allow horizontal scaling with at-least-once delivery.
    Dead-letter queue (DLQ) handles events that exceed retry budgets.
    """

    def __init__(
        self,
        redis_url: str,
        stream_prefix: str = "vclaw:stream",
        consumer_group: str = "vclaw-workers",
        max_len: int = 10_000,
        dlq_stream: str = "vclaw:dlq",
        block_ms: int = 2000,
    ) -> None:
        self._redis_url = redis_url
        self._stream_prefix = stream_prefix
        self._consumer_group = consumer_group
        self._max_len = max_len
        self._dlq_stream = dlq_stream
        self._block_ms = block_ms
        self._redis: Any = None
        self._handlers: dict[EventType, list[tuple[str, EventHandler]]] = {}
        self._consumer_tasks: list[asyncio.Task[None]] = []
        self._running = False

    def _stream_key(self, event_type: EventType) -> str:
        return f"{self._stream_prefix}:{event_type}"

    async def start(self) -> None:
        try:
            import redis.asyncio as aioredis

            self._redis = await aioredis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            await self._redis.ping()
            self._running = True
            logger.info("event_bus_started", backend="redis_streams")
        except Exception as exc:
            raise EventBusError(f"Failed to connect to Redis: {exc}") from exc

    async def stop(self) -> None:
        self._running = False
        for task in self._consumer_tasks:
            task.cancel()
        await asyncio.gather(*self._consumer_tasks, return_exceptions=True)
        if self._redis:
            await self._redis.aclose()
        logger.info("event_bus_stopped")

    async def health_check(self) -> bool:
        try:
            if self._redis:
                await self._redis.ping()
                return True
            return False
        except Exception:
            return False

    async def publish(self, event: CloudEvent, stream: str | None = None) -> None:
        if not self._redis:
            raise EventBusError("Event bus not started")
        stream_key = stream or self._stream_key(event.type)
        payload = {
            "event": event.model_dump_json(),
            "type": event.type,
            "id": event.id,
        }
        try:
            await self._redis.xadd(
                stream_key,
                payload,
                maxlen=self._max_len,
                approximate=True,
            )
            logger.debug(
                "event_published",
                event_id=event.id,
                event_type=event.type,
                stream=stream_key,
            )
        except Exception as exc:
            raise EventBusError(f"Failed to publish event {event.id}: {exc}") from exc

    async def subscribe(
        self,
        event_types: list[EventType],
        handler: EventHandler,
        consumer_name: str,
        stream: str | None = None,
    ) -> None:
        for event_type in event_types:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
                stream_key = stream or self._stream_key(event_type)
                await self._ensure_consumer_group(stream_key)

            self._handlers[event_type].append((consumer_name, handler))

        task = asyncio.create_task(
            self._consume_loop(event_types, consumer_name, stream),
            name=f"consumer-{consumer_name}",
        )
        self._consumer_tasks.append(task)

    async def _ensure_consumer_group(self, stream_key: str) -> None:
        try:
            await self._redis.xgroup_create(
                stream_key, self._consumer_group, id="0", mkstream=True
            )
        except Exception as exc:
            if "BUSYGROUP" not in str(exc):
                logger.warning("consumer_group_create_warning", stream=stream_key, error=str(exc))

    async def _consume_loop(
        self,
        event_types: list[EventType],
        consumer_name: str,
        stream: str | None,
    ) -> None:
        streams = {
            (stream or self._stream_key(et)): ">" for et in event_types
        }
        while self._running:
            try:
                results = await self._redis.xreadgroup(
                    groupname=self._consumer_group,
                    consumername=consumer_name,
                    streams=streams,
                    count=10,
                    block=self._block_ms,
                )
                if not results:
                    continue

                for stream_key, messages in results:
                    for msg_id, fields in messages:
                        await self._dispatch(stream_key, msg_id, fields, consumer_name)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("consumer_loop_error", consumer=consumer_name, error=str(exc))
                await asyncio.sleep(1)

    async def _dispatch(
        self,
        stream_key: str,
        msg_id: str,
        fields: dict[str, str],
        consumer_name: str,
    ) -> None:
        try:
            event = CloudEvent.model_validate_json(fields["event"])
            handlers = self._handlers.get(event.type, [])
            for _, handler in handlers:
                await handler(event)
            await self._redis.xack(stream_key, self._consumer_group, msg_id)
        except Exception as exc:
            logger.error(
                "event_dispatch_error",
                stream=stream_key,
                msg_id=msg_id,
                error=str(exc),
            )
            await self._send_to_dlq(fields, msg_id, str(exc))

    async def _send_to_dlq(
        self, original_fields: dict[str, str], msg_id: str, error: str
    ) -> None:
        dlq_payload = {**original_fields, "original_msg_id": msg_id, "dlq_error": error}
        try:
            await self._redis.xadd(self._dlq_stream, dlq_payload, maxlen=5000)
        except Exception as dlq_exc:
            logger.critical("dlq_write_failed", error=str(dlq_exc))


class InMemoryEventBus(EventBus):
    """
    In-memory event bus for testing and local development.
    Uses asyncio queues with a single process – no persistence.
    """

    def __init__(self) -> None:
        self._handlers: dict[EventType, list[tuple[str, EventHandler]]] = {}
        self._running = False
        self._queue: asyncio.Queue[CloudEvent] = asyncio.Queue()
        self._dispatch_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self._running = True
        self._dispatch_task = asyncio.create_task(self._dispatch_loop())
        logger.info("event_bus_started", backend="in_memory")

    async def stop(self) -> None:
        self._running = False
        if self._dispatch_task:
            self._dispatch_task.cancel()
            await asyncio.gather(self._dispatch_task, return_exceptions=True)
        logger.info("event_bus_stopped")

    async def health_check(self) -> bool:
        return self._running

    async def publish(self, event: CloudEvent, stream: str | None = None) -> None:
        await self._queue.put(event)

    async def subscribe(
        self,
        event_types: list[EventType],
        handler: EventHandler,
        consumer_name: str,
        stream: str | None = None,
    ) -> None:
        for event_type in event_types:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append((consumer_name, handler))

    async def _dispatch_loop(self) -> None:
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                handlers = self._handlers.get(event.type, [])
                await asyncio.gather(*[h(event) for _, h in handlers], return_exceptions=True)
                self._queue.task_done()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
