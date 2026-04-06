"""Core domain value objects and entities shared across the platform."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class AgentCapability(StrEnum):
    TASK_MANAGEMENT = "task_management"
    PUBLIC_SERVICE = "public_service"
    CODE_REVIEW = "code_review"
    SEARCH = "search"
    CALENDAR = "calendar"
    NOTIFICATION = "notification"
    ANALYTICS = "analytics"
    GENERAL = "general"


class MessageSource(StrEnum):
    TELEGRAM = "telegram"
    API = "api"
    INTERNAL = "internal"
    WEBHOOK = "webhook"


class TaskStatus(StrEnum):
    PENDING = "pending"
    ROUTING = "routing"
    EXECUTING = "executing"
    AGGREGATING = "aggregating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class Priority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class TenantContext(BaseModel):
    """Propagated tenant/user context for multi-tenant isolation."""

    tenant_id: str
    user_id: str
    chat_id: str
    language: str = "vi"
    timezone: str = "Asia/Ho_Chi_Minh"
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}


class IncomingMessage(BaseModel):
    """Normalized message from any source before entering the event bus."""

    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    idempotency_key: str
    source: MessageSource
    tenant: TenantContext
    text: str
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    reply_to_message_id: str | None = None
    received_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    raw_payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def ensure_idempotency_key(cls, values: dict[str, Any]) -> dict[str, Any]:
        if not values.get("idempotency_key"):
            values["idempotency_key"] = str(uuid.uuid4())
        return values


class IntentClassification(BaseModel):
    """Result of LLM intent classification."""

    primary_capability: AgentCapability
    confidence: float = Field(ge=0.0, le=1.0)
    secondary_capabilities: list[AgentCapability] = Field(default_factory=list)
    extracted_entities: dict[str, Any] = Field(default_factory=dict)
    requires_decomposition: bool = False
    raw_intent: str = ""


class SubTask(BaseModel):
    """A decomposed unit of work routed to a specific agent."""

    subtask_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    parent_task_id: str
    capability: AgentCapability
    agent_id: str | None = None
    input_data: dict[str, Any] = Field(default_factory=dict)
    priority: Priority = Priority.NORMAL
    depends_on: list[str] = Field(default_factory=list)
    timeout_seconds: int = 30
    retry_count: int = 0
    max_retries: int = 3


class AgentResult(BaseModel):
    """Standardized output from any agent execution."""

    subtask_id: str
    agent_id: str
    success: bool
    output: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    error_code: str | None = None
    execution_time_ms: float = 0.0
    tool_calls_made: list[dict[str, Any]] = Field(default_factory=list)
    completed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OrchestratorTask(BaseModel):
    """Full lifecycle task tracked by the orchestrator."""

    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    idempotency_key: str
    tenant: TenantContext
    original_message: IncomingMessage
    intent: IntentClassification | None = None
    subtasks: list[SubTask] = Field(default_factory=list)
    results: list[AgentResult] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    priority: Priority = Priority.NORMAL
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    final_response: str | None = None
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    def transition_to(self, new_status: TaskStatus) -> None:
        self.status = new_status
        self.updated_at = datetime.now(UTC)
        if new_status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            self.completed_at = datetime.now(UTC)
