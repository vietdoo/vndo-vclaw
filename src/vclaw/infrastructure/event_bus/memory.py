"""In-memory event bus for development and testing."""

from __future__ import annotations

import asyncio
from collections import defaultdict

import structlog

from vclaw.domain.events import CloudEvent, EventTypes
from vclaw.infrastructure.event_bus.base import EventBus, EventHandler

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class InMemoryEventBus(EventBus):
    """Async in-memory pub/sub event bus.

    Suitable for single-process deployments and testing.
    Delivers events via asyncio tasks with backpressure via semaphore.
    """

    def __init__(self, max_concurrent: int = 100) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._dlq: list[tuple[CloudEvent, str]] = []
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._running = False
        self._pending_tasks: set[asyncio.Task[None]] = set()

    async def publish(self, event: CloudEvent) -> None:
        if not self._running:
            logger.warning("event_bus_not_running", event_type=event.type)
            return

        handlers = self._handlers.get(event.type, [])
        if not handlers:
            logger.debug("no_handlers", event_type=event.type)
            return

        for handler in handlers:
            task = asyncio.create_task(self._dispatch(handler, event))
            self._pending_tasks.add(task)
            task.add_done_callback(self._pending_tasks.discard)

    async def _dispatch(self, handler: EventHandler, event: CloudEvent) -> None:
        async with self._semaphore:
            try:
                await handler(event)
            except Exception:
                logger.exception(
                    "handler_error",
                    event_type=event.type,
                    event_id=event.id,
                    handler=handler.__qualname__,
                )
                await self.publish_to_dlq(event, f"Handler {handler.__qualname__} failed")

    async def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)
        logger.info("handler_subscribed", event_type=event_type, handler=handler.__qualname__)

    async def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        handlers = self._handlers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)
            logger.info("handler_unsubscribed", event_type=event_type)

    async def start(self) -> None:
        self._running = True
        logger.info("event_bus_started", backend="memory")

    async def stop(self) -> None:
        self._running = False
        if self._pending_tasks:
            logger.info("draining_pending_tasks", count=len(self._pending_tasks))
            await asyncio.gather(*self._pending_tasks, return_exceptions=True)
        logger.info("event_bus_stopped", backend="memory")

    async def publish_to_dlq(self, event: CloudEvent, error: str) -> None:
        self._dlq.append((event, error))
        dlq_event = CloudEvent(
            type=EventTypes.DLQ_MESSAGE,
            source="vclaw.event_bus.memory",
            data={"original_event": event.model_dump(mode="json"), "error": error},
            correlation_id=event.correlation_id,
            tenant_id=event.tenant_id,
        )
        for handler in self._handlers.get(EventTypes.DLQ_MESSAGE, []):
            try:
                await handler(dlq_event)
            except Exception:
                logger.exception("dlq_handler_error")

    @property
    def dlq(self) -> list[tuple[CloudEvent, str]]:
        return list(self._dlq)
