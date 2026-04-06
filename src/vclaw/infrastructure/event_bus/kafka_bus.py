"""Kafka event bus for production-grade distributed event streaming."""

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


class KafkaEventBus(EventBus):
    """Production event bus backed by Apache Kafka via aiokafka.

    Features:
    - Consumer groups for horizontal scaling
    - Topic-per-event-type for independent scaling
    - Automatic offset management
    - Dead-letter queue via a dedicated topic
    - Configurable batch size and poll timeout
    - Graceful shutdown with consumer drain
    """

    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        consumer_group: str = "vclaw",
        topic_prefix: str = "vclaw.",
        max_concurrent: int = 50,
        poll_timeout_ms: int = 1000,
        auto_offset_reset: str = "earliest",
    ) -> None:
        self._bootstrap_servers = bootstrap_servers
        self._consumer_group = consumer_group
        self._topic_prefix = topic_prefix
        self._max_concurrent = max_concurrent
        self._poll_timeout_ms = poll_timeout_ms
        self._auto_offset_reset = auto_offset_reset

        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._running = False
        self._producer: Any = None
        self._consumers: dict[str, Any] = {}
        self._consume_tasks: list[asyncio.Task[None]] = []

    def _topic_name(self, event_type: str) -> str:
        return f"{self._topic_prefix}{event_type.replace('.', '-')}"

    async def start(self) -> None:
        from aiokafka import AIOKafkaProducer

        self._producer = AIOKafkaProducer(
            bootstrap_servers=self._bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            acks="all",
            enable_idempotence=True,
            max_request_size=1048576,
            linger_ms=5,
            compression_type="gzip",
        )
        await self._producer.start()
        self._running = True

        for event_type in self._handlers:
            await self._start_consumer(event_type)

        logger.info(
            "event_bus_started",
            backend="kafka",
            bootstrap_servers=self._bootstrap_servers,
        )

    async def stop(self) -> None:
        self._running = False

        for task in self._consume_tasks:
            task.cancel()
        if self._consume_tasks:
            await asyncio.gather(*self._consume_tasks, return_exceptions=True)

        for consumer in self._consumers.values():
            with contextlib.suppress(Exception):
                await consumer.stop()
        self._consumers.clear()

        if self._producer:
            await self._producer.stop()

        logger.info("event_bus_stopped", backend="kafka")

    async def publish(self, event: CloudEvent) -> None:
        if not self._producer:
            logger.error("kafka_producer_not_connected")
            return

        topic = self._topic_name(event.type)
        payload = json.loads(event.model_dump_json())
        key = event.correlation_id or event.id

        await self._producer.send_and_wait(topic, value=payload, key=key)
        logger.debug("event_published", event_type=event.type, topic=topic)

    async def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)
        if self._running:
            await self._start_consumer(event_type)

    async def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        handlers = self._handlers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    async def publish_to_dlq(self, event: CloudEvent, error: str) -> None:
        if not self._producer:
            return

        dlq_topic = self._topic_name("dlq")
        dlq_data = {"original_event": json.loads(event.model_dump_json()), "error": error}
        await self._producer.send_and_wait(dlq_topic, value=dlq_data, key=event.id)
        logger.warning("event_sent_to_dlq", event_id=event.id, error=error)

    async def _start_consumer(self, event_type: str) -> None:
        if event_type in self._consumers:
            return

        from aiokafka import AIOKafkaConsumer

        topic = self._topic_name(event_type)
        consumer = AIOKafkaConsumer(
            topic,
            bootstrap_servers=self._bootstrap_servers,
            group_id=self._consumer_group,
            auto_offset_reset=self._auto_offset_reset,
            enable_auto_commit=True,
            auto_commit_interval_ms=5000,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            max_poll_interval_ms=300000,
        )
        await consumer.start()
        self._consumers[event_type] = consumer

        task = asyncio.create_task(self._consume_loop(event_type, consumer))
        self._consume_tasks.append(task)

    async def _consume_loop(self, event_type: str, consumer: Any) -> None:
        while self._running:
            try:
                msg_batch = await consumer.getmany(
                    timeout_ms=self._poll_timeout_ms,
                    max_records=100,
                )
                for _tp, messages in msg_batch.items():
                    for msg in messages:
                        await self._process_message(event_type, msg.value)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("kafka_consume_error", event_type=event_type)
                await asyncio.sleep(1)

    async def _process_message(self, event_type: str, data: dict[str, Any]) -> None:
        async with self._semaphore:
            try:
                event = CloudEvent.model_validate(data)
                for handler in self._handlers.get(event_type, []):
                    try:
                        await handler(event)
                    except Exception:
                        logger.exception(
                            "handler_error",
                            event_type=event_type,
                            event_id=event.id,
                            handler=handler.__qualname__,
                        )
                        await self.publish_to_dlq(event, f"Handler {handler.__qualname__} failed")
            except Exception:
                logger.exception("kafka_message_parse_error", event_type=event_type)
