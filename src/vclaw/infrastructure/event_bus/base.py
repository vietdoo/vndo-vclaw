"""Abstract event bus interface and handler protocol."""

from __future__ import annotations

import abc
from collections.abc import Callable, Coroutine
from typing import Any

from vclaw.domain.events import CloudEvent

EventHandler = Callable[[CloudEvent], Coroutine[Any, Any, None]]


class EventBus(abc.ABC):
    """Abstract async pub/sub event bus.

    Implementations must guarantee:
    - At-least-once delivery semantics
    - Message ordering within a single subject
    - Dead-letter queue routing for unprocessable events
    """

    @abc.abstractmethod
    async def publish(self, event: CloudEvent) -> None:
        """Publish an event to the bus."""

    @abc.abstractmethod
    async def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Register a handler for a specific event type."""

    @abc.abstractmethod
    async def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """Remove a handler for a specific event type."""

    @abc.abstractmethod
    async def start(self) -> None:
        """Initialize connections and begin consuming."""

    @abc.abstractmethod
    async def stop(self) -> None:
        """Gracefully drain and close connections."""

    @abc.abstractmethod
    async def publish_to_dlq(self, event: CloudEvent, error: str) -> None:
        """Route a failed event to the dead-letter queue."""
