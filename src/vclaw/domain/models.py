"""Core domain models with pydantic v2 schemas."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field
from ulid import ULID


def _ulid() -> str:
    return str(ULID())


def _now() -> datetime:
    return datetime.now(UTC)


class MessageSource(StrEnum):
    TELEGRAM = "telegram"
    API = "api"
    INTERNAL = "internal"


class TaskStatus(StrEnum):
    PENDING = "pending"
    ROUTING = "routing"
    EXECUTING = "executing"
    AGGREGATING = "aggregating"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


class AgentCapability(BaseModel):
    """Declares a single capability an agent can perform."""

    name: str
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    priority: int = 0


class ToolDefinition(BaseModel):
    """MCP-compatible tool definition for agent tool-calling."""

    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    required_params: list[str] = Field(default_factory=list)


class AgentManifest(BaseModel):
    """Metadata manifest for agent registration and discovery."""

    name: str
    version: str = "0.1.0"
    description: str = ""
    capabilities: list[AgentCapability] = Field(default_factory=list)
    tools: list[ToolDefinition] = Field(default_factory=list)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    max_concurrent: int = 5
    timeout_seconds: float = 60.0
    retry_policy: RetryPolicy | None = None
    tags: list[str] = Field(default_factory=list)
    enabled: bool = True


class RetryPolicy(BaseModel):
    """Configurable retry behaviour for agent execution."""

    max_retries: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 30.0
    exponential_base: float = 2.0


class IncomingMessage(BaseModel):
    """Normalized inbound message from any source."""

    id: str = Field(default_factory=_ulid)
    source: MessageSource = MessageSource.TELEGRAM
    chat_id: str = ""
    user_id: str = ""
    text: str = ""
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=_now)
    idempotency_key: str = ""

    def model_post_init(self, __context: Any) -> None:
        if not self.idempotency_key:
            self.idempotency_key = f"{self.source.value}:{self.chat_id}:{self.id}"


class IntentClassification(BaseModel):
    """Result of LLM intent classification."""

    intent: str
    confidence: float = 0.0
    target_agent: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)
    reasoning: str = ""


class SubTask(BaseModel):
    """A decomposed unit of work within an orchestration workflow."""

    id: str = Field(default_factory=_ulid)
    agent_name: str
    input_data: dict[str, Any] = Field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    result: dict[str, Any] | None = None
    error: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None


class WorkflowState(BaseModel):
    """Full state of an orchestration workflow execution."""

    id: str = Field(default_factory=_ulid)
    message: IncomingMessage
    intent: IntentClassification | None = None
    subtasks: list[SubTask] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: dict[str, Any] | None = None
    error: str | None = None
    tenant_id: str = ""
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    retry_count: int = 0

    def transition(self, new_status: TaskStatus) -> None:
        self.status = new_status
        self.updated_at = _now()


class AgentRequest(BaseModel):
    """Standardized input contract for agent execution."""

    workflow_id: str
    subtask_id: str
    agent_name: str
    input_data: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    tenant_id: str = ""
    timeout_seconds: float = 60.0
    idempotency_key: str = ""


class AgentResponse(BaseModel):
    """Standardized output contract from agent execution."""

    workflow_id: str
    subtask_id: str
    agent_name: str
    success: bool = True
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    duration_ms: float = 0.0
    timestamp: datetime = Field(default_factory=_now)


class LLMRequest(BaseModel):
    """Unified request to the LLM abstraction layer."""

    messages: list[dict[str, Any]]
    model: str = ""
    tools: list[dict[str, Any]] = Field(default_factory=list)
    tool_choice: str | dict[str, Any] = "auto"
    temperature: float = 0.1
    max_tokens: int = 4096
    response_format: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LLMResponse(BaseModel):
    """Unified response from the LLM abstraction layer."""

    content: str = ""
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    model: str = ""
    provider: str = ""
    usage: dict[str, int] = Field(default_factory=dict)
    latency_ms: float = 0.0
    cost_estimate: float = 0.0
