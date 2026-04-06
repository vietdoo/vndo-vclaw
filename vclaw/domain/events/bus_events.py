"""CloudEvents-compatible event schema definitions for the platform event bus."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class EventType(StrEnum):
    # Ingestion layer
    MESSAGE_RECEIVED = "vclaw.message.received"
    MESSAGE_DEDUPLICATED = "vclaw.message.deduplicated"

    # Orchestrator lifecycle
    TASK_CREATED = "vclaw.task.created"
    TASK_INTENT_CLASSIFIED = "vclaw.task.intent_classified"
    TASK_DECOMPOSED = "vclaw.task.decomposed"
    TASK_ROUTING = "vclaw.task.routing"
    TASK_COMPLETED = "vclaw.task.completed"
    TASK_FAILED = "vclaw.task.failed"
    TASK_CANCELLED = "vclaw.task.cancelled"
    TASK_TIMEOUT = "vclaw.task.timeout"

    # Agent lifecycle
    AGENT_TASK_ASSIGNED = "vclaw.agent.task_assigned"
    AGENT_TASK_STARTED = "vclaw.agent.task_started"
    AGENT_TASK_COMPLETED = "vclaw.agent.task_completed"
    AGENT_TASK_FAILED = "vclaw.agent.task_failed"
    AGENT_REGISTERED = "vclaw.agent.registered"
    AGENT_DEREGISTERED = "vclaw.agent.deregistered"
    AGENT_HEALTH_CHECK = "vclaw.agent.health_check"

    # Response layer
    RESPONSE_READY = "vclaw.response.ready"
    RESPONSE_SENT = "vclaw.response.sent"

    # DLQ
    DLQ_MESSAGE = "vclaw.dlq.message"


class CloudEvent(BaseModel):
    """CloudEvents v1.0-compatible envelope for all platform events."""

    specversion: str = "1.0"
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: str = "vclaw-platform"
    type: EventType
    datacontenttype: str = "application/json"
    time: datetime = Field(default_factory=lambda: datetime.now(UTC))
    subject: str | None = None  # task_id or agent_id for correlation
    data: dict[str, Any] = Field(default_factory=dict)

    # Vclaw-specific extensions (CE extension attributes)
    tenant_id: str | None = None
    trace_id: str | None = None
    idempotency_key: str | None = None
    attempt: int = 1

    model_config = {"populate_by_name": True}

    @classmethod
    def create(
        cls,
        event_type: EventType,
        data: dict[str, Any],
        subject: str | None = None,
        tenant_id: str | None = None,
        trace_id: str | None = None,
        idempotency_key: str | None = None,
        attempt: int = 1,
    ) -> "CloudEvent":
        return cls(
            type=event_type,
            data=data,
            subject=subject,
            tenant_id=tenant_id,
            trace_id=trace_id,
            idempotency_key=idempotency_key,
            attempt=attempt,
        )
