"""Redis Streams event bus for distributed deployments."""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections import defaultdict
from typing import Any

import structlog

from vclaw.domain.events import CloudEvent
from vclaw.infrastructure.event_bus.base import EventBus, EventHandler

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class RedisStreamsEventBus(EventBus):
    """Production event bus backed by Redis Streams.

    Features:
    - Consumer groups for horizontal scaling
    - Automatic acknowledgement after successful processing
    - Dead-letter queue via a dedicated stream
    - Configurable batch size and block timeout
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        consumer_group: str = "vclaw",
        consumer_name: str = "worker-0",
        stream_prefix: str = "vclaw:",
        batch_size: int = 10,
        block_ms: int = 1000,
        max_concurrent: int = 50,
    ) -> None:
        self._redis_url = redis_url
        self._consumer_group = consumer_group
        self._consumer_name = consumer_name
        self._stream_prefix = stream_prefix
        self._batch_size = batch_size
        self._block_ms = block_ms
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._running = False
        self._consume_tasks: list[asyncio.Task[None]] = []
        self._redis: Any = None

    def _stream_name(self, event_type: str) -> str:
        return f"{self._stream_prefix}{event_type}"

    async def start(self) -> None:
        import redis.asyncio as aioredis

        self._redis = aioredis.from_url(self._redis_url, decode_responses=True)
        self._running = True

        for event_type in self._handlers:
            stream = self._stream_name(event_type)
            with contextlib.suppress(Exception):
                await self._redis.xgroup_create(
                    stream, self._consumer_group, id="0", mkstream=True,
                )
            task = asyncio.create_task(self._consume_loop(event_type))
            self._consume_tasks.append(task)

        logger.info("event_bus_started", backend="redis_streams")

    async def stop(self) -> None:
        self._running = False
        for task in self._consume_tasks:
            task.cancel()
        if self._consume_tasks:
            await asyncio.gather(*self._consume_tasks, return_exceptions=True)
        if self._redis:
            await self._redis.aclose()
        logger.info("event_bus_stopped", backend="redis_streams")

    async def publish(self, event: CloudEvent) -> None:
        if not self._redis:
            logger.error("redis_not_connected")
            return

        stream = self._stream_name(event.type)
        payload = event.model_dump_json()
        await self._redis.xadd(stream, {"data": payload})
        logger.debug("event_published", event_type=event.type, stream=stream)

    async def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)
        if self._running and self._redis:
            stream = self._stream_name(event_type)
            with contextlib.suppress(Exception):
                await self._redis.xgroup_create(stream, self._consumer_group, id="0", mkstream=True)
            task = asyncio.create_task(self._consume_loop(event_type))
            self._consume_tasks.append(task)

    async def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        handlers = self._handlers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    async def publish_to_dlq(self, event: CloudEvent, error: str) -> None:
        if not self._redis:
            return
        dlq_stream = self._stream_name("dlq")
        dlq_data = {"original_event": event.model_dump_json(), "error": error}
        await self._redis.xadd(dlq_stream, {"data": json.dumps(dlq_data)})

    async def _consume_loop(self, event_type: str) -> None:
        stream = self._stream_name(event_type)
        while self._running:
            try:
                messages = await self._redis.xreadgroup(
                    groupname=self._consumer_group,
                    consumername=self._consumer_name,
                    streams={stream: ">"},
                    count=self._batch_size,
                    block=self._block_ms,
                )
                if not messages:
                    continue

                for _stream_name, entries in messages:
                    for msg_id, fields in entries:
                        await self._process_message(event_type, stream, msg_id, fields)

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("consume_error", event_type=event_type)
                await asyncio.sleep(1)

    async def _process_message(
        self, event_type: str, stream: str, msg_id: str, fields: dict[str, str]
    ) -> None:
        async with self._semaphore:
            try:
                raw = fields.get("data", "{}")
                event = CloudEvent.model_validate_json(raw)

                for handler in self._handlers.get(event_type, []):
                    await handler(event)

                await self._redis.xack(stream, self._consumer_group, msg_id)
            except Exception:
                logger.exception("process_error", msg_id=msg_id, event_type=event_type)
                event_data = fields.get("data", "{}")
                try:
                    event = CloudEvent.model_validate_json(event_data)
                    await self.publish_to_dlq(event, f"Processing failed for {msg_id}")
                except Exception:
                    logger.exception("dlq_routing_failed", msg_id=msg_id)
