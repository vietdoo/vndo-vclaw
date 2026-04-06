"""CloudEvents-compatible domain events for the event bus."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field
from ulid import ULID


def _ulid() -> str:
    return str(ULID())


def _now() -> datetime:
    return datetime.now(UTC)


class CloudEvent(BaseModel):
    """CloudEvents v1.0 compatible base event."""

    specversion: str = "1.0"
    id: str = Field(default_factory=_ulid)
    source: str = "vclaw"
    type: str
    subject: str = ""
    time: datetime = Field(default_factory=_now)
    datacontenttype: str = "application/json"
    data: dict[str, Any] = Field(default_factory=dict)
    tenant_id: str = ""
    correlation_id: str = ""

    def model_post_init(self, __context: Any) -> None:
        if not self.correlation_id:
            self.correlation_id = self.id


class EventTypes:
    """Central registry of all event type strings."""

    MESSAGE_RECEIVED = "vclaw.message.received"
    MESSAGE_NORMALIZED = "vclaw.message.normalized"
    INTENT_CLASSIFIED = "vclaw.intent.classified"
    TASK_DECOMPOSED = "vclaw.task.decomposed"
    AGENT_DISPATCHED = "vclaw.agent.dispatched"
    AGENT_COMPLETED = "vclaw.agent.completed"
    AGENT_FAILED = "vclaw.agent.failed"
    WORKFLOW_COMPLETED = "vclaw.workflow.completed"
    WORKFLOW_FAILED = "vclaw.workflow.failed"
    AGENT_REGISTERED = "vclaw.agent.registered"
    AGENT_DEREGISTERED = "vclaw.agent.deregistered"
    AGENT_HEALTH_CHECK = "vclaw.agent.health_check"
    DLQ_MESSAGE = "vclaw.dlq.message"
